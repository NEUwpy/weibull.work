"""
Study/01 B2 — WMLE / LSE same-condition external reference.

Contract (02-实验协议 §5.2, message 1 B2):
  - Only WMLE and LSE (MLE excluded from the paper result table).
  - Use the current 160-combination design and the SAME 48,000 samples
    (same seed namespace study01_nrmc_v1, eta=1000, gamma=goe*eta).  Sample
    keys are verified against the reused MC scan.
  - Report pooled J1, per-n J1, three-parameter Bias/RMSE, failure rate.
  - These are external coordinates only; they do not decide the main offset
    conclusion.  If the production implementation fails or is unreasonable,
    failures are counted honestly and reported, not hidden and not fixed by
    rebuilding an estimation platform.

Failure handling: a sample is a failure when the estimator does not converge
or returns a physically invalid estimate (not finite, or beta<=0, or eta<=0,
or gamma<0).  J1 / Bias / RMSE are computed on complete cases; the failure
rate is reported alongside and never silently dropped.

Output: artifacts/formal/E6_dimensional_raw/traditional_ref/
  estimation.csv (gitignored, per-sample), summary.json, summary.csv,
  param_metrics.csv, sample_key_verification.json, manifest.json, SHA256SUMS

Run:  python code/run_b2_traditional_ref.py [--force-rerun] [--workers N]
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from multiprocessing import Pool

import numpy as np
import pandas as pd

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_DIR = os.path.join(os.path.dirname(os.path.dirname(STUDY_CODE_DIR)),
                          "python")
for p in (STUDY_CODE_DIR, PYTHON_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import dim_raw_config as CFG
import paper_support as PS

from studies.common.sample import generate_sample
from studies.common.runner import run_method

CONTRACT_VERSION = "B2_traditional_ref_v1"
METHODS = ["WMLE", "LSE"]
METHOD_IDS = {"WMLE": "wmle", "LSE": "lse"}
OUT_DIR = PS.TRADITIONAL_REF_DIR
ETA_TRUE = CFG.ETA
SEED_NS = CFG.SEED_NAMESPACE


# ============================================================
# Sample grid (same 48,000 samples as the MC scan)
# ============================================================

def build_sample_grid():
    rows = []
    for b in CFG.BETA_GRID:
        for g in CFG.GAMMA_OVER_ETA_GRID:
            gamma = g * ETA_TRUE
            for n in CFG.N_GRID:
                for rid in range(CFG.REPEATS):
                    rows.append({"beta": float(b), "eta": float(ETA_TRUE),
                                 "gamma": float(gamma),
                                 "gamma_over_eta": float(g),
                                 "n": int(n), "repeat_id": int(rid)})
    return pd.DataFrame(rows)


def verify_sample_keys(grid):
    """Grid keys must exactly match the reused MC scan unique keys."""
    df_mc, _df_full, _raw = PS.load_scan(verbose=False)
    scan_keys = set(
        map(tuple, df_mc[PS.SAMPLE_KEYS].drop_duplicates().values))
    grid_keys = set(map(tuple, grid[PS.SAMPLE_KEYS].values))
    only_scan = scan_keys - grid_keys
    only_grid = grid_keys - scan_keys
    return {"n_scan_keys": len(scan_keys), "n_grid_keys": len(grid_keys),
            "only_in_scan": len(only_scan), "only_in_grid": len(only_grid),
            "match": not only_scan and not only_grid}


# ============================================================
# Estimator worker (module-level for multiprocessing pickling)
# ============================================================

def _estimate_one(args):
    row, method_label = args
    method_id = METHOD_IDS[method_label]
    beta, eta, gamma = row["beta"], row["eta"], row["gamma"]
    n, rid = int(row["n"]), int(row["repeat_id"])
    sample = generate_sample(beta, eta, gamma, n, rid, seed=SEED_NS)
    result = run_method(method_id, sample)
    bh = result.get("beta_hat")
    eh = result.get("eta_hat")
    gh = result.get("gamma_hat")
    converged = bool(result.get("converged"))

    failed = (not converged) or (bh is None or eh is None or gh is None)
    reason = ""
    if not converged:
        reason = f"{method_id}_not_converged"
    if not failed:
        vals = [bh, eh, gh]
        if not all(np.isfinite(v) for v in vals):
            failed, reason = True, "non_finite_estimate"
        elif bh <= 0 or eh <= 0:
            failed, reason = True, "invalid_positive_constraint"
        elif gh < 0:
            failed, reason = True, "location_negative"

    if failed:
        bh = eh = gh = 0.0
        loss = float("nan")
        valid = False
    else:
        loss = ((bh - beta) / beta) ** 2 + ((eh - eta) / eta) ** 2 \
            + ((gh - gamma) / eta) ** 2
        valid = True

    return {"method": method_label, "beta": float(beta), "eta": float(eta),
            "gamma": float(gamma), "gamma_over_eta": float(row["gamma_over_eta"]),
            "n": int(n), "repeat_id": int(rid),
            "beta_hat": float(bh), "eta_hat": float(eh), "gamma_hat": float(gh),
            "converged": converged, "failed": failed, "failure_reason": reason,
            "loss": float(loss), "valid": valid}


# ============================================================
# Aggregation
# ============================================================

def compute_summary(df):
    """Per-method pooled / per-n J1 (complete case) and failure rate."""
    rows = []
    for method, g in df.groupby("method"):
        n_total = int(len(g))
        n_fail = int(g["failed"].sum())
        valid = g[g["valid"]]
        pooled = PS.j1_from_loss(valid["loss"]) if len(valid) else float("nan")
        r = {"method": method, "J1": pooled, "n_total": n_total,
             "n_failed": n_fail, "n_valid": int(len(valid)),
             "failure_rate": float(n_fail / n_total)}
        for nv, ng in g.groupby("n"):
            nv_valid = ng[ng["valid"]]
            r[f"J1_n{int(nv)}"] = (PS.j1_from_loss(nv_valid["loss"])
                                   if len(nv_valid) else float("nan"))
            r[f"failure_n{int(nv)}"] = float(ng["failed"].mean())
        rows.append(r)
    return pd.DataFrame(rows)


def compute_param_metrics(df):
    rows = []
    for method, g in df.groupby("method"):
        valid = g[g["valid"]]
        metrics = PS.param_bias_rmse_mae(valid)
        row = {"method": method, "n_valid": int(len(valid))}
        for name, m in metrics.items():
            row[f"bias_{name}"] = m["bias"]
            row[f"rmse_{name}"] = m["rmse"]
            row[f"mae_{name}"] = m["mae"]
        rows.append(row)
    return pd.DataFrame(rows)


# ============================================================
# Main
# ============================================================

def main(force_rerun=False, workers=8):
    os.makedirs(OUT_DIR, exist_ok=True)
    est_path = os.path.join(OUT_DIR, "estimation.csv")
    log = lambda msg: print(msg, flush=True)   # noqa: E731
    t_start = time.time()
    log("=" * 72)
    log("Study/01 B2 — WMLE / LSE same-condition external reference")
    log(f"Output: {OUT_DIR}")
    log("=" * 72)

    grid = build_sample_grid()
    key_check = verify_sample_keys(grid)
    log(f"[1/4] Sample keys vs MC scan: {key_check}")
    if not key_check["match"]:
        raise SystemExit(f"Sample key mismatch: {key_check}")

    if force_rerun and os.path.exists(est_path):
        os.remove(est_path)

    if os.path.exists(est_path):
        log(f"[2/4] Loading existing estimation.csv ({len(pd.read_csv(est_path))} rows)")
        df_est = pd.read_csv(est_path)
    else:
        log(f"[2/4] Estimating WMLE/LSE on 48,000 samples "
            f"(workers={workers})...")
        tasks = []
        for _, row in grid.iterrows():
            for m in METHODS:
                tasks.append((row, m))
        with Pool(processes=workers) as pool:
            results = pool.map(_estimate_one, tasks, chunksize=512)
        df_est = pd.DataFrame(results)
        df_est.to_csv(est_path, index=False)
        log(f"  wrote {len(df_est)} estimation rows")

    n_total = len(df_est)
    assert n_total == 48000 * len(METHODS), f"rows {n_total} != expected"
    for method, g in df_est.groupby("method"):
        assert len(g) == 48000
        # complete-delta-per-key contract already guaranteed by the grid

    log("[3/4] Summaries...")
    summary_df = compute_summary(df_est)
    summary_df.to_csv(os.path.join(OUT_DIR, "summary.csv"), index=False)
    param_df = compute_param_metrics(df_est)
    param_df.to_csv(os.path.join(OUT_DIR, "param_metrics.csv"), index=False)
    for _, r in summary_df.iterrows():
        log(f"  {r['method']}: pooled J1={r['J1']:.6f} "
            f"failure_rate={r['failure_rate']*100:.2f}% "
            f"(n_valid={r['n_valid']}/{r['n_total']})")

    log("[4/4] Provenance...")
    summary = {
        "experiment": "B2 WMLE/LSE same-condition external reference",
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "methods": METHODS,
        "method_ids": METHOD_IDS,
        "seed_namespace": SEED_NS,
        "design": CFG.design_summary(),
        "sample_key_verification": key_check,
        "failure_handling": ("complete-case J1/Bias/RMSE; failure_rate reported "
                             "separately; never dropped"),
        "summary": summary_df.to_dict(orient="records"),
        "param_metrics": param_df.to_dict(orient="records"),
        "elapsed_s": float(time.time() - t_start),
        "role_note": "external coordinates only; does not decide the offset conclusion",
        **PS.git_meta(),
    }
    PS.atomic_write_json(summary, os.path.join(OUT_DIR, "summary.json"))
    PS.atomic_write_json(key_check, os.path.join(
        OUT_DIR, "sample_key_verification.json"))
    manifest = {
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_entry": "code/run_b2_traditional_ref.py",
        "code_sha256": PS.code_sha256(PS),
        "estimators": "python/methods/wmle.py + python/methods/lse.py via "
                      "studies/common/runner.run_method (reused production impl)",
        "output_files": ["summary.json", "summary.csv", "param_metrics.csv",
                         "sample_key_verification.json", "manifest.json",
                         "SHA256SUMS", "estimation.csv (gitignored)"],
        "elapsed_s": float(time.time() - t_start),
        **PS.git_meta(),
    }
    PS.atomic_write_json(manifest, os.path.join(OUT_DIR, "manifest.json"))
    with open(os.path.join(OUT_DIR, ".gitignore"), "w", encoding="utf-8") as f:
        f.write("estimation.csv\nrun_b2_detached*\n")

    for p in (os.path.join(OUT_DIR, "summary.json"),
              os.path.join(OUT_DIR, "manifest.json"),
              os.path.join(OUT_DIR, "summary.csv"),
              os.path.join(OUT_DIR, "param_metrics.csv"),
              os.path.join(OUT_DIR, "sample_key_verification.json")):
        PS.lf_normalize(p)
    n_entries = PS.write_sha256sums(OUT_DIR)
    log(f"\nDone in {time.time()-t_start:.1f}s. Outputs in {OUT_DIR} "
        f"(SHA256SUMS: {n_entries} entries)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-rerun", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    main(force_rerun=args.force_rerun, workers=args.workers)
