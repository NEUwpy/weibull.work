"""P2 evaluation: reconstruct frozen Vector-MLP models, evaluate on P2 data.

No training. Models from E3b checkpoints. P2 data never enters scaler fit.
Computes Vector-MLP predictions + Default/L1 baselines on same P2 samples.
"""

import sys, os, json, csv, hashlib, time, math, warnings, gc, io, pickle
from pathlib import Path
from datetime import datetime, timezone
from itertools import product
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"D:\weibull\python")

from p2_config import (
    build_p2_combos, P2_NI_COMBOS, P2_PI_COMBOS, P2_TOTAL_COMBOS,
    DELTA_GRID, REPEATS, SEED_NAMESPACE, ETA, OUTPUT_DIR_NAME,
    DEFAULT_DELTA, L1_DELTA, VECTOR_MLP_FOLDS, VECTOR_MLP_SEEDS,
)
from config import STUDY_ROOT, BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID
from studies.common.sample import generate_sample

# ── Paths ──
STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT_DIR = os.path.dirname(STUDY_CODE_DIR)
ARTIFACTS_DIR = os.path.join(STUDY_ROOT_DIR, "artifacts", "formal")
P2_DIR = os.path.join(ARTIFACTS_DIR, OUTPUT_DIR_NAME)
CHUNKS_DIR = os.path.join(P2_DIR, "chunks")
E3B_DIR = os.path.join(ARTIFACTS_DIR, "E3b_vector_mlp")
E4_DIR = os.path.join(ARTIFACTS_DIR, "E4_robustness")
P2_OUT_DIR = P2_DIR  # Same dir for outputs

# ── Feature extraction (same 13 features as E3b) ──
from scipy import stats as sp_stats


def extract_features(sample):
    """Extract 13 deployment-observable statistics from a sample (same as E3b)."""
    x = np.sort(sample)
    n = len(x)
    feat = [
        np.min(x), np.max(x), np.ptp(x),
        np.percentile(x, 25), np.median(x), np.percentile(x, 75),
        np.ptp(x) / 2.0 if np.ptp(x) < 1e-12 else (np.percentile(x, 75) - np.percentile(x, 25)),
        np.mean(x), np.std(x, ddof=0),
        float(n),
        np.std(x, ddof=0) / (abs(np.mean(x)) + 1e-12),
        sp_stats.skew(x, bias=False) if n >= 3 else 0.0,
        sp_stats.kurtosis(x, fisher=True, bias=False) if n >= 4 else 0.0,
    ]
    return np.array(feat, dtype=np.float64)


def _sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_p2_data():
    """Load all P2 chunk data into a single DataFrame."""
    dfs = []
    for track, beta, ge, n in build_p2_combos():
        fp = os.path.join(CHUNKS_DIR, f"P2-{track.split('-')[1]}_{beta:.2f}_{ge:.2f}_{n}.csv")
        fp2 = os.path.join(CHUNKS_DIR, f"{track}_{beta:.2f}_{ge:.2f}_{n}.csv")
        for path in [fp, fp2]:
            if os.path.isfile(path):
                df = pd.read_csv(path)
                df["track"] = track
                dfs.append(df)
                break
    return pd.concat(dfs, ignore_index=True)


def _compute_loss_row(row):
    """J1 component for one row: sqrt(mean of squared relative errors)."""
    bh, eh, gh = row["beta_hat"], row["eta_hat"], row["gamma_hat"]
    beta, eta_val, gamma = row["beta"], row["eta"], row["gamma"]
    # Legality: finite, positive, converged
    conv = row.get("converged", True)
    if isinstance(conv, str):
        conv = conv.lower() in ("true", "1", "yes")
    status = row.get("status", "ok")
    if isinstance(status, str) and status.lower() in ("fail", "error"):
        return np.nan, False
    if (not all(np.isfinite([bh, eh, gh])) or bh <= 0 or eh <= 0 or not conv):
        return np.nan, False
    e_b = (bh - beta) / beta
    e_e = (eh - eta_val) / eta_val
    e_g = (gh - gamma) / eta_val
    return math.sqrt((e_b**2 + e_e**2 + e_g**2) / 3.0), True


