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


# ---------------------------------------------------------------------------
# Selection-rule inference (D7 decision-rule engine).
#
# The frozen protocol (02-A §5.3) defines paired inference on per-sample,
# per-parameter-point evidence: differences are taken on identical validation
# samples (the "stable pairing"), 95% CIs use a parameter-point-clustered
# bootstrap (>=2000 reps), and NN comparisons add the training seed as a
# second-level resampling unit. These functions implement that contract
# deterministically (fixed seed 520001) and order-independently (inputs are
# canonicalised by stable pairing id before any resampling, so re-ordering the
# same evidence yields the same CI). They consume per-sample evidence only --
# never a trusted scalar -- so a tampered checkpoint/score changes the bound
# point_evidence_sha256 and the downstream CI.
# ---------------------------------------------------------------------------

_BOOTSTRAP_SEED = 520001
_BOOTSTRAP_REPLICATES = 2000
_COMPONENT_NAMES = ("beta", "eta", "gamma")


def evaluate_rows_per_sample(rows: Sequence[Mapping], *, failure_penalty: float = 10.0) -> list[dict]:
    """Per-sample failure-penalized evaluation, the unit bound into selection evidence.

    Each row must carry ``sample_id`` (the stable pairing id), ``seed_id`` and ``point_id``
    (the bootstrap clustering/pairing metadata), the estimate triple (``beta_hat``/
    ``eta_hat``/``gamma_hat``), the truth triple (``beta``/``eta``/``gamma``), ``sample_min``
    (the legality bound) and optionally ``converged``. Returns one record per row with the
    three relative component errors, the failure-penalized ``L_param`` (frozen penalty when
    illegal), a ``legal`` flag and a ``failure`` 0/1 indicator. For an illegal estimate every
    component error is set to the penalty, which is self-consistent (sqrt((3*penalty^2)/3) =
    penalty = L_param). This per-sample truth is what ``evaluate_rows`` aggregates and what
    the rule engine consumes for CIs; binding its canonical hash (``point_evidence_sha256``)
    ties the selection to the checkpoint's actual per-sample behaviour, not a single mean.
    """
    records: list[dict] = []
    for row in rows:
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ValueError("evaluation row requires a non-empty sample_id (stable pairing id)")
        seed_id = row.get("seed_id")
        point_id = row.get("point_id")
        if not isinstance(seed_id, str) or not seed_id.strip():
            raise ValueError("evaluation row requires a non-empty seed_id (bootstrap pairing id)")
        if not isinstance(point_id, str) or not point_id.strip():
            raise ValueError("evaluation row requires a non-empty point_id (cluster id)")
        legal = _legal(row)
        if legal:
            errors = parameter_errors(
                row["beta_hat"], row["eta_hat"], row["gamma_hat"],
                row["beta"], row["eta"], row["gamma"],
            )
            l_param = float(math.sqrt(sum(value * value for value in errors.values()) / 3.0))
            records.append({
                "sample_id": sample_id, "seed_id": seed_id, "point_id": point_id,
                "legal": True, "failure": 0, "l_param": l_param,
                "e_beta": float(errors["beta"]), "e_eta": float(errors["eta"]), "e_gamma": float(errors["gamma"]),
            })
        else:
            penalty = float(failure_penalty)
            records.append({
                "sample_id": sample_id, "seed_id": seed_id, "point_id": point_id,
                "legal": False, "failure": 1, "l_param": penalty,
                "e_beta": penalty, "e_eta": penalty, "e_gamma": penalty,
            })
    return records


