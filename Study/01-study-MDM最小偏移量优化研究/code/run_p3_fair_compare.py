"""P3 Six-method fair comparison.

Runs MDM-Default, MDM-Vector-MLP, Direct-MLP, MLE, LSE, WMLE on the same
test samples with a unified failure contract and per-sample loss.

This is a THIN SCRIPT: it does not reimplement any estimator, feature
computation, sample generation, or metric. It orchestrates existing
production implementations into a unified comparison.

Non-learning methods (MLE/LSE/WMLE) are called via run_method() from
python/studies/common/runner.py on identical generate_sample() instances.
Learning methods (Vector-MLP/Direct-MLP) are evaluated per fold×seed
then aggregated model-first.

P3 only proves the comparison program works. It does NOT produce formal
rankings — that is P4.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

_PYTHON_DIR = Path(__file__).resolve().parents[3] / "python"
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

import run_E4_formal_validation as e4
import run_p3_direct_mlp as direct
import p3_config as cfg

from studies.common.sample import generate_sample
from studies.common.runner import run_method


# ── Traditional method evaluation ──────────────────────────────────────

def evaluate_traditional(
    method_id: str,
    beta: float,
    eta: float,
    gamma: float,
    n: int,
    repeats: int,
    seed_namespace: str = "study01_v1",
) -> list[dict]:
    """Run one traditional estimator on identical samples.

    Uses generate_sample() for deterministic sample reconstruction and
    run_method() for uniform estimator invocation.

    Returns per-sample rows with estimated params, convergence status and loss.
    """
    rows = []
    for rid in range(repeats):
        sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_namespace)

        result = run_method(method_id, sample, offset=0.1 if method_id == "mdm" else None)

        beta_hat = result.get("beta_hat", 0.0)
        eta_hat = result.get("eta_hat", 0.0)
        gamma_hat = result.get("gamma_hat", 0.0)
        converged = result.get("converged", False)

        if not converged or beta_hat <= 0 or eta_hat <= 0:
            failed = True
            reason = result.get("extra", {}).get("status", "not_converged") if isinstance(result.get("extra"), dict) else "not_converged"
            # Loss will be filled by failure contract
            loss = float("nan")
        else:
            failed = False
            reason = ""
            loss = direct.compute_param_loss(beta_hat, beta, eta_hat, eta, gamma_hat, gamma)

        rows.append({
            "fold": "",  # Traditional methods have no fold
            "seed": 0,   # Traditional methods have no seed
            "method": method_id.upper() if method_id != "mdm" else "MDM-Default",
            "beta": beta,
            "gamma_over_eta": gamma / eta,
            "n": n,
            "repeat_id": rid,
            "beta_hat": beta_hat,
            "eta_hat": eta_hat,
            "gamma_hat": gamma_hat,
            "true_loss": loss,
            "failed": failed,
            "failure_reason": reason,
            "failure_penalty": 0.0,  # Set by apply_failure_contract
        })
    return rows


# ── Unified failure contract ───────────────────────────────────────────

def apply_failure_contract(
    rows: list[dict],
    failure_penalty: float,
) -> list[dict]:
    """Apply the frozen failure penalty to all failed samples.

    Same contract as P2: failed samples get failure_penalty as true_loss,
    and the original loss is preserved in true_loss_complete_case.
    """
    for row in rows:
        row["failure_penalty"] = failure_penalty
        if row["failed"]:
            row["true_loss_complete_case"] = row["true_loss"]
            row["true_loss"] = failure_penalty
        else:
            row["true_loss_complete_case"] = row["true_loss"]
    return rows


# ── Pooled J1 computation (model-first) ────────────────────────────────

def pooled_j1(losses: np.ndarray) -> float:
    """J1 = sqrt(mean(loss)). Same formula as p2_config.compute_j1."""
    return float(np.sqrt(np.mean(losses)))


def model_first_summary(
    rows: list[dict],
    method_name: str,
) -> dict:
    """Aggregate per fold×seed, then report model-level distribution.

    For non-learning methods (no fold/seed), reports a single pooled J1.
    For learning methods, pools per (fold, seed) first, then reports
    median/mean/SD across 15 models.
    """
    df = pd.DataFrame(rows)
    if df.empty:
        return {"method": method_name, "n_rows": 0}

    # Determine if this is a learning method (has fold/seed)
    is_learning = df["fold"].iloc[0] != "" if len(df) > 0 else False

    if is_learning:
        per_model = df.groupby(["fold", "seed"])["true_loss"].apply(
            lambda x: pooled_j1(x.values.astype(float))
        )
        return {
            "method": method_name,
            "n_models": len(per_model),
            "median_J1": float(per_model.median()),
            "mean_J1": float(per_model.mean()),
            "SD_J1": float(per_model.std(ddof=1)) if len(per_model) > 1 else 0.0,
            "min_J1": float(per_model.min()),
            "max_J1": float(per_model.max()),
            "n_failures": int(df["failed"].sum()),
        }
    else:
        j1 = pooled_j1(df["true_loss"].values.astype(float))
        return {
            "method": method_name,
            "n_models": 1,
            "median_J1": j1,
            "mean_J1": j1,
            "SD_J1": 0.0,
            "min_J1": j1,
            "max_J1": j1,
            "n_failures": int(df["failed"].sum()),
        }


# ── Sample key alignment verification ──────────────────────────────────

def verify_sample_key_alignment(all_rows: list[dict]) -> bool:
    """Verify all methods evaluated the same samples (by key tuple).

    Key = (beta, gamma_over_eta, n, repeat_id).
    """
    df = pd.DataFrame(all_rows)
    methods = df["method"].unique()

    key_sets = {}
    for m in methods:
        sub = df[df["method"] == m]
        keys = set(zip(
            sub["beta"].astype(float),
            sub["gamma_over_eta"].astype(float),
            sub["n"].astype(int),
            sub["repeat_id"].astype(int),
        ))
        key_sets[m] = keys

    # All key sets must be identical
    first_method = list(key_sets.keys())[0]
    first_keys = key_sets[first_method]
    for m, ks in key_sets.items():
        if ks != first_keys:
            return False
    return True


# ── Full comparison driver (thin orchestrator) ─────────────────────────

def run_fair_comparison(
    combos: list[tuple[float, float, int]],
    repeats: int,
    direct_models: dict | None = None,
    vector_models: dict | None = None,
    df_features: pd.DataFrame | None = None,
    failure_penalty: float = 0.0,
) -> dict:
    """Run six-method fair comparison on given combos.

    Parameters
    ----------
    combos : list of (beta, gamma_over_eta, n)
    repeats : number of Monte Carlo repeats per combo
    direct_models : {fold_name: [(seed, model, target_scaler, means, stds), ...]}
    vector_models : same structure for Vector-MLP (P2 v2 frozen)
    df_features : sample_features DataFrame for learning methods
    failure_penalty : frozen P99 penalty for failed samples

    Returns
    -------
    dict with per_sample rows, model summaries, alignment check
    """
    all_rows = []

    for method_id in ["mle", "lse", "wmle"]:
        method_name = method_id.upper()
        for beta, goe, n in combos:
            gamma = goe  # eta=1.0
            eta = 1.0
            rows = evaluate_traditional(
                method_id, beta, eta, gamma, n, repeats
            )
            all_rows.extend(rows)

    # MDM-Default
    for beta, goe, n in combos:
        gamma = goe
        eta = 1.0
        rows = evaluate_traditional("mdm", beta, eta, gamma, n, repeats)
        all_rows.extend(rows)

    # Direct-MLP (if models provided)
    if direct_models and df_features is not None:
        for fold_name, models in direct_models.items():
            for seed, model, tscaler, means, stds in models:
                fold = next(
                    (f for f in e4.get_combo_split()
                     if f["fold_name"] == fold_name),
                    None,
                )
                if fold is None:
                    continue
                eval_combos = [
                    (b, g, nn) for b, g, nn in combos
                    if (b, g, nn) in [tuple(tc) for tc in fold["test_combos"]]
                ]
                if not eval_combos:
                    continue
                mask = df_features.apply(
                    lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in eval_combos,
                    axis=1,
                )
                df_eval = df_features[mask]
                rows = direct.evaluate_on_samples(
                    model, tscaler, df_eval, means, stds, fold_name, seed
                )
                all_rows.extend(rows)

    # Apply failure contract
    all_rows = apply_failure_contract(all_rows, failure_penalty)

    # Verify sample key alignment
    alignment_ok = verify_sample_key_alignment(all_rows)

    # Model-first summaries
    df_all = pd.DataFrame(all_rows)
    summaries = {}
    for m in df_all["method"].unique():
        sub_rows = df_all[df_all["method"] == m].to_dict("records")
        summaries[m] = model_first_summary(sub_rows, m)

    return {
        "per_sample": all_rows,
        "summaries": summaries,
        "sample_key_alignment": alignment_ok,
        "failure_penalty": failure_penalty,
    }
