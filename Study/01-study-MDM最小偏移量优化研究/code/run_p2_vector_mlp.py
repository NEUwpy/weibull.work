"""P2 Vector-MLP evaluation: rebuild 15 models from E3b config, evaluate on P2 data.

Uses the EXACT same production path as E4d: 13 features, full-combo folds,
3 seeds, train-fold-only scaler, P99 failure penalty, MLP(256,128,64).
P2 data NEVER enters training, scaler fit, or seed selection.
"""

import sys, os, json, time, math, warnings, gc, hashlib
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
    compute_j1, compute_j1_squared,
)
from config import STUDY_ROOT, BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID
from studies.common.sample import generate_sample

from scipy import stats as sp_stats
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning

# ── MLP config (identical to E4d) ──
MLP_HIDDEN = (256, 128, 64)
MLP_MAX_ITER = 300
MLP_BATCH = 256
MLP_ALPHA = 1e-4
MLP_LR = 1e-3

# ── Paths ──
STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT_DIR = os.path.dirname(STUDY_CODE_DIR)
ARTIFACTS_DIR = os.path.join(STUDY_ROOT_DIR, "artifacts", "formal")
P2_DIR = os.path.join(ARTIFACTS_DIR, OUTPUT_DIR_NAME)
CHUNKS_DIR = os.path.join(P2_DIR, "chunks")
SHARED_DIR = os.path.join(ARTIFACTS_DIR, "shared_data")
E3B_DIR = os.path.join(ARTIFACTS_DIR, "E3b_vector_mlp")


def _sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def extract_features(sample):
    """13 deployment-observable statistics (identical to E3b/E4d)."""
    x = np.sort(sample)
    n = len(x)
    q25, q50, q75 = np.percentile(x, [25, 50, 75])
    return np.array([
        np.min(x), np.max(x), np.ptp(x), q25, q50, q75,
        q75 - q25, np.mean(x), np.std(x, ddof=0), float(n),
        np.std(x, ddof=0) / (abs(np.mean(x)) + 1e-12),
        sp_stats.skew(x, bias=False) if n >= 3 else 0.0,
        sp_stats.kurtosis(x, fisher=True, bias=False) if n >= 4 else 0.0,
    ], dtype=np.float64)


def _load_shared_data():
    """Load main grid training data from shared_data chunks."""
    shared_chunks = os.path.join(SHARED_DIR, "chunks")
    if not os.path.isdir(shared_chunks):
        # Try merged file
        merged = os.path.join(SHARED_DIR, "mc_scan_raw.csv")
        if os.path.isfile(merged):
            return pd.read_csv(merged)
        raise FileNotFoundError(f"No shared data at {SHARED_DIR}")

    dfs = []
    for fn in sorted(os.listdir(shared_chunks)):
        if fn.endswith("_mdm.csv"):
            dfs.append(pd.read_csv(os.path.join(shared_chunks, fn)))
    return pd.concat(dfs, ignore_index=True)


