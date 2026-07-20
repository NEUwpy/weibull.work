"""
Method comparison: MLE, WMLE, LSE, LRE, MDM-0.1, MDM-MLP, MDM-L6-oracle
For (beta=2.0, eta=1.0, gamma=1.0) x n in {7, 10, 20} x 1000 repeats = 3000 samples.
Display scale: (2, 1000, 1000).
"""

import os
import sys
import csv
import json
import time
import math
import hashlib
import argparse
import traceback
import multiprocessing as mp
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

mp.set_start_method("spawn", force=True)

sys.path.insert(0, r"D:\weibull\python")
from studies.common.sample import generate_sample
from studies.common.runner import run_method

BETA_NORM = 2.0
ETA_NORM = 1.0
GAMMA_NORM = 1.0
SEED_NAMESPACE = "study01_v1"
N_VALUES = [7, 10, 20]
N_REPEATS = 1000
DISPLAY_SCALE = 1000.0

TRADITIONAL_METHODS = ["mle", "wmle", "lse", "lre"]
# Methods that failed scale equivariance check: must run at display scale directly.
# LSE passes: can use norm scale and multiply by 1000.
METHODS_NEED_DISPLAY_SCALE = {"mle", "wmle", "lre"}

STUDY_DIR = os.path.dirname(os.path.abspath(__file__))
SUB_STUDY_DIR = os.path.dirname(STUDY_DIR)
PARENT_STUDY_DIR = os.path.dirname(SUB_STUDY_DIR)
PLATFORM_DIR = r"D:\weibull\python"
FORMAL_DIR = os.path.join(PARENT_STUDY_DIR, "artifacts", "formal")
ARTIFACTS_DIR = os.path.join(SUB_STUDY_DIR, "artifacts")

MC_SCAN_CSV = os.path.join(FORMAL_DIR, "shared_data", "mc_scan_raw.csv")
MLP_CSV = os.path.join(FORMAL_DIR, "E3b_vector_mlp", "vector_mlp_results.csv")
L6_CSV = os.path.join(FORMAL_DIR, "E2_oracle_layers", "L6_per_sample_delta.csv")

PER_SAMPLE_CSV = os.path.join(ARTIFACTS_DIR, "per_sample_results.csv")
OVERALL_CSV = os.path.join(ARTIFACTS_DIR, "overall_summary.csv")
SUMMARY_N7_CSV = os.path.join(ARTIFACTS_DIR, "summary_n7.csv")
SUMMARY_N10_CSV = os.path.join(ARTIFACTS_DIR, "summary_n10.csv")
SUMMARY_N20_CSV = os.path.join(ARTIFACTS_DIR, "summary_n20.csv")
SCALE_CHECK_CSV = os.path.join(ARTIFACTS_DIR, "scale_equivariance_check.csv")
MANIFEST_JSON = os.path.join(ARTIFACTS_DIR, "manifest.json")
RUN_LOG_TXT = os.path.join(ARTIFACTS_DIR, "run_log.txt")

INPUT_FILES = [MC_SCAN_CSV, MLP_CSV, L6_CSV]
CRITICAL_FILES = [
    os.path.join(FORMAL_DIR, "shared_data", "manifest.json"),
    os.path.join(FORMAL_DIR, "E3b_vector_mlp", "manifest.json"),
    os.path.join(FORMAL_DIR, "E2_oracle_layers", "manifest.json"),
]

N_WORKERS = min(8, mp.cpu_count())
CHECKPOINT_N_WORKERS = min(4, mp.cpu_count())

SCALE_CHECK_REPEATS = list(range(5))
SCALE_TOLERANCE = 1e-10

DELTA_GRID = [round(0.00 + 0.02 * i, 2) for i in range(26)]


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)


def compute_single_error(beta_hat, eta_hat, gamma_hat, beta, eta, gamma):
    e_beta = (beta_hat - beta) / beta if beta != 0 else float("inf")
    e_eta = (eta_hat - eta) / eta if eta != 0 else float("inf")
    e_gamma = (gamma_hat - gamma) / eta
    L_i = e_beta**2 + e_eta**2 + e_gamma**2
    return e_beta, e_eta, e_gamma, L_i


def is_finite_valid(result: dict) -> Tuple[bool, str]:
    if not result["converged"]:
        return False, "converged=False"
    bh = result["beta_hat"]
    eh = result["eta_hat"]
    gh = result["gamma_hat"]
    if bh is None or eh is None or gh is None:
        return False, "None estimate"
    if not all(math.isfinite(v) for v in [bh, eh, gh]):
        return False, "non-finite estimate"
    if bh <= 0 or eh <= 0:
        return False, "non-positive beta/eta"
    if result.get("extra") and result["extra"].get("error"):
        return False, f"error: {result['extra']['error']}"
    return True, ""


