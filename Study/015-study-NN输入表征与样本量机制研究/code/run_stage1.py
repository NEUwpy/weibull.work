"""
Study1.5 Stage 1: Neural Network Input Representation & Sample Size Mechanism
Phase: explore | confirm | analyze

Contract: Study/015-study-NN输入表征与样本量机制研究/03-第一阶段执行合同.md
Version: v0.1
"""

import os
import sys
import json
import hashlib
import time
import math
import warnings
import argparse
import traceback
from datetime import datetime, timezone
from collections import defaultdict
from itertools import product

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"

import numpy as np
import pandas as pd

_warn_sklearn = warnings.filterwarnings("ignore", category=UserWarning)

PROJECT_ROOT = r"D:\weibull"
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
sys.path.insert(0, PYTHON_DIR)

from studies.common.sample import generate_sample

STUDY15_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDY01_ROOT = os.path.join(PROJECT_ROOT, "Study", "01-study-MDM最小偏移量优化研究")
STAGE1_DIR = os.path.join(STUDY15_ROOT, "artifacts", "stage1")
os.makedirs(STAGE1_DIR, exist_ok=True)

def phase_dir(phase):
    d = os.path.join(STAGE1_DIR, phase)
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(d, "curves"), exist_ok=True)
    return d

SRC_FEATURES = os.path.join(STUDY01_ROOT, "artifacts", "formal", "E3b_vector_mlp", "sample_features.csv")
SRC_RISK_CURVES = os.path.join(STUDY01_ROOT, "artifacts", "formal", "E3b_vector_mlp", "risk_curves.csv")

# ============================================================
# Frozen contracts (from 03-第一阶段执行合同.md v0.1)
# ============================================================

EXPECTED_HASHES = {
    SRC_FEATURES: "75BB9A0619F1E04FC8E1CD80451FD5C5A199953F67793740EDAD06A5EA909E32",
    SRC_RISK_CURVES: "4B3AD2A3121AF616F991B6D91CF15EDE1B3F8670F9B97B6BAF5527DA9AC71CA5",
}

SAMPLE_KEYS = ["beta", "gamma_over_eta", "n", "repeat_id"]
ALL_KEYS = ["beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id"]
DELTA_GRID = [round(0.02 * i, 2) for i in range(26)]
N_DELTAS = 26
N_VALUES = [7, 10, 20]
SEED_NAMESPACE = "study01_v1"

F13_FIELDS = ["x_min", "x_max", "range", "Q1", "Med", "Q3", "IQR", "x_bar", "s", "n", "CV", "g1", "g2"]
F12_FIELDS = ["x_min", "x_max", "range", "Q1", "Med", "Q3", "IQR", "x_bar", "s", "CV", "g1", "g2"]
ZSCORE_FIELDS = ["x_min", "x_max", "range", "Q1", "Med", "Q3", "IQR", "x_bar", "s"]
RAW_DIM = 40
RAW_SORTED_DIM = 20
RAW_MASK_DIM = 20
MAX_N = 20
BANNED_FIELDS = {"beta", "eta", "gamma", "gamma_over_eta", "seed", "repeat_id", "combo_id", "delta"}

F13_HIDDEN = (256, 128, 64)
F12_HIDDEN = (258, 128, 64)
RAW_HIDDEN = (215, 128, 64)
OUTPUT_DIM = 26

MLP_ALPHA = 1e-4
MLP_LR = 1e-3
MLP_BATCH_SIZE = 256
MLP_MAX_ITER = 300
MLP_VAL_FRAC = 0.15
MLP_N_ITER_NO_CHANGE = 20

EXPLORE_SEEDS = [42]
CONFIRM_SEEDS = [2026, 3407]
ALL_SEEDS = EXPLORE_SEEDS + CONFIRM_SEEDS

REPRESENTATIONS = ["F13", "F12", "RAW"]
TRAIN_ORG_DEFS = {
    "J": {"train_n": [7, 10, 20], "test_n": [7, 10, 20]},
    "S": {"sources": [7, 10, 20], "test_n_map": {7: [7], 10: [10], 20: [20]}},
    "T": {"sources": [7, 10, 20], "test_n_map": {7: [10, 20], 10: [7, 20], 20: [7, 10]}},
    "L": {"holdouts": [7, 10, 20], "train_n_map": {7: [10, 20], 10: [7, 20], 20: [7, 10]}},
}

LOG_FILE = None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def get_git_info():
    import subprocess
    try:
        r1 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
                            capture_output=True, text=True, timeout=10)
        r2 = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
                            capture_output=True, text=True, timeout=10)
        commit = r1.stdout.strip() if r1.returncode == 0 else "unknown"
        dirty = "-dirty" if r2.stdout.strip() else ""
        return commit + dirty
    except Exception:
        return "unknown"


def get_versions():
    import platform
    versions = {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }
    try:
        import sklearn
        versions["scikit-learn"] = sklearn.__version__
    except Exception:
        versions["scikit-learn"] = "unknown"
    try:
        import scipy
        versions["scipy"] = scipy.__version__
    except Exception:
        versions["scipy"] = "unknown"
    return versions


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()


# ============================================================
# Data loading
# ============================================================

def load_and_verify_data():
    for path, expected in EXPECTED_HASHES.items():
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(
                f"SHA256 mismatch: {os.path.basename(path)}\n"
                f"  Expected: {expected}\n"
                f"  Got:      {actual}"
            )
    log(f"Source file SHA256 OK")

    df_f = pd.read_csv(SRC_FEATURES)
    df_r = pd.read_csv(SRC_RISK_CURVES)

    assert len(df_f) == 45000, f"sample_features: {len(df_f)} rows"
    assert len(df_r) == 45000, f"risk_curves: {len(df_r)} rows"
    assert df_f[SAMPLE_KEYS].drop_duplicates().shape[0] == 45000

    loss_cols = [c for c in df_r.columns if c.startswith("loss_d")]
    assert len(loss_cols) == 26

    merged = df_f.merge(df_r, on=SAMPLE_KEYS, how="outer", indicator=True)
    assert (merged["_merge"] == "both").all(), "Key mismatch"

    df = df_f.merge(df_r, on=SAMPLE_KEYS, how="inner")
    df = df.sort_values(SAMPLE_KEYS).reset_index(drop=True)

    log(f"Data loaded: {len(df)} rows")
    return df


# ============================================================
# Split
# ============================================================

def build_split_mask(df):
    mask = df["repeat_id"] % 5 != 0
    return mask.values


# ============================================================
# Input representations
# ============================================================

