"""P3 Six-method fair comparison.

Runs MDM-Default, MDM-Vector-MLP, Direct-MLP, MLE, LSE, WMLE on the same
test samples with a per-fold failure contract and per-sample loss.

This is a THIN ORCHESTRATOR: it does not reimplement any estimator, feature
computation, sample generation, or metric. It calls existing production
implementations into a unified comparison.

Per-model fairness contract:
  - Each fold×seed has its own frozen failure penalty (P99 of training losses)
  - All six methods on that fold×seed use the same penalty
  - Sample keys are aligned per method×fold×seed, not just globally
  - No method may silently drop failed samples

P3 only proves the comparison program works. It does NOT produce formal
rankings — that is P4.
"""

from __future__ import annotations

import sys
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


# ════════════════════════════════════════════════════════════════════════
# The six methods
# ════════════════════════════════════════════════════════════════════════

ALL_SIX_METHODS = [
    "MDM-Default",
    "MDM-Vector-MLP",
    "Direct-MLP",
    "MLE",
    "LSE",
    "WMLE",
]


# ════════════════════════════════════════════════════════════════════════
# Traditional method evaluation (MLE, LSE, WMLE, MDM-Default)
# ════════════════════════════════════════════════════════════════════════

def evaluate_traditional(
    method_id: str,
    method_name: str,
    combos: list[tuple[float, float, int]],
    repeats: int,
    fold_name: str,
    seed: int,
    failure_penalty: float,
    seed_namespace: str = "study01_v1",
) -> list[dict]:
    """Run one traditional estimator on identical samples.

    Each row carries the fold_name, seed, and failure_penalty so that
    per-model fairness can be verified.
    """
    rows = []
    for beta, goe, n in combos:
        eta = 1.0
        gamma = goe * eta
        for rid in range(repeats):
            sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_namespace)

            kwargs = {"offset": 0.1} if method_id == "mdm" else {}
            result = run_method(method_id, sample, **kwargs)

            beta_hat = result.get("beta_hat", 0.0)
            eta_hat = result.get("eta_hat", 0.0)
            gamma_hat = result.get("gamma_hat", 0.0)
            converged = result.get("converged", False)

            if not converged or beta_hat <= 0 or eta_hat <= 0:
                failed = True
                extra = result.get("extra", {})
                reason = extra.get("status", "not_converged") if isinstance(extra, dict) else "not_converged"
                loss = float("nan")
            else:
                failed = False
                reason = ""
                loss = direct.compute_param_loss(beta_hat, beta, eta_hat, eta, gamma_hat, gamma)

            rows.append({
                "fold": fold_name, "seed": seed, "method": method_name,
                "beta": beta, "gamma_over_eta": goe, "n": n, "repeat_id": rid,
                "beta_hat": beta_hat, "eta_hat": eta_hat, "gamma_hat": gamma_hat,
                "true_loss": loss,
                "failed": failed, "failure_reason": reason,
                "failure_penalty": failure_penalty,
            })
    return rows


# ════════════════════════════════════════════════════════════════════════
# Unified failure contract
# ════════════════════════════════════════════════════════════════════════

def apply_failure_contract(
    rows: list[dict],
) -> list[dict]:
    """Apply each row's own failure_penalty to its true_loss.

    Each row already carries its per-fold failure_penalty (set by the
    evaluation functions). Failed rows get that penalty as true_loss;
    the original loss is preserved in true_loss_complete_case.
    """
    for row in rows:
        penalty = row.get("failure_penalty", 0.0)
        assert penalty > 0, (
            f"failure_penalty must be > 0, got {penalty} for "
            f"method={row.get('method')} fold={row.get('fold')}"
        )
        if row["failed"]:
            row["true_loss_complete_case"] = row["true_loss"]
            row["true_loss"] = penalty
        else:
            row["true_loss_complete_case"] = row["true_loss"]
    return rows


# ════════════════════════════════════════════════════════════════════════
# Pooled J1 and model-first aggregation
# ════════════════════════════════════════════════════════════════════════