def _sample_key(n, repeat_id):
    return f"{SEED_NAMESPACE}|{BETA_NORM}|{ETA_NORM}|{GAMMA_NORM}|{n}|{repeat_id}"


def worker_traditional(args):
    method_id, beta, eta, gamma, n, repeat_id, seed_namespace, use_display = args
    try:
        sample = generate_sample(beta, eta, gamma, n, repeat_id, seed=seed_namespace)
        if use_display:
            sample = sample * DISPLAY_SCALE
            run_beta, run_eta, run_gamma = beta, eta * DISPLAY_SCALE, gamma * DISPLAY_SCALE
        else:
            run_beta, run_eta, run_gamma = beta, eta, gamma
        result = run_method(method_id, sample)
        result["beta_true"] = run_beta
        result["eta_true"] = run_eta
        result["gamma_true"] = run_gamma
        result["n_sample"] = n
        result["repeat_id"] = repeat_id
        result["sample_hash"] = hashlib.sha256(
            _sample_key(n, repeat_id).encode()
        ).hexdigest()[:16]
        return result
    except Exception as e:
        return {
            "method_id": method_id,
            "beta_hat": None,
            "eta_hat": None,
            "gamma_hat": None,
            "r_squared": None,
            "converged": False,
            "time": 0.0,
            "extra": {"error": f"worker exception: {type(e).__name__}: {e}"},
            "beta_true": beta * (DISPLAY_SCALE if use_display else 1.0),
            "eta_true": eta * (DISPLAY_SCALE if use_display else 1.0),
            "gamma_true": gamma * (DISPLAY_SCALE if use_display else 1.0),
            "n_sample": n,
            "repeat_id": repeat_id,
            "sample_hash": "",
        }