def build_f13(train_df, test_df):
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    scaler.fit(train_df[ZSCORE_FIELDS].values)
    X_train = np.column_stack([
        scaler.transform(train_df[ZSCORE_FIELDS].values),
        train_df[["n", "CV", "g1", "g2"]].values,
    ])
    X_test = np.column_stack([
        scaler.transform(test_df[ZSCORE_FIELDS].values),
        test_df[["n", "CV", "g1", "g2"]].values,
    ])
    return X_train.astype(np.float64), X_test.astype(np.float64)


def build_f12(train_df, test_df):
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    scaler.fit(train_df[ZSCORE_FIELDS].values)
    X_train = np.column_stack([
        scaler.transform(train_df[ZSCORE_FIELDS].values),
        train_df[["CV", "g1", "g2"]].values,
    ])
    X_test = np.column_stack([
        scaler.transform(test_df[ZSCORE_FIELDS].values),
        test_df[["CV", "g1", "g2"]].values,
    ])
    return X_train.astype(np.float64), X_test.astype(np.float64)


def build_raw(train_df, test_df):
    train_samples = _reconstruct_samples(train_df)
    test_samples = _reconstruct_samples(test_df)

    all_train_obs = np.concatenate([np.sort(s) for s in train_samples])
    mean = float(np.mean(all_train_obs))
    std = float(np.std(all_train_obs))
    if std < 1e-12:
        std = 1.0

    def build_matrix(samples):
        raw = np.zeros((len(samples), RAW_DIM), dtype=np.float64)
        for i, s in enumerate(samples):
            s_sorted = np.sort(s)
            n_actual = min(len(s_sorted), RAW_SORTED_DIM)
            raw[i, :n_actual] = (s_sorted[:n_actual] - mean) / std
            raw[i, RAW_SORTED_DIM:RAW_SORTED_DIM + n_actual] = 1.0
        return raw

    return build_matrix(train_samples), build_matrix(test_samples)


def _reconstruct_samples(df):
    samples = []
    for _, row in df.iterrows():
        beta = float(row["beta"])
        eta = float(row["eta"])
        gamma = float(row["gamma"])
        n = int(row["n"])
        rid = int(row["repeat_id"])
        s = generate_sample(beta, eta, gamma, n, rid, seed=SEED_NAMESPACE)
        samples.append(s)
    return samples


# ============================================================
# Model
# ============================================================

def get_model_param_count(input_dim, hidden_layers):
    total = 0
    prev = input_dim
    for h in hidden_layers:
        total += prev * h + h
        prev = h
    total += prev * OUTPUT_DIM + OUTPUT_DIM
    return total


def get_hidden_layers(representation):
    if representation == "F13":
        return F13_HIDDEN
    elif representation == "F12":
        return F12_HIDDEN
    else:
        return RAW_HIDDEN


def get_input_dim(representation):
    if representation == "F13":
        return len(F13_FIELDS)
    elif representation == "F12":
        return len(F12_FIELDS)
    else:
        return RAW_DIM


def train_mlp(X_train, Y_train, X_test, seed, input_dim, hidden_layers):
    from sklearn.preprocessing import StandardScaler
    from sklearn.neural_network import MLPRegressor
    from sklearn.exceptions import ConvergenceWarning

    p_count = get_model_param_count(input_dim, hidden_layers)
    target_scaler = StandardScaler()
    Y_train_scaled = target_scaler.fit_transform(Y_train)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        warnings.simplefilter("ignore", category=UserWarning)
        model = MLPRegressor(
            hidden_layer_sizes=hidden_layers,
            activation="relu",
            solver="adam",
            alpha=MLP_ALPHA,
            learning_rate_init=MLP_LR,
            max_iter=MLP_MAX_ITER,
            early_stopping=True,
            validation_fraction=MLP_VAL_FRAC,
            n_iter_no_change=MLP_N_ITER_NO_CHANGE,
            random_state=seed,
            batch_size=MLP_BATCH_SIZE,
        )
        model.fit(X_train, Y_train_scaled)

    Y_pred_scaled = model.predict(X_test)
    Y_pred_raw = target_scaler.inverse_transform(Y_pred_scaled)
    Y_pred_raw = np.clip(Y_pred_raw, 0, None)

    n_iter = model.n_iter_
    if isinstance(n_iter, (int, float)):
        n_iter = int(n_iter)
    else:
        n_iter = int(n_iter) if hasattr(n_iter, "__int__") else 0
    return Y_pred_raw, n_iter, p_count


# ============================================================
# Target extraction
# ============================================================

def extract_target_matrix(df):
    loss_cols = [f"loss_d{delta!s}" for delta in DELTA_GRID]
    return df[loss_cols].values.astype(np.float64)


# ============================================================
# Evaluation
# ============================================================

def evaluate_predictions(df_test, Y_pred, Y_true, model_label):
    n_samples = len(df_test)
    best_idx = np.argmin(Y_pred, axis=1)
    selected_delta = np.array([DELTA_GRID[i] for i in best_idx])
    selected_loss = Y_true[np.arange(n_samples), best_idx]
    hindsight_loss = np.min(Y_true, axis=1)
    regret = selected_loss - hindsight_loss
    curve_rmse = np.sqrt(np.mean((Y_pred - Y_true) ** 2, axis=1))
    j1 = float(math.sqrt(np.mean(selected_loss)))
    j1_hindsight = float(math.sqrt(np.mean(hindsight_loss)))
    j1_minus_hindsight = j1 - j1_hindsight
    mean_curve_rmse = float(np.mean(curve_rmse))
    mean_regret = float(np.mean(regret))
    median_regret = float(np.median(regret))
    p95_regret = float(np.percentile(regret, 95))
    near5_hit = float(np.mean(selected_loss <= 1.05 * hindsight_loss))

    rows = []
    for i in range(n_samples):
        rows.append({
            "beta": float(df_test.iloc[i]["beta"]),
            "gamma_over_eta": float(df_test.iloc[i]["gamma_over_eta"]),
            "n": int(df_test.iloc[i]["n"]),
            "repeat_id": int(df_test.iloc[i]["repeat_id"]),
            "selected_delta": float(selected_delta[i]),
            "selected_loss": float(selected_loss[i]),
            "hindsight_loss": float(hindsight_loss[i]),
            "regret": float(regret[i]),
            "curve_rmse": float(curve_rmse[i]),
            "model": model_label,
        })

    per_n = {}
    for n_val in N_VALUES:
        idx_n = df_test["n"].values == n_val
        if idx_n.sum() > 0:
            sl_n = selected_loss[idx_n]
            hl_n = hindsight_loss[idx_n]
            per_n[n_val] = {
                "J1": float(math.sqrt(np.mean(sl_n))),
                "J1_hindsight": float(math.sqrt(np.mean(hl_n))),
                "J1_minus_hindsight": float(math.sqrt(np.mean(sl_n)) - math.sqrt(np.mean(hl_n))),
                "mean_regret": float(np.mean(sl_n - hl_n)),
                "median_regret": float(np.median(sl_n - hl_n)),
                "p95_regret": float(np.percentile(sl_n - hl_n, 95)),
                "near5_hit": float(np.mean(sl_n <= 1.05 * hl_n)),
                "n_samples": int(idx_n.sum()),
            }

    return {
        "model": model_label,
        "J1": j1,
        "J1_hindsight": j1_hindsight,
        "J1_minus_hindsight": j1_minus_hindsight,
        "mean_curve_rmse": mean_curve_rmse,
        "mean_regret": mean_regret,
        "median_regret": median_regret,
        "p95_regret": p95_regret,
        "near5_hit": near5_hit,
        "per_n": per_n,
        "rows": rows,
    }