def run_vector_mlp_evaluation(smoke_only=True):
    """Run Vector-MLP P2 evaluation.

    If smoke_only=True, only evaluate 1 combo to validate the pipeline.
    """
    print("Loading training data from shared_data...")
    train_data = _load_shared_data()
    print(f"  Loaded {len(train_data)} rows")

    # Load P2 data
    print("Loading P2 test data...")
    p2_dfs = []
    combos = build_p2_combos()
    if smoke_only:
        combos = combos[:1]  # Just 1 combo for smoke
    for track, beta, ge, n in combos:
        fp = os.path.join(CHUNKS_DIR, f"{track}_{beta:.2f}_{ge:.2f}_{n}.csv")
        if os.path.isfile(fp):
            p2_dfs.append(pd.read_csv(fp))
    p2_data = pd.concat(p2_dfs, ignore_index=True)
    print(f"  Loaded {len(p2_data)} P2 test rows ({len(combos)} combos)")

    # Train 15 models on main grid, evaluate on P2
    results = []
    for fold in range(VECTOR_MLP_FOLDS):
        for seed in VECTOR_MLP_SEEDS:
            t0 = time.time()
            model_id = f"fold{fold}_seed{seed}"

            # Train fold/test split based on repeat_id mod 5
            train_mask = train_data["repeat_id"] % VECTOR_MLP_FOLDS != fold
            test_mask = ~train_mask

            train_df = train_data[train_mask]
            # Features for training
            train_features = []
            train_losses = []
            for _, row in train_df.iterrows():
                try:
                    sample = generate_sample(
                        beta=row["beta"], eta=row["eta"], gamma=row["gamma"],
                        n=int(row["n"]), repeat_id=int(row["repeat_id"]),
                        seed=42001 + int(row["repeat_id"]))
                    feat = extract_features(sample)
                    # Build 26-dim risk curve (true loss per delta)
                    curve = []
                    for delta in DELTA_GRID:
                        sub = train_df[(train_df["beta"] == row["beta"]) &
                                       (train_df["gamma_over_eta"] == row["gamma_over_eta"]) &
                                       (train_df["n"] == row["n"]) &
                                       (train_df["repeat_id"] == row["repeat_id"])]
                        if len(sub) > 0:
                            r = sub[sub["delta"] == delta].iloc[0] if len(sub[sub["delta"] == delta]) > 0 else None
                            if r is not None and r["status"] == "ok":
                                j1_sq = compute_j1_squared(
                                    float(r["beta_hat"]), float(r["beta"]),
                                    float(r["eta_hat"]), float(r["eta"]),
                                    float(r["gamma_hat"]), float(r["gamma"]))
                                curve.append(j1_sq)
                            else:
                                curve.append(np.nan)
                        else:
                            curve.append(np.nan)
                    train_features.append(feat)
                    train_losses.append(curve)
                except Exception:
                    continue

            if len(train_features) == 0:
                print(f"  {model_id}: no training data, skipping")
                continue

            X_train = np.array(train_features)
            Y_train = np.array(train_losses)

            # P99 failure penalty from training
            valid_mask = ~np.isnan(Y_train).all(axis=1)
            if valid_mask.sum() > 0:
                train_valid = Y_train[valid_mask]
                failure_penalty = float(np.nanpercentile(train_valid, 99))
            else:
                failure_penalty = 10.0

            # Fill NaN with failure penalty
            Y_train_filled = np.where(np.isnan(Y_train), failure_penalty, Y_train)

            # Train feature scaler on training data only
            feat_scaler = StandardScaler()
            X_train_scaled = feat_scaler.fit_transform(X_train)

            # Train target scaler
            target_scaler = StandardScaler()
            Y_train_scaled = target_scaler.fit_transform(Y_train_filled)

            # Train MLP
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=ConvergenceWarning)
                model = MLPRegressor(
                    hidden_layer_sizes=MLP_HIDDEN, activation="relu",
                    solver="adam", alpha=MLP_ALPHA, learning_rate_init=MLP_LR,
                    max_iter=MLP_MAX_ITER, early_stopping=True,
                    validation_fraction=0.1, n_iter_no_change=10,
                    random_state=seed, batch_size=MLP_BATCH,
                )
                model.fit(X_train_scaled, Y_train_scaled)

            elapsed = time.time() - t0
            print(f"  {model_id}: trained in {elapsed:.0f}s")

            # Evaluate on P2 data
            p2_features = []
            p2_keys = []
            for _, row in p2_data.iterrows():
                try:
                    sample = generate_sample(
                        beta=row["beta"], eta=row["eta"], gamma=row["gamma"],
                        n=int(row["n"]), repeat_id=int(row["repeat_id"]),
                        seed=42001 + int(row["repeat_id"]))
                    feat = extract_features(sample)
                    p2_features.append(feat)
                    p2_keys.append((row["beta"], row["gamma_over_eta"], row["n"], row["repeat_id"]))
                except Exception:
                    continue

            if len(p2_features) == 0:
                continue

            X_p2 = np.array(p2_features)
            X_p2_scaled = feat_scaler.transform(X_p2)
            Y_p2_pred = target_scaler.inverse_transform(model.predict(X_p2_scaled))
            Y_p2_pred = np.clip(Y_p2_pred, 0, None)

            # Best delta per sample
            best_idx = np.argmin(Y_p2_pred, axis=1)
            pred_losses = Y_p2_pred[np.arange(len(Y_p2_pred)), best_idx]
            j1 = compute_j1(pred_losses[pred_losses < failure_penalty])
            results.append({
                "fold": fold, "seed": seed, "model_id": model_id,
                "n_test_samples": len(pred_losses),
                "j1": j1, "failure_penalty": failure_penalty,
                "elapsed_s": elapsed,
            })

    if results:
        df = pd.DataFrame(results)
        df.to_csv(os.path.join(P2_DIR, "p2_vector_mlp_results.csv"), index=False)
        j1s = df["j1"].values
        print(f"\nVector-MLP P2 results ({len(results)} models):")
        print(f"  J1: min={np.min(j1s):.4f} med={np.median(j1s):.4f} max={np.max(j1s):.4f}")
    else:
        print("No results produced")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", default=True)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    run_vector_mlp_evaluation(smoke_only=not args.full)
