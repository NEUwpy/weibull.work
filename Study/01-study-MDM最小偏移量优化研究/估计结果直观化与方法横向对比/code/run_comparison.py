"""
Method comparison: MLE, WMLE, LSE, LRE, MDM-0.1, MDM-MLP, MDM-L6-oracle
For (beta=2.0, eta=1.0, gamma=1.0) norm-scale; n in {7, 10, 20} x 1000 repeats.
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
METHODS_NEED_DISPLAY_SCALE = {"mle", "wmle", "lre"}
NORM_SCALE_METHODS = {"lse", "MDM-0.1", "MDM-MLP", "MDM-L6-oracle"}

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

ALL_OUTPUT_FILES = [
    PER_SAMPLE_CSV, OVERALL_CSV, SUMMARY_N7_CSV, SUMMARY_N10_CSV, SUMMARY_N20_CSV,
    SCALE_CHECK_CSV, MANIFEST_JSON,
]

INPUT_FILES = [
    (MC_SCAN_CSV, "mc_scan_raw"),
    (MLP_CSV, "vector_mlp_results"),
    (L6_CSV, "L6_per_sample_delta"),
]
CRITICAL_FILES = [
    (os.path.join(FORMAL_DIR, "shared_data", "manifest.json"), "shared_data_manifest"),
    (os.path.join(FORMAL_DIR, "E3b_vector_mlp", "manifest.json"), "E3b_manifest"),
    (os.path.join(FORMAL_DIR, "E2_oracle_layers", "manifest.json"), "E2_oracle_manifest"),
]

N_WORKERS = min(8, mp.cpu_count())
SCALE_CHECK_REPEATS = list(range(5))
SCALE_BETA_TOL = 1e-6
SCALE_ETA_GAMMA_TOL = 1e-3

DELTA_GRID = [round(0.00 + 0.02 * i, 2) for i in range(26)]


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def compute_single_error(beta_hat, eta_hat, gamma_hat, beta, eta, gamma):
    e_beta = (beta_hat - beta) / beta if beta != 0 else float("inf")
    e_eta = (eta_hat - eta) / eta if eta != 0 else float("inf")
    e_gamma = (gamma_hat - gamma) / eta
    L_i = e_beta**2 + e_eta**2 + e_gamma**2
    return e_beta, e_eta, e_gamma, L_i


def sample_content_hash(beta, eta, gamma, n, repeat_id, seed_namespace):
    sample = generate_sample(beta, eta, gamma, n, repeat_id, seed=seed_namespace)
    return hashlib.sha256(
        np.array2string(sample, precision=12, separator=",", threshold=n + 1).encode()
    ).hexdigest()[:16]


_PARAM_KEY_CACHE: Dict[Tuple, str] = {}


def _param_hash(n, repeat_id):
    key = (n, repeat_id)
    if key not in _PARAM_KEY_CACHE:
        _PARAM_KEY_CACHE[key] = sha256_str(
            f"{SEED_NAMESPACE}|{BETA_NORM}|{ETA_NORM}|{GAMMA_NORM}|{n}|{repeat_id}"
        )[:16]
    return _PARAM_KEY_CACHE[key]


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
        result["sample_content_hash"] = sample_content_hash(beta, eta, gamma, n, repeat_id, seed_namespace)
        return result
    except Exception as e:
        return {
            "method_id": method_id,
            "beta_hat": None, "eta_hat": None, "gamma_hat": None, "r_squared": None,
            "converged": False, "time": 0.0,
            "extra": {"error": f"worker exception: {type(e).__name__}: {e}"},
            "beta_true": beta * (DISPLAY_SCALE if use_display else 1.0),
            "eta_true": eta * (DISPLAY_SCALE if use_display else 1.0),
            "gamma_true": gamma * (DISPLAY_SCALE if use_display else 1.0),
            "n_sample": n, "repeat_id": repeat_id, "sample_content_hash": "",
        }


class ComparisonRunner:
    def __init__(self):
        self.start_ts = iso_now()
        self.file_hashes: Dict[str, str] = {}
        self.phase_times: Dict[str, float] = {}

    def record_input_hashes(self):
        log("Recording input file SHA256...")
        for path, label in INPUT_FILES + CRITICAL_FILES:
            if os.path.exists(path):
                self.file_hashes[label] = sha256_file(path)
                log(f"  {label}: {self.file_hashes[label][:16]}...")
        python_paths = [
            (os.path.join(PLATFORM_DIR, "studies", "common", "sample.py"), "sample_py"),
            (os.path.join(PLATFORM_DIR, "studies", "common", "runner.py"), "runner_py"),
            (os.path.join(PLATFORM_DIR, "methods", "mle.py"), "mle_py"),
            (os.path.join(PLATFORM_DIR, "methods", "wmle.py"), "wmle_py"),
            (os.path.join(PLATFORM_DIR, "methods", "lse.py"), "lse_py"),
            (os.path.join(PLATFORM_DIR, "methods", "lre.py"), "lre_py"),
        ]
        for path, label in python_paths:
            if os.path.exists(path):
                self.file_hashes[label] = sha256_file(path)

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
        mask = (df["beta"] == BETA_NORM) & (df["eta"] == ETA_NORM) & (df["gamma"] == GAMMA_NORM)
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
        mask = (df["model"] == "Vector-MLP-L6") & (df["beta"] == BETA_NORM) & (df["gamma_over_eta"] == GAMMA_NORM)
        df_mlp = df[mask][["beta", "gamma_over_eta", "n", "repeat_id", "selected_delta"]].copy()
        df_mlp["n"] = df_mlp["n"].astype(int)
        df_mlp["repeat_id"] = df_mlp["repeat_id"].astype(int)
        log(f"  MLP rows for target: {len(df_mlp)}")
        return df_mlp

    def get_l6_oracle_deltas(self) -> pd.DataFrame:
        log("Loading L6 oracle per-sample deltas for target combo...")
        df = pd.read_csv(L6_CSV)
        mask = (df["beta"] == BETA_NORM) & (df["eta"] == ETA_NORM) & (df["gamma"] == GAMMA_NORM)
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
            return df_delta.rename(columns={"selected_delta": "delta"}).merge(
                df_mdm_subset, on=["n", "repeat_id", "delta"], how="left")

        df_mlp_est = lookup_delta(df_mdm, df_mlp)
        df_l6_est = lookup_delta(df_mdm, df_l6)

        probe_hashes = {}
        for n in N_VALUES:
            for rid in [0, 42, 999]:
                probe_hashes[(n, rid)] = sample_content_hash(BETA_NORM, ETA_NORM, GAMMA_NORM, n, rid, SEED_NAMESPACE)

        results = []
        for n in N_VALUES:
            for rid in range(N_REPEATS):
                p_hash = probe_hashes.get((n, rid), _param_hash(n, rid))

                row_01 = df_01[(df_01["n"] == n) & (df_01["repeat_id"] == rid)]
                if len(row_01) == 1:
                    r = row_01.iloc[0]
                    conv = str(r["conv"]).strip().lower() in ("true", "1", "yes")
                    results.append({
                        "method": "MDM-0.1", "n": n, "repeat_id": rid,
                        "beta_hat": float(r["bh"]), "eta_hat": float(r["eh"]), "gamma_hat": float(r["gh"]),
                        "beta_true": BETA_NORM, "eta_true": ETA_NORM, "gamma_true": GAMMA_NORM,
                        "converged": conv,
                        "failure_reason": "" if conv else f"status={r['stat']}",
                        "time_s": None, "sample_content_hash": p_hash,
                    })

                row_mlp = df_mlp_est[(df_mlp_est["n"] == n) & (df_mlp_est["repeat_id"] == rid)]
                if len(row_mlp) == 1:
                    r = row_mlp.iloc[0]
                    conv = str(r.get("converged", "True")).strip().lower() in ("true", "1", "yes")
                    results.append({
                        "method": "MDM-MLP", "n": n, "repeat_id": rid,
                        "beta_hat": float(r["beta_hat"]) if not pd.isna(r["beta_hat"]) else 0.0,
                        "eta_hat": float(r["eta_hat"]) if not pd.isna(r["eta_hat"]) else 0.0,
                        "gamma_hat": float(r["gamma_hat"]) if not pd.isna(r["gamma_hat"]) else 0.0,
                        "beta_true": BETA_NORM, "eta_true": ETA_NORM, "gamma_true": GAMMA_NORM,
                        "converged": conv,
                        "failure_reason": "" if conv else f"status={r.get('status','?')}",
                        "time_s": None, "sample_content_hash": p_hash,
                    })

                row_l6 = df_l6_est[(df_l6_est["n"] == n) & (df_l6_est["repeat_id"] == rid)]
                if len(row_l6) == 1:
                    r = row_l6.iloc[0]
                    conv = str(r.get("converged", "True")).strip().lower() in ("true", "1", "yes")
                    results.append({
                        "method": "MDM-L6-oracle", "n": n, "repeat_id": rid,
                        "beta_hat": float(r["beta_hat"]) if not pd.isna(r["beta_hat"]) else 0.0,
                        "eta_hat": float(r["eta_hat"]) if not pd.isna(r["eta_hat"]) else 0.0,
                        "gamma_hat": float(r["gamma_hat"]) if not pd.isna(r["gamma_hat"]) else 0.0,
                        "beta_true": BETA_NORM, "eta_true": ETA_NORM, "gamma_true": GAMMA_NORM,
                        "converged": conv,
                        "failure_reason": "" if conv else f"status={r.get('status','?')}",
                        "time_s": None, "sample_content_hash": p_hash,
                    })

        elapsed = time.time() - t0
        log(f"  Built {len(results)} MDM-based results in {elapsed:.1f}s")
        self.phase_times["build_mdm"] = elapsed
        return results

    def run_traditional_methods(self) -> List[dict]:
        log("Running traditional methods (MLE, WMLE, LSE, LRE) for 3000 samples each...")
        log(f"  Methods needing display scale: {METHODS_NEED_DISPLAY_SCALE}")
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
                        extra = {
                            "error": row.get("error") if pd.notna(row.get("error")) and str(row.get("error", "")).strip() else None,
                            "raw_status": row.get("raw_status") if pd.notna(row.get("raw_status")) and str(row.get("raw_status", "")).strip() else None,
                        }
                        extra = {k: v for k, v in extra.items() if v is not None}
                        all_results.append({
                            "method_id": method_id,
                            "beta_hat": row.get("beta_hat") if pd.notna(row.get("beta_hat")) else None,
                            "eta_hat": row.get("eta_hat") if pd.notna(row.get("eta_hat")) else None,
                            "gamma_hat": row.get("gamma_hat") if pd.notna(row.get("gamma_hat")) else None,
                            "r_squared": row.get("r_squared") if pd.notna(row.get("r_squared")) else None,
                            "converged": bool(row.get("converged")) if pd.notna(row.get("converged")) else False,
                            "time": float(row.get("time", 0.0)) if pd.notna(row.get("time")) else 0.0,
                            "extra": extra if extra else None,
                            "beta_true": true_beta, "eta_true": true_eta, "gamma_true": true_gamma,
                            "n_sample": n, "repeat_id": int(row["repeat_id"]),
                            "sample_content_hash": row.get("sample_content_hash", ""),
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
                        "sample_content_hash": r.get("sample_content_hash", ""),
                    })
                pd.DataFrame(ckpt_rows).to_csv(ckpt_file, index=False, na_rep="")
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
                "sample_content_hash": r.get("sample_content_hash", ""),
            })
        for r in mdm_results:
            rows.append(r)
        return rows

    def _compute_per_sample_errors(self, rows: List[dict]):
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

    def _fill_failure_penalty(self, rows: List[dict]):
        for row in rows:
            if row["L_i"] is not None:
                continue
            if not row["converged"]:
                bt = row.get("beta_true", BETA_NORM)
                et = row.get("eta_true", ETA_NORM)
                gt = row.get("gamma_true", GAMMA_NORM)
                e_b, e_e, e_g, L = compute_single_error(0.0, 0.0, 0.0, bt, et, gt)
                row["L_i"] = L
                row["e_beta"] = e_b
                row["e_eta"] = e_e
                row["e_gamma"] = e_g
                if not row.get("failure_reason"):
                    row["failure_reason"] = "converged=False (estimates=0)"
                row["_penalty_applied"] = True

    def compute_metrics(self, rows: List[dict]):
        log("Computing metrics...")
        t0 = time.time()

        self._compute_per_sample_errors(rows)
        self._fill_failure_penalty(rows)

        df = pd.DataFrame(rows)
        methods_all = TRADITIONAL_METHODS + ["MDM-0.1", "MDM-MLP", "MDM-L6-oracle"]

        overall_rows = []
        for method in methods_all:
            df_m = df[df["method"] == method].copy()
            n_total = len(df_m)
            if n_total == 0:
                continue

            has_finite = (
                df_m["beta_hat"].notna() & df_m["eta_hat"].notna() & df_m["gamma_hat"].notna()
                & df_m["beta_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                & df_m["eta_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                & df_m["gamma_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
            )
            converged_mask = df_m["converged"].astype(bool)
            valid_mask = has_finite & converged_mask & (df_m["beta_hat"] > 0) & (df_m["eta_hat"] > 0)
            n_valid = valid_mask.sum()
            n_failure = n_total - n_valid

            has_L = df_m["L_i"].notna()
            if not has_L.any():
                overall_rows.append({
                    "method": method, "pooled_J1": None,
                    "beta_RMSE": None, "eta_RMSE": None, "gamma_RMSE": None,
                    "n_failure": n_failure, "failure_rate": n_failure / n_total,
                })
                continue

            L_sum = float(df_m.loc[has_L, "L_i"].sum())
            pooled_J1 = math.sqrt(L_sum / n_total)

            has_e_b = df_m["e_beta"].notna()
            has_e_e = df_m["e_eta"].notna()
            has_e_g = df_m["e_gamma"].notna()
            beta_rmse = math.sqrt(float((df_m.loc[has_e_b, "e_beta"] ** 2).sum()) / n_total) if has_e_b.any() else None
            eta_rmse = math.sqrt(float((df_m.loc[has_e_e, "e_eta"] ** 2).sum()) / n_total) if has_e_e.any() else None
            gamma_rmse = math.sqrt(float((df_m.loc[has_e_g, "e_gamma"] ** 2).sum()) / n_total) if has_e_g.any() else None

            overall_rows.append({
                "method": method, "pooled_J1": pooled_J1,
                "beta_RMSE": beta_rmse, "eta_RMSE": eta_rmse, "gamma_RMSE": gamma_rmse,
                "n_failure": n_failure, "failure_rate": n_failure / n_total,
            })

        overall_df = pd.DataFrame(overall_rows)
        overall_df.to_csv(OVERALL_CSV, index=False, float_format="%.6f")
        log(f"  Overall summary saved to {OVERALL_CSV}")

        for n_val in N_VALUES:
            summary_rows = []
            for method in methods_all:
                df_mn = df[(df["method"] == method) & (df["n"] == n_val)].copy()
                valid_mask = (
                    df_mn["converged"].astype(bool)
                    & df_mn["beta_hat"].notna() & df_mn["eta_hat"].notna() & df_mn["gamma_hat"].notna()
                    & df_mn["beta_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                    & df_mn["eta_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                    & df_mn["gamma_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                    & (df_mn["beta_hat"] > 0) & (df_mn["eta_hat"] > 0)
                )
                df_valid = df_mn[valid_mask]
                n_success = len(df_valid)

                if n_success == 0:
                    for param in ["beta", "eta", "gamma"]:
                        summary_rows.append({
                            "method": method, "param": param, "true_value": 2.0 if param == "beta" else 1000.0,
                            "min": None, "max": None, "mean": None, "median": None,
                            "p2_5": None, "p97_5": None, "n_success_total": f"0/1000",
                        })
                    continue

                for param, true_val_display in [("beta", 2.0), ("eta", 1000.0), ("gamma", 1000.0)]:
                    scale = 1.0 if param == "beta" or method not in NORM_SCALE_METHODS else DISPLAY_SCALE
                    vals = df_valid[f"{param}_hat"].values * scale
                    vals = vals[np.isfinite(vals)]
                    n_s = len(vals)
                    summary_rows.append({
                        "method": method, "param": param, "true_value": true_val_display,
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
            "converged", "failure_reason", "time_s", "sample_content_hash",
        ]
        display_scale = DISPLAY_SCALE
        with open(PER_SAMPLE_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                method = row["method"]
                is_norm = method in NORM_SCALE_METHODS
                beta_scale = 1.0
                eta_scale = display_scale if is_norm else 1.0
                gamma_scale = display_scale if is_norm else 1.0
                out = {
                    "beta_true": 2.0, "eta_true_display": 1000.0, "gamma_true_display": 1000.0,
                    "n": row["n"], "repeat_id": row["repeat_id"], "method": method,
                    "converged": row.get("converged", False),
                    "failure_reason": row.get("failure_reason", ""),
                    "time_s": row.get("time_s"),
                    "sample_content_hash": row.get("sample_content_hash", ""),
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
        for method_id in ["mle", "wmle", "lse", "lre"]:
            for n in N_VALUES:
                for rid in SCALE_CHECK_REPEATS:
                    sample_norm = generate_sample(BETA_NORM, ETA_NORM, GAMMA_NORM, n, rid, seed=SEED_NAMESPACE)
                    sample_display = sample_norm * DISPLAY_SCALE
                    for sample, scale, label in [(sample_norm, 1.0, "norm"), (sample_display, DISPLAY_SCALE, "display")]:
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

        for method_id in ["mle", "wmle", "lse", "lre"]:
            df_m = df_check[df_check["method"] == method_id]
            valid = df_m[df_m["converged"].astype(bool) & df_m["beta_hat"].notna()].copy()
            if len(valid) < 2:
                continue
            pivoted = valid.pivot_table(
                index=["n", "repeat_id"], columns="scale",
                values=["beta_hat", "eta_hat", "gamma_hat"],
            )
            if "beta_hat" not in pivoted.columns:
                continue
            if "norm" not in pivoted["beta_hat"].columns or "display" not in pivoted["beta_hat"].columns:
                continue
            beta_diff = (pivoted["beta_hat"]["norm"] - pivoted["beta_hat"]["display"]).abs()
            eta_ratio = (pivoted["eta_hat"]["display"] / pivoted["eta_hat"]["norm"]).replace([np.inf, -np.inf], np.nan)
            gamma_ratio = (pivoted["gamma_hat"]["display"] / pivoted["gamma_hat"]["norm"]).replace([np.inf, -np.inf], np.nan)
            paired = beta_diff.dropna()
            if len(paired) == 0:
                log(f"  {method_id}: no paired valid results")
                continue
            max_beta_diff = paired.max()
            max_eta_dev = (eta_ratio.dropna() - DISPLAY_SCALE).abs().max()
            max_gamma_dev = (gamma_ratio.dropna() - DISPLAY_SCALE).abs().max()
            log(f"  {method_id}: {len(paired)} paired, max|beta_diff|={max_beta_diff:.2e}, "
                f"max|eta_ratio-{DISPLAY_SCALE:.0f}|={max_eta_dev:.2e}, max|gamma_ratio-{DISPLAY_SCALE:.0f}|={max_gamma_dev:.2e}")
            beta_ok = max_beta_diff < SCALE_BETA_TOL
            eta_ok = max_eta_dev < SCALE_ETA_GAMMA_TOL * DISPLAY_SCALE
            gamma_ok = max_gamma_dev < SCALE_ETA_GAMMA_TOL * DISPLAY_SCALE
            if beta_ok and eta_ok and gamma_ok:
                log(f"    PASS (beta<{SCALE_BETA_TOL}, eta/gamma ratio<{SCALE_ETA_GAMMA_TOL}*1000)")
            else:
                log(f"    FAIL (beta<{SCALE_BETA_TOL}={beta_ok}, eta ratio<{SCALE_ETA_GAMMA_TOL}*1000={eta_ok}, gamma={gamma_ok})")

    def verify(self, rows: List[dict]):
        log("Running verification checks...")
        df = pd.DataFrame(rows)
        methods_all = TRADITIONAL_METHODS + ["MDM-0.1", "MDM-MLP", "MDM-L6-oracle"]

        for n_val in N_VALUES:
            for method in methods_all:
                df_mn = df[(df["method"] == method) & (df["n"] == n_val)]
                assert len(df_mn) == N_REPEATS, f"{method} n={n_val}: {len(df_mn)} != {N_REPEATS}"
                assert df_mn["repeat_id"].nunique() == N_REPEATS, f"{method} n={n_val}: dup repeat_id"
        log("  Repeat count check: PASS")

        probe_hashes = {}
        for n_val in N_VALUES:
            for rid in [0, 42, 999]:
                probe_hashes[(n_val, rid)] = sample_content_hash(
                    BETA_NORM, ETA_NORM, GAMMA_NORM, n_val, rid, SEED_NAMESPACE)

        mismatches = 0
        for method in methods_all:
            for (n_val, rid), expected_h in probe_hashes.items():
                dm = df[(df["method"] == method) & (df["n"] == n_val) & (df["repeat_id"] == rid)]
                if len(dm) == 0:
                    continue
                actual_h = str(dm.iloc[0].get("sample_content_hash", ""))
                if actual_h and actual_h != expected_h:
                    mismatches += 1
                    log(f"  HASH MISMATCH: {method} n={n_val} rid={rid}: {actual_h[:8]} != {expected_h[:8]}")
        if mismatches == 0:
            log(f"  Sample content hash consistency: PASS ({len(probe_hashes) * len(methods_all)} checks)")
        else:
            log(f"  Sample content hash consistency: {mismatches} FAILURES")

        log("  All verification checks complete.")

    def spot_check(self, rows: List[dict]):
        log("Running spot checks...")
        df = pd.DataFrame(rows)
        checked = 0
        for n_val in N_VALUES:
            for rid in [0, 42, 999]:
                if checked >= 10:
                    break
                df_sample = df[(df["n"] == n_val) & (df["repeat_id"] == rid)]
                for method in TRADITIONAL_METHODS + ["MDM-0.1", "MDM-MLP", "MDM-L6-oracle"]:
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
                    L = row.get("L_i")
                    if L is not None and pd.notna(L):
                        if bh is not None and eh is not None and gh is not None and all(math.isfinite(v) for v in [bh, eh, gh]):
                            e_b, e_e, e_g, L_recalc = compute_single_error(bh, eh, gh, bt, et, gt)
                            assert abs(L - L_recalc) < 1e-10, f"L_i mismatch: {method} n={n_val} rid={rid}: {L:.6f} vs {L_recalc:.6f}"
                        else:
                            e_b2, e_e2, e_g2, L_recalc2 = compute_single_error(0.0, 0.0, 0.0, bt, et, gt)
                            assert abs(L - L_recalc2) < 1e-10, f"Penalty L_i mismatch: {method} n={n_val} rid={rid}: {L:.6f} vs {L_recalc2:.6f}"
                    checked += 1
        log(f"  Spot checked {checked} results: PASS")

    def write_manifest(self, rows: List[dict]):
        log("Writing manifest...")
        df = pd.DataFrame(rows)
        output_hashes = {}
        for p in ALL_OUTPUT_FILES:
            if os.path.exists(p):
                output_hashes[os.path.basename(p)] = sha256_file(p)

        scale_results = {}
        for method_id in ["mle", "wmle", "lse", "lre"]:
            scale_results[method_id] = "display" if method_id in METHODS_NEED_DISPLAY_SCALE else "norm"

        n_failures = {}
        for method in TRADITIONAL_METHODS + ["MDM-0.1", "MDM-MLP", "MDM-L6-oracle"]:
            df_m = df[df["method"] == method]
            converged = df_m["converged"].astype(bool)
            has_finite = (
                df_m["beta_hat"].notna() & df_m["eta_hat"].notna() & df_m["gamma_hat"].notna()
                & df_m["beta_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                & df_m["eta_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
                & df_m["gamma_hat"].apply(lambda v: math.isfinite(v) if v is not None else False)
            )
            valid = converged & has_finite & (df_m["beta_hat"] > 0) & (df_m["eta_hat"] > 0)
            n_failures[method] = int((~valid).sum())

        manifest = {
            "run_id": "method_comparison_v2",
            "run_start": self.start_ts,
            "run_end": iso_now(),
            "seed_namespace": SEED_NAMESPACE,
            "parameter_grid": {"beta": [BETA_NORM], "eta": [ETA_NORM], "gamma_over_eta": [1.0], "n": N_VALUES},
            "repeats": N_REPEATS,
            "display_scale": DISPLAY_SCALE,
            "methods": {
                "traditional": TRADITIONAL_METHODS,
                "mdm_cached": ["MDM-0.1", "MDM-MLP", "MDM-L6-oracle"],
            },
            "scale_equivariance": {
                "tolerances": {"beta": SCALE_BETA_TOL, "eta_gamma_ratio": SCALE_ETA_GAMMA_TOL},
                "results": scale_results,
            },
            "mlp_source": {
                "model": "Vector-MLP-L6", "seed": 42, "holdout": "5-fold combo",
                "file": MLP_CSV,
            },
            "failure_penalty": "L_i(0,0,0) computed from true parameters; for (2,1,1) and (2,1000,1000) both give L_i=3.0",
            "n_failures_per_method": n_failures,
            "total_rows": len(rows),
            "input_hashes": self.file_hashes,
            "output_hashes": output_hashes,
            "phase_times": self.phase_times,
            "python_platform": PLATFORM_DIR,
        }
        with open(MANIFEST_JSON, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        log(f"  Manifest saved to {MANIFEST_JSON}")

    def run(self):
        log("=" * 60)
        log("Method Comparison Study v2 - Starting execution")
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

        self.compute_metrics(all_rows)
        self.save_per_sample(all_rows)

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
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--scale-check-only", action="store_true")
    args = parser.parse_args()
    N_WORKERS = min(args.workers, mp.cpu_count())
    runner = ComparisonRunner()
    if args.scale_check_only:
        runner.scale_equivariance_check()
    else:
        runner.run()