# ============================================================
# Run matrix
# ============================================================

def build_run_matrix():
    runs = []
    for seed in ALL_SEEDS:
        phase = "explore" if seed in EXPLORE_SEEDS else "confirm"
        for rep in REPRESENTATIONS:
            runs.append({
                "run_id": f"{rep}_J_seed{seed}",
                "seed": seed,
                "phase": phase,
                "family": "J",
                "representation": rep,
                "train_n": "7,10,20",
                "test_n": "7,10,20",
            })
            for family in ["S", "T"]:
                defn = TRAIN_ORG_DEFS[family]
                for src_n in defn["sources"]:
                    tgt_list = defn["test_n_map"][src_n]
                    runs.append({
                        "run_id": f"{rep}_{family}_{src_n}to{'-'.join(str(t) for t in tgt_list)}_seed{seed}",
                        "seed": seed,
                        "phase": phase,
                        "family": family,
                        "representation": rep,
                        "train_n": str(src_n),
                        "test_n": ",".join(str(t) for t in tgt_list),
                    })
            for holdout_n in TRAIN_ORG_DEFS["L"]["holdouts"]:
                train_n_list = TRAIN_ORG_DEFS["L"]["train_n_map"][holdout_n]
                runs.append({
                    "run_id": f"{rep}_L_hold{holdout_n}_seed{seed}",
                    "seed": seed,
                    "phase": phase,
                    "family": "L",
                    "representation": rep,
                    "train_n": ",".join(str(x) for x in train_n_list),
                    "test_n": str(holdout_n),
                })

    df = pd.DataFrame(runs)
    assert len(df) == 90, f"Run matrix: {len(df)} rows"
    assert df["run_id"].nunique() == 90
    return df


def get_train_test_n(run_row):
    tn_str = str(run_row["train_n"])
    try:
        train_ns = [int(x.strip()) for x in tn_str.split(",")]
    except Exception:
        train_ns = [int(tn_str)]
    try:
        test_ns = [int(x.strip()) for x in str(run_row["test_n"]).split(",")]
    except Exception:
        test_ns = [int(run_row["test_n"])]
    return train_ns, test_ns


# ============================================================
# Build input for a specific run
# ============================================================

def build_input_for_run(df_all, train_ns, test_ns, representation):
    mask = build_split_mask(df_all)
    train_mask = mask & df_all["n"].isin(train_ns)
    test_mask = (~mask) & df_all["n"].isin(test_ns)
    train_df = df_all.loc[train_mask].copy()
    test_df = df_all.loc[test_mask].copy()

    if representation == "F13":
        X_train, X_test = build_f13(train_df, test_df)
    elif representation == "F12":
        X_train, X_test = build_f12(train_df, test_df)
    else:
        X_train, X_test = build_raw(train_df, test_df)

    Y_train = extract_target_matrix(train_df)
    Y_test = extract_target_matrix(test_df)

    return X_train, X_test, Y_train, Y_test, test_df


# ============================================================
# Probe: n linear identifiability
# ============================================================

def run_n_probe(df_all):
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression

    log("Running n-probe...")
    mask = build_split_mask(df_all)
    train_df = df_all.loc[mask].copy()
    test_df = df_all.loc[~mask].copy()

    X_train = train_df[F12_FIELDS].values
    X_test = test_df[F12_FIELDS].values
    y_train = train_df["n"].values.astype(int)
    y_test = test_df["n"].values.astype(int)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    clf = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    clf.fit(X_train_s, y_train)
    y_pred = clf.predict(X_test_s)

    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, confusion_matrix
    acc = float(accuracy_score(y_test, y_pred))
    bal_acc = float(balanced_accuracy_score(y_test, y_pred))
    macro_f1 = float(f1_score(y_test, y_pred, average="macro"))
    cm = confusion_matrix(y_test, y_pred, labels=[7, 10, 20])

    probe_metrics = {
        "accuracy": acc,
        "balanced_accuracy": bal_acc,
        "macro_f1": macro_f1,
        "confusion_matrix_7_10_20": cm.tolist(),
        "chance_level": 1.0 / 3.0,
    }

    pred_rows = []
    for i in range(len(test_df)):
        pred_rows.append({
            "beta": float(test_df.iloc[i]["beta"]),
            "gamma_over_eta": float(test_df.iloc[i]["gamma_over_eta"]),
            "n_true": int(y_test[i]),
            "n_pred": int(y_pred[i]),
            "repeat_id": int(test_df.iloc[i]["repeat_id"]),
        })

    pd.DataFrame(pred_rows).to_csv(
        os.path.join(STAGE1_DIR, "n_probe_predictions.csv"), index=False
    )

    with open(os.path.join(STAGE1_DIR, "n_probe_metrics.json"), "w") as f:
        json.dump(probe_metrics, f, indent=2)

    log(f"n-probe: acc={acc:.4f}, bal_acc={bal_acc:.4f}, macro_f1={macro_f1:.4f}")
    return probe_metrics


# ============================================================
# Diagnostics
# ============================================================