class ComparisonRunner:
    def __init__(self):
        self.start_ts = iso_now()
        self.results: List[dict] = []
        self.file_hashes: Dict[str, str] = {}
        self.phase_times: Dict[str, float] = {}

    def record_input_hashes(self):
        log("Recording input file SHA256...")
        for p in INPUT_FILES + CRITICAL_FILES:
            if os.path.exists(p):
                self.file_hashes[os.path.basename(p)] = sha256_file(p)
                log(f"  {os.path.basename(p)}: {self.file_hashes[os.path.basename(p)][:16]}...")
        python_paths = [
            os.path.join(PLATFORM_DIR, "studies", "common", "sample.py"),
            os.path.join(PLATFORM_DIR, "studies", "common", "runner.py"),
            os.path.join(PLATFORM_DIR, "methods", "mle.py"),
            os.path.join(PLATFORM_DIR, "methods", "wmle.py"),
            os.path.join(PLATFORM_DIR, "methods", "lse.py"),
            os.path.join(PLATFORM_DIR, "methods", "lre.py"),
        ]
        for p in python_paths:
            if os.path.exists(p):
                self.file_hashes[os.path.basename(p)] = sha256_file(p)

    def extract_mdm_from_cache(self) -> pd.DataFrame:
        log("Loading mc_scan_raw.csv for target combo...")
        t0 = time.time()
        dtypes = {
            "beta": float, "eta": float, "gamma": float, "n": int,
            "repeat_id": int, "delta": float,
            "beta_hat": float, "eta_hat": float, "gamma_hat": float,
            "r_squared": float, "converged": str, "status": str,
        }
        df = pd.read_csv(MC_SCAN_CSV, dtype=dtypes, low_memory=False)
        mask = (
            (df["beta"] == BETA_NORM)
            & (df["eta"] == ETA_NORM)
            & (df["gamma"] == GAMMA_NORM)
        )
        df_target = df[mask].copy()
        del df
        df_target["delta"] = df_target["delta"].astype(float)
        df_target["n"] = df_target["n"].astype(int)
        df_target["repeat_id"] = df_target["repeat_id"].astype(int)
        elapsed = time.time() - t0
        log(f"  Loaded {len(df_target)} MDM rows in {elapsed:.1f}s")
        self.phase_times["extract_mdm"] = elapsed
        return df_target

    def get_mlp_deltas(self) -> pd.DataFrame:
        log("Loading MLP predictions for Vector-MLP-L6, target combo...")
        df = pd.read_csv(MLP_CSV)
        mask = (
            (df["model"] == "Vector-MLP-L6")
            & (df["beta"] == BETA_NORM)
            & (df["gamma_over_eta"] == GAMMA_NORM)
        )
        df_mlp = df[mask][["beta", "gamma_over_eta", "n", "repeat_id", "selected_delta"]].copy()
        df_mlp["n"] = df_mlp["n"].astype(int)
        df_mlp["repeat_id"] = df_mlp["repeat_id"].astype(int)
        log(f"  MLP rows for target: {len(df_mlp)}")
        return df_mlp

    def get_l6_oracle_deltas(self) -> pd.DataFrame:
        log("Loading L6 oracle per-sample deltas for target combo...")
        df = pd.read_csv(L6_CSV)
        mask = (
            (df["beta"] == BETA_NORM)
            & (df["eta"] == ETA_NORM)
            & (df["gamma"] == GAMMA_NORM)
        )
        df_l6 = df[mask][["beta", "eta", "gamma", "n", "repeat_id", "delta_star_L6"]].copy()
        df_l6["n"] = df_l6["n"].astype(int)
        df_l6["repeat_id"] = df_l6["repeat_id"].astype(int)
        df_l6 = df_l6.rename(columns={"delta_star_L6": "selected_delta"})
        log(f"  L6 oracle rows for target: {len(df_l6)}")
        return df_l6

    def build_mdm_results(self, df_mdm: pd.DataFrame, df_mlp: pd.DataFrame, df_l6: pd.DataFrame) -> List[dict]:
        log("Building MDM-based results (0.1, MLP, L6 oracle)...")
        t0 = time.time()

        df_01 = df_mdm[df_mdm["delta"] == 0.1].copy()
        df_01 = df_01.rename(columns={
            "beta_hat": "bh", "eta_hat": "eh", "gamma_hat": "gh",
            "r_squared": "r2", "converged": "conv", "status": "stat",
        })

        def lookup_delta(df_mdm_subset, df_delta):
            joined = df_delta.merge(
                df_mdm_subset,
                on=["n", "repeat_id", "delta"],
                how="left",
            )
            return joined

        df_mlp_est = lookup_delta(df_mdm, df_mlp.rename(columns={"selected_delta": "delta"}))
        df_l6_est = lookup_delta(df_mdm, df_l6.rename(columns={"selected_delta": "delta"}))

        results = []
        for n in N_VALUES:
            for rid in range(N_REPEATS):
                sample_hash = hashlib.sha256(
                    _sample_key(n, rid).encode()
                ).hexdigest()[:16]

                row_01 = df_01[(df_01["n"] == n) & (df_01["repeat_id"] == rid)]
                if len(row_01) == 1:
                    r = row_01.iloc[0]
                    conv = str(r["conv"]).strip().lower()
                    results.append({
                        "method": "MDM-0.1", "n": n, "repeat_id": rid,
                        "beta_hat": float(r["bh"]), "eta_hat": float(r["eh"]), "gamma_hat": float(r["gh"]),
                        "converged": conv in ("true", "1", "yes"),
                        "failure_reason": "" if conv in ("true", "1", "yes") else f"status={r['stat']}",
                        "time_s": None, "sample_hash": sample_hash,
                    })

                row_mlp = df_mlp_est[(df_mlp_est["n"] == n) & (df_mlp_est["repeat_id"] == rid)]
                if len(row_mlp) == 1:
                    r = row_mlp.iloc[0]
                    conv = str(r.get("converged", "True")).strip().lower()
                    results.append({
                        "method": "MDM-MLP", "n": n, "repeat_id": rid,
                        "beta_hat": float(r["beta_hat"]) if not pd.isna(r["beta_hat"]) else 0.0,
                        "eta_hat": float(r["eta_hat"]) if not pd.isna(r["eta_hat"]) else 0.0,
                        "gamma_hat": float(r["gamma_hat"]) if not pd.isna(r["gamma_hat"]) else 0.0,
                        "converged": conv in ("true", "1", "yes"),
                        "failure_reason": "" if conv in ("true", "1", "yes") else f"status={r.get('status','?')}",
                        "time_s": None, "sample_hash": sample_hash,
                    })

                row_l6 = df_l6_est[(df_l6_est["n"] == n) & (df_l6_est["repeat_id"] == rid)]
                if len(row_l6) == 1:
                    r = row_l6.iloc[0]
                    conv = str(r.get("converged", "True")).strip().lower()
                    results.append({
                        "method": "MDM-L6-oracle", "n": n, "repeat_id": rid,
                        "beta_hat": float(r["beta_hat"]) if not pd.isna(r["beta_hat"]) else 0.0,
                        "eta_hat": float(r["eta_hat"]) if not pd.isna(r["eta_hat"]) else 0.0,
                        "gamma_hat": float(r["gamma_hat"]) if not pd.isna(r["gamma_hat"]) else 0.0,
                        "converged": conv in ("true", "1", "yes"),
                        "failure_reason": "" if conv in ("true", "1", "yes") else f"status={r.get('status','?')}",
                        "time_s": None, "sample_hash": sample_hash,
                    })

        elapsed = time.time() - t0
        log(f"  Built {len(results)} MDM-based results in {elapsed:.1f}s")
        self.phase_times["build_mdm"] = elapsed
        return results

    def run_traditional_methods(self) -> List[dict]:
        log("Running traditional methods (MLE, WMLE, LSE, LRE) for 3000 samples each...")
        log(f"  Methods needing display scale: {METHODS_NEED_DISPLAY_SCALE}")
        log(f"  LSE: uses norm scale (validated scale-equivariant)")
        t0 = time.time()

        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        checkpoint_dir = os.path.join(ARTIFACTS_DIR, "checkpoints")
        os.makedirs(checkpoint_dir, exist_ok=True)

        all_results = []
        for method_id in TRADITIONAL_METHODS:
            use_display = method_id in METHODS_NEED_DISPLAY_SCALE
            true_beta = BETA_NORM
            true_eta = ETA_NORM * (DISPLAY_SCALE if use_display else 1.0)
            true_gamma = GAMMA_NORM * (DISPLAY_SCALE if use_display else 1.0)
            scale_tag = "display" if use_display else "norm"

            for n in N_VALUES:
                ckpt_file = os.path.join(checkpoint_dir, f"trad_{method_id}_n{n}_{scale_tag}.csv")
                if os.path.exists(ckpt_file):
                    log(f"  Loading checkpoint for {method_id} n={n} ({scale_tag})...")
                    df_ckpt = pd.read_csv(ckpt_file)
                    for _, row in df_ckpt.iterrows():
                        all_results.append({
                            "method_id": method_id,
                            "beta_hat": row.get("beta_hat"),
                            "eta_hat": row.get("eta_hat"),
                            "gamma_hat": row.get("gamma_hat"),
                            "r_squared": row.get("r_squared"),
                            "converged": row.get("converged", False),
                            "time": row.get("time", 0.0),
                            "extra": {"error": row.get("error", None), "raw_status": row.get("raw_status", None)},
                            "beta_true": true_beta,
                            "eta_true": true_eta,
                            "gamma_true": true_gamma,
                            "n_sample": n,
                            "repeat_id": int(row["repeat_id"]),
                            "sample_hash": row.get("sample_hash", ""),
                        })
                    continue

                tasks = [(method_id, BETA_NORM, ETA_NORM, GAMMA_NORM, n, rid, SEED_NAMESPACE, use_display)
                         for rid in range(N_REPEATS)]
                log(f"  Running {method_id} n={n} ({scale_tag}): {len(tasks)} estimates...")

                combo_results = []
                with mp.Pool(processes=N_WORKERS) as pool:
                    for result in pool.imap_unordered(worker_traditional, tasks, chunksize=20):
                        combo_results.append(result)

                ckpt_rows = []
                for r in combo_results:
                    extra = r.get("extra") or {}
                    ckpt_rows.append({
                        "repeat_id": r["repeat_id"],
                        "beta_hat": r["beta_hat"],
                        "eta_hat": r["eta_hat"],
                        "gamma_hat": r["gamma_hat"],
                        "r_squared": r.get("r_squared"),
                        "converged": r["converged"],
                        "time": r.get("time", 0.0),
                        "error": extra.get("error", ""),
                        "raw_status": extra.get("raw_status", ""),
                        "sample_hash": r.get("sample_hash", ""),
                    })
                pd.DataFrame(ckpt_rows).to_csv(ckpt_file, index=False)
                log(f"    Checkpoint saved: {ckpt_file} ({len(combo_results)} rows)")

                all_results.extend(combo_results)

        elapsed = time.time() - t0
        log(f"  All traditional methods completed in {elapsed:.1f}s ({elapsed/3600:.1f}h)")
        self.phase_times["run_traditional"] = elapsed
        return all_results

    def convert_to_rows(self, trad_results: List[dict], mdm_results: List[dict]) -> List[dict]:
        log("Converting results to unified row format...")
        rows = []

        for r in trad_results:
            method = r["method_id"]
            n = r["n_sample"]
            rid = r["repeat_id"]
            extra = r.get("extra") or {}
            rows.append({
                "method": method, "n": n, "repeat_id": rid,
                "beta_hat": r["beta_hat"], "eta_hat": r["eta_hat"], "gamma_hat": r["gamma_hat"],
                "beta_true": r.get("beta_true", BETA_NORM),
                "eta_true": r.get("eta_true", ETA_NORM),
                "gamma_true": r.get("gamma_true", GAMMA_NORM),
                "converged": bool(r["converged"]) if r["converged"] is not None else False,
                "failure_reason": extra.get("error", "") or extra.get("raw_status", ""),
                "time_s": r.get("time"),
                "sample_hash": r.get("sample_hash", ""),
            })

        for r in mdm_results:
            r["beta_true"] = BETA_NORM
            r["eta_true"] = ETA_NORM
            r["gamma_true"] = GAMMA_NORM
            rows.append(r)

        return rows

    def compute_metrics(self, rows: List[dict]):
        log("Computing metrics...")
        t0 = time.time()

        for row in rows:
            bh = row["beta_hat"]
            eh = row["eta_hat"]
            gh = row["gamma_hat"]
            bt = row.get("beta_true", BETA_NORM)
            et = row.get("eta_true", ETA_NORM)
            gt = row.get("gamma_true", GAMMA_NORM)
            if bh is not None and eh is not None and gh is not None and all(math.isfinite(v) for v in [bh, eh, gh]):
                e_b, e_e, e_g, L = compute_single_error(bh, eh, gh, bt, et, gt)
                row["e_beta"] = e_b
                row["e_eta"] = e_e
                row["e_gamma"] = e_g
                row["L_i"] = L
            else:
                row["e_beta"] = None
                row["e_eta"] = None
                row["e_gamma"] = None
                row["L_i"] = None

        # Pooled summary
        # Contract: J1 = sqrt(1/3000 * sum_i L_i) where all 3000 samples contribute.
        # Failures with zero estimates naturally contribute L_i = ((0-beta)/beta)^2+...
        # = 1+1+1 = 3 for our parameters. Failures with None estimates are counted
        # in n_failure, and their L_i is treated as missing (not in sum).
        df = pd.DataFrame(rows)
        methods_all = TRADITIONAL_METHODS + ["MDM-0.1", "MDM-MLP", "MDM-L6-oracle"]

        overall_rows = []
        for method in methods_all:
            df_m = df[df["method"] == method]
            n_total = len(df_m)
            if n_total == 0:
                continue

            has_L = df_m["L_i"].notna()
            df_with_L = df_m[has_L].copy()
            n_with_L = len(df_with_L)
            n_no_estimate = n_total - n_with_L

            has_finite = (
                df_m["beta_hat"].notna()
                & df_m["eta_hat"].notna()
                & df_m["gamma_hat"].notna()
                & df_m["beta_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                & df_m["eta_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                & df_m["gamma_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
            )
            converged_mask = df_m["converged"].astype(bool)
            valid_mask = has_finite & converged_mask & (df_m["beta_hat"] > 0) & (df_m["eta_hat"] > 0)
            n_valid = valid_mask.sum()
            n_failure = n_total - n_valid

            if n_with_L == 0:
                overall_rows.append({
                    "method": method, "pooled_J1": None,
                    "beta_RMSE": None, "eta_RMSE": None, "gamma_RMSE": None,
                    "n_failure": n_failure, "failure_rate": n_failure / n_total,
                })
                continue

            L_sum = df_with_L["L_i"].sum()
            pooled_J1 = math.sqrt(L_sum / n_total)

            beta_L = df_m["e_beta"].notna()
            eta_L = df_m["e_eta"].notna()
            gamma_L = df_m["e_gamma"].notna()
            beta_rmse = math.sqrt((df_m.loc[beta_L, "e_beta"] ** 2).sum() / n_total) if beta_L.any() else None
            eta_rmse = math.sqrt((df_m.loc[eta_L, "e_eta"] ** 2).sum() / n_total) if eta_L.any() else None
            gamma_rmse = math.sqrt((df_m.loc[gamma_L, "e_gamma"] ** 2).sum() / n_total) if gamma_L.any() else None

            overall_rows.append({
                "method": method, "pooled_J1": pooled_J1,
                "beta_RMSE": beta_rmse, "eta_RMSE": eta_rmse, "gamma_RMSE": gamma_rmse,
                "n_failure": n_failure, "failure_rate": n_failure / n_total,
                "n_no_estimate": n_no_estimate,
            })

        overall_df = pd.DataFrame(overall_rows)
        overall_df.to_csv(OVERALL_CSV, index=False, float_format="%.6f")
        log(f"  Overall summary saved to {OVERALL_CSV}")

        # Per-n summaries
        for n_val in N_VALUES:
            summary_rows = []
            for method in methods_all:
                df_mn = df[(df["method"] == method) & (df["n"] == n_val)]
                n_total = len(df_mn)
                valid_mask = (
                    df_mn["converged"].astype(bool)
                    & df_mn["beta_hat"].notna()
                    & df_mn["eta_hat"].notna()
                    & df_mn["gamma_hat"].notna()
                    & df_mn["beta_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                    & df_mn["eta_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                    & df_mn["gamma_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                    & (df_mn["beta_hat"] > 0)
                    & (df_mn["eta_hat"] > 0)
                )
                df_valid = df_mn[valid_mask].copy()
                n_success = len(df_valid)

                if n_success == 0:
                    for param in ["beta", "eta", "gamma"]:
                        summary_rows.append({
                            "method": method, "param": param,
                            "true_value": BETA_NORM if param == "beta" else ETA_NORM if param == "eta" else GAMMA_NORM,
                            "min": None, "max": None, "mean": None, "median": None,
                            "p2_5": None, "p97_5": None, "n_success_total": f"0/1000",
                        })
                    continue

                display_scale = DISPLAY_SCALE
                for param, true_val_display in [("beta", 2.0), ("eta", 1000.0), ("gamma", 1000.0)]:
                    scale = 1.0
                    if method in ("lse", "MDM-0.1", "MDM-MLP", "MDM-L6-oracle"):
                        scale = 1.0 if param == "beta" else display_scale
                    vals = df_valid[f"{param}_hat"].values * scale
                    vals = vals[np.isfinite(vals)]
                    n_s = len(vals)
                    summary_rows.append({
                        "method": method, "param": param,
                        "true_value": true_val_display,
                        "min": float(np.min(vals)) if n_s > 0 else None,
                        "max": float(np.max(vals)) if n_s > 0 else None,
                        "mean": float(np.mean(vals)) if n_s > 0 else None,
                        "median": float(np.median(vals)) if n_s > 0 else None,
                        "p2_5": float(np.percentile(vals, 2.5)) if n_s >= 40 else None,
                        "p97_5": float(np.percentile(vals, 97.5)) if n_s >= 40 else None,
                        "n_success_total": f"{n_s}/1000",
                    })

            summary_df = pd.DataFrame(summary_rows)
            fname_map = {7: SUMMARY_N7_CSV, 10: SUMMARY_N10_CSV, 20: SUMMARY_N20_CSV}
            summary_df.to_csv(fname_map[n_val], index=False, float_format="%.6f")
            log(f"  Summary n={n_val} saved to {fname_map[n_val]}")

        elapsed = time.time() - t0
        self.phase_times["compute_metrics"] = elapsed

        return overall_df

    def save_per_sample(self, rows: List[dict]):
        log("Saving per-sample results...")
        fieldnames = [
            "beta_true", "eta_true_display", "gamma_true_display",
            "n", "repeat_id", "method",
            "beta_hat_display", "eta_hat_display", "gamma_hat_display",
            "e_beta", "e_eta", "e_gamma", "L_i",
            "converged", "failure_reason", "time_s", "sample_hash",
        ]
        display_scale = DISPLAY_SCALE
        norm_scale_methods = {"lse", "MDM-0.1", "MDM-MLP", "MDM-L6-oracle"}
        with open(PER_SAMPLE_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                method = row["method"]
                is_norm = method in norm_scale_methods
                beta_scale = 1.0
                eta_scale = display_scale if is_norm else 1.0
                gamma_scale = display_scale if is_norm else 1.0
                out = {
                    "beta_true": 2.0,
                    "eta_true_display": 1000.0,
                    "gamma_true_display": 1000.0,
                    "n": row["n"],
                    "repeat_id": row["repeat_id"],
                    "method": method,
                    "converged": row.get("converged", False),
                    "failure_reason": row.get("failure_reason", ""),
                    "time_s": row.get("time_s"),
                    "sample_hash": row.get("sample_hash", ""),
                }
                bh = row.get("beta_hat")
                eh = row.get("eta_hat")
                gh = row.get("gamma_hat")
                if bh is not None and eh is not None and gh is not None:
                    out["beta_hat_display"] = bh * beta_scale
                    out["eta_hat_display"] = eh * eta_scale
                    out["gamma_hat_display"] = gh * gamma_scale
                    out["e_beta"] = row.get("e_beta")
                    out["e_eta"] = row.get("e_eta")
                    out["e_gamma"] = row.get("e_gamma")
                    out["L_i"] = row.get("L_i")
                w.writerow(out)
        log(f"  Saved {len(rows)} rows to {PER_SAMPLE_CSV}")

    def scale_equivariance_check(self):
        log("Running scale equivariance check...")
        check_rows = []
        methods_check = ["mle", "wmle", "lse", "lre"]
        for method_id in methods_check:
            for n in N_VALUES:
                for rid in SCALE_CHECK_REPEATS:
                    sample_norm = generate_sample(BETA_NORM, ETA_NORM, GAMMA_NORM, n, rid, seed=SEED_NAMESPACE)
                    sample_display = sample_norm * DISPLAY_SCALE

                    for sample, scale, label in [
                        (sample_norm, 1.0, "norm"),
                        (sample_display, DISPLAY_SCALE, "display"),
                    ]:
                        result = run_method(method_id, sample)
                        bh = result["beta_hat"]
                        eh = result["eta_hat"]
                        gh = result["gamma_hat"]
                        if bh is not None and eh is not None and gh is not None and all(math.isfinite(v) for v in [bh, eh, gh]):
                            e_b, e_e, e_g, L = compute_single_error(bh, eh, gh, BETA_NORM * scale, ETA_NORM * scale, GAMMA_NORM * scale)
                        else:
                            e_b = e_e = e_g = L = None
                        check_rows.append({
                            "method": method_id, "n": n, "repeat_id": rid,
                            "scale": label, "scale_factor": scale,
                            "beta_hat": bh, "eta_hat": eh, "gamma_hat": gh,
                            "e_beta": e_b, "e_eta": e_e, "e_gamma": e_g, "L_i": L,
                            "converged": result["converged"],
                        })

                df_check = pd.DataFrame(check_rows)
        df_check.to_csv(SCALE_CHECK_CSV, index=False, float_format="%.12f")
        log(f"  Scale check saved to {SCALE_CHECK_CSV}")

        for method_id in methods_check:
            df_m = df_check[df_check["method"] == method_id]
            valid = df_m[df_m["converged"].astype(bool) & df_m["beta_hat"].notna()].copy()
            if len(valid) < 2:
                continue
            pivoted = valid.pivot_table(
                index=["n", "repeat_id"], columns="scale",
                values=["beta_hat", "eta_hat", "gamma_hat"],
            )
            if "beta_hat" in pivoted.columns and ("norm" in pivoted["beta_hat"].columns and "display" in pivoted["beta_hat"].columns):
                beta_diff = (pivoted["beta_hat"]["norm"] - pivoted["beta_hat"]["display"]).abs()
                eta_ratio = (pivoted["eta_hat"]["display"] / pivoted["eta_hat"]["norm"]).replace([np.inf, -np.inf], np.nan)
                gamma_ratio = (pivoted["gamma_hat"]["display"] / pivoted["gamma_hat"]["norm"]).replace([np.inf, -np.inf], np.nan)

                paired = beta_diff.dropna()
                if len(paired) > 0:
                    log(f"  {method_id}: {len(paired)} paired valid results")
                    log(f"    max|beta_diff|={paired.max():.2e}, "
                        f"max|eta_ratio-{DISPLAY_SCALE:.0f}|={(eta_ratio.dropna() - DISPLAY_SCALE).abs().max():.2e}, "
                        f"max|gamma_ratio-{DISPLAY_SCALE:.0f}|={(gamma_ratio.dropna() - DISPLAY_SCALE).abs().max():.2e}")
                    beta_ok = paired.max() < SCALE_TOLERANCE
                    eta_ok = (eta_ratio.dropna() - DISPLAY_SCALE).abs().max() < SCALE_TOLERANCE * DISPLAY_SCALE
                    gamma_ok = (gamma_ratio.dropna() - DISPLAY_SCALE).abs().max() < SCALE_TOLERANCE * DISPLAY_SCALE
                    if not (beta_ok and eta_ok and gamma_ok):
                        log(f"  *** WARNING: {method_id} exceeds scale tolerance! ***")
                else:
                    log(f"  {method_id}: no paired valid results for scale check")
            else:
                log(f"  {method_id}: insufficient paired data for scale check")

    def verify(self, rows: List[dict]):
        log("Running verification checks...")
        df = pd.DataFrame(rows)

        for n_val in N_VALUES:
            for method in TRADITIONAL_METHODS + ["MDM-0.1", "MDM-MLP", "MDM-L6-oracle"]:
                df_mn = df[(df["method"] == method) & (df["n"] == n_val)]
                assert len(df_mn) == N_REPEATS, f"Expected {N_REPEATS} repeats for {method} n={n_val}, got {len(df_mn)}"
                unique_rids = df_mn["repeat_id"].nunique()
                assert unique_rids == N_REPEATS, f"Expected {N_REPEATS} unique repeat_ids for {method} n={n_val}, got {unique_rids}"
        log("  Repeat count check: PASS")

        df_mdm_01 = df[df["method"] == "MDM-0.1"]
        df_mlp = df[df["method"] == "MDM-MLP"]
        df_l6 = df[df["method"] == "MDM-L6-oracle"]
        for trad_method in TRADITIONAL_METHODS:
            df_trad = df[df["method"] == trad_method]
            for n_val in N_VALUES:
                hashes_01 = set(df_mdm_01[df_mdm_01["n"] == n_val]["sample_hash"].dropna())
                hashes_trad = set(df_trad[df_trad["n"] == n_val]["sample_hash"].dropna())
                if hashes_01 and hashes_trad:
                    if hashes_01 != hashes_trad:
                        log(f"  WARNING: sample hash mismatch between MDM-0.1 and {trad_method} for n={n_val}")
                        log(f"    MDM-0.1 unique: {len(hashes_01)}, {trad_method} unique: {len(hashes_trad)}")
                    else:
                        log(f"  Sample hash match: MDM-0.1 == {trad_method} for n={n_val}")
        log("  Sample hash consistency check: DONE")

        df_check = pd.read_csv(SCALE_CHECK_CSV)
        for method_id in ["mle", "wmle", "lse", "lre"]:
            df_m = df_check[df_check["method"] == method_id]
            valid = df_m[df_m["converged"].astype(bool) & df_m["beta_hat"].notna()]
            n_valid = len(valid)
            log(f"  Scale check for {method_id}: {n_valid}/{len(df_m)} valid")

        for n_val in N_VALUES:
            overall_df = pd.read_csv(OVERALL_CSV)
            n7_df = pd.read_csv(SUMMARY_N7_CSV)
            n10_df = pd.read_csv(SUMMARY_N10_CSV)
            n20_df = pd.read_csv(SUMMARY_N20_CSV)
            log(f"  Summary files for n={n_val}: rows={len({7: n7_df, 10: n10_df, 20: n20_df}[n_val])}")
        log("  All verification checks complete.")

    def spot_check(self, rows: List[dict]):
        log("Running spot checks...")
        df = pd.DataFrame(rows)
        checked = 0
        methods = TRADITIONAL_METHODS + ["MDM-0.1", "MDM-MLP", "MDM-L6-oracle"]
        for n_val in N_VALUES:
            for rid in [0, 42, 999]:
                if checked >= 10:
                    break
                df_sample = df[(df["n"] == n_val) & (df["repeat_id"] == rid)]
                for method in methods:
                    dm = df_sample[df_sample["method"] == method]
                    if len(dm) == 0:
                        continue
                    row = dm.iloc[0]
                    bh = row["beta_hat"]
                    eh = row["eta_hat"]
                    gh = row["gamma_hat"]
                    bt = row.get("beta_true", BETA_NORM)
                    et = row.get("eta_true", ETA_NORM)
                    gt = row.get("gamma_true", GAMMA_NORM)
                    if bh is not None and eh is not None and gh is not None:
                        L = row.get("L_i")
                        if L is not None and pd.notna(L):
                            e_b, e_e, e_g, L_recalc = compute_single_error(bh, eh, gh, bt, et, gt)
                            assert abs(L - L_recalc) < 1e-10, f"L_i mismatch for {method} n={n_val} rid={rid}: {L} vs {L_recalc}"
                    checked += 1
        log(f"  Spot checked {checked} results: PASS")

    def write_manifest(self, rows: List[dict]):
        log("Writing manifest...")
        df = pd.DataFrame(rows)
        manifest = {
            "run_id": "method_comparison_v1",
            "run_start": self.start_ts,
            "run_end": iso_now(),
            "seed_namespace": SEED_NAMESPACE,
            "parameter_grid": {
                "beta": [BETA_NORM], "eta": [ETA_NORM],
                "gamma_over_eta": [1.0], "n": N_VALUES,
            },
            "repeats": N_REPEATS,
            "display_scale": DISPLAY_SCALE,
            "methods": {
                "traditional": TRADITIONAL_METHODS,
                "cached_mdm": ["MDM-0.1", "MDM-MLP", "MDM-L6-oracle"],
            },
            "mlp_source": {
                "model": "Vector-MLP-L6",
                "seed": 42,
                "holdout": "5-fold combo",
                "file": MLP_CSV,
            },
            "file_hashes": self.file_hashes,
            "phase_times": self.phase_times,
            "per_method_counts": {
                method: int(len(df[df["method"] == method]))
                for method in TRADITIONAL_METHODS + ["MDM-0.1", "MDM-MLP", "MDM-L6-oracle"]
            },
            "python_platform": sys.path[1],
        }
        with open(MANIFEST_JSON, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        log(f"  Manifest saved to {MANIFEST_JSON}")

    def run(self):
        log("=" * 60)
        log("Method Comparison Study - Starting execution")
        log(f"Start time: {self.start_ts}")
        log(f"Workers: {N_WORKERS}")
        log("=" * 60)

        self.record_input_hashes()

        df_mdm = self.extract_mdm_from_cache()
        df_mlp = self.get_mlp_deltas()
        df_l6 = self.get_l6_oracle_deltas()

        mdm_results = self.build_mdm_results(df_mdm, df_mlp, df_l6)

        trad_results = self.run_traditional_methods()

        all_rows = self.convert_to_rows(trad_results, mdm_results)

        self.save_per_sample(all_rows)

        self.compute_metrics(all_rows)

        self.scale_equivariance_check()

        self.verify(all_rows)
        self.spot_check(all_rows)
        self.write_manifest(all_rows)

        total_elapsed = sum(self.phase_times.values())
        log("=" * 60)
        log(f"ALL PHASES COMPLETE. Total compute time: {total_elapsed:.1f}s ({total_elapsed/3600:.1f}h)")
        for phase, t in self.phase_times.items():
            log(f"  {phase}: {t:.1f}s")
        log("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel workers")
    parser.add_argument("--scale-check-only", action="store_true")
    args = parser.parse_args()
    N_WORKERS = min(args.workers, mp.cpu_count())

    runner = ComparisonRunner()

    if args.scale_check_only:
        runner.scale_equivariance_check()
    else:
        runner.run()
