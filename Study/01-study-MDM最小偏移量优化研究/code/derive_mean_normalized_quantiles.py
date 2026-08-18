"""Derive x_0.90/x_0.95/x_0.99 for the mean-normalized selector.

The script joins the already-sealed E5 out-of-fold selected deltas to the
existing 26-delta MDM parameter-estimate scan.  It does not rerun MDM or train
a network.  Default and L6 are re-derived from that same scan.  WMLE/LSE rows
are reused unchanged from the existing B3 package after verifying its tracked
SHA ledger and the B2 48,000-key alignment receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
if STUDY_CODE_DIR not in sys.path:
    sys.path.insert(0, STUDY_CODE_DIR)

import dim_raw_config as CFG
import paper_support as PS
import run_b3_quantiles as B3

_THIS = sys.modules[__name__]

CONTRACT_VERSION = "E8_mean_normalized_quantiles_v1"
MODEL_NAME = "Mean-Normalized"
SEEDS = list(CFG.STABILITY_SEEDS)
OUT_DIR = os.path.join(
    PS.STUDY_ROOT, "artifacts", "formal", "E8_mean_normalized_selector",
    "quantiles")
SELECTION_PATH = os.path.join(
    PS.STUDY_ROOT, "artifacts", "formal", "E5_normalized_raw", "specialist",
    "raw_specialist_results.csv")
SELECTION_EXPECTED_SHA256 = (
    "b67578fe3a6e02c606ce0ba0bf224f4ce8a7acbf48de1fd87ef1739e368ad7db")
SELECTION_SOURCE_COMMIT = "ddc75754"
OLD_QUANTILES = os.path.join(PS.E6_DIR, "quantiles")
TRADITIONAL_REF = PS.TRADITIONAL_REF_DIR


def sha256_lf(path: str) -> str:
    return hashlib.sha256(
        open(path, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def verify_tracked_ledger(root: str) -> dict:
    ledger = os.path.join(root, "SHA256SUMS")
    checked = []
    with open(ledger, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            expected, rel = line.split("  ", 1)
            path = os.path.join(root, rel)
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            actual = PS.sha256_file_lf(path)
            if actual != expected:
                raise ValueError(f"SHA mismatch: {path}")
            checked.append(rel)
    return {"ledger": os.path.relpath(ledger, PS.STUDY_ROOT).replace(os.sep, "/"),
            "entries_verified": len(checked), "files": checked}


def key_digest(frame: pd.DataFrame) -> str:
    keys = (frame[PS.SAMPLE_KEYS].drop_duplicates()
            .sort_values(PS.SAMPLE_KEYS).reset_index(drop=True))
    digest = hashlib.sha256()
    for row in keys.itertuples(index=False, name=None):
        digest.update(("|".join(format(float(x), ".12g") if i < 4 else str(int(x))
                                for i, x in enumerate(row)) + "\n").encode())
    return digest.hexdigest()


def add_quantiles(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for name, reliability in B3.QUANTILE_R.items():
        scale = -math.log(reliability)
        result[f"true_{name}"] = (
            result["gamma"] + result["eta"] * scale ** (1.0 / result["beta"]))
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            result[f"est_{name}"] = (
                result["gamma_hat"]
                + result["eta_hat"] * scale ** (1.0 / result["beta_hat"]))
        result.loc[~result["valid"].astype(bool), f"est_{name}"] = np.nan
    return result


def metric_rows(per_sample: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pooled_rows, by_n_rows = [], []
    for (method, seed), rows in per_sample.groupby(["method", "seed"]):
        for qname, reliability in B3.QUANTILE_R.items():
            qdf = pd.DataFrame({
                "true_x": rows[f"true_{qname}"],
                "est_x": rows[f"est_{qname}"],
                "valid": rows["valid"],
            })
            rec = B3.quantile_metrics(qdf, qname, reliability)
            rec.update({"method": method, "seed": int(seed)})
            pooled_rows.append(rec)
            for n_val, n_rows in rows.groupby("n"):
                ndf = pd.DataFrame({
                    "true_x": n_rows[f"true_{qname}"],
                    "est_x": n_rows[f"est_{qname}"],
                    "valid": n_rows["valid"],
                })
                nrec = B3.quantile_metrics(ndf, qname, reliability)
                nrec.update({"method": method, "seed": int(seed),
                             "n": int(n_val)})
                by_n_rows.append(nrec)
    return pd.DataFrame(pooled_rows), pd.DataFrame(by_n_rows)


def three_seed_summary(metrics: pd.DataFrame) -> dict:
    sub = metrics[metrics["method"] == MODEL_NAME]
    out = {}
    for qname, rows in sub.groupby("quantile"):
        out[qname] = {}
        for metric in ("bias", "rmse", "mae", "p95_abs_rel", "failure_rate"):
            values = rows[metric].astype(float).to_numpy()
            out[qname][metric] = {
                "mean": float(values.mean()),
                "std": float(values.std(ddof=0)),
                "per_seed": {str(int(seed)): float(value)
                             for seed, value in zip(rows["seed"], values)},
            }
    return out


def run() -> dict:
    runtime_start_git = PS.git_meta()
    os.makedirs(OUT_DIR, exist_ok=True)
    started = time.time()

    actual_selection_hash = sha256_lf(SELECTION_PATH)
    if actual_selection_hash != SELECTION_EXPECTED_SHA256:
        raise ValueError("E5 out-of-fold selection SHA256 mismatch")

    old_quantile_ledger = verify_tracked_ledger(OLD_QUANTILES)
    traditional_ledger = verify_tracked_ledger(TRADITIONAL_REF)
    key_receipt = json.load(open(
        os.path.join(TRADITIONAL_REF, "sample_key_verification.json"),
        encoding="utf-8"))
    if not (key_receipt.get("match") is True
            and key_receipt.get("n_scan_keys") == 48000
            and key_receipt.get("n_grid_keys") == 48000):
        raise ValueError("B2 sample-key receipt is not valid")

    df_mc, df_full, _ = PS.load_scan(verbose=False)
    PS.verify_design(df_full)
    selections = pd.read_csv(SELECTION_PATH)
    expected_columns = set(PS.SAMPLE_KEYS + ["seed", "selected_delta"])
    if not expected_columns.issubset(selections.columns):
        raise ValueError("E5 selection schema mismatch")
    if set(selections["seed"].unique()) != set(SEEDS):
        raise ValueError("E5 selection seeds mismatch")
    if not set(selections["selected_delta"].unique()).issubset(CFG.DELTA_GRID):
        raise ValueError("E5 selected delta outside frozen grid")

    scan_key_sha = key_digest(df_full)
    selection_key_sha = key_digest(selections)
    if selection_key_sha != scan_key_sha:
        raise ValueError("E5 selections and MC scan do not share the same sample keys")
    counts = selections.groupby("seed").size().to_dict()
    unique_counts = selections.groupby("seed").apply(
        lambda x: len(x[PS.SAMPLE_KEYS].drop_duplicates()),
        include_groups=False).to_dict()
    if any(counts.get(seed) != 48000 or unique_counts.get(seed) != 48000
           for seed in SEEDS):
        raise ValueError("E5 selection sample multiplicity mismatch")

    frames = []
    for seed in SEEDS:
        selected = selections[selections["seed"] == seed].copy()
        selected["delta"] = selected["selected_delta"].astype(float)
        estimates = B3.mdm_estimates_for(selected, df_mc)
        estimates = B3.derive(estimates, df_mc, None, MODEL_NAME, seed=seed)
        frames.append(estimates)

    default = df_mc[df_mc["delta"] == CFG.DEFAULT_DELTA].copy()
    default = default[PS.SAMPLE_KEYS + ["beta_hat", "eta_hat", "gamma_hat",
                                        "status"]]
    default["valid"] = default["status"].eq("success") & default["beta_hat"].notna()
    default["failure_reason"] = np.where(default["valid"], "", "invalid")
    frames.append(B3.derive(default, df_mc, None, "Default"))

    baseline = PS.default_and_l6(df_full)
    l6_selected = baseline[PS.SAMPLE_KEYS + ["l6_delta"]].rename(
        columns={"l6_delta": "delta"})
    l6_estimates = B3.mdm_estimates_for(l6_selected, df_mc)
    frames.append(B3.derive(l6_estimates, df_mc, None, "L6"))

    per_sample = add_quantiles(pd.concat(frames, ignore_index=True))
    per_sample.to_csv(os.path.join(OUT_DIR, "per_sample.csv"), index=False)
    metrics, by_n = metric_rows(per_sample)

    old_metrics = pd.read_csv(os.path.join(OLD_QUANTILES, "summary.csv"))
    old_by_n = pd.read_csv(os.path.join(OLD_QUANTILES, "summary_by_n.csv"))
    reused_methods = ["WMLE", "LSE"]
    reused = old_metrics[old_metrics["method"].isin(reused_methods)].copy()
    reused_by_n = old_by_n[old_by_n["method"].isin(reused_methods)].copy()
    if len(reused) != 6 or len(reused_by_n) != 24:
        raise ValueError("Existing WMLE/LSE quantile summary is incomplete")
    metrics = pd.concat([metrics, reused], ignore_index=True)
    by_n = pd.concat([by_n, reused_by_n], ignore_index=True)
    metrics.to_csv(os.path.join(OUT_DIR, "summary.csv"), index=False)
    by_n.to_csv(os.path.join(OUT_DIR, "summary_by_n.csv"), index=False)

    # Re-derived deterministic anchors must exactly reproduce the old B3 rows.
    for method in ("Default", "L6"):
        left = (metrics[metrics["method"] == method]
                .sort_values("quantile").reset_index(drop=True))
        right = (old_metrics[old_metrics["method"] == method]
                 .sort_values("quantile").reset_index(drop=True))
        for column in ("bias", "rmse", "mae", "p95_abs_rel", "failure_rate"):
            if not np.allclose(left[column], right[column], rtol=0.0, atol=1e-12):
                raise ValueError(f"{method} {column} does not reproduce old B3")

    summary = {
        "experiment": "Mean-normalized selector engineering quantiles",
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "formula": "x_R = gamma + eta * (-ln(R))^(1/beta)",
        "mean_normalized_three_seed": three_seed_summary(metrics),
        "deterministic_and_external_methods": (
            metrics[metrics["method"].isin(["Default", "L6", "WMLE", "LSE"])]
            .to_dict(orient="records")),
        "sample_keys": {"count": 48000, "sha256": scan_key_sha,
                        "selection_match": True},
        "boundary": ("quantiles are derived from the selected MDM parameter "
                     "estimates; they are not a training target"),
        "runtime_start_git": runtime_start_git,
    }
    PS.atomic_write_json(summary, os.path.join(OUT_DIR, "summary.json"))

    manifest = {
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_entry": "code/derive_mean_normalized_quantiles.py",
        "code_sha256": PS.code_sha256(_THIS, PS, CFG, B3),
        "sources": {
            "mean_normalized_selected_delta": {
                "path": os.path.relpath(SELECTION_PATH, PS.STUDY_ROOT).replace(os.sep, "/"),
                "sha256_lf": actual_selection_hash,
                "formal_source_commit": SELECTION_SOURCE_COMMIT,
            },
            "mdm_parameters": "E5 shared_data 26-delta scan; reused, no MDM rerun",
            "Default_L6": "re-derived from the same scan",
            "WMLE_LSE": ("unchanged rows reused from E6 quantiles after B2 "
                         "sample-key receipt and tracked ledgers were verified"),
        },
        "source_verification": {
            "old_quantiles": old_quantile_ledger,
            "traditional_ref": traditional_ledger,
            "traditional_sample_key_receipt": key_receipt,
            "scan_and_selection_key_sha256": scan_key_sha,
        },
        "outputs": ["summary.json", "summary.csv", "summary_by_n.csv",
                    "manifest.json", "SHA256SUMS",
                    "SHA256SUMS.local_not_in_git", "per_sample.csv (gitignored)"],
        "elapsed_s": float(time.time() - started),
        "runtime_start_git": runtime_start_git,
    }
    PS.atomic_write_json(manifest, os.path.join(OUT_DIR, "manifest.json"))
    with open(os.path.join(OUT_DIR, ".gitignore"), "w", encoding="utf-8") as handle:
        handle.write("per_sample.csv\n")
    for name in ("summary.json", "manifest.json", "summary.csv", "summary_by_n.csv"):
        PS.lf_normalize(os.path.join(OUT_DIR, name))
    PS.write_sha256sums(OUT_DIR)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    run()