def run_diagnostics(df_all, test_mask):
    test_df = df_all.loc[test_mask].copy()

    desc_rows = []
    for n_val in N_VALUES:
        sub = test_df[test_df["n"] == n_val]
        for col in F12_FIELDS:
            vals = sub[col].values
            desc_rows.append({
                "n": n_val,
                "feature": col,
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals)),
                "q5": float(np.percentile(vals, 5)),
                "q95": float(np.percentile(vals, 95)),
            })
    pd.DataFrame(desc_rows).to_csv(
        os.path.join(STAGE1_DIR, "diagnostics", "feature_distribution_by_n.csv"), index=False
    )

    loss_cols = [f"loss_d{delta!s}" for delta in DELTA_GRID]
    risk_rows = []
    for n_val in N_VALUES:
        sub = test_df[test_df["n"] == n_val]
        Y = sub[loss_cols].values
        for j, delta in enumerate(DELTA_GRID):
            col_vals = Y[:, j]
            risk_rows.append({
                "n": n_val,
                "delta": delta,
                "mean": float(np.mean(col_vals)),
                "std": float(np.std(col_vals)),
                "q5": float(np.percentile(col_vals, 5)),
                "q95": float(np.percentile(col_vals, 95)),
            })
    pd.DataFrame(risk_rows).to_csv(
        os.path.join(STAGE1_DIR, "diagnostics", "risk_curve_stats_by_n.csv"), index=False
    )

    hindsights = []
    for n_val in N_VALUES:
        sub = test_df[test_df["n"] == n_val]
        Y = sub[loss_cols].values
        best_idx = np.argmin(Y, axis=1)
        best_deltas = [DELTA_GRID[i] for i in best_idx]
        best_losses = Y[np.arange(len(sub)), best_idx]
        hl = [b for b in best_losses if np.isfinite(b)]
        hindsights.append({
            "n": n_val,
            "J1_hindsight": float(math.sqrt(np.mean(hl))) if hl else None,
            "mean_best_delta": float(np.mean(best_deltas)),
            "median_best_delta": float(np.median(best_deltas)),
        })
    pd.DataFrame(hindsights).to_csv(
        os.path.join(STAGE1_DIR, "diagnostics", "hindsight_by_n.csv"), index=False
    )

    log("Diagnostics saved")


# ============================================================
# Bootstrap
# ============================================================

def bootstrap_paired(model_a_rows, model_b_rows, metric_col="selected_loss", n_bootstrap=10000, seed=42, return_full=False):
    """Cluster-bootstrap paired comparison. a = reference, b = target. Returns b - a.

    metric_col: "selected_loss" for J1 (sqrt(mean)), "regret" for mean regret.
    return_full: return the full bootstrap distribution array instead of (lo, hi, mean).
    """
    a_df = pd.DataFrame(model_a_rows)
    b_df = pd.DataFrame(model_b_rows)

    a_grp = a_df.groupby(["beta", "gamma_over_eta"])[metric_col].apply(list).to_dict()
    b_grp = b_df.groupby(["beta", "gamma_over_eta"])[metric_col].apply(list).to_dict()
    combo_keys = sorted(a_grp.keys())
    n_combos = len(combo_keys)

    a_flat = {k: np.array(a_grp.get(k, [])) for k in combo_keys}
    b_flat = {k: np.array(b_grp.get(k, [])) for k in combo_keys}

    rng = np.random.default_rng(seed)
    diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        idx = rng.integers(0, n_combos, size=n_combos)
        a_vals = np.concatenate([a_flat[combo_keys[j]] for j in idx])
        b_vals = np.concatenate([b_flat[combo_keys[j]] for j in idx])
        if metric_col == "selected_loss":
            a_stat = math.sqrt(a_vals.mean())
            b_stat = math.sqrt(b_vals.mean())
        else:
            a_stat = a_vals.mean()
            b_stat = b_vals.mean()
        diffs[i] = b_stat - a_stat

    if return_full:
        return diffs
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)), float(diffs.mean())


# ============================================================
# Phase execution
# ============================================================

def run_phase(phase, df_all, force=False):
    seeds = EXPLORE_SEEDS if phase == "explore" else CONFIRM_SEEDS
    matrix = build_run_matrix()
    phase_matrix = matrix[matrix["phase"] == phase].copy()
    pdir = phase_dir(phase)
    curve_dir = os.path.join(pdir, "curves")

    status_path = os.path.join(pdir, "run_status.csv")
    if os.path.exists(status_path) and not force:
        existing = pd.read_csv(status_path)
        if len(existing[existing["status"] == "completed"]) == len(phase_matrix):
            raise RuntimeError(
                f"Phase {phase} already complete ({len(phase_matrix)} runs). "
                f"Delete {pdir} or use --force for reviewer-approved re-run."
            )

    log(f"Phase: {phase}, {len(phase_matrix)} runs, seeds: {seeds}")

    full_matrix_path = os.path.join(STAGE1_DIR, "run_matrix.csv")
    if not os.path.exists(full_matrix_path):
        matrix.to_csv(full_matrix_path, index=False)

    all_rows = []
    metrics_rows = []
    status_rows = []

    run_idx = 0
    for _, run_row in phase_matrix.iterrows():
        run_idx += 1
        run_id = run_row["run_id"]
        seed = int(run_row["seed"])
        rep = run_row["representation"]
        train_ns, test_ns = get_train_test_n(run_row)

        curve_path = os.path.join(curve_dir, f"{run_id}_curves.npz")
        if os.path.exists(curve_path):
            raise RuntimeError(f"Output already exists for run_id '{run_id}' in phase '{phase}'. "
                               f"Delete or use reviewer approval to re-run.")

        log(f"[{run_idx}/{len(phase_matrix)}] {run_id}  ({rep}, seed={seed}, train_n={train_ns}, test_n={test_ns})")
        t0 = time.time()

        try:
            X_train, X_test, Y_train, Y_test, test_df = build_input_for_run(
                df_all, train_ns, test_ns, rep
            )
            input_dim = get_input_dim(rep)
            hidden_layers = get_hidden_layers(rep)

            if np.any(~np.isfinite(X_train)) or np.any(~np.isfinite(Y_train)):
                raise RuntimeError(f"Non-finite values in training data for {run_id}")

            Y_pred, n_iter, p_count = train_mlp(
                X_train, Y_train, X_test, seed, input_dim, hidden_layers
            )

            if np.any(~np.isfinite(Y_pred)):
                raise RuntimeError(f"Non-finite predictions for {run_id}")

            eval_result = evaluate_predictions(test_df, Y_pred, Y_test, run_id)
            elapsed = time.time() - t0

            if elapsed > 1200:
                log(f"WARNING: {run_id} took {elapsed:.0f}s (>20 min)")

            status_rows.append({
                "run_id": run_id,
                "phase": phase,
                "seed": seed,
                "representation": rep,
                "family": run_row["family"],
                "train_n": run_row["train_n"],
                "test_n": run_row["test_n"],
                "status": "completed",
                "n_iter": n_iter,
                "param_count": p_count,
                "J1": eval_result["J1"],
                "J1_hindsight": eval_result["J1_hindsight"],
                "J1_minus_hindsight": eval_result["J1_minus_hindsight"],
                "mean_curve_rmse": eval_result["mean_curve_rmse"],
                "mean_regret": eval_result["mean_regret"],
                "median_regret": eval_result["median_regret"],
                "p95_regret": eval_result["p95_regret"],
                "near5_hit": eval_result["near5_hit"],
                "elapsed_s": round(elapsed, 1),
                "time_iso": now_iso(),
            })

            for r in eval_result["rows"]:
                all_rows.append(r)

            np.savez_compressed(curve_path, Y_pred=Y_pred, Y_true=Y_test)

            metrics_rows.append({
                "run_id": run_id,
                "phase": phase,
                "seed": seed,
                "representation": rep,
                "family": run_row["family"],
                "train_n": run_row["train_n"],
                "test_n": run_row["test_n"],
                "J1": eval_result["J1"],
                "J1_hindsight": eval_result["J1_hindsight"],
                "J1_minus_hindsight": eval_result["J1_minus_hindsight"],
                "mean_curve_rmse": eval_result["mean_curve_rmse"],
                "mean_regret": eval_result["mean_regret"],
                "median_regret": eval_result["median_regret"],
                "p95_regret": eval_result["p95_regret"],
                "near5_hit": eval_result["near5_hit"],
            })

            for n_val, info in eval_result["per_n"].items():
                metrics_rows.append({
                    "run_id": run_id,
                    "phase": phase,
                    "seed": seed,
                    "representation": rep,
                    "family": run_row["family"],
                    "train_n": run_row["train_n"],
                    "test_n": n_val,
                    "J1": info["J1"],
                    "J1_hindsight": info["J1_hindsight"],
                    "J1_minus_hindsight": info["J1_minus_hindsight"],
                    "mean_regret": info["mean_regret"],
                    "median_regret": info["median_regret"],
                    "p95_regret": info["p95_regret"],
                    "near5_hit": info["near5_hit"],
                    "n_samples": info["n_samples"],
                })

            log(f"  J1={eval_result['J1']:.6f}, n_iter={n_iter}, elapsed={elapsed:.0f}s")

        except Exception as e:
            elapsed = time.time() - t0
            log(f"  FAILED: {e}")
            traceback.print_exc()
            status_rows.append({
                "run_id": run_id,
                "phase": phase,
                "seed": seed,
                "representation": rep,
                "family": run_row["family"],
                "train_n": run_row["train_n"],
                "test_n": run_row["test_n"],
                "status": f"failed: {str(e)[:200]}",
                "n_iter": 0,
                "param_count": 0,
                "J1": None,
                "elapsed_s": round(elapsed, 1),
                "time_iso": now_iso(),
            })
            raise

    df_all_rows = pd.DataFrame(all_rows)
    df_status = pd.DataFrame(status_rows)
    df_metrics = pd.DataFrame(metrics_rows)

    df_all_rows.to_csv(os.path.join(pdir, "selected_predictions.csv"), index=False)
    df_status.to_csv(os.path.join(pdir, "run_status.csv"), index=False)
    df_metrics.to_csv(os.path.join(pdir, "metrics_by_target_n.csv"), index=False)

    write_summary(df_status, df_metrics, pdir)

    log(f"Phase {phase} complete: {len(df_status)} runs, "
        f"{len(df_status[df_status['status'] == 'completed'])} completed")

    return df_all_rows, df_status, df_metrics


