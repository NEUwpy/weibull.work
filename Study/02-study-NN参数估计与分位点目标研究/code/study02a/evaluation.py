"""Failure-transparent metrics and paired inference for Study/02."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

import numpy as np


def parameter_errors(
    beta_hat: float,
    eta_hat: float,
    gamma_hat: float,
    beta: float,
    eta: float,
    gamma: float,
) -> dict[str, float]:
    return {
        "beta": (float(beta_hat) - float(beta)) / float(beta),
        "eta": (float(eta_hat) - float(eta)) / float(eta),
        "gamma": (float(gamma_hat) - float(gamma)) / float(eta),
    }


def parameter_loss(
    beta_hat: float,
    eta_hat: float,
    gamma_hat: float,
    beta: float,
    eta: float,
    gamma: float,
) -> float:
    errors = parameter_errors(beta_hat, eta_hat, gamma_hat, beta, eta, gamma)
    return float(math.sqrt(sum(value * value for value in errors.values()) / 3.0))


def _legal(row: Mapping) -> bool:
    estimates = [row.get("beta_hat"), row.get("eta_hat"), row.get("gamma_hat")]
    if any(value is None or not np.isfinite(value) for value in estimates):
        return False
    return bool(
        row.get("converged", True)
        and float(estimates[0]) > 0
        and float(estimates[1]) > 0
        and float(estimates[2]) < float(row["sample_min"])
    )


def evaluate_rows(rows: Sequence[Mapping], failure_penalty: float = 10.0) -> dict:
    conditional_losses = []
    unconditional_losses = []
    component_errors = {name: [] for name in ("beta", "eta", "gamma")}
    for row in rows:
        if not _legal(row):
            unconditional_losses.append(float(failure_penalty))
            continue
        errors = parameter_errors(
            row["beta_hat"], row["eta_hat"], row["gamma_hat"],
            row["beta"], row["eta"], row["gamma"],
        )
        loss = float(math.sqrt(sum(value * value for value in errors.values()) / 3.0))
        conditional_losses.append(loss)
        unconditional_losses.append(loss)
        for name, value in errors.items():
            component_errors[name].append(value)

    n_total = len(rows)
    n_valid = len(conditional_losses)
    result = {
        "n_total": n_total,
        "n_valid": n_valid,
        "n_failure": n_total - n_valid,
        "failure_rate": (n_total - n_valid) / n_total if n_total else None,
        "conditional_mean_l_param": float(np.mean(conditional_losses)) if conditional_losses else None,
        "unconditional_mean_l_param": float(np.mean(unconditional_losses)) if unconditional_losses else None,
    }
    for name, values in component_errors.items():
        result[f"bias_{name}_rel"] = float(np.mean(values)) if values else None
        result[f"rmse_{name}_rel"] = float(np.sqrt(np.mean(np.square(values)))) if values else None
        result[f"mae_{name}_rel"] = float(np.mean(np.abs(values))) if values else None
    return result


def global_better_from_intervals(
    *,
    failure_diff_upper: float,
    l_param_improvement_lower: float,
    component_worsening_upper: Mapping[str, float],
) -> str:
    failure_noninferior = failure_diff_upper <= 0.01
    l_param_better = l_param_improvement_lower > 0.0
    components_noninferior = all(value <= 0.05 for value in component_worsening_upper.values())
    if failure_noninferior and l_param_better and components_noninferior:
        return "globally_better"
    if l_param_better or any(value < 0 for value in component_worsening_upper.values()):
        return "tradeoff"
    return "no_clear_advantage"


def cluster_bootstrap_difference(
    candidate_loss: Sequence[float],
    comparator_loss: Sequence[float],
    clusters: Sequence,
    *,
    replicates: int = 2000,
    seed: int = 520001,
) -> dict[str, float]:
    candidate = np.asarray(candidate_loss, dtype=float)
    comparator = np.asarray(comparator_loss, dtype=float)
    cluster_values = np.asarray(clusters)
    if not (len(candidate) == len(comparator) == len(cluster_values)):
        raise ValueError("loss and cluster arrays must have equal length")
    unique = np.unique(cluster_values)
    if unique.size < 2:
        raise ValueError("cluster bootstrap requires at least two clusters")
    cluster_improvements = np.array([
        np.mean(comparator[cluster_values == cluster] - candidate[cluster_values == cluster])
        for cluster in unique
    ])
    rng = np.random.default_rng(seed)
    draws = cluster_improvements[rng.integers(0, len(unique), size=(int(replicates), len(unique)))].mean(axis=1)
    return {
        "mean_improvement": float(np.mean(comparator - candidate)),
        "ci_lower": float(np.quantile(draws, 0.025)),
        "ci_upper": float(np.quantile(draws, 0.975)),
    }