def pooled_j1(losses: np.ndarray) -> float:
    """J1 = sqrt(mean(loss)). Same formula as p2_config.compute_j1."""
    return float(np.sqrt(np.mean(losses)))


def model_first_summary(
    rows: list[dict],
    method_name: str,
) -> dict:
    """Aggregate per fold×seed, then report model-level distribution."""
    df = pd.DataFrame(rows)
    if df.empty:
        return {"method": method_name, "n_rows": 0, "error": "empty"}

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
            "n_rows": len(df),
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
            "n_rows": len(df),
        }


# ════════════════════════════════════════════════════════════════════════
# Sample key alignment: per method×fold×seed verification
# ════════════════════════════════════════════════════════════════════════

def verify_sample_key_alignment(all_rows: list[dict]) -> dict:
    """Verify sample key alignment per method×fold×seed.

    Checks: complete keys, equal row counts, no duplicates, no missing.
    Returns a dict with pass/fail and diagnostics.
    """
    df = pd.DataFrame(all_rows)
    if df.empty:
        return {"ok": False, "reason": "no rows"}

    KEY_COLS = ["beta", "gamma_over_eta", "n", "repeat_id"]

    # Group by method×fold×seed and check key sets match
    groups = df.groupby(["method", "fold", "seed"])

    # Get the reference key set from the first group
    first_name, first_group = next(iter(groups))
    first_keys = first_group[KEY_COLS].apply(tuple, axis=1)
    first_key_set = set(first_keys)
    first_n = len(first_keys)
    first_unique = len(first_key_set)

    if first_n != first_unique:
        return {"ok": False, "reason": f"duplicate keys in {first_name}"}

    # Check all other groups have the same key set
    for (method, fold, seed), group in groups:
        keys = group[KEY_COLS].apply(tuple, axis=1)
        key_set = set(keys)
        if len(keys) != len(key_set):
            return {"ok": False, "reason": f"duplicate keys in {method}/{fold}/{seed}"}
        if key_set != first_key_set:
            only_here = key_set - first_key_set
            only_ref = first_key_set - key_set
            return {
                "ok": False,
                "reason": f"key mismatch in {method}/{fold}/{seed}",
                "only_here": len(only_here),
                "only_ref": len(only_ref),
            }

    return {
        "ok": True,
        "n_methods": df["method"].nunique(),
        "n_groups": len(groups),
        "n_keys_per_group": first_n,
        "methods": sorted(df["method"].unique().tolist()),
    }


# ════════════════════════════════════════════════════════════════════════
# Full comparison driver
# ════════════════════════════════════════════════════════════════════════