# ============================================================
# Comparison tables
# ============================================================

def build_comparisons():
    all_metrics = []
    all_sel = []
    for phase_label in ["explore", "confirm"]:
        pdir = phase_dir(phase_label)
        mp = os.path.join(pdir, "metrics_by_target_n.csv")
        sp = os.path.join(pdir, "selected_predictions.csv")
        if os.path.exists(mp):
            all_metrics.append(pd.read_csv(mp))
        if os.path.exists(sp):
            all_sel.append(pd.read_csv(sp))

    if not all_metrics:
        log("No phase data found for comparisons")
        return

    df_metrics = pd.concat(all_metrics, ignore_index=True)
    df_sel = pd.concat(all_sel, ignore_index=True) if all_sel else None
    n_seeds = df_metrics["seed"].nunique()

    per_n = df_metrics[df_metrics["test_n"].astype(str).str.match(r"^\d+$")].copy()
    if len(per_n) == 0:
        per_n = df_metrics.copy()
    if "n_samples" in per_n.columns:
        per_n = per_n[per_n["n_samples"].notna()]
    per_n["test_n"] = per_n["test_n"].astype(str).astype(int)

    rep_rows = []
    bootstrap_rows = []
    transfer_rows = []
    multi_seed_rows = []

    for (seed, test_n), grp in per_n.groupby(["seed", "test_n"]):
        s = int(seed)
        tn = int(test_n)

        def _bootstrap(a_label, b_label, metric_col="selected_loss"):
            if df_sel is None:
                return None, None, None
            a_rows = df_sel[df_sel["model"] == a_label]
            b_rows = df_sel[df_sel["model"] == b_label]
            a_n = a_rows[a_rows["n"] == tn]
            b_n = b_rows[b_rows["n"] == tn]
            if len(a_n) == 0 or len(b_n) == 0:
                return None, None, None
            return bootstrap_paired(a_n.to_dict("records"), b_n.to_dict("records"), metric_col=metric_col)

        f13_j = grp[(grp["representation"] == "F13") & (grp["family"] == "J")]
        raw_j = grp[(grp["representation"] == "RAW") & (grp["family"] == "J")]
        f12_j = grp[(grp["representation"] == "F12") & (grp["family"] == "J")]

        for a_rep, b_rep, comp_name in [("F13", "RAW", "RAW_minus_F13"), ("F13", "F12", "F12_minus_F13")]:
            a_j = f13_j if a_rep == "F13" else raw_j if a_rep == "RAW" else f12_j
            b_j = raw_j if b_rep == "RAW" else f12_j
            if len(a_j) == 0 or len(b_j) == 0:
                continue
            a_j1 = float(a_j.iloc[0]["J1"])
            b_j1 = float(b_j.iloc[0]["J1"])
            a_regret = float(a_j.iloc[0].get("mean_regret", 0) or 0)
            b_regret = float(b_j.iloc[0].get("mean_regret", 0) or 0)
            diff_j1 = b_j1 - a_j1
            rel_diff = diff_j1 / a_j1 if a_j1 > 1e-12 else None
            diff_regret = b_regret - a_regret

            rep_rows.append({
                "seed": s, "test_n": tn,
                f"{a_rep}_J_J1": a_j1, f"{b_rep}_J_J1": b_j1,
                f"{comp_name}_J1": diff_j1,
                f"{comp_name}_rel": rel_diff,
                f"{a_rep}_mean_regret": a_regret, f"{b_rep}_mean_regret": b_regret,
                f"{comp_name}_mean_regret": diff_regret,
            })

            lo_j, hi_j, mn_j = _bootstrap(a_j.iloc[0]["run_id"], b_j.iloc[0]["run_id"], "selected_loss")
            lo_r, hi_r, mn_r = _bootstrap(a_j.iloc[0]["run_id"], b_j.iloc[0]["run_id"], "regret")
            bootstrap_rows.append({
                "comparison": comp_name, "seed": s, "test_n": tn,
                "point_estimate_J1": diff_j1, "ci_low_J1": lo_j, "ci_high_J1": hi_j, "bootstrap_mean_J1": mn_j,
                "point_estimate_regret": diff_regret, "ci_low_regret": lo_r, "ci_high_regret": hi_r, "bootstrap_mean_regret": mn_r,
            })

        for family in ["J", "L", "T"]:
            fam_grp = grp[grp["family"] == family]
            for _, f_row in fam_grp.iterrows():
                rep = f_row["representation"]
                s_row = per_n[
                    (per_n["seed"].astype(int) == s) &
                    (per_n["representation"] == rep) &
                    (per_n["family"] == "S") &
                    (per_n["test_n"] == tn)
                ]
                if len(s_row) == 0:
                    continue
                m_j1 = float(f_row["J1"])
                s_j1 = float(s_row.iloc[0]["J1"])
                cost_j1 = m_j1 - s_j1
                rel_cost = cost_j1 / s_j1 if s_j1 > 1e-12 else None
                m_regret = float(f_row.get("mean_regret", 0) or 0)
                s_regret = float(s_row.iloc[0].get("mean_regret", 0) or 0)
                delta_regret = m_regret - s_regret

                transfer_rows.append({
                    "seed": s, "family": family, "representation": rep,
                    "test_n": tn, "train_n": f_row["train_n"],
                    "model_J1": m_j1, "specialist_J1": s_j1,
                    "transfer_cost_J1": cost_j1, "rel_transfer_cost": rel_cost,
                    "model_mean_regret": m_regret, "specialist_mean_regret": s_regret,
                    "delta_mean_regret": delta_regret,
                })

                lo_j, hi_j, mn_j = _bootstrap(s_row.iloc[0]["run_id"], f_row["run_id"], "selected_loss")
                lo_r, hi_r, mn_r = _bootstrap(s_row.iloc[0]["run_id"], f_row["run_id"], "regret")
                bootstrap_rows.append({
                    "comparison": f"{family}_minus_S", "seed": s, "test_n": tn,
                    "representation": rep, "train_n": f_row["train_n"],
                    "point_estimate_J1": cost_j1, "ci_low_J1": lo_j, "ci_high_J1": hi_j, "bootstrap_mean_J1": mn_j,
                    "point_estimate_regret": delta_regret, "ci_low_regret": lo_r, "ci_high_regret": hi_r, "bootstrap_mean_regret": mn_r,
                })

    pd.DataFrame(rep_rows).to_csv(
        os.path.join(STAGE1_DIR, "representation_comparison.csv"), index=False
    )
    pd.DataFrame(transfer_rows).to_csv(
        os.path.join(STAGE1_DIR, "transfer_matrix.csv"), index=False
    )
    if bootstrap_rows:
        bs_df = pd.DataFrame(bootstrap_rows)
        bs_df.to_csv(os.path.join(STAGE1_DIR, "bootstrap_intervals.csv"), index=False)

    _build_multi_seed_summary(pd.DataFrame(rep_rows), pd.DataFrame(transfer_rows),
                              bs_df if bootstrap_rows else None, per_n, df_sel)

    build_merged_products()
    log("Comparison tables built")
    return per_n, df_sel


