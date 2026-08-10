"""Risk-landscape screening for traditional three-parameter Weibull estimators.

This Research reuses Study01's frozen 160-cell / 48,000-sample design.  It
does not modify Study01 artifacts and it does not train a deployable selector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve()
RESEARCH_ROOT = HERE.parents[1]
PROJECT_ROOT = HERE.parents[3]
PYTHON_ROOT = PROJECT_ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from studies.common.runner import run_method  # noqa: E402
from studies.common.sample import generate_sample  # noqa: E402


RUN_ID = "risk_landscape_v1"
SEED_NAMESPACE = "study01_nrmc_v1"
UNIT_SCALE = 1000.0
BETA_GRID = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
GAMMA_RATIO_GRID = [0.10, 0.25, 0.50, 0.75, 1.00]
N_GRID = [7, 10, 15, 20]
REPEATS = 300
FOLDS = 5
FAILURE_LOSS = 3.0
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 20260810

PRIMARY_METHODS = ["MDM-0.1", "WMLE", "LSE"]
DIAGNOSTIC_METHODS = ["MLE", "LRE"]
PRODUCTION_IDS = {"WMLE": "wmle", "LSE": "lse", "MLE": "mle", "LRE": "lre"}
ALL_METHODS = PRIMARY_METHODS + DIAGNOSTIC_METHODS

SAMPLE_KEYS = ["beta", "gamma_over_eta", "n", "repeat_id"]
CELL_KEYS = ["beta", "gamma_over_eta", "n"]

STUDY01_ROOT = PROJECT_ROOT / "Study" / "01-study-MDM最小偏移量优化研究"
SHARED_ROOT = STUDY01_ROOT / "artifacts" / "formal" / "E5_normalized_raw" / "shared_data"
MC_SCAN = SHARED_ROOT / "mc_scan_raw.csv"
MC_MANIFEST = SHARED_ROOT / "manifest.json"
MC_SUMS = SHARED_ROOT / "data_sha256sums.txt"
B2_ROOT = STUDY01_ROOT / "artifacts" / "formal" / "E6_dimensional_raw" / "traditional_ref"
B2_SUMMARY = B2_ROOT / "summary.csv"

OUT_DIR = RESEARCH_ROOT / "artifacts" / RUN_ID
RAW_PATH = OUT_DIR / "per_sample_losses.csv.gz"
METHOD_SUMMARY_PATH = OUT_DIR / "method_summary.csv"
CELL_SUMMARY_PATH = OUT_DIR / "cell_summary.csv"
SELECTOR_SUMMARY_PATH = OUT_DIR / "selector_summary.csv"
FOLD_CHOICES_PATH = OUT_DIR / "fold_choices.csv"
WINNER_STABILITY_PATH = OUT_DIR / "winner_stability.csv"
BOOTSTRAP_PATH = OUT_DIR / "bootstrap_summary.csv"
SUBGROUP_PATH = OUT_DIR / "subgroup_summary.csv"
SCALE_PATH = OUT_DIR / "scale_sensitivity.csv"
RESULT_PATH = OUT_DIR / "result.json"
MANIFEST_PATH = OUT_DIR / "manifest.json"
RUN_LOG_PATH = OUT_DIR / "run_log.txt"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def build_grid() -> list[tuple[float, float, int, int]]:
    return [
        (float(beta), float(gamma_ratio), int(n), int(repeat_id))
        for beta in BETA_GRID
        for gamma_ratio in GAMMA_RATIO_GRID
        for n in N_GRID
        for repeat_id in range(REPEATS)
    ]


def _failure_reason(result: dict) -> str:
    extra = result.get("extra") or {}
    if isinstance(extra, dict):
        return str(extra.get("raw_status") or extra.get("error") or "not_converged")
    return "not_converged"


def _evaluate_estimate(
    method: str,
    beta_true: float,
    gamma_ratio: float,
    beta_hat,
    eta_hat,
    gamma_hat,
    converged: bool,
    reason: str = "",
) -> dict:
    values = [beta_hat, eta_hat, gamma_hat]
    failed = not converged or any(v is None for v in values)
    if not failed:
        failed = not all(np.isfinite(float(v)) for v in values)
    if not failed:
        failed = float(beta_hat) <= 0 or float(eta_hat) <= 0 or float(gamma_hat) < 0
    if failed:
        beta_hat = eta_hat = gamma_hat = 0.0
        natural_loss = 1.0 + 1.0 + gamma_ratio**2
        primary_loss = FAILURE_LOSS
    else:
        beta_hat = float(beta_hat)
        eta_hat = float(eta_hat)
        gamma_hat = float(gamma_hat)
        natural_loss = (
            ((beta_hat - beta_true) / beta_true) ** 2
            + (eta_hat - 1.0) ** 2
            + (gamma_hat - gamma_ratio) ** 2
        )
        primary_loss = natural_loss
    return {
        "method": method,
        "beta_hat": float(beta_hat),
        "eta_hat_norm": float(eta_hat),
        "gamma_hat_norm": float(gamma_hat),
        "failed": bool(failed),
        "failure_reason": reason if failed else "",
        "loss_primary": float(primary_loss),
        "loss_natural_zero": float(natural_loss),
    }


def estimate_production_methods(task: tuple[float, float, int, int]) -> list[dict]:
    beta, gamma_ratio, n, repeat_id = task
    sample_display = generate_sample(
        beta, UNIT_SCALE, gamma_ratio * UNIT_SCALE, n, repeat_id, seed=SEED_NAMESPACE
    )
    sample_norm = sample_display / UNIT_SCALE
    rows = []
    for label in ["WMLE", "LSE", "MLE", "LRE"]:
        result = run_method(PRODUCTION_IDS[label], sample_norm)
        row = _evaluate_estimate(
            label,
            beta,
            gamma_ratio,
            result.get("beta_hat"),
            result.get("eta_hat"),
            result.get("gamma_hat"),
            bool(result.get("converged")),
            _failure_reason(result),
        )
        row.update(
            {
                "beta": beta,
                "gamma_over_eta": gamma_ratio,
                "n": n,
                "repeat_id": repeat_id,
                "fold": repeat_id % FOLDS,
            }
        )
        rows.append(row)
    return rows


def load_mdm_default() -> pd.DataFrame:
    usecols = [
        "beta",
        "eta",
        "gamma",
        "gamma_over_eta",
        "n",
        "repeat_id",
        "delta",
        "beta_hat",
        "eta_hat",
        "gamma_hat",
        "converged",
        "status",
    ]
    parts = []
    for chunk in pd.read_csv(MC_SCAN, usecols=usecols, chunksize=200_000):
        selected = chunk[np.isclose(chunk["delta"].astype(float), 0.1)].copy()
        if not selected.empty:
            parts.append(selected)
    raw = pd.concat(parts, ignore_index=True)
    rows = []
    for row in raw.itertuples(index=False):
        converged = str(row.converged).lower() in {"true", "1"} and str(row.status) == "success"
        evaluated = _evaluate_estimate(
            "MDM-0.1",
            float(row.beta),
            float(row.gamma_over_eta),
            row.beta_hat,
            float(row.eta_hat) / UNIT_SCALE if pd.notna(row.eta_hat) else None,
            float(row.gamma_hat) / UNIT_SCALE if pd.notna(row.gamma_hat) else None,
            converged,
            str(row.status),
        )
        evaluated.update(
            {
                "beta": float(row.beta),
                "gamma_over_eta": float(row.gamma_over_eta),
                "n": int(row.n),
                "repeat_id": int(row.repeat_id),
                "fold": int(row.repeat_id) % FOLDS,
            }
        )
        rows.append(evaluated)
    out = pd.DataFrame(rows)
    expected = len(BETA_GRID) * len(GAMMA_RATIO_GRID) * len(N_GRID) * REPEATS
    if len(out) != expected:
        raise RuntimeError(f"MDM default rows {len(out)} != {expected}")
    return out


def run_estimators(workers: int) -> pd.DataFrame:
    grid = build_grid()
    method_rows: list[dict] = []
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for batch in pool.imap_unordered(estimate_production_methods, grid, chunksize=40):
            method_rows.extend(batch)
    production = pd.DataFrame(method_rows)
    mdm = load_mdm_default()
    raw = pd.concat([mdm, production], ignore_index=True)
    raw = raw.sort_values(SAMPLE_KEYS + ["method"]).reset_index(drop=True)
    return raw


def validate_raw(raw: pd.DataFrame) -> None:
    expected_samples = len(BETA_GRID) * len(GAMMA_RATIO_GRID) * len(N_GRID) * REPEATS
    expected_rows = expected_samples * len(ALL_METHODS)
    if len(raw) != expected_rows:
        raise RuntimeError(f"raw rows {len(raw)} != {expected_rows}")
    if raw[SAMPLE_KEYS].drop_duplicates().shape[0] != expected_samples:
        raise RuntimeError("sample-key count mismatch")
    if raw.duplicated(SAMPLE_KEYS + ["method"]).any():
        raise RuntimeError("duplicate sample-method rows")
    counts = raw.groupby(SAMPLE_KEYS)["method"].nunique()
    if not (counts == len(ALL_METHODS)).all():
        raise RuntimeError("methods do not share all sample keys")
    if not np.isfinite(raw["loss_primary"]).all():
        raise RuntimeError("non-finite primary loss")


def method_summary(raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, g in raw.groupby("method", sort=True):
        rows.append(
            {
                "method": method,
                "role": "primary" if method in PRIMARY_METHODS else "diagnostic",
                "n_samples": len(g),
                "J1_primary": math.sqrt(float(g["loss_primary"].mean())),
                "J1_natural_zero": math.sqrt(float(g["loss_natural_zero"].mean())),
                "mean_loss_primary": float(g["loss_primary"].mean()),
                "failure_count": int(g["failed"].sum()),
                "failure_rate": float(g["failed"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["role", "J1_primary", "method"])


def cell_summary(raw: pd.DataFrame) -> pd.DataFrame:
    return (
        raw.groupby(CELL_KEYS + ["method"], as_index=False)
        .agg(
            mean_loss_primary=("loss_primary", "mean"),
            J1_primary=("loss_primary", lambda x: math.sqrt(float(x.mean()))),
            failure_rate=("failed", "mean"),
            n_samples=("loss_primary", "size"),
        )
        .sort_values(CELL_KEYS + ["method"])
    )


SELECTORS = {
    "Fixed": [],
    "n": ["n"],
    "beta": ["beta"],
    "beta+n": ["beta", "n"],
    "cell": CELL_KEYS,
}


def _training_choices(train: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if not group_cols:
        means = train.groupby("method", as_index=False)["loss_primary"].mean()
        choice = means.sort_values(["loss_primary", "method"]).iloc[0]
        return pd.DataFrame([{"selected_method": choice["method"], "train_mean_loss": choice["loss_primary"]}])
    means = train.groupby(group_cols + ["method"], as_index=False)["loss_primary"].mean()
    means = means.sort_values(group_cols + ["loss_primary", "method"])
    out = means.drop_duplicates(group_cols).rename(
        columns={"method": "selected_method", "loss_primary": "train_mean_loss"}
    )
    return out[group_cols + ["selected_method", "train_mean_loss"]]


def build_crossfit(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = raw[raw["method"].isin(PRIMARY_METHODS)].copy()
    evaluations = []
    decisions = []
    for selector, group_cols in SELECTORS.items():
        for fold in range(FOLDS):
            train = data[data["fold"] != fold]
            test = data[data["fold"] == fold]
            choices = _training_choices(train, group_cols)
            choices["selector"] = selector
            choices["fold"] = fold
            decisions.append(choices)
            if group_cols:
                merged = test.merge(choices[group_cols + ["selected_method"]], on=group_cols, how="left")
            else:
                merged = test.copy()
                merged["selected_method"] = choices.iloc[0]["selected_method"]
            selected = merged[merged["method"] == merged["selected_method"]].copy()
            if selected[SAMPLE_KEYS].drop_duplicates().shape[0] != data[data["fold"] == fold][SAMPLE_KEYS].drop_duplicates().shape[0]:
                raise RuntimeError(f"selector coverage failure: {selector}, fold {fold}")
            selected["selector"] = selector
            evaluations.append(selected)

    hindsight = (
        data.sort_values(SAMPLE_KEYS + ["loss_primary", "method"])
        .drop_duplicates(SAMPLE_KEYS)
        .copy()
    )
    hindsight["selected_method"] = hindsight["method"]
    hindsight["selector"] = "sample_hindsight"
    evaluations.append(hindsight)
    return pd.concat(evaluations, ignore_index=True), pd.concat(decisions, ignore_index=True)


def selector_summary(evaluations: pd.DataFrame) -> pd.DataFrame:
    fixed = evaluations[evaluations["selector"] == "Fixed"]
    fixed_mse = float(fixed["loss_primary"].mean())
    hindsight_mse = float(
        evaluations[evaluations["selector"] == "sample_hindsight"]["loss_primary"].mean()
    )
    denom = fixed_mse - hindsight_mse
    rows = []
    order = list(SELECTORS) + ["sample_hindsight"]
    for selector in order:
        g = evaluations[evaluations["selector"] == selector]
        mse = float(g["loss_primary"].mean())
        shares = Counter(g["selected_method"])
        rows.append(
            {
                "selector": selector,
                "information": {
                    "Fixed": "none",
                    "n": "observable n",
                    "beta": "true beta (oracle)",
                    "beta+n": "true beta + observable n (oracle)",
                    "cell": "true beta + true gamma/eta + n (oracle)",
                    "sample_hindsight": "realized sample loss (hindsight)",
                }[selector],
                "n_samples": len(g),
                "mean_loss": mse,
                "J1": math.sqrt(mse),
                "relative_J1_improvement_vs_fixed": 1.0 - math.sqrt(mse / fixed_mse),
                "oracle_MSE_space_recovered": (fixed_mse - mse) / denom if denom > 0 else np.nan,
                "selected_failure_rate": float(g["failed"].mean()),
                "MDM_share": shares.get("MDM-0.1", 0) / len(g),
                "WMLE_share": shares.get("WMLE", 0) / len(g),
                "LSE_share": shares.get("LSE", 0) / len(g),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_summary(evaluations: pd.DataFrame) -> pd.DataFrame:
    cell = (
        evaluations.groupby(["selector"] + CELL_KEYS, as_index=False)["loss_primary"]
        .mean()
        .pivot(index=CELL_KEYS, columns="selector", values="loss_primary")
        .sort_index()
    )
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = rng.integers(0, len(cell), size=(BOOTSTRAP_REPS, len(cell)))
    fixed = cell["Fixed"].to_numpy()
    rows = []
    for selector in list(SELECTORS) + ["sample_hindsight"]:
        selected = cell[selector].to_numpy()
        fixed_draw = fixed[indices].mean(axis=1)
        selected_draw = selected[indices].mean(axis=1)
        rel = 1.0 - np.sqrt(selected_draw / fixed_draw)
        rows.append(
            {
                "selector": selector,
                "bootstrap_unit": "design_cell",
                "n_cells": len(cell),
                "n_bootstrap": BOOTSTRAP_REPS,
                "relative_J1_improvement_point": 1.0 - math.sqrt(selected.mean() / fixed.mean()),
                "ci95_low": float(np.quantile(rel, 0.025)),
                "ci95_high": float(np.quantile(rel, 0.975)),
                "probability_positive": float((rel > 0).mean()),
            }
        )
    return pd.DataFrame(rows)


def winner_stability(cell: pd.DataFrame, choices: pd.DataFrame) -> pd.DataFrame:
    full_primary = cell[cell["method"].isin(PRIMARY_METHODS)].copy()
    ranked = full_primary.sort_values(CELL_KEYS + ["mean_loss_primary", "method"])
    best = ranked.groupby(CELL_KEYS, as_index=False).first().rename(
        columns={"method": "full_winner", "mean_loss_primary": "best_mean_loss"}
    )
    second = ranked.groupby(CELL_KEYS, as_index=False).nth(1).reset_index(drop=True).rename(
        columns={"mean_loss_primary": "second_mean_loss"}
    )
    best = best.merge(second[CELL_KEYS + ["second_mean_loss"]], on=CELL_KEYS, how="left")
    best["relative_margin_vs_second"] = 1.0 - np.sqrt(
        best["best_mean_loss"] / best["second_mean_loss"]
    )
    c = choices[choices["selector"] == "cell"].copy()
    rows = []
    for keys, group in c.groupby(CELL_KEYS):
        counts = Counter(group["selected_method"])
        mode, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        rows.append(
            {
                "beta": keys[0],
                "gamma_over_eta": keys[1],
                "n": keys[2],
                "fold_mode_winner": mode,
                "fold_agreement": count / FOLDS,
                "fold_winners": json.dumps(dict(sorted(counts.items())), ensure_ascii=False),
            }
        )
    out = pd.DataFrame(rows).merge(
        best[CELL_KEYS + ["full_winner", "best_mean_loss", "second_mean_loss", "relative_margin_vs_second"]],
        on=CELL_KEYS,
        how="left",
    )
    return out.sort_values(CELL_KEYS)


def subgroup_summary(evaluations: pd.DataFrame) -> pd.DataFrame:
    selected = evaluations[evaluations["selector"].isin(["Fixed", "n", "cell"])].copy()
    rows = []
    for group_type, col in [("n", "n"), ("beta", "beta"), ("gamma_over_eta", "gamma_over_eta")]:
        grouped = selected.groupby([col, "selector"], as_index=False)["loss_primary"].mean()
        pivot = grouped.pivot(index=col, columns="selector", values="loss_primary")
        for value, row in pivot.iterrows():
            for selector in ["n", "cell"]:
                rows.append(
                    {
                        "group_type": group_type,
                        "group_value": value,
                        "selector": selector,
                        "J1_fixed": math.sqrt(float(row["Fixed"])),
                        "J1_selected": math.sqrt(float(row[selector])),
                        "relative_J1_improvement": 1.0 - math.sqrt(float(row[selector] / row["Fixed"])),
                    }
                )
    return pd.DataFrame(rows)


def scale_sensitivity(summary: pd.DataFrame) -> pd.DataFrame:
    if not B2_SUMMARY.exists():
        return pd.DataFrame()
    b2 = pd.read_csv(B2_SUMMARY)
    current = summary.set_index("method")
    rows = []
    for method in ["WMLE", "LSE"]:
        display_j1 = float(b2.loc[b2["method"] == method, "J1"].iloc[0])
        norm_j1 = float(current.loc[method, "J1_primary"])
        rows.append(
            {
                "method": method,
                "direct_display_scale_J1_from_Study01_B2": display_j1,
                "common_unit_normalized_J1_current": norm_j1,
                "relative_difference_norm_vs_display": norm_j1 / display_j1 - 1.0,
                "interpretation": "implementation scale sensitivity; not a statistical method effect",
            }
        )
    return pd.DataFrame(rows)


def make_decision(
    summary: pd.DataFrame,
    selectors: pd.DataFrame,
    bootstrap: pd.DataFrame,
    stability: pd.DataFrame,
    subgroups: pd.DataFrame,
) -> dict:
    primary_fail_ok = bool(
        (summary[summary["method"].isin(PRIMARY_METHODS)]["failure_rate"] <= 0.01).all()
    )
    cell_row = selectors.set_index("selector").loc["cell"]
    cell_boot = bootstrap.set_index("selector").loc["cell"]
    rel = float(cell_row["relative_J1_improvement_vs_fixed"])
    ci_low = float(cell_boot["ci95_low"])
    n_rows = subgroups[(subgroups["group_type"] == "n") & (subgroups["selector"] == "cell")]
    positive_n = int((n_rows["relative_J1_improvement"] > 0).sum())
    stable = stability[stability["fold_agreement"] >= 0.8]
    stable_counts = stable["fold_mode_winner"].value_counts().to_dict()
    methods_with_regions = sorted([m for m, count in stable_counts.items() if count >= 5])
    criteria = {
        "primary_failure_gate": primary_fail_ok,
        "cell_relative_J1_at_least_3pct": rel >= 0.03,
        "cell_bootstrap_ci_lower_positive": ci_low > 0,
        "positive_in_at_least_3_of_4_n": positive_n >= 3,
        "at_least_two_methods_with_5_stable_cells": len(methods_with_regions) >= 2,
    }
    return {
        "decision": "CONTINUE_TO_OBSERVABLE_SELECTION_RESEARCH" if all(criteria.values()) else "STOP_OR_REPAIR_BEFORE_SELECTOR_RESEARCH",
        "criteria": criteria,
        "cell_relative_J1_improvement": rel,
        "cell_bootstrap_ci95": [ci_low, float(cell_boot["ci95_high"])],
        "positive_n_groups": positive_n,
        "stable_region_counts": stable_counts,
        "methods_with_replicated_regions": methods_with_regions,
    }


def write_outputs(raw: pd.DataFrame, elapsed: float) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw.to_csv(
        RAW_PATH,
        index=False,
        compression={"method": "gzip", "compresslevel": 6, "mtime": 0},
    )
    summary = method_summary(raw)
    cell = cell_summary(raw)
    evaluations, choices = build_crossfit(raw)
    selectors = selector_summary(evaluations)
    bootstrap = bootstrap_summary(evaluations)
    stability = winner_stability(cell, choices)
    subgroups = subgroup_summary(evaluations)
    scale = scale_sensitivity(summary)
    decision = make_decision(summary, selectors, bootstrap, stability, subgroups)

    summary.to_csv(METHOD_SUMMARY_PATH, index=False)
    cell.to_csv(CELL_SUMMARY_PATH, index=False)
    selectors.to_csv(SELECTOR_SUMMARY_PATH, index=False)
    choices.to_csv(FOLD_CHOICES_PATH, index=False)
    stability.to_csv(WINNER_STABILITY_PATH, index=False)
    bootstrap.to_csv(BOOTSTRAP_PATH, index=False)
    subgroups.to_csv(SUBGROUP_PATH, index=False)
    scale.to_csv(SCALE_PATH, index=False)

    result = {
        "run_id": RUN_ID,
        "created_at": utc_now(),
        "status": "complete",
        "question": "Is there stable, material conditional method-selection opportunity?",
        "design": {
            "beta": BETA_GRID,
            "gamma_over_eta": GAMMA_RATIO_GRID,
            "n": N_GRID,
            "repeats": REPEATS,
            "samples": 48_000,
            "folds": FOLDS,
            "seed_namespace": SEED_NAMESPACE,
            "unit_scale": UNIT_SCALE,
        },
        "primary_methods": PRIMARY_METHODS,
        "diagnostic_methods": DIAGNOSTIC_METHODS,
        "failure_loss": FAILURE_LOSS,
        "decision": decision,
        "elapsed_seconds": elapsed,
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def write_manifest(result: dict, elapsed: float) -> None:
    input_paths = {
        "research_contract": RESEARCH_ROOT / "README.md",
        "mc_scan_raw": MC_SCAN,
        "mc_manifest": MC_MANIFEST,
        "mc_data_sha256sums": MC_SUMS,
        "study01_b2_summary": B2_SUMMARY,
        "runner": PYTHON_ROOT / "studies" / "common" / "runner.py",
        "sample": PYTHON_ROOT / "studies" / "common" / "sample.py",
        "mdm": PYTHON_ROOT / "methods" / "mdm.py",
        "mle": PYTHON_ROOT / "methods" / "mle.py",
        "wmle": PYTHON_ROOT / "methods" / "wmle.py",
        "lse": PYTHON_ROOT / "methods" / "lse.py",
        "lre": PYTHON_ROOT / "methods" / "lre.py",
        "run_code": HERE,
    }
    outputs = [
        RAW_PATH,
        METHOD_SUMMARY_PATH,
        CELL_SUMMARY_PATH,
        SELECTOR_SUMMARY_PATH,
        FOLD_CHOICES_PATH,
        WINNER_STABILITY_PATH,
        BOOTSTRAP_PATH,
        SUBGROUP_PATH,
        SCALE_PATH,
        RESULT_PATH,
        RUN_LOG_PATH,
    ]
    manifest = {
        "run_id": RUN_ID,
        "created_at": utc_now(),
        "git_head": git_value("rev-parse", "HEAD"),
        "git_branch": git_value("branch", "--show-current"),
        "workspace_dirty": bool(git_value("status", "--porcelain")),
        "contract": {
            "primary_methods": PRIMARY_METHODS,
            "diagnostic_methods": DIAGNOSTIC_METHODS,
            "failure_loss": FAILURE_LOSS,
            "crossfit": "repeat_id mod 5",
            "bootstrap": {"unit": "design_cell", "reps": BOOTSTRAP_REPS, "seed": BOOTSTRAP_SEED},
            "decision_gate": "README.md",
        },
        "input_hashes": {
            name: sha256_file(path) for name, path in input_paths.items() if path.exists()
        },
        "output_hashes": {path.name: sha256_file(path) for path in outputs if path.exists()},
        "elapsed_seconds": elapsed,
        "decision": result["decision"],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(force: bool = False, workers: int = 8) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()
    lines = [
        f"run_id={RUN_ID}",
        f"started_at={utc_now()}",
        f"workers={workers}",
        f"source_scan={MC_SCAN}",
    ]
    if RAW_PATH.exists() and not force:
        lines.append("raw_mode=reuse")
        raw = pd.read_csv(RAW_PATH)
    else:
        lines.append("raw_mode=regenerate")
        raw = run_estimators(workers)
    validate_raw(raw)
    elapsed = time.time() - started
    result = write_outputs(raw, elapsed)
    lines.extend(
        [
            f"raw_rows={len(raw)}",
            f"elapsed_seconds={elapsed:.3f}",
            f"decision={result['decision']['decision']}",
            f"completed_at={utc_now()}",
        ]
    )
    RUN_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_manifest(result, elapsed)
    print(json.dumps(result["decision"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    mp.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    args = parser.parse_args()
    main(force=args.force, workers=max(1, args.workers))