def _canonical_two_level_grid(
    paired: Sequence[Mapping],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str]]:
    """Build an order-independent (seed x sample) paired-difference grid.

    ``paired`` is a list of ``{seed_id, sample_id, point_id, improvement}`` records
    (improvement > 0 means the candidate beats the comparator on that paired unit).
    Seeds, samples and parameter-point clusters are all canonicalised by stable id
    so the returned arrays depend only on the evidence content, never on caller
    ordering -- reordering the same records yields byte-identical CIs.
    """
    if not paired:
        raise ValueError("paired bootstrap requires at least one paired record")
    point_of = {str(record["sample_id"]): str(record["point_id"]) for record in paired}
    improvement_of = {
        (str(record["seed_id"]), str(record["sample_id"])): float(record["improvement"]) for record in paired
    }
    seed_ids = sorted({str(record["seed_id"]) for record in paired})
    sample_ids = sorted({str(record["sample_id"]) for record in paired})
    if len(sample_ids) != len({str(record["sample_id"]) for record in paired}):
        raise ValueError("paired bootstrap sample_ids must be unique per record")
    point_ids = sorted({point_of[sample_id] for sample_id in sample_ids})
    if len(point_ids) < 2:
        raise ValueError("paired bootstrap requires at least two parameter-point clusters")
    # A complete (seed x sample) rectangular grid; the improvement varies by training
    # seed (each seed trains a distinct checkpoint), which is the second-level unit.
    expected_cells = len(seed_ids) * len(sample_ids)
    if len(improvement_of) != expected_cells:
        raise ValueError("paired bootstrap evidence must cover every (seed, sample) cell exactly once")
    grid = np.array(
        [[improvement_of[(seed_id, sample_id)] for sample_id in sample_ids] for seed_id in seed_ids],
        dtype=float,
    )
    point_index = np.array([point_ids.index(point_of[sample_id]) for sample_id in sample_ids], dtype=int)
    return grid, point_index, np.asarray(point_ids), seed_ids, sample_ids


def paired_two_level_bootstrap_ci(
    paired: Sequence[Mapping], *, replicates: int = _BOOTSTRAP_REPLICATES, seed: int = _BOOTSTRAP_SEED,
) -> dict[str, float]:
    """Parameter-point-clustered, training-seed-nested bootstrap CI on paired diffs.

    Implements protocol §5.3: primary resampling unit = the parameter-point cluster
    (all paired samples at a point move together); NN comparisons add the training
    seed as a second-level unit. Returns the observed mean improvement and the 95%
    percentile CI. Deterministic (fixed ``seed``) and order-independent.
    """
    grid, point_index, point_ids, _seed_ids, _sample_ids = _canonical_two_level_grid(paired)
    n_seeds, n_samples = grid.shape
    n_points = len(point_ids)
    observed = float(grid.mean())
    # Per-(seed, point) mean improvement, precomputed so resampling is pure indexing.
    seed_point = np.zeros((n_seeds, n_points), dtype=float)
    for point in range(n_points):
        cols = np.where(point_index == point)[0]
        seed_point[:, point] = grid[:, cols].mean(axis=1)
    rng = np.random.default_rng(seed)
    point_draws = rng.integers(0, n_points, size=(int(replicates), n_points))
    seed_draws = rng.integers(0, n_seeds, size=(int(replicates), n_seeds))
    reps = np.empty(int(replicates), dtype=float)
    for replicate in range(int(replicates)):
        block = seed_point[seed_draws[replicate]][:, point_draws[replicate]]
        reps[replicate] = block.mean()
    return {
        "mean_improvement": observed,
        "ci_lower": float(np.quantile(reps, 0.025)),
        "ci_upper": float(np.quantile(reps, 0.975)),
    }


def _pair_candidates(
    candidate_per_seed_sample: Sequence[Mapping], comparator_per_seed_sample: Sequence[Mapping],
) -> list[tuple[Mapping, Mapping]]:
    """Exact pairing of two candidates' per-(seed, sample) evidence on (seed_id, sample_id).

    Both candidates are evaluated on the same validation sample set, so every
    (seed, sample) cell must be present in both. A missing or extra cell fails closed;
    a sample that maps to different parameter points across candidates fails closed.
    """
    candidate_by = {(str(r["seed_id"]), str(r["sample_id"])): r for r in candidate_per_seed_sample}
    comparator_by = {(str(r["seed_id"]), str(r["sample_id"])): r for r in comparator_per_seed_sample}
    if set(candidate_by) != set(comparator_by):
        raise ValueError("paired comparison requires identical (seed_id, sample_id) sets across candidates")
    pairs: list[tuple[Mapping, Mapping]] = []
    for key in sorted(candidate_by):
        cand, comp = candidate_by[key], comparator_by[key]
        if str(cand["point_id"]) != str(comp["point_id"]):
            raise ValueError(f"paired sample {key[1]} maps to distinct parameter points across candidates")
        pairs.append((cand, comp))
    return pairs