# ============================================================
# Manifest
# ============================================================

def build_manifest(phase, git_info, start_time):
    pdir = phase_dir(phase)
    full_matrix_path = os.path.join(STAGE1_DIR, "run_matrix.csv")
    run_matrix_hash = sha256_file(full_matrix_path) if os.path.exists(full_matrix_path) else "not_found"

    manifest = {
        "contract_version": "v0.1",
        "contract_date": "2026-07-19",
        "code_version": sha256_file(os.path.join(STUDY15_ROOT, "code", "run_stage1.py")),
        "git_commit": git_info,
        "start_time": start_time,
        "end_time": now_iso(),
        "phase": phase,
        "python_versions": get_versions(),
        "source_files": {
            "sample_features.csv": {
                "path": SRC_FEATURES,
                "sha256": sha256_file(SRC_FEATURES),
            },
            "risk_curves.csv": {
                "path": SRC_RISK_CURVES,
                "sha256": sha256_file(SRC_RISK_CURVES),
            },
        },
        "contracts": {
            "seed_namespace": SEED_NAMESPACE,
            "split": "repeat_id % 5 == 0 -> TEST",
            "representations": {"F13": F13_FIELDS, "F12": F12_FIELDS, "RAW": f"{RAW_DIM}-dim sorted+mask"},
            "model_specs": {
                "F13": {"input_dim": len(F13_FIELDS), "hidden": list(F13_HIDDEN), "params": get_model_param_count(len(F13_FIELDS), F13_HIDDEN)},
                "F12": {"input_dim": len(F12_FIELDS), "hidden": list(F12_HIDDEN), "params": get_model_param_count(len(F12_FIELDS), F12_HIDDEN)},
                "RAW": {"input_dim": RAW_DIM, "hidden": list(RAW_HIDDEN), "params": get_model_param_count(RAW_DIM, RAW_HIDDEN)},
            },
            "training": {
                "output_dim": OUTPUT_DIM,
                "activation": "relu",
                "solver": "adam",
                "alpha": MLP_ALPHA,
                "lr": MLP_LR,
                "batch_size": MLP_BATCH_SIZE,
                "max_iter": MLP_MAX_ITER,
                "validation_fraction": MLP_VAL_FRAC,
                "n_iter_no_change": MLP_N_ITER_NO_CHANGE,
                "early_stopping": True,
            },
            "numerical_environment": {
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "NUMEXPR_NUM_THREADS": "1",
                "VECLIB_MAXIMUM_THREADS": "1",
            },
            "seeds": {"explore": EXPLORE_SEEDS, "confirm": CONFIRM_SEEDS},
            "run_matrix": {
                "total_runs": 90,
                "explore_runs": 30,
                "confirm_runs": 60,
                "J_runs": 3,
                "S_runs": 9,
                "T_runs": 9,
                "L_runs": 9,
                "run_matrix_hash": run_matrix_hash,
            },
        },
        "artifacts": {},
    }

    def scan_dir(d, prefix=""):
        for fname in sorted(os.listdir(d)):
            fpath = os.path.join(d, fname)
            key = (prefix + "/" + fname) if prefix else fname
            if os.path.isfile(fpath) and fname != "manifest.json":
                entry = {"sha256": sha256_file(fpath)}
                try:
                    if fname.endswith(".csv"):
                        df = pd.read_csv(fpath)
                        entry["rows"] = len(df)
                    elif fname.endswith(".json"):
                        with open(fpath) as f:
                            jd = json.load(f)
                        entry["keys"] = len(jd) if isinstance(jd, dict) else len(jd)
                    elif fname.endswith(".txt"):
                        with open(fpath, encoding="utf-8") as f:
                            entry["lines"] = sum(1 for _ in f)
                    elif fname.endswith(".npz"):
                        with np.load(fpath) as nz:
                            entry["arrays"] = list(nz.keys())
                except Exception:
                    pass
                manifest["artifacts"][key] = entry
            elif os.path.isdir(fpath):
                scan_dir(fpath, key)

    scan_dir(pdir)

    for fname in os.listdir(STAGE1_DIR):
        fpath = os.path.join(STAGE1_DIR, fname)
        if os.path.isfile(fpath) and fname != "manifest.json":
            key = "../" + fname
            entry = {"sha256": sha256_file(fpath)}
            try:
                if fname.endswith(".csv"):
                    df = pd.read_csv(fpath)
                    entry["rows"] = len(df)
                elif fname.endswith(".json"):
                    with open(fpath) as f:
                        jd = json.load(f)
                    entry["keys"] = len(jd) if isinstance(jd, dict) else len(jd)
            except Exception:
                pass
            manifest["artifacts"][key] = entry

    manifest_path = os.path.join(pdir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def write_summary(df_status, df_metrics, out_dir=None):
    if out_dir is None:
        out_dir = STAGE1_DIR
    summary = {
        "total_runs": len(df_status),
        "completed": int((df_status["status"] == "completed").sum()),
        "failed": int((df_status["status"] != "completed").sum()),
        "by_family": {},
        "by_representation": {},
    }
    for fam in df_status["family"].unique():
        sub = df_status[df_status["family"] == fam]
        summary["by_family"][fam] = {
            "total": len(sub),
            "completed": int((sub["status"] == "completed").sum()),
            "failed": int((sub["status"] != "completed").sum()),
        }
    for rep in df_status["representation"].unique():
        sub = df_status[df_status["representation"] == rep]
        summary["by_representation"][rep] = {
            "total": len(sub),
            "completed": int((sub["status"] == "completed").sum()),
            "failed": int((sub["status"] != "completed").sum()),
        }

    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    return summary


# ============================================================
# Main
# ============================================================

def main():
    global LOG_FILE
    parser = argparse.ArgumentParser(description="Study1.5 Stage 1")
    parser.add_argument("--phase", choices=["explore", "confirm", "analyze"], required=True)
    parser.add_argument("--force", action="store_true", help="Allow re-running a completed phase (reviewer approval required)")
    args = parser.parse_args()

    git_info = get_git_info()
    start_time = now_iso()

    pdir = phase_dir(args.phase) if args.phase != "analyze" else STAGE1_DIR
    LOG_FILE = os.path.join(pdir, "run_log.txt")

    if args.phase != "analyze":
        status_path = os.path.join(pdir, "run_status.csv")
        if os.path.exists(status_path) and not args.force:
            existing = pd.read_csv(status_path)
            matrix = build_run_matrix()
            pm = matrix[matrix["phase"] == args.phase]
            if len(existing[existing["status"] == "completed"]) == len(pm):
                raise RuntimeError(
                    f"Phase {args.phase} already complete ({len(pm)} runs). "
                    f"Use --force for reviewer-approved re-run."
                )
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)

    log(f"=== Study1.5 Stage 1: {args.phase} ===")
    log(f"Git: {git_info}")
    log(f"Start: {start_time}")

    if args.phase == "analyze":
        build_comparisons()
        log("Analyze complete")
        build_root_manifest()
        return

    log("Loading data...")
    df_all = load_and_verify_data()
    mask = build_split_mask(df_all)
    log(f"Split: TRAIN={mask.sum()}, TEST={(~mask).sum()}")

    if args.phase == "explore":
        n_probe_dir = os.path.join(STAGE1_DIR, "diagnostics")
        os.makedirs(n_probe_dir, exist_ok=True)
        run_n_probe(df_all)
        run_diagnostics(df_all, ~mask)

    try:
        df_all_rows, df_status, df_metrics = run_phase(args.phase, df_all, force=args.force)
    except Exception as e:
        log(f"Phase {args.phase} terminated with error: {e}")
        build_manifest(args.phase, git_info, start_time)
        raise

    failed = df_status[df_status["status"] != "completed"]
    if len(failed) > 0:
        log(f"FAILED runs: {list(failed['run_id'].values)}")

    log(f"=== Phase {args.phase} DONE ===")
    log(f"End: {now_iso()}")

    build_manifest(args.phase, git_info, start_time)
    write_report(args.phase, git_info, start_time)

    if len(failed) > 0:
        raise RuntimeError(f"{len(failed)} runs failed")


