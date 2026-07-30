"""P3 Six-method fair comparison.

Runs MDM-Default, MDM-Vector-MLP, Direct-MLP, MLE, LSE, WMLE on the same
test samples with per-fold failure contract and per-sample J1 loss.

Per-model fairness contract:
  - Each fold×seed has its own frozen failure penalty (P99 of ALL 26 delta
    losses in the training fold, not just delta=0.1)
  - All six methods on that fold×seed use the same penalty
  - Sample keys are aligned per method×fold×seed
  - No method may silently drop failed samples

Vector-MLP integration:
  Vector-MLP predictions come from a trained model + MC chunk join.
  The caller provides vector_models with (beta_hat, eta_hat, gamma_hat)
  extracted from the actual MDM parameter estimates at the selected delta.
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


ALL_SIX_METHODS = [
    "MDM-Default",
    "MDM-Vector-MLP",
    "Direct-MLP",
    "MLE",
    "LSE",
    "WMLE",
]


# ════════════════════════════════════════════════════════════════════════
# Traditional method evaluation
# ════════════════════════════════════════════════════════════════════════

def evaluate_traditional(
    method_id, method_name, combos, repeats,
    fold_name, seed, failure_penalty,
    seed_namespace="study01_v1",
):
    """Run one traditional estimator on identical samples."""
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

def apply_failure_contract(rows):
    """Apply each row's own failure_penalty. Reject penalty <= 0."""
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

def pooled_j1(losses):
    return float(np.sqrt(np.mean(losses)))


def model_first_summary(rows, method_name):
    df = pd.DataFrame(rows)
    if df.empty:
        return {"method": method_name, "n_rows": 0, "error": "empty"}
    is_learning = df["fold"].iloc[0] != "" if len(df) > 0 else False
    if is_learning:
        per_model = df.groupby(["fold", "seed"])["true_loss"].apply(
            lambda x: pooled_j1(x.values.astype(float))
        )
        return {
            "method": method_name, "n_models": len(per_model),
            "median_J1": float(per_model.median()),
            "mean_J1": float(per_model.mean()),
            "SD_J1": float(per_model.std(ddof=1)) if len(per_model) > 1 else 0.0,
            "min_J1": float(per_model.min()), "max_J1": float(per_model.max()),
            "n_failures": int(df["failed"].sum()), "n_rows": len(df),
        }
    else:
        j1 = pooled_j1(df["true_loss"].values.astype(float))
        return {
            "method": method_name, "n_models": 1,
            "median_J1": j1, "mean_J1": j1, "SD_J1": 0.0,
            "min_J1": j1, "max_J1": j1,
            "n_failures": int(df["failed"].sum()), "n_rows": len(df),
        }


# ════════════════════════════════════════════════════════════════════════
# Sample key alignment: per method×fold×seed
# ════════════════════════════════════════════════════════════════════════

def verify_sample_key_alignment(all_rows):
    """Verify sample key alignment per method×fold×seed."""
    df = pd.DataFrame(all_rows)
    if df.empty:
        return {"ok": False, "reason": "no rows"}

    KEY_COLS = ["beta", "gamma_over_eta", "n", "repeat_id"]
    groups = df.groupby(["method", "fold", "seed"])

    first_name, first_group = next(iter(groups))
    first_keys = first_group[KEY_COLS].apply(tuple, axis=1)
    first_key_set = set(first_keys)

    for (method, fold, seed), group in groups:
        keys = group[KEY_COLS].apply(tuple, axis=1)
        key_set = set(keys)
        if len(keys) != len(key_set):
            return {"ok": False, "reason": f"duplicate keys in {method}/{fold}/{seed}"}
        if key_set != first_key_set:
            return {"ok": False, "reason": f"key mismatch in {method}/{fold}/{seed}"}

    # Check penalty consistency within each fold×seed
    penalty_groups = df.groupby(["fold", "seed"])["failure_penalty"].nunique()
    if penalty_groups.max() > 1:
        return {"ok": False, "reason": "inconsistent failure_penalty within fold×seed"}

    return {
        "ok": True,
        "n_methods": df["method"].nunique(),
        "n_groups": len(groups),
        "n_keys_per_group": len(first_keys),
        "methods": sorted(df["method"].unique().tolist()),
    }


