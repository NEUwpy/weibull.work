"""Failure-transparent metrics and paired inference for Study/02."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import math
from typing import Any

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
# Frozen, auditable bootstrap configuration bound into every rule diagnostics artifact.
_BOOTSTRAP_CONFIG: dict[str, int] = {"seed": _BOOTSTRAP_SEED, "replicates": _BOOTSTRAP_REPLICATES}


# The canonical per-sample point-record schema (single authority; selection.py imports it).
# R3#1: the exact field set a point record carries -- bound verbatim into the point-evidence
# SHA, so a missing/extra field changes the digest. R4#2 validates each field's semantics.
POINT_RECORD_FIELDS = ("sample_id", "seed_id", "point_id", "legal", "failure",
                       "l_param", "e_beta", "e_eta", "e_gamma")
# Frozen failure penalty applied to every illegal validation cell (protocol 02-A, constant
# across the formal pipeline; an illegal cell's l_param and component errors all equal it).
FROZEN_FAILURE_PENALTY = 10.0


def validate_point_records(records: Sequence[Mapping]) -> list[dict]:
    """R3: validate per-sample point records BEFORE any dict is built.

    Rejects (a) a duplicate ``(seed_id, sample_id)`` cell, (b) one ``sample_id``
    mapping to multiple ``point_id`` values, (c) a missing pairing field. Returns
    the records as a plain list of dicts. This is the gate that makes a swapped or
    duplicated point-evidence artifact fail closed before it can poison a pairing.
    """
    validated: list[dict] = []
    point_of: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("point record must be a mapping")
        sample_id = record.get("sample_id")
        seed_id = record.get("seed_id")
        point_id = record.get("point_id")
        for name, value in (("sample_id", sample_id), ("seed_id", seed_id), ("point_id", point_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"point record requires a non-empty {name}")
        cell = (seed_id, sample_id)
        if cell in seen:
            raise ValueError(f"duplicate (seed_id, sample_id) point record: {cell}")
        seen.add(cell)
        if sample_id in point_of and point_of[sample_id] != point_id:
            raise ValueError(f"sample {sample_id!r} maps to multiple parameter points across records")
        point_of.setdefault(sample_id, point_id)
        validated.append(dict(record))
    return validated


def validate_canonical_point_records(records: Sequence[Mapping], *, support_seed: int) -> list[dict]:
    """R4#2: structural + semantic validation of per-sample point records before hashing.

    The single gate every point-evidence artifact passes before its content SHA is computed
    (called from :func:`compute_point_evidence_sha256`), so any semantic tamper either raises
    here or changes the bound digest. Delegates the structural checks (mapping type, non-empty
    pairing ids, no duplicate cell, no cross-point sample within the list) to
    :func:`validate_point_records`, then enforces per-record semantics -- all fail-closed:

    * exact canonical field set (no missing/extra field) and JSON-correct types;
    * ``seed_id == str(support_seed)`` -- the record belongs to this fit's frozen support seed
      (a record relabelled to another seed is a tamper);
    * finite numerics (no NaN / Inf); ``l_param >= 0``; ``failure`` in {0, 1};
    * ``legal`` <-> ``failure`` consistency (legal <=> failure == 0);
    * ``l_param`` <-> component errors: for a legal record ``l_param == rms(e_beta, e_eta,
      e_gamma)``; for an illegal record ``l_param`` and all three component errors equal the
      frozen failure penalty.
    """
    validated = validate_point_records(records)
    expected_seed = str(int(support_seed))
    canonical: list[dict] = []
    for record in validated:
        if set(record) != set(POINT_RECORD_FIELDS):
            raise ValueError(
                f"point record must carry exactly the canonical fields {list(POINT_RECORD_FIELDS)}; "
                f"got {sorted(record)}"
            )
        legal = record["legal"]
        failure = record["failure"]
        if not isinstance(legal, bool):
            raise ValueError("point record 'legal' must be a boolean")
        if isinstance(failure, bool) or not isinstance(failure, int) or failure not in (0, 1):
            raise ValueError("point record 'failure' must be the integer 0 or 1")
        if str(record["seed_id"]) != expected_seed:
            raise ValueError(
                f"point record seed_id {record['seed_id']!r} disagrees with frozen support seed {expected_seed!r}"
            )
        numeric = {field: record[field] for field in ("l_param", "e_beta", "e_eta", "e_gamma")}
        for field, value in numeric.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"point record {field!r} must be finite (no NaN/Inf)")
        l_param = float(numeric["l_param"])
        if l_param < 0:
            raise ValueError("point record 'l_param' must be non-negative")
        if (failure == 0) != legal:
            raise ValueError("point record 'legal' and 'failure' are inconsistent")
        if legal:
            expected = math.sqrt(
                (float(numeric["e_beta"]) ** 2 + float(numeric["e_eta"]) ** 2
                 + float(numeric["e_gamma"]) ** 2) / 3.0
            )
            if not math.isclose(l_param, expected, rel_tol=1e-9, abs_tol=1e-12):
                raise ValueError("point record 'l_param' disagrees with its component errors")
        else:
            for field in ("e_beta", "e_eta", "e_gamma"):
                if not math.isclose(float(numeric[field]), FROZEN_FAILURE_PENALTY, rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError(f"illegal point record {field!r} must equal the frozen failure penalty")
            if not math.isclose(l_param, FROZEN_FAILURE_PENALTY, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("illegal point record 'l_param' must equal the frozen failure penalty")
        canonical.append(record)
    return canonical


def _paired_grids(
    candidate_records: Sequence[Mapping], comparator_records: Sequence[Mapping], *, field: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str], list[str]]:
    """Pair two candidates' per-(seed, sample) records and build aligned value grids.

    Both records lists are validated (:func:`validate_point_records`), then paired
    exactly on ``(seed_id, sample_id)``. Mismatched cell sets, a sample mapped to
    distinct points across candidates, fewer than two parameter-point clusters, or
    an incomplete rectangular (seed x sample) grid all fail closed. Returns candidate
    and comparator ``(seed x sample)`` value grids for ``field`` plus the cluster index.
    """
    cand_records = validate_point_records(candidate_records)
    comp_records = validate_point_records(comparator_records)
    cand_by = {(r["seed_id"], r["sample_id"]): r for r in cand_records}
    comp_by = {(r["seed_id"], r["sample_id"]): r for r in comp_records}
    if set(cand_by) != set(comp_by):
        raise ValueError("paired comparison requires identical (seed_id, sample_id) sets across candidates")
    if not cand_by:
        raise ValueError("paired comparison requires at least one paired cell")
    # R4#2: across the two candidates being paired, the same (seed_id, sample_id) cell must
    # carry the SAME point_id. ``sample_id`` is the stable pairing id of one validation sample
    # (one frozen true-parameter point), so it determines ``point_id``; a relabel that gives one
    # candidate's cell a different parameter-point id than the comparator's would otherwise pair
    # two different truths on the same id (the CROSS_POINT attack) and silently accept them.
    for cell in cand_by:
        if cand_by[cell]["point_id"] != comp_by[cell]["point_id"]:
            raise ValueError(
                f"cross-candidate point_id mismatch for {cell!r}: "
                f"{cand_by[cell]['point_id']!r} vs {comp_by[cell]['point_id']!r}"
            )
    seed_ids = sorted({k[0] for k in cand_by})
    sample_ids = sorted({k[1] for k in cand_by})
    point_ids = sorted({cand_by[k]["point_id"] for k in cand_by})
    if len(point_ids) < 2:
        raise ValueError("paired bootstrap requires at least two parameter-point clusters")
    for sample_id in sample_ids:
        points = {cand_by[(s, sample_id)]["point_id"] for s in seed_ids}
        if len(points) != 1:
            raise ValueError(f"paired sample {sample_id!r} maps to multiple parameter points within a candidate")
    cand_grid = np.array([[cand_by[(s, x)][field] for x in sample_ids] for s in seed_ids], dtype=float)
    comp_grid = np.array([[comp_by[(s, x)][field] for x in sample_ids] for s in seed_ids], dtype=float)
    point_index = np.array([point_ids.index(cand_by[(seed_ids[0], x)]["point_id"]) for x in sample_ids], dtype=int)
    return cand_grid, comp_grid, point_index, seed_ids, sample_ids, point_ids


def _seed_point_aggregate(grid: np.ndarray, point_index: np.ndarray, *, sqmean: bool) -> np.ndarray:
    """Per-(seed, parameter-point) aggregate of a value grid: mean or mean-of-squares.

    Under the frozen protocol the validation set is balanced (each parameter point
    contributes the same number of samples at each n), so the mean-of-squares over
    resampled (seed, point) cells equals the mean squared error over the resampled
    sample cells, and sqrt of that is the RMSE the protocol's relative-RMSE rule uses.
    """
    unique_points = sorted(set(int(p) for p in point_index.tolist()))
    aggregate = np.zeros((grid.shape[0], len(unique_points)), dtype=float)
    for new_index, point in enumerate(unique_points):
        cols = np.where(point_index == point)[0]
        block = grid[:, cols]
        aggregate[:, new_index] = np.mean(block ** 2, axis=1) if sqmean else np.mean(block, axis=1)
    return aggregate


def _two_level_resample(
    agg_cand: np.ndarray, agg_comp: np.ndarray, *,
    summary: Callable[[np.ndarray, np.ndarray], float],
    replicates: int = _BOOTSTRAP_REPLICATES, seed: int = _BOOTSTRAP_SEED,
) -> dict[str, float]:
    """Parameter-point-clustered, training-seed-nested bootstrap on a summary statistic.

    Primary resampling unit = the parameter-point cluster; NN comparisons add the
    training seed as a second-level unit (protocol §5.3). ``summary(cand_block,
    comp_block)`` is applied to the observed (seed x point) aggregates and to every
    resampled block (seeds and point clusters resampled with replacement). Returns
    the observed statistic and the 2.5/97.5 percentile CI. Deterministic (fixed
    ``seed``) and order-independent (inputs canonicalised by stable pairing id in
    :func:`_paired_grids` before any resampling).
    """
    n_seeds, n_points = agg_cand.shape
    observed = float(summary(agg_cand, agg_comp))
    rng = np.random.default_rng(seed)
    point_draws = rng.integers(0, n_points, size=(int(replicates), n_points))
    seed_draws = rng.integers(0, n_seeds, size=(int(replicates), n_seeds))
    reps = np.empty(int(replicates), dtype=float)
    for replicate in range(int(replicates)):
        cand_block = agg_cand[seed_draws[replicate]][:, point_draws[replicate]]
        comp_block = agg_comp[seed_draws[replicate]][:, point_draws[replicate]]
        reps[replicate] = summary(cand_block, comp_block)
    finite = reps[np.isfinite(reps)]
    if len(finite) != int(replicates):
        # A non-finite statistic (only the RMSE ratio can produce +inf, from a zero
        # comparator RMSE with a positive candidate error) is fail-closed: the CI is
        # unbounded in the worsening direction (R3#4).
        ci_lower = float(np.quantile(finite, 0.025)) if len(finite) else float("-inf")
        ci_upper = float("inf")
    else:
        ci_lower = float(np.quantile(reps, 0.025))
        ci_upper = float(np.quantile(reps, 0.975))
    return {"observed": observed, "ci_lower": ci_lower, "ci_upper": ci_upper}


def _mean_diff_summary(cand_block: np.ndarray, comp_block: np.ndarray) -> float:
    """Mean improvement ``comparator - candidate`` over the (resampled) cells."""
    return float(np.mean(comp_block - cand_block))


def _mean_worsening_summary(cand_block: np.ndarray, comp_block: np.ndarray) -> float:
    """Mean worsening ``candidate - comparator`` over the (resampled) cells (failure rate)."""
    return float(np.mean(cand_block - comp_block))


def _rmse_ratio_summary(cand_block: np.ndarray, comp_block: np.ndarray) -> float:
    """Relative RMSE worsening ``RMSE_candidate / RMSE_comparator - 1`` (R3#4).

    ``cand_block`` / ``comp_block`` are per-(seed, point) mean-of-squares, so
    ``sqrt(mean(block))`` is the RMSE over the resampled cells. A zero comparator
    RMSE is handled frozen and fail-closed: if the candidate is also perfect the
    ratio is 0; otherwise the candidate strictly worsens that component (``+inf``),
    which fails the ``<= 5%`` upper-bound test and blocks a "globally better" verdict.
    """
    rmse_cand = float(np.sqrt(np.mean(cand_block)))
    rmse_comp = float(np.sqrt(np.mean(comp_block)))
    if rmse_comp == 0.0:
        return 0.0 if rmse_cand == 0.0 else float("inf")
    return rmse_cand / rmse_comp - 1.0


def paired_two_level_bootstrap_ci(
    paired: Sequence[Mapping], *, replicates: int = _BOOTSTRAP_REPLICATES, seed: int = _BOOTSTRAP_SEED,
) -> dict[str, float]:
    """Two-level bootstrap CI on pre-computed paired-improvement records.

    Each record carries ``seed_id``/``sample_id``/``point_id``/``improvement``
    (improvement > 0 means the candidate beats the comparator). Returns the observed
    mean improvement and the 95% percentile CI. Kept as a thin wrapper over
    :func:`_two_level_resample` for the ``L_param`` improvement tests (e.g. the
    training-size rule). Deterministic and order-independent.
    """
    records = validate_point_records(paired)
    for record in records:
        if "improvement" not in record:
            raise ValueError("paired bootstrap record requires an 'improvement' field")
    cand_grid, comp_grid, point_index = _improvement_grid(records)
    result = _two_level_resample(
        _seed_point_aggregate(cand_grid, point_index, sqmean=False),
        _seed_point_aggregate(comp_grid, point_index, sqmean=False),
        summary=_mean_diff_summary, replicates=replicates, seed=seed,
    )
    return {"mean_improvement": result["observed"], "ci_lower": result["ci_lower"], "ci_upper": result["ci_upper"]}


def _improvement_grid(records: Sequence[Mapping]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a degenerate candidate=0 / comparator=improvement grid for the wrapper."""
    seed_ids = sorted({str(r["seed_id"]) for r in records})
    sample_ids = sorted({str(r["sample_id"]) for r in records})
    point_ids = sorted({str(r["point_id"]) for r in records})
    if len(point_ids) < 2:
        raise ValueError("paired bootstrap requires at least two parameter-point clusters")
    by = {(str(r["seed_id"]), str(r["sample_id"])): float(r["improvement"]) for r in records}
    expected = len(seed_ids) * len(sample_ids)
    if len(by) != expected:
        raise ValueError("paired bootstrap evidence must cover every (seed, sample) cell exactly once")
    point_of = {(str(r["seed_id"]), str(r["sample_id"])): str(r["point_id"]) for r in records}
    comp_grid = np.array([[by[(s, x)] for x in sample_ids] for s in seed_ids], dtype=float)
    cand_grid = np.zeros_like(comp_grid)
    point_index = np.array([point_ids.index(point_of[(seed_ids[0], x)]) for x in sample_ids], dtype=int)
    return cand_grid, comp_grid, point_index


def global_better_intervals(
    *, candidate: Sequence[Mapping], comparator: Sequence[Mapping],
    replicates: int = _BOOTSTRAP_REPLICATES, seed: int = _BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Frozen "globally better" three-CI verdict (protocol §5.3) from per-sample evidence.

    ``candidate``/``comparator`` are each a list of per-(seed, sample) records (each carrying
    ``sample_id``, ``point_id``, ``seed_id``, ``failure`` as 0/1, ``l_param`` and the three
    component errors). Returns the frozen bootstrap config, the failure-rate, paired-``L_param``
    and per-component RELATIVE-RMSE-worsening 95% CIs, and the verdict.

    "Globally better" requires (§5.3, R3#4): the candidate's failure-rate WORSENING
    (``candidate_failure - comparator_failure``) CI upper <= 1pp (the candidate fails no
    more than 1pp above the comparator), the paired ``L_param`` IMPROVEMENT
    (``comparator_l_param - candidate_l_param``) CI lower > 0, and every component's
    relative RMSE worsening (``RMSE_cand / RMSE_comp - 1``) CI upper <= 5%. The
    relative-RMSE ratio (not a raw MSE difference) is scale-free; a zero comparator RMSE
    with any candidate error fails closed.
    """
    failure_cand, failure_comp, failure_pt, _, _, _ = _paired_grids(candidate, comparator, field="failure")
    lparam_cand, lparam_comp, lparam_pt, _, _, _ = _paired_grids(candidate, comparator, field="l_param")
    # failure: candidate minus comparator (worsening) -- non-inferior if its upper <= 1pp.
    failure_ci = _two_level_resample(
        _seed_point_aggregate(failure_cand, failure_pt, sqmean=False),
        _seed_point_aggregate(failure_comp, failure_pt, sqmean=False),
        summary=_mean_worsening_summary, replicates=replicates, seed=seed,
    )
    # L_param: comparator minus candidate (improvement) -- better if its lower > 0.
    l_param_ci = _two_level_resample(
        _seed_point_aggregate(lparam_cand, lparam_pt, sqmean=False),
        _seed_point_aggregate(lparam_comp, lparam_pt, sqmean=False),
        summary=_mean_diff_summary, replicates=replicates, seed=seed,
    )
    component_ratio_ci: dict[str, dict[str, float]] = {}
    component_ratio_upper: dict[str, float] = {}
    for name in _COMPONENT_NAMES:
        field = f"e_{name}"
        cand_grid, comp_grid, pt_idx, _, _, _ = _paired_grids(candidate, comparator, field=field)
        ci = _two_level_resample(
            _seed_point_aggregate(cand_grid, pt_idx, sqmean=True),
            _seed_point_aggregate(comp_grid, pt_idx, sqmean=True),
            summary=_rmse_ratio_summary, replicates=replicates, seed=seed,
        )
        component_ratio_ci[name] = ci
        component_ratio_upper[name] = ci["ci_upper"]
    verdict = global_better_from_intervals(
        failure_diff_upper=failure_ci["ci_upper"], l_param_improvement_lower=l_param_ci["ci_lower"],
        component_worsening_upper=component_ratio_upper,
    )
    return {
        "bootstrap_config": dict(_BOOTSTRAP_CONFIG),
        "failure_rate_ci": failure_ci, "l_param_ci": l_param_ci,
        "component_rmse_ratio_ci": component_ratio_ci, "verdict": verdict,
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
    Failed seeds are included in the paired evidence (their records carry the penalty), so a
    training size that fails more seeds is not silently favoured.
    """
    if not candidate_scores:
        raise ValueError("smallest_within_2pct_ci requires at least one candidate")
    ordered_by_score = sorted(candidate_scores, key=lambda cid: (float(candidate_scores[cid]), cid))
    best_id = ordered_by_score[0]
    best_score = float(candidate_scores[best_id])
    threshold = best_score * 1.02

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