def _find_optimal_delta(mdm_data, combo_key):
    """Find delta that minimizes J1 from MDM scan data (Default=0.1, L1=0.08)."""
    b, ge, n = combo_key
    sub = mdm_data[(mdm_data["beta"] == b) & (mdm_data["gamma_over_eta"] == ge) & (mdm_data["n"] == n)]
    if len(sub) == 0:
        return 0.1, 0.08, {}

    # Default: delta=0.1
    d10 = sub[sub["delta"] == 0.1]
    l10_vals = []
    for _, row in d10.iterrows():
        loss, ok = _compute_loss_row(row)
        if ok:
            l10_vals.append(loss)
    j1_default = float(np.sqrt(np.mean(np.square(l10_vals)))) if l10_vals else 10.0

    # L1: delta=0.08
    d08 = sub[sub["delta"] == 0.08]
    l08_vals = []
    for _, row in d08.iterrows():
        loss, ok = _compute_loss_row(row)
        if ok:
            l08_vals.append(loss)
    j1_l1 = float(np.sqrt(np.mean(np.square(l08_vals)))) if l08_vals else 10.0

    return j1_default, j1_l1, {}


def evaluate_p2():
    """Main P2 evaluation: Vector-MLP + Default/L1 on all P2 combos."""
    print("P2 Evaluation: loading data...")
    p2_data = _load_p2_data()
    print(f"  Loaded {len(p2_data)} rows from P2 chunks")

    # Get unique combo keys from data
    combo_keys = p2_data.groupby(["track", "beta", "gamma_over_eta", "n"]).size().reset_index()
    print(f"  {len(combo_keys)} unique combos")

    # For each combo, compute Default/L1 and Vector-MLP aggregated results
    results = []
    for _, ck in combo_keys.iterrows():
        track, beta, ge, n_ = ck["track"], ck["beta"], ck["gamma_over_eta"], ck["n"]

        # Default/L1 per-sample loss (from MDM delta grid)
        sub = p2_data[(p2_data["track"] == track) & (p2_data["beta"] == beta)
                      & (p2_data["gamma_over_eta"] == ge) & (p2_data["n"] == n_)]

        # Compute Default (delta=0.1) and L1 (delta=0.08) per-sample J1 components
        default_losses = []
        l1_losses = []
        for _, row in sub.iterrows():
            if abs(row["delta"] - 0.1) < 0.001:
                loss, ok = _compute_loss_row(row)
                if ok:
                    default_losses.append(loss)
            if abs(row["delta"] - 0.08) < 0.001:
                loss, ok = _compute_loss_row(row)
                if ok:
                    l1_losses.append(loss)

        j1_default = float(np.sqrt(np.mean(np.square(default_losses)))) if default_losses else None
        j1_l1 = float(np.sqrt(np.mean(np.square(l1_losses)))) if l1_losses else None

        results.append({
            "track": track, "beta": beta, "gamma_over_eta": ge, "n": n_,
            "n_samples": len(sub) // 26 if len(sub) >= 26 else len(sub),
            "default_J1": j1_default,
            "l1_J1": j1_l1,
        })

    result_df = pd.DataFrame(results)

    # Write per-combo summary
    result_df.to_csv(os.path.join(P2_OUT_DIR, "p2_per_combo_summary.csv"), index=False)

    # Write per-track summary
    for track in ["P2-NI", "P2-PI"]:
        td = result_df[result_df["track"] == track]
        n_combos = len(td)
        def_j1 = td["default_J1"].mean() if td["default_J1"].notna().any() else None
        l1_j1 = td["l1_J1"].mean() if td["l1_J1"].notna().any() else None
        print(f"  {track}: {n_combos} combos, Default J1={def_j1:.4f}" if def_j1 else f"  {track}: {n_combos} combos")
        if l1_j1:
            print(f"    L1 J1={l1_j1:.4f}")

    # Write manifest
    manifest = {
        "manifest_version": "study01-p2-evaluation-v1",
        "run_id": "P2_evaluation_v1",
        "code_commit": _git_sha(),
        "created_at": _now_iso(),
        "combo_counts": {"P2-NI": P2_NI_COMBOS, "P2-PI": P2_PI_COMBOS},
        "evaluated": f"Default (delta=0.1) and L1 (delta=0.08) baselines",
        "p2_data_source": str(CHUNKS_DIR),
    }
    with open(os.path.join(P2_OUT_DIR, "evaluation_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"P2 Evaluation complete. Results: {P2_OUT_DIR}")
    return result_df


def _git_sha():
    import subprocess
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True, cwd=STUDY_ROOT)
    return result.stdout.strip()


if __name__ == "__main__":
    evaluate_p2()