def run_fair_comparison(
    df_features: pd.DataFrame,
    direct_models: dict,
    vector_models: dict,
    df_risk_curves: pd.DataFrame,
    folds: list[dict] | None = None,
    repeats: int = 10,
    seed_namespace: str = "study01_v1",
    require_all_six: bool = True,
) -> dict:
    """Run six-method fair comparison.

    Parameters
    ----------
    df_features : sample_features DataFrame (13 features + keys)
    direct_models : {fold_name: [(seed, model, target_scaler, means, stds), ...]}
    vector_models : {fold_name: [(seed, predictions_df), ...]}
        where predictions_df has columns: beta, gamma_over_eta, n, repeat_id,
        beta_hat, eta_hat, gamma_hat, failed, failure_reason
    df_risk_curves : E3b risk_curves.csv for computing fold penalties
    folds : list of fold dicts (from e4.get_combo_split()). If None, use all 5.
    repeats : MC repeats per combo for traditional methods
    require_all_six : if True, fail if fewer than 6 methods produce results
    """
    if folds is None:
        folds = e4.get_combo_split()

    all_rows = []
    methods_seen = set()

    for fold in folds:
        fold_name = fold["fold_name"]
        train_combos = fold["train_combos"]
        test_combos = fold["test_combos"]

        # Compute per-fold penalty
        fold_penalty = direct.compute_fold_penalty(
            df_features, df_risk_curves, train_combos
        )
        assert fold_penalty > 0, f"Fold penalty must be > 0 for {fold_name}"

        for seed in cfg.DIRECT_MLP_SEEDS:
            # ── MDM-Default ──
            rows = evaluate_traditional(
                "mdm", "MDM-Default", test_combos, repeats,
                fold_name, seed, fold_penalty, seed_namespace,
            )
            all_rows.extend(rows)
            methods_seen.add("MDM-Default")

            # ── MLE ──
            rows = evaluate_traditional(
                "mle", "MLE", test_combos, repeats,
                fold_name, seed, fold_penalty, seed_namespace,
            )
            all_rows.extend(rows)
            methods_seen.add("MLE")

            # ── LSE ──
            rows = evaluate_traditional(
                "lse", "LSE", test_combos, repeats,
                fold_name, seed, fold_penalty, seed_namespace,
            )
            all_rows.extend(rows)
            methods_seen.add("LSE")

            # ── WMLE ──
            rows = evaluate_traditional(
                "wmle", "WMLE", test_combos, repeats,
                fold_name, seed, fold_penalty, seed_namespace,
            )
            all_rows.extend(rows)
            methods_seen.add("WMLE")

            # ── Direct-MLP ──
            if fold_name in direct_models:
                for ms in direct_models[fold_name]:
                    if ms[0] == seed:
                        model, tscaler, means, stds = ms[1], ms[2], ms[3], ms[4]
                        mask = df_features.apply(
                            lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos,
                            axis=1,
                        )
                        df_eval = df_features[mask]
                        rows = direct.evaluate_on_samples(
                            model, tscaler, df_eval, means, stds,
                            fold_name, seed, fold_penalty,
                        )
                        all_rows.extend(rows)
                        methods_seen.add("Direct-MLP")
                        break

            # ── MDM-Vector-MLP ──
            if fold_name in vector_models:
                for vs in vector_models[fold_name]:
                    if vs[0] == seed:
                        pred_df = vs[1]
                        for _, prow in pred_df.iterrows():
                            loss = direct.compute_param_loss(
                                prow["beta_hat"], prow["beta"],
                                prow["eta_hat"], prow.get("eta", 1.0),
                                prow["gamma_hat"], prow.get("gamma", prow["gamma_over_eta"]),
                            )
                            all_rows.append({
                                "fold": fold_name, "seed": seed,
                                "method": "MDM-Vector-MLP",
                                "beta": prow["beta"],
                                "gamma_over_eta": prow["gamma_over_eta"],
                                "n": prow["n"], "repeat_id": prow["repeat_id"],
                                "beta_hat": prow["beta_hat"],
                                "eta_hat": prow["eta_hat"],
                                "gamma_hat": prow["gamma_hat"],
                                "true_loss": loss,
                                "failed": prow.get("failed", False),
                                "failure_reason": prow.get("failure_reason", ""),
                                "failure_penalty": fold_penalty,
                            })
                        methods_seen.add("MDM-Vector-MLP")
                        break

    # Apply failure contract
    all_rows = apply_failure_contract(all_rows)

    # Verify alignment
    alignment = verify_sample_key_alignment(all_rows)

    # Check all six methods present
    if require_all_six:
        missing = set(ALL_SIX_METHODS) - methods_seen
        assert not missing, (
            f"Missing methods: {missing}. Only saw: {methods_seen}"
        )

    # Model-first summaries
    df_all = pd.DataFrame(all_rows)
    summaries = {}
    for m in df_all["method"].unique():
        sub_rows = df_all[df_all["method"] == m].to_dict("records")
        summaries[m] = model_first_summary(sub_rows, m)

    return {
        "per_sample": all_rows,
        "summaries": summaries,
        "sample_key_alignment": alignment,
        "methods_seen": sorted(methods_seen),
        "n_rows": len(all_rows),
    }
