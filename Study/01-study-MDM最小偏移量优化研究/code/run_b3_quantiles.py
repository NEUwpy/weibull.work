"""
Study/01 B3 — engineering-life quantiles x_0.90 / x_0.95 / x_0.99.

Contract (02-实验协议 §5.3, message 1 B3):
  - Derive quantiles from the E6 selection results and the shared candidate
    estimates via  x_R = gamma + eta * (-ln(R))^(1/beta).
  - Compare Dimensional-RAW-MLP / Default / L6; WMLE and LSE are included when
    the B2 reference is complete.  No MDM rerun, no delta re-selection for the
    quantile goal, no direct-quantile network.
  - Report relative Bias, RMSE, MAE, P95 and failure rate for R in
    {0.90, 0.95, 0.99}, pooled and per n.  Do not presuppose that parameter J1
    gains propagate to the engineering quantiles.

Sources:
  - DIM-RAW selected delta per (sample, seed): E6 raw_specialist_results.csv
    (combo-holdout, out-of-fold selections).
  - MDM parameter estimates at a given delta: the reused 160-combo MC scan
    (shared_data chunks).  Default uses delta=0.1; L6 uses the per-sample
    argmin over the 26-point grid.
  - WMLE/LSE: B2 estimation.csv (same 48,000 samples).

Output: artifacts/formal/E6_dimensional_raw/quantiles/
  per_sample.csv (gitignored), summary.json, summary.csv,
  manifest.json, SHA256SUMS
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

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

_THIS = sys.modules[__name__]

CONTRACT_VERSION = "B3_quantiles_v1"
QUANTILE_R = {"x0.90": 0.90, "x0.95": 0.95, "x0.99": 0.99}
OUT_DIR = PS.QUANTILES_DIR
E6_SPECIALIST_DIR = PS.E6_DIR
RAW_SEL_PATH = os.path.join(E6_SPECIALIST_DIR, "specialist",
                            "raw_specialist_results.csv")
B2_EST_PATH = os.path.join(PS.TRADITIONAL_REF_DIR, "estimation.csv")
SEEDS = CFG.STABILITY_SEEDS


# ============================================================
# Quantile derivation
# ============================================================

def true_quantile(beta, eta, gamma, R):
    return gamma + eta * (-math.log(R)) ** (1.0 / beta)


def est_quantile(beta_hat, eta_hat, gamma_hat, R):
    return gamma_hat + eta_hat * (-math.log(R)) ** (1.0 / beta_hat)


def derive(df_est, df_mc, baseline, method, seed=None):
    """For one method, attach the per-sample 3-parameter estimate.

    df_est columns must include SAMPLE_KEYS and (beta_hat, eta_hat, gamma_hat,
    valid).  Returns a per-sample frame ready for quantile computation.
    """
    est = df_est.copy()
    est["method"] = method
    if seed is not None:
        est["seed"] = int(seed)
    else:
        est["seed"] = -1  # deterministic method
    return est


def mdm_estimates_for(df_est, df_mc):
    """Join per-(sample, delta) MDM estimates from the MC scan.

    df_est has SAMPLE_KEYS + selected_delta (+ seed/method).  The MC scan has
    one row per (sample, delta) with beta_hat/eta_hat/gamma_hat.
    """
    scan = df_mc[PS.SAMPLE_KEYS + ["delta", "beta_hat", "eta_hat", "gamma_hat",
                                   "status"]].copy()
    scan["delta"] = scan["delta"].astype(float)
    joined = df_est.merge(scan,
                          on=PS.SAMPLE_KEYS + ["delta"],
                          how="left", validate="many_to_one")
    missing = joined["beta_hat"].isna()
    joined["valid"] = (~missing).astype(bool)
    joined["failure_reason"] = np.where(missing, "mdm_estimate_missing", "")
    return joined


# ============================================================
# Metrics
# ============================================================

def quantile_metrics(df, qname, R):
    true_x = df["true_x"].astype(float)
    est_x = df["est_x"].astype(float)
    rel = (est_x - true_x) / true_x
    valid = df["valid"].astype(bool)
    n_total = int(len(df))
    n_fail = int((~valid).sum())
    rel_valid = rel[valid]
    if len(rel_valid) == 0:
        return {"quantile": qname, "R": R, "bias": float("nan"),
                "rmse": float("nan"), "mae": float("nan"),
                "p95_abs_rel": float("nan"),
                "failure_rate": float(n_fail / n_total) if n_total else float("nan"),
                "n_valid": 0, "n_total": n_total}
    abs_rel = rel_valid.abs()
    return {"quantile": qname, "R": R,
            "bias": float(rel_valid.mean()),
            "rmse": float(math.sqrt((rel_valid ** 2).mean())),
            "mae": float(abs_rel.mean()),
            "p95_abs_rel": float(np.percentile(abs_rel, 95)),
            "failure_rate": float(n_fail / n_total),
            "n_valid": int(len(rel_valid)), "n_total": n_total}


def summarize_quantiles(df, group_cols):
    rows = []
    for keys, g in df.groupby(group_cols, dropna=False):
        if isinstance(keys, tuple):
            row = dict(zip(group_cols, keys))
        else:
            row = {group_cols[0]: keys}
        for qname, R in QUANTILE_R.items():
            m = quantile_metrics(g, qname, R)
            for k, v in m.items():
                if k not in ("quantile", "R"):
                    row[f"{qname}_{k}"] = v
        rows.append(row)
    return pd.DataFrame(rows)


# ============================================================
# Main
# ============================================================

def main(force_rerun=False):
    os.makedirs(OUT_DIR, exist_ok=True)
    per_sample_path = os.path.join(OUT_DIR, "per_sample.csv")
    log = lambda msg: print(msg, flush=True)   # noqa: E731
    t_start = time.time()
    log("=" * 72)
    log("Study/01 B3 — engineering quantiles x_0.90/x_0.95/x_0.99")
    log(f"Output: {OUT_DIR}")
    log("=" * 72)

    if force_rerun and os.path.exists(per_sample_path):
        os.remove(per_sample_path)

    df_mc, df_full, _raw = PS.load_scan(verbose=False)
    PS.verify_design(df_full)
    baseline = PS.default_and_l6(df_full)

    frames = []

    # --- DIM-RAW (per seed) ---
    log("[1/4] Dimensional-RAW per-sample selections (from E6 raw_specialist)...")
    if not os.path.exists(RAW_SEL_PATH):
        raise SystemExit(f"Missing E6 raw_specialist_results.csv: {RAW_SEL_PATH}")
    raw_sel = pd.read_csv(RAW_SEL_PATH)
    raw_sel["delta"] = raw_sel["selected_delta"].astype(float)
    for seed in SEEDS:
        sub = raw_sel[raw_sel["seed"] == seed].copy()
        dim = mdm_estimates_for(sub, df_mc)
        dim = derive(dim, df_mc, baseline, "Dimensional-RAW", seed=seed)
        frames.append(dim)

    # --- Default ---
    log("[2/4] Default (delta=0.1) + L6 (hindsight)...")
    default_rows = df_mc[df_mc["delta"] == CFG.DEFAULT_DELTA].copy()
    default_rows = default_rows[PS.SAMPLE_KEYS + ["beta_hat", "eta_hat",
                                                  "gamma_hat", "status"]]
    default_rows["valid"] = default_rows["status"].eq("success") & \
        default_rows["beta_hat"].notna()
    default_rows["failure_reason"] = ""
    frames.append(derive(default_rows, df_mc, baseline, "Default"))

    l6_sub = baseline[["l6_delta"] + PS.SAMPLE_KEYS].rename(
        columns={"l6_delta": "delta"})
    l6_est = mdm_estimates_for(l6_sub, df_mc)
    frames.append(derive(l6_est, df_mc, baseline, "L6"))

    # --- WMLE / LSE (from B2) ---
    log("[3/4] WMLE / LSE (from B2 estimation.csv)...")
    if os.path.exists(B2_EST_PATH):
        b2 = pd.read_csv(B2_EST_PATH)
        for method, g in b2.groupby("method"):
            est = g[["beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id",
                     "beta_hat", "eta_hat", "gamma_hat", "valid"]].copy()
            est["failure_reason"] = np.where(est["valid"], "",
                                             "b2_invalid")
            frames.append(derive(est, df_mc, baseline, method))
        log("  WMLE/LSE included")
    else:
        log("  WARNING: B2 estimation.csv not found; WMLE/LSE excluded "
            "(can rerun after B2)")

    df = pd.concat(frames, ignore_index=True)
    for qname, R in QUANTILE_R.items():
        logR = -math.log(R)
        df[f"true_{qname}"] = (df["gamma"]
                               + df["eta"] * logR ** (1.0 / df["beta"]))
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            df[f"est_{qname}"] = (df["gamma_hat"]
                                  + df["eta_hat"]
                                  * logR ** (1.0 / df["beta_hat"]))
        df.loc[~df["valid"], f"est_{qname}"] = np.nan

    # sample-count contract per (method, seed)
    counts = df.groupby(["method", "seed"]).size()
    assert counts.loc[("Default", -1)] == 48000
    assert counts.loc[("L6", -1)] == 48000
    for m in ("WMLE", "LSE"):
        assert counts.loc[(m, -1)] == 48000
    for seed in SEEDS:
        assert counts.loc[("Dimensional-RAW", seed)] == 48000

    df.to_csv(per_sample_path, index=False)
    log(f"  per_sample rows: {len(df)}")

    log("[4/4] Metrics + provenance...")
    metric_frames = []
    metric_by_n_frames = []
    for method, g in df.groupby("method"):
        for seed, sg in g.groupby("seed"):
            rows = []
            for qname, R in QUANTILE_R.items():
                qdf = pd.DataFrame({
                    "method": method, "seed": seed,
                    "true_x": sg[f"true_{qname}"], "est_x": sg[f"est_{qname}"],
                    "valid": sg["valid"], "n": sg["n"],
                })
                rows.append(quantile_metrics(qdf, qname, R))
            mdf = pd.DataFrame(rows)
            mdf["method"] = method
            mdf["seed"] = int(seed)
            metric_frames.append(mdf)
            # per-n metrics (pooled across the 5 gamma/eta levels for each n)
            for nv, ng in sg.groupby("n"):
                for qname, R in QUANTILE_R.items():
                    qn = pd.DataFrame({
                        "method": method, "seed": seed, "n": int(nv),
                        "true_x": ng[f"true_{qname}"],
                        "est_x": ng[f"est_{qname}"], "valid": ng["valid"]})
                    m = quantile_metrics(qn, qname, R)
                    rec = {"method": method, "seed": int(seed), "n": int(nv),
                           "quantile": qname}
                    rec.update({k: m[k] for k in (
                        "bias", "rmse", "mae", "p95_abs_rel",
                        "failure_rate", "n_valid", "n_total")})
                    metric_by_n_frames.append(rec)
    metrics_df = pd.concat(metric_frames, ignore_index=True)
    metrics_df.to_csv(os.path.join(OUT_DIR, "summary.csv"), index=False)
    metrics_by_n = pd.DataFrame(metric_by_n_frames)
    metrics_by_n.to_csv(os.path.join(OUT_DIR, "summary_by_n.csv"), index=False)

    summary = {"experiment": "B3 engineering quantiles",
               "contract_version": CONTRACT_VERSION,
               "created_at": datetime.now(timezone.utc).isoformat(),
               "quantiles": QUANTILE_R,
               "per_method": {}}
    for method, g in metrics_df.groupby("method"):
        per_seed = {}
        for seed, sg in g.groupby("seed"):
            rec = {row["quantile"]: {
                "bias": row["bias"], "rmse": row["rmse"], "mae": row["mae"],
                "p95_abs_rel": row["p95_abs_rel"],
                "failure_rate": row["failure_rate"],
                "n_valid": row["n_valid"], "n_total": row["n_total"]}
                for _, row in sg.iterrows()}
            per_seed[int(seed)] = rec
        entry = {
            "role": ("deterministic" if method not in ("Dimensional-RAW",)
                     else "per-seed MLP selection"),
            "per_seed": per_seed,
        }
        if method == "Dimensional-RAW":
            # model-first three-seed mean AND SD (ddof=0, matching E6/B1)
            qnames = list(QUANTILE_R)
            metrics = ("bias", "rmse", "mae", "p95_abs_rel", "failure_rate")
            three_mean, three_std = {}, {}
            for q in qnames:
                vals = [per_seed[s][q] for s in SEEDS]
                three_mean[q] = {
                    metric: float(np.mean([v[metric] for v in vals]))
                    for metric in metrics}
                three_std[q] = {
                    metric: float(np.std([v[metric] for v in vals], ddof=0))
                    for metric in metrics}
            entry["three_seed_mean"] = three_mean
            entry["three_seed_std"] = three_std
            entry["three_seed_std_ddof"] = 0
            entry["n_seeds"] = len(SEEDS)
        summary["per_method"][method] = entry
    PS.atomic_write_json(summary, os.path.join(OUT_DIR, "summary.json"))

    manifest = {
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_entry": "code/run_b3_quantiles.py",
        "code_sha256": PS.code_sha256(_THIS, PS, CFG),
        "source": {
            "Dimensional-RAW": "E6 specialist/raw_specialist_results.csv "
                               "(out-of-fold selected delta per seed)",
            "Default": "MC scan at delta=0.1",
            "L6": "MC scan at per-sample argmin delta",
            "WMLE/LSE": "B2 traditional_ref/estimation.csv",
            "mdm_params": "reused shared_data MC scan (no MDM rerun)",
        },
        "formula": "x_R = gamma + eta * (-ln(R))^(1/beta)",
        "metric": "relative error (x_hat - x)/x; Bias/RMSE/MAE/P95; "
                  "failure_rate on invalid estimates",
        "provenance_note": ("code_sha256 binds the committed content of the "
                            "entry script and material dependencies; "
                            "git_commit records the runtime HEAD at generation "
                            "(see branch commit chain for the implementation "
                            "commits). SHA256SUMS covers git-tracked files "
                            "only; SHA256SUMS.local_not_in_git lists "
                            "gitignored/local raw files.  Dimensional-RAW "
                            "three-seed model-first mean is in "
                            "per_method[method].three_seed_mean."),
        "output_files": ["summary.json", "summary.csv", "summary_by_n.csv",
                         "manifest.json", "SHA256SUMS",
                         "SHA256SUMS.local_not_in_git",
                         "per_sample.csv (gitignored)"],
        "elapsed_s": float(time.time() - t_start),
        **PS.git_meta(),
    }
    n_tracked, n_local = PS.count_sha256(OUT_DIR)
    manifest["sha256_tracked_entries"] = n_tracked
    manifest["sha256_local_not_in_git_entries"] = n_local
    PS.atomic_write_json(manifest, os.path.join(OUT_DIR, "manifest.json"))
    with open(os.path.join(OUT_DIR, ".gitignore"), "w", encoding="utf-8") as f:
        f.write("per_sample.csv\nrun_b3_detached*\n")

    for p in (os.path.join(OUT_DIR, "summary.json"),
              os.path.join(OUT_DIR, "manifest.json"),
              os.path.join(OUT_DIR, "summary.csv"),
              os.path.join(OUT_DIR, "summary_by_n.csv")):
        PS.lf_normalize(p)
    # ledgers LAST so they include the just-written manifest
    n_tracked, n_local = PS.write_sha256sums(OUT_DIR)
    log(f"\nDone in {time.time()-t_start:.1f}s. Outputs in {OUT_DIR} "
        f"(SHA256SUMS tracked: {n_tracked}, local_not_in_git: {n_local})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-rerun", action="store_true")
    args = ap.parse_args()
    main(force_rerun=args.force_rerun)