# ════════════════════════════════════════════════════════════════════════
# Full comparison driver with fold×seed coverage check
# ════════════════════════════════════════════════════════════════════════

def run_fair_comparison(
    df_features, direct_models, vector_models, df_risk_curves,
    folds=None, repeats=10, seeds=None,
    seed_namespace="study01_v1", require_all_six=True,
):
    """Run six-method fair comparison with full fold×seed coverage.

    Parameters
    ----------
    df_features : sample_features DataFrame
    direct_models : {fold_name: {seed: (model, info, means, stds)}}
    vector_models : {fold_name: {seed: pd.DataFrame of predictions}}
    df_risk_curves : risk_curves DataFrame (26 loss_d columns)
    folds : list of fold dicts
    repeats : MC repeats per combo for traditional methods
    seeds : list of seeds to evaluate (default: all 3)
    """
    if folds is None:
        folds = e4.get_combo_split()
    if seeds is None:
        seeds = cfg.DIRECT_MLP_SEEDS

    all_rows = []
    methods_seen = set()
    fold_seed_coverage = {}  # (fold, seed) → set of methods

    for fold in folds:
        fold_name = fold["fold_name"]
        train_combos = fold["train_combos"]
        test_combos = fold["test_combos"]

        # Compute per-fold penalty from ALL 26 delta losses
        fold_penalty = direct.compute_fold_penalty(
            df_features, df_risk_curves, train_combos
        )
        assert fold_penalty > 0

        for seed in seeds:
            key = (fold_name, seed)
            fold_seed_coverage[key] = set()

            # Traditional methods (4 per fold×seed)
            for mid, mname in [("mdm", "MDM-Default"), ("mle", "MLE"),
                               ("lse", "LSE"), ("wmle", "WMLE")]:
                rows = evaluate_traditional(
                    mid, mname, test_combos, repeats,
                    fold_name, seed, fold_penalty, seed_namespace,
                )
                all_rows.extend(rows)
                methods_seen.add(mname)
                fold_seed_coverage[key].add(mname)

            # Direct-MLP
            if fold_name in direct_models and seed in direct_models[fold_name]:
                model, info, means, stds = direct_models[fold_name][seed]
                mask = df_features.apply(
                    lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos, axis=1
                )
                df_eval = df_features[mask]
                rows = direct.evaluate_on_samples(
                    model, info, df_eval, means, stds,
                    fold_name, seed, fold_penalty,
                )
                all_rows.extend(rows)
                methods_seen.add("Direct-MLP")
                fold_seed_coverage[key].add("Direct-MLP")

            # Vector-MLP
            if fold_name in vector_models and seed in vector_models[fold_name]:
                pred_df = vector_models[fold_name][seed]
                for _, prow in pred_df.iterrows():
                    loss = direct.compute_param_loss(
                        prow["beta_hat"], prow["beta"],
                        prow["eta_hat"], prow.get("eta", prow.get("eta_hat", 1.0)),
                        prow["gamma_hat"], prow.get("gamma", prow["gamma_hat"] * prow.get("gamma_over_eta", prow["gamma_hat"] / prow.get("eta_hat", 1.0))),
                    ) if "gamma" in prow else direct.compute_param_loss(
                        prow["beta_hat"], prow["beta"],
                        prow["eta_hat"], prow.get("eta", 1.0),
                        prow["gamma_hat"], prow["gamma_over_eta"] * prow.get("eta", 1.0),
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
                fold_seed_coverage[key].add("MDM-Vector-MLP")

    # Verify full coverage
    coverage_gaps = {}
    for (fn, sd), ms in fold_seed_coverage.items():
        missing = set(ALL_SIX_METHODS) - ms
        if missing:
            coverage_gaps[f"{fn}/{sd}"] = sorted(missing)

    if require_all_six:
        assert not coverage_gaps, (
            f"Method coverage gaps: {coverage_gaps}"
        )

    all_rows = apply_failure_contract(all_rows)
    alignment = verify_sample_key_alignment(all_rows)

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
        "fold_seed_coverage": {str(k): sorted(v) for k, v in fold_seed_coverage.items()},
        "coverage_gaps": coverage_gaps,
    }