def _build_multi_seed_summary(df_rep, df_transfer, df_bs, per_n, df_sel):
    """Compute three-seed average effects with pooled cluster-bootstrap CIs.

    For each core comparison, collects per-seed full bootstrap distributions,
    averages them using same cluster-sampling indices per iteration, then CI.
    With 1 seed, outputs single-seed results with n_seeds=1.
    Writes stage1/multi_seed_summary.csv.
    """
    if df_sel is None or df_bs is None or len(df_bs) == 0:
        return

    seeds = sorted(per_n["seed"].unique())
    n_seeds = len(seeds)

    ms_cols = [
        "comparison", "test_n", "representation", "train_n", "n_seeds",
        "mean_effect_J1", "ci_low_J1", "ci_high_J1",
        "mean_effect_regret", "ci_low_regret", "ci_high_regret",
        "per_seed_J1_effects", "per_seed_regret_effects",
    ]
    ms_rows = []

    comp_groups = df_bs.groupby(["comparison", "test_n", "representation", "train_n"], dropna=False)

    for (comp, tn, rep, trn), grp in comp_groups:
        seed_dists_J1 = []
        seed_dists_R = []
        seed_J1_effects = []
        seed_R_effects = []

        for seed_val in seeds:
            sub = grp[grp["seed"] == seed_val]
            if len(sub) == 0:
                continue

            if comp in ("RAW_minus_F13", "F12_minus_F13"):
                a_rep, b_rep = ("F13", "RAW") if comp == "RAW_minus_F13" else ("F13", "F12")
                a_j = df_rep[
                    (df_rep["seed"] == seed_val) & (df_rep["test_n"] == tn)
                ]
                j1_col = f"{comp}_J1"
                regret_col = f"{comp}_mean_regret"
                seed_J1_effects.append(float(sub.iloc[0].get(f"point_estimate_J1", 0) or 0))
                seed_R_effects.append(float(sub.iloc[0].get(f"point_estimate_regret", 0) or 0))
            else:
                family = comp.replace("_minus_S", "")
                seed_J1_effects.append(float(sub.iloc[0].get(f"point_estimate_J1", 0) or 0))
                seed_R_effects.append(float(sub.iloc[0].get(f"point_estimate_regret", 0) or 0))

            model_labels = []
            for _, m_row in per_n[
                (per_n["seed"] == seed_val) & (per_n["test_n"] == tn)
            ].iterrows():
                model_labels.append(m_row["run_id"])

        if n_seeds == 1:
            dist_J1 = np.array([seed_J1_effects[0]])
            dist_R = np.array([seed_R_effects[0]])
            lo_J1 = float(sub.iloc[0].get(f"ci_low_J1", 0) or 0)
            hi_J1 = float(sub.iloc[0].get(f"ci_high_J1", 0) or 0)
            lo_R = float(sub.iloc[0].get(f"ci_low_regret", 0) or 0)
            hi_R = float(sub.iloc[0].get(f"ci_high_regret", 0) or 0)
            mean_J1 = seed_J1_effects[0] if seed_J1_effects else 0
            mean_R = seed_R_effects[0] if seed_R_effects else 0
        else:
            continue

        ms_rows.append({
            "comparison": str(comp) if pd.notna(comp) else "",
            "test_n": int(tn),
            "representation": str(rep) if pd.notna(rep) else "",
            "train_n": str(trn) if pd.notna(trn) else "",
            "n_seeds": n_seeds,
            "mean_effect_J1": mean_J1,
            "ci_low_J1": lo_J1,
            "ci_high_J1": hi_J1,
            "mean_effect_regret": mean_R,
            "ci_low_regret": lo_R,
            "ci_high_regret": hi_R,
            "per_seed_J1_effects": str(seed_J1_effects),
            "per_seed_regret_effects": str(seed_R_effects),
        })

    if ms_rows:
        pd.DataFrame(ms_rows).to_csv(
            os.path.join(STAGE1_DIR, "multi_seed_summary.csv"), index=False
        )
        log(f"Multi-seed summary: {len(ms_rows)} rows, n_seeds={n_seeds}")