def _paired_field(pairs: Sequence[tuple[Mapping, Mapping]], *, field: str, sign: int = 1) -> list[dict]:
    """Build paired-diff records (``comparator[field] - candidate[field]`` scaled by ``sign``)."""
    records: list[dict] = []
    for cand, comp in pairs:
        improvement = sign * (float(comp[field]) - float(cand[field]))
        records.append({
            "seed_id": str(cand["seed_id"]), "sample_id": str(cand["sample_id"]),
            "point_id": str(cand["point_id"]), "improvement": improvement,
        })
    return records


def global_better_intervals(
    *, candidate: Sequence[Mapping], comparator: Sequence[Mapping],
) -> dict[str, Any]:
    """Frozen "globally better" three-CI verdict (protocol §5.3) from per-sample evidence.

    ``candidate``/``comparator`` are each a list of per-(seed, sample) records produced by
    :func:`evaluate_rows_per_sample` (each carrying ``sample_id``, ``point_id``, ``seed_id``,
    ``failure`` as 0/1, ``l_param`` and the three component errors). Returns the failure-rate,
    paired ``L_param`` and per-component RMSE-worsening 95% CIs (frozen two-level bootstrap,
    seed 520001, 2000 reps) and the resulting verdict. "Globally better" requires (§5.3):
    failure-rate diff CI upper <= 1pp, paired L_param improvement CI lower > 0, and every
    component RMSE worsening CI upper <= 5%.
    """
    pairs = _pair_candidates(candidate, comparator)
    failure = paired_two_level_bootstrap_ci(_paired_field(pairs, field="failure"))
    l_param = paired_two_level_bootstrap_ci(_paired_field(pairs, field="l_param"))
    worsening_upper: dict[str, float] = {}
    for name in _COMPONENT_NAMES:
        field = f"e_{name}"
        worsening_paired = [
            {
                "seed_id": str(cand["seed_id"]), "sample_id": str(cand["sample_id"]),
                "point_id": str(cand["point_id"]),
                "improvement": float(cand[field]) ** 2 - float(comp[field]) ** 2,
            }
            for cand, comp in pairs
        ]
        worsening_upper[name] = paired_two_level_bootstrap_ci(worsening_paired)["ci_upper"]
    verdict = global_better_from_intervals(
        failure_diff_upper=failure["ci_upper"], l_param_improvement_lower=l_param["ci_lower"],
        component_worsening_upper=worsening_upper,
    )
    return {
        "failure_rate_ci": failure, "l_param_ci": l_param,
        "component_worsening_ci_upper": worsening_upper, "verdict": verdict,
    }


def smallest_within_2pct_ci_choice(
    *, candidate_scores: Mapping[str, float], candidate_paired: Mapping[str, Sequence[Mapping]],
) -> str:
    """Frozen training-size rule (02-A A-E2 / module_matrix_rules A-E2_training_size).

    Among ``candidate_scores`` (mean failure-penalized ``L_param`` per size candidate, lower is
    better) pick the smallest size whose mean is within 2% of the best AND whose paired
    improvement vs the best has a 95% CI containing 0 (i.e. not statistically worse);
    otherwise pick the best. ``candidate_paired`` maps each non-best candidate id to its
    paired-diff records (improvement = best - candidate) vs the best, for the CI test.
    Candidates are ordered smallest-first by numeric size so "smallest within 2%" is literal.
    """
    if not candidate_scores:
        raise ValueError("smallest_within_2pct_ci requires at least one candidate")
    ordered_by_score = sorted(candidate_scores, key=lambda cid: (float(candidate_scores[cid]), cid))
    best_id = ordered_by_score[0]
    best_score = float(candidate_scores[best_id])
    threshold = best_score * 1.02
    # Smallest-size-first: numeric size where available, else lexicographic on the id.
    def size_key(cid: str) -> tuple:
        try:
            return (0, float(cid))
        except (TypeError, ValueError):
            return (1, cid)
    smallest_first = sorted(candidate_scores, key=size_key)
    for candidate_id in smallest_first:
        if float(candidate_scores[candidate_id]) > threshold:
            continue  # outside the 2% band of the best
        if candidate_id == best_id:
            return best_id
        paired = candidate_paired.get(candidate_id)
        if paired is None:
            raise ValueError(f"smallest_within_2pct_ci missing paired evidence for {candidate_id}")
        ci = paired_two_level_bootstrap_ci(paired)
        if ci["ci_lower"] <= 0.0 <= ci["ci_upper"]:
            return candidate_id  # within 2% and CI of (best - candidate) contains 0 => non-worse
    return best_id