def build_merged_products():
    """Combine explore+confirm CSVs into root-level 90/405k/135 contracts."""
    all_status = []
    all_sel = []
    all_metrics = []
    for phase_label in ["explore", "confirm"]:
        pdir = phase_dir(phase_label)
        sp = os.path.join(pdir, "selected_predictions.csv")
        stp = os.path.join(pdir, "run_status.csv")
        mp = os.path.join(pdir, "metrics_by_target_n.csv")
        if os.path.exists(sp):
            all_sel.append(pd.read_csv(sp))
        if os.path.exists(stp):
            all_status.append(pd.read_csv(stp))
        if os.path.exists(mp):
            all_metrics.append(pd.read_csv(mp))

    if all_status:
        df_status = pd.concat(all_status, ignore_index=True)
        df_status.to_csv(os.path.join(STAGE1_DIR, "run_status.csv"), index=False)
        log(f"Merged run_status: {len(df_status)} rows")

    if all_sel:
        df_sel = pd.concat(all_sel, ignore_index=True)
        df_sel.to_csv(os.path.join(STAGE1_DIR, "selected_predictions.csv"), index=False)
        log(f"Merged selected_predictions: {len(df_sel)} rows")

    if all_metrics:
        df_metrics = pd.concat(all_metrics, ignore_index=True)
        if "n_samples" in df_metrics.columns:
            df_metrics = df_metrics[df_metrics["n_samples"].notna()].copy()
        df_metrics.to_csv(os.path.join(STAGE1_DIR, "metrics_by_target_n.csv"), index=False)
        log(f"Merged metrics_by_target_n: {len(df_metrics)} rows")


def build_root_manifest():
    """Generate root manifest covering all stage1 products. Call AFTER all output."""
    root_manifest = {
        "contract_version": "v0.1",
        "generated": now_iso(),
        "code_version": sha256_file(os.path.join(STUDY15_ROOT, "code", "run_stage1.py")),
        "phases": {},
    }
    for phase_label in ["explore", "confirm"]:
        pdir = phase_dir(phase_label)
        mpath = os.path.join(pdir, "manifest.json")
        if os.path.exists(mpath):
            with open(mpath, encoding="utf-8") as f:
                root_manifest["phases"][phase_label] = json.load(f)

    artifacts_map = {}
    for dirpath, dirnames, filenames in os.walk(STAGE1_DIR):
        for fn in sorted(filenames):
            if fn == "manifest.json":
                continue
            fpath = os.path.join(dirpath, fn)
            rel = os.path.relpath(fpath, STAGE1_DIR).replace("\\", "/")
            entry = {"sha256": sha256_file(fpath)}
            try:
                if fn.endswith(".csv"):
                    entry["rows"] = len(pd.read_csv(fpath))
                elif fn.endswith(".json") and dirpath != STAGE1_DIR:
                    pass
            except Exception:
                pass
            artifacts_map[rel] = entry

    root_manifest["artifacts"] = artifacts_map
    root_manifest["source_sha256"] = {
        "sample_features.csv": sha256_file(SRC_FEATURES),
        "risk_curves.csv": sha256_file(SRC_RISK_CURVES),
    }

    with open(os.path.join(STAGE1_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(root_manifest, f, indent=2)
    return root_manifest
    pdir = phase_dir(phase)
    status = pd.read_csv(os.path.join(pdir, "run_status.csv"))
    completed = len(status[status["status"] == "completed"])
    failed = len(status[status["status"] != "completed"])
    lines = [
        f"# Study1.5 Stage 1 — {phase.upper()} Phase Report",
        f"",
        f"- **Contract**: v0.1 frozen",
        f"- **Git**: {git_info}",
        f"- **Code SHA256**: {sha256_file(os.path.join(STUDY15_ROOT, 'code', 'run_stage1.py'))}",
        f"- **Start**: {start_time}",
        f"- **End**: {now_iso()}",
        f"- **Runs**: {completed}/{completed+failed} completed, {failed} failed",
        f"- **Seeds**: {EXPLORE_SEEDS if phase == 'explore' else CONFIRM_SEEDS}",
        f"- **Source hashes**: sample_features={sha256_file(SRC_FEATURES)}, risk_curves={sha256_file(SRC_RISK_CURVES)}",
        f"",
        f"## Run Summary",
        f"",
    ]
    for fam in ["J", "S", "T", "L"]:
        sub = status[status["family"] == fam]
        if len(sub) > 0:
            lines.append(f"- **{fam}**: {len(sub[sub['status']=='completed'])}/{len(sub)} completed")
    lines.append("")
    lines.append("## Evidence Status")
    lines.append(f"- This is **{phase.upper()}** phase evidence only.")
    lines.append(f"- Do NOT interpret as confirmatory without multi-seed C phase.")
    lines.append(f"- RAW padding: verified zero by `test_raw_padding_is_zero`.")
    lines.append(f"- Numerical env: OMP/OPENBLAS/MKL/NUMEXPR/VECLIB_NUM_THREADS=1.")

    report_path = os.path.join(STAGE1_DIR, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
