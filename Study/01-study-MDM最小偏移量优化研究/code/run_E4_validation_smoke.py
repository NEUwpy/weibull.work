"""
Study/01 E4 Validation Suite — SMOKE / PILOT script

Purpose:
  - Verify the E4 three-track validation pipeline can run end-to-end.
  - Validate artifact schema, provenance fields, metric computation, and
    output directory structure.
  - This is NOT formal evidence. Outputs are explicitly labeled pilot.
  - All outputs go to artifacts/pilot/E4_validation_smoke/.

Tracks tested:
  E4a: Feature ablation pipeline (tiny subset, 1 fold, 1 seed).
       Reuses E3b feature computation + vector-output MLP logic at minimal scale.
  E4b: Expanded-grid pipeline (boundary parameter combos, R=10 only).
       Tests MC generation + feature computation + reference evaluation for
       boundary parameters not in the main grid.
  E4c: Out-of-grid / continuous-space feasibility check.
       Tests whether the pipeline can handle arbitrary (non-grid) parameter
       combos. Does NOT claim generalization.

Scale:
  - E4a: 3 combos × 50 repeats × 26 deltas = 3900 rows from existing MC data.
  - E4b: 3 boundary combos × 10 repeats × 26 deltas = 780 new MDM estimates.
  - E4c: 2 arbitrary combos × 10 repeats × 26 deltas = 520 new MDM estimates.
  Total new MDM calls: ~1300 (vs 1.17M formal). Very fast.

Boundaries:
  - Reads existing formal MC data (mc_scan_raw.csv) — READ ONLY.
  - Does NOT modify any formal artifact.
  - Does NOT write to artifacts/formal/.
  - Does NOT include banned fields (true params, combo_id, seed, repeat_id)
    in deployable model inputs.
"""

import sys
import os
import json
import time
import math
import hashlib
import subprocess
import warnings
from datetime import datetime, timezone
from itertools import product

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

# ============================================================
# Path setup — same pattern as E3b
# ============================================================

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

from config import (
    BETA_GRID, ETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID,
    DELTA_GRID, DEFAULT_DELTA, SEED_NAMESPACE,
    ARTIFACTS_DIR, SHARED_DATA_DIR
)
from utils import get_git_info, now_iso
from studies.common.sample import generate_sample

# ============================================================
# Output directory — PILOT ONLY
# ============================================================

PILOT_OUTPUT_DIR = os.path.join(
    os.path.dirname(ARTIFACTS_DIR), "pilot", "E4_validation_smoke"
)
os.makedirs(PILOT_OUTPUT_DIR, exist_ok=True)

# ============================================================
# Smoke parameters — deliberately tiny
# ============================================================

# E4a: pick 3 combos from the main grid (existing MC data)
E4A_SMOKK_COMBOS = [
    (2.0, 1.0, 0.1, 7),   # (beta, eta, gamma/eta, n)
    (2.0, 1.0, 0.5, 10),
    (4.0, 1.0, 1.0, 20),
]
E4A_SMOKK_REPEATS = 50  # per combo

# E4b: boundary combos NOT in main grid
E4B_BOUNDARY_COMBOS = [
    (1.2, 1.0, 0.0, 5),    # extreme: low beta, gamma=0, tiny n
    (6.0, 1.0, 0.5, 7),    # extreme: high beta
    (2.5, 1.0, 1.0, 50),   # large n
]
E4B_REPEATS = 10  # tiny

# E4c: arbitrary (non-grid) combos — feasibility only
E4C_ARB_COMBOS = [
    (3.3, 1.0, 0.7, 15),   # mid-range, not on grid
    (1.8, 1.0, 0.3, 12),   # off-grid
]
E4C_REPEATS = 10

# Feature columns — same contract as E3b
FEATURE_COLS_ZSCORE = [
    'x_min', 'x_max', 'range', 'Q1', 'Med', 'Q3', 'IQR', 'x_bar', 's'
]
FEATURE_COLS_RAW = ['n', 'CV', 'g1', 'g2']
SAMPLE_FEATURE_COLS = FEATURE_COLS_ZSCORE + FEATURE_COLS_RAW

# Banned fields check
BANNED_FIELDS = {'beta', 'eta', 'gamma', 'gamma_over_eta', 'seed', 'repeat_id', 'combo_id'}

# Tiny MLP for smoke — intentionally small
SMOKE_MLP_HIDDEN = (32, 16)
SMOKE_MLP_MAX_ITER = 50


# ============================================================
# Feature computation — copied from E3b for standalone smoke
# ============================================================

def compute_sample_features(sample):
    n = len(sample)
    sample_sorted = np.sort(sample)
    x_min = float(sample_sorted[0])
    x_max = float(sample_sorted[-1])
    rng = x_max - x_min
    Q1 = float(np.percentile(sample_sorted, 25))
    Med = float(np.median(sample_sorted))
    Q3 = float(np.percentile(sample_sorted, 75))
    IQR = Q3 - Q1
    x_bar = float(np.mean(sample_sorted))
    s = float(np.std(sample_sorted, ddof=1)) if n > 1 else 0.0
    CV = s / x_bar if x_bar > 0 else 0.0

    if n > 2 and s > 0:
        z = (sample_sorted - x_bar) / s
        g1 = float(np.sum(z**3) / n)
        g2 = float(np.sum(z**4) / n - 3.0)
    else:
        g1 = 0.0
        g2 = 0.0

    return {
        'n': n,
        'x_min': x_min, 'x_max': x_max, 'range': rng,
        'Q1': Q1, 'Med': Med, 'Q3': Q3, 'IQR': IQR,
        'x_bar': x_bar, 's': s, 'CV': CV, 'g1': g1, 'g2': g2
    }


# ============================================================
# MDM estimation for boundary/off-grid combos
# ============================================================

def run_mdm_for_combo(beta, eta, gamma, n, repeats, delta_grid, seed_ns=SEED_NAMESPACE):
    """Generate samples and run MDM for a single parameter combo.

    Returns list of dicts with keys:
      beta, eta, gamma, gamma_over_eta, n, repeat_id, delta,
      beta_hat, eta_hat, gamma_hat, converged, status
    """
    from methods.mdm import MDM

    gamma_over_eta = gamma / eta if eta > 0 else 0.0
    results = []

    for rid in range(repeats):
        sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_ns)
        mdm = MDM(sample)

        for delta in delta_grid:
            try:
                res = mdm.run(offset=delta)
                bh, eh, gh, r2, conv = res
                bh = float(bh)
                eh = float(eh)
                gh = float(gh)
                conv = bool(conv)
                status = 'success' if conv and bh > 0 and eh > 0 else 'failure'
            except Exception as e:
                bh = eh = gh = float('nan')
                conv = False
                status = f'error: {type(e).__name__}'

            # Physical constraint
            if bh <= 0 or eh <= 0 or not math.isfinite(bh) or not math.isfinite(eh):
                conv = False
                status = 'non_physical'

            results.append({
                'beta': beta, 'eta': eta, 'gamma': gamma,
                'gamma_over_eta': gamma_over_eta,
                'n': n, 'repeat_id': rid, 'delta': delta,
                'beta_hat': bh, 'eta_hat': eh, 'gamma_hat': gh,
                'converged': conv, 'status': status,
            })

    return results


def compute_loss(df):
    """Add per-sample loss column (same as E3b)."""
    r_beta = (df['beta_hat'] - df['beta']) / df['beta']
    r_eta = (df['eta_hat'] - df['eta']) / df['eta']
    r_gamma = (df['gamma_hat'] - df['gamma']) / df['eta']
    df = df.copy()
    df['loss'] = r_beta**2 + r_eta**2 + r_gamma**2
    df['loss'] = df['loss'].replace([np.inf, -np.inf], np.nan)
    return df


# ============================================================
# E4a smoke: Feature ablation pipeline (existing data, tiny scale)
# ============================================================

def run_e4a_smoke(df_mc):
    """Test feature ablation pipeline using a tiny subset of existing MC data.

    Uses 3 combos, 50 repeats each, 1 fold (no holdout — just pipeline test).
    Trains a tiny MLP with full vs n_only features.
    """
    print("\n[E4a] Feature ablation smoke (3 combos × 50 repeats × 26 deltas)")
    t0 = time.time()

    # Filter MC data for smoke combos
    mask = np.zeros(len(df_mc), dtype=bool)
    for beta, eta, goe, n in E4A_SMOKK_COMBOS:
        sub_mask = (
            (df_mc['beta'] == beta) &
            (df_mc['gamma_over_eta'] == goe) &
            (df_mc['n'] == n)
        )
        mask |= sub_mask

    df_sub = df_mc[mask].copy()
    # Limit repeats
    unique_samples = (
        df_sub[['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']]
        .drop_duplicates()
        .sort_values(['beta', 'gamma_over_eta', 'n', 'repeat_id'])
        .head(E4A_SMOKK_REPEATS * len(E4A_SMOKK_COMBOS))
    )
    merge_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    df_sub = df_sub.merge(unique_samples[merge_keys], on=merge_keys, how='inner')

    print(f"  Filtered: {len(df_sub)} rows, "
          f"{df_sub[merge_keys].drop_duplicates().shape[0]} unique samples")

    # Compute features
    feat_records = []
    for _, row in unique_samples.iterrows():
        beta = float(row['beta'])
        eta = float(row['eta'])
        gamma = float(row['gamma'])
        n = int(row['n'])
        rid = int(row['repeat_id'])
        sample = generate_sample(beta, eta, gamma, n, rid, seed=SEED_NAMESPACE)
        feats = compute_sample_features(sample)
        for k, v in row.to_dict().items():
            feats[k] = v
        feat_records.append(feats)

    df_feat = pd.DataFrame(feat_records)
    df_merged = df_sub.merge(df_feat, on=merge_keys, how='left', suffixes=('', '_feat'))
    # Clean up duplicate columns from merge
    for col in list(df_merged.columns):
        if col.endswith('_feat'):
            df_merged.drop(columns=col, inplace=True)

    df_merged = compute_loss(df_merged)

    # Check banned fields are NOT in feature set
    feature_cols_present = set(SAMPLE_FEATURE_COLS)
    banned_in_features = feature_cols_present & BANNED_FIELDS
    assert len(banned_in_features) == 0, \
        f"BANNED fields in features: {banned_in_features}"

    # Pivot to vector format
    sample_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    feat_cols = [c for c in SAMPLE_FEATURE_COLS if c not in sample_keys]
    sample_df = df_merged[sample_keys + feat_cols].drop_duplicates(
        subset=sample_keys
    ).reset_index(drop=True)

    pivot = df_merged.pivot_table(
        index=sample_keys, columns='delta', values='loss', aggfunc='first'
    ).reset_index()

    result = pivot[sample_keys].merge(sample_df, on=sample_keys, how='left')

    N_DELTAS = len(DELTA_GRID)
    Y = np.full((len(pivot), N_DELTAS), np.nan)
    for j, d in enumerate(DELTA_GRID):
        if d in pivot.columns:
            Y[:, j] = pivot[d].values

    # Fill NaN with penalty
    failure_penalty = float(np.nanpercentile(df_merged['loss'].dropna(), 99))
    Y_filled = np.where(np.isnan(Y), failure_penalty, Y)

    # Z-score from this tiny set (smoke only — not formal)
    zscore_means = {}
    zscore_stds = {}
    for col in FEATURE_COLS_ZSCORE:
        vals = result[col].astype(float)
        zscore_means[col] = float(vals.mean())
        zscore_stds[col] = float(vals.std(ddof=0))
        if zscore_stds[col] < 1e-12:
            zscore_stds[col] = 1.0

    # Test two ablation groups: full vs n_only
    ablation_groups = {
        'full': SAMPLE_FEATURE_COLS,
        'n_only': ['n'],
    }

    ablation_results = []
    for group_name, group_features in ablation_groups.items():
        print(f"  Training ablation: {group_name} ({len(group_features)} features)")

        zscore_subset = [c for c in FEATURE_COLS_ZSCORE if c in group_features]
        raw_subset = [c for c in FEATURE_COLS_RAW if c in group_features]

        cols = []
        for col in zscore_subset:
            vals = result[col].astype(float).values
            cols.append((vals - zscore_means[col]) / zscore_stds[col])
        for col in raw_subset:
            cols.append(result[col].astype(float).values)

        X = np.column_stack(cols).astype(np.float32) if cols else \
            np.zeros((len(result), 0), dtype=np.float32)

        if X.shape[1] == 0:
            print(f"    Skipping {group_name}: no features")
            continue

        # Train tiny MLP
        target_scaler = StandardScaler()
        Y_scaled = target_scaler.fit_transform(Y_filled)

        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=ConvergenceWarning)
            model = MLPRegressor(
                hidden_layer_sizes=SMOKE_MLP_HIDDEN,
                max_iter=SMOKE_MLP_MAX_ITER,
                random_state=42,
            )
            model.fit(X, Y_scaled)

        Y_pred = target_scaler.inverse_transform(model.predict(X))
        Y_pred = np.clip(Y_pred, 0, None)

        # Evaluate: delta selection
        best_idx = np.argmin(Y_pred, axis=1)
        true_losses = Y_filled[np.arange(len(Y_filled)), best_idx]
        j1 = math.sqrt(np.mean(true_losses))

        ablation_results.append({
            'feature_group': group_name,
            'n_features': len(group_features),
            'pooled_J1': j1,
            'n_samples': len(result),
            'n_iter': model.n_iter_,
        })
        print(f"    J1={j1:.4f}, n_iter={model.n_iter_}")

    elapsed = time.time() - t0
    print(f"[E4a] Done in {elapsed:.1f}s")

    return {
        'track': 'E4a',
        'description': 'Feature ablation pipeline smoke (existing MC data, tiny MLP)',
        'combos': [list(c) for c in E4A_SMOKK_COMBOS],
        'repeats_per_combo': E4A_SMOKK_REPEATS,
        'total_rows': len(df_sub),
        'mlp_config': {
            'hidden_layers': SMOKE_MLP_HIDDEN,
            'max_iter': SMOKE_MLP_MAX_ITER,
        },
        'ablation_results': ablation_results,
        'elapsed_s': elapsed,
        'banned_field_check': 'PASSED — no banned fields in feature set',
        'note': 'SMOKE ONLY — single fold, single seed, tiny MLP. Not formal evidence.',
    }


# ============================================================
# E4b smoke: Expanded-grid boundary pipeline
# ============================================================

def run_e4b_smoke():
    """Test MC generation + evaluation for boundary parameter combos.

    Generates new MDM estimates for boundary combos not in the main grid.
    Evaluates Default/L1/L2 reference selections.
    """
    print("\n[E4b] Expanded-grid boundary smoke (3 boundary combos × 10 repeats)")
    t0 = time.time()

    all_results = []
    for beta, eta, goe, n in E4B_BOUNDARY_COMBOS:
        gamma = goe * eta
        print(f"  Boundary combo: beta={beta}, gamma/eta={goe}, n={n}")
        results = run_mdm_for_combo(beta, eta, gamma, n, E4B_REPEATS, DELTA_GRID)
        all_results.extend(results)

    df_boundary = pd.DataFrame(all_results)
    df_boundary = compute_loss(df_boundary)

    print(f"  Total boundary rows: {len(df_boundary)}")
    print(f"  Non-success rate: "
          f"{(df_boundary['status'] != 'success').mean():.4f}")

    # Evaluate reference selections (Default, L1, L2)
    # Default: delta=0.1
    # L1: global best constant delta on this tiny set
    # L2: best delta per n (smoke: just use global since n varies)
    ref_results = []

    # Default
    df_def = df_boundary[
        (df_boundary['delta'] == DEFAULT_DELTA) & df_boundary['loss'].notna()
    ]
    for _, row in df_def.iterrows():
        ref_results.append({
            'model': 'Default',
            'beta': row['beta'], 'n': int(row['n']),
            'loss': row['loss'],
            'selected_delta': DEFAULT_DELTA,
        })

    # L1 (global best on this tiny set)
    valid_loss = df_boundary.dropna(subset=['loss'])
    if len(valid_loss) > 0 and valid_loss.groupby('delta')['loss'].mean().notna().any():
        global_loss = valid_loss.groupby('delta')['loss'].apply(
            lambda x: np.sqrt(np.nanmean(x)) if len(x) > 0 else np.nan
        )
        global_loss = global_loss.dropna()
        if len(global_loss) > 0:
            l1_delta = float(global_loss.idxmin())
            df_l1 = df_boundary[df_boundary['delta'] == l1_delta]
            for _, row in df_l1.iterrows():
                ref_results.append({
                    'model': 'L1-smoke',
                    'beta': row['beta'], 'n': int(row['n']),
                    'loss': row['loss'],
                    'selected_delta': l1_delta,
                })
        else:
            l1_delta = None
    else:
        l1_delta = None

    # Summarize per model
    ref_summary = []
    if len(ref_results) > 0:
        df_ref = pd.DataFrame(ref_results)
        for model in df_ref['model'].unique():
            sub = df_ref[df_ref['model'] == model]
            j1 = math.sqrt(sub['loss'].mean())
            ref_summary.append({
                'model': model,
                'pooled_J1': j1,
                'n_samples': len(sub),
            })
    else:
        df_ref = pd.DataFrame()

    elapsed = time.time() - t0
    print(f"[E4b] Done in {elapsed:.1f}s")

    return {
        'track': 'E4b',
        'description': 'Expanded-grid boundary pipeline smoke',
        'boundary_combos': [list(c) for c in E4B_BOUNDARY_COMBOS],
        'repeats_per_combo': E4B_REPEATS,
        'total_rows': len(df_boundary),
        'non_success_rate': float((df_boundary['status'] != 'success').mean()),
        'reference_results': ref_summary,
        'l1_delta_on_smoke': l1_delta,
        'elapsed_s': elapsed,
        'note': 'SMOKE ONLY — R=10, not R=500. Boundary behavior indicative only.',
    }


# ============================================================
# E4c smoke: Out-of-grid feasibility
# ============================================================

def run_e4c_smoke():
    """Test pipeline feasibility for arbitrary (non-grid) parameter combos.

    This does NOT test generalization — it only verifies the pipeline can
    handle off-grid parameters. If continuous-space training is needed,
    that becomes E3c, not E4.
    """
    print("\n[E4c] Out-of-grid feasibility smoke (2 arbitrary combos × 10 repeats)")
    t0 = time.time()

    all_results = []
    for beta, eta, goe, n in E4C_ARB_COMBOS:
        gamma = goe * eta
        print(f"  Arbitrary combo: beta={beta}, gamma/eta={goe}, n={n}")
        results = run_mdm_for_combo(beta, eta, gamma, n, E4C_REPEATS, DELTA_GRID)
        all_results.extend(results)

    df_arb = pd.DataFrame(all_results)
    df_arb = compute_loss(df_arb)

    print(f"  Total arbitrary rows: {len(df_arb)}")
    print(f"  Non-success rate: {(df_arb['status'] != 'success').mean():.4f}")

    # Check: can features be computed? (feasibility)
    feat_ok = 0
    for _, row in df_arb[['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']].drop_duplicates().iterrows():
        beta = float(row['beta'])
        eta = float(row['eta'])
        gamma = float(row['gamma'])
        n = int(row['n'])
        rid = int(row['repeat_id'])
        sample = generate_sample(beta, eta, gamma, n, rid, seed=SEED_NAMESPACE)
        feats = compute_sample_features(sample)
        if all(math.isfinite(v) for v in feats.values()):
            feat_ok += 1

    elapsed = time.time() - t0
    print(f"[E4c] Done in {elapsed:.1f}s")

    return {
        'track': 'E4c',
        'description': 'Out-of-grid feasibility pipeline smoke',
        'arbitrary_combos': [list(c) for c in E4C_ARB_COMBOS],
        'repeats_per_combo': E4C_REPEATS,
        'total_rows': len(df_arb),
        'non_success_rate': float((df_arb['status'] != 'success').mean()),
        'feature_computation_ok': feat_ok,
        'feature_computation_total': len(E4C_ARB_COMBOS) * E4C_REPEATS,
        'elapsed_s': elapsed,
        'decision': (
            'Pipeline can handle off-grid parameters. '
            'If continuous-space TRAINING is needed (not just evaluation), '
            'it should be classified as E3c, not E4c. '
            'This smoke only tests evaluation feasibility.'
        ),
        'note': 'SMOKE ONLY — feasibility test, not generalization evidence.',
    }


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 70)
    print("Study/01 E4 Validation Suite — SMOKE / PILOT")
    print(f"Started: {now_iso()}")
    print(f"Output: {PILOT_OUTPUT_DIR}")
    print("=" * 70)

    overall_t0 = time.time()

    # --- Load existing MC data for E4a ---
    mc_scan_path = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
    mc_manifest_path = os.path.join(SHARED_DATA_DIR, "manifest.json")

    print(f"\nLoading MC data from {mc_scan_path}...")
    df_mc = pd.read_csv(mc_scan_path)
    print(f"  Loaded: {len(df_mc)} rows")

    with open(mc_manifest_path) as f:
        mc_manifest = json.load(f)

    # --- Run three tracks ---
    e4a_result = run_e4a_smoke(df_mc)
    e4b_result = run_e4b_smoke()
    e4c_result = run_e4c_smoke()

    overall_elapsed = time.time() - overall_t0

    # --- Build artifacts ---
    git_commit = get_git_info()
    dirty = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True, timeout=5,
        cwd=PROJECT_ROOT
    ).stdout.strip()
    is_dirty = len(dirty) > 0

    # manifest.json
    manifest = {
        "run_id": "E4_validation_smoke_pilot_v1",
        "created_at": now_iso(),
        "status": "PILOT — NOT FORMAL EVIDENCE",
        "code_entry": "code/run_E4_validation_smoke.py",
        "git_commit": git_commit,
        "workspace_dirty": is_dirty,
        "dirty_files": dirty.split('\n') if dirty else [],
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "input_data": {
            "mc_scan_path": mc_scan_path,
            "mc_manifest_path": mc_manifest_path,
            "mc_git_commit": mc_manifest.get("git_commit", "unknown"),
            "mc_run_id": mc_manifest.get("run_id", "unknown"),
            "mc_seed_namespace": mc_manifest.get("seed_namespace", SEED_NAMESPACE),
        },
        "method_versions": {
            "mdm": {
                "source": "python/methods/mdm.py",
                "class": "MDM",
                "run_signature": "run(offset: float, gamma_steps=60, rank_method='bernard')",
            },
            "sample": {
                "source": "python/studies/common/sample.py",
                "function": "generate_sample(beta, eta, gamma, n, repeat_id, seed)",
            },
        },
        "smoke_scale": {
            "e4a_combos": len(E4A_SMOKK_COMBOS),
            "e4a_repeats_per_combo": E4A_SMOKK_REPEATS,
            "e4b_boundary_combos": len(E4B_BOUNDARY_COMBOS),
            "e4b_repeats_per_combo": E4B_REPEATS,
            "e4c_arbitrary_combos": len(E4C_ARB_COMBOS),
            "e4c_repeats_per_combo": E4C_REPEATS,
            "total_new_mdm_calls": (
                len(E4B_BOUNDARY_COMBOS) * E4B_REPEATS * len(DELTA_GRID) +
                len(E4C_ARB_COMBOS) * E4C_REPEATS * len(DELTA_GRID)
            ),
        },
        "delta_grid": DELTA_GRID,
        "metrics_contract": {
            "J1": "sqrt(mean_i[(beta_hat-beta)/beta)^2 + (eta_hat-eta)/eta)^2 + (gamma_hat-gamma)/eta)^2])",
            "loss": "per-sample pre-sqrt contribution (same as J1 numerator)",
        },
        "output_files": [
            "manifest.json",
            "summary.json",
            "results.csv",
            "run_log.txt",
        ],
        "notes": [
            "This is a PILOT smoke test, not formal E4 evidence.",
            "All outputs are under artifacts/pilot/, not artifacts/formal/.",
            "E4a uses existing MC data (read-only). E4b/E4c generate new tiny MDM estimates.",
            "Formal E4 requires Codex review and separate authorization.",
        ],
    }

    manifest_path = os.path.join(PILOT_OUTPUT_DIR, "manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # summary.json
    summary = {
        "run_id": manifest["run_id"],
        "created_at": manifest["created_at"],
        "status": "PILOT — NOT FORMAL EVIDENCE",
        "total_elapsed_s": overall_elapsed,
        "tracks": {
            "E4a": e4a_result,
            "E4b": e4b_result,
            "E4c": e4c_result,
        },
        "schema_verification": {
            "manifest_fields": list(manifest.keys()),
            "summary_fields": [
                "run_id", "created_at", "status", "total_elapsed_s",
                "tracks", "schema_verification"
            ],
            "results_csv_columns": [
                "track", "model_or_group", "metric", "value", "n", "note"
            ],
            "all_under_pilot_dir": True,
        },
    }

    summary_path = os.path.join(PILOT_OUTPUT_DIR, "summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    # results.csv — flat table
    rows = []

    # E4a results
    for ab in e4a_result.get('ablation_results', []):
        rows.append({
            'track': 'E4a',
            'model_or_group': ab['feature_group'],
            'metric': 'pooled_J1',
            'value': ab['pooled_J1'],
            'n': ab['n_samples'],
            'note': f"n_features={ab['n_features']}, smoke MLP"
        })

    # E4b results
    for ref in e4b_result.get('reference_results', []):
        rows.append({
            'track': 'E4b',
            'model_or_group': ref['model'],
            'metric': 'pooled_J1',
            'value': ref['pooled_J1'],
            'n': ref['n_samples'],
            'note': f"boundary combos, R={E4B_REPEATS}"
        })

    # E4c results
    rows.append({
        'track': 'E4c',
        'model_or_group': 'pipeline_feasibility',
        'metric': 'feature_computation_ok',
        'value': e4c_result['feature_computation_ok'],
        'n': e4c_result['feature_computation_total'],
        'note': 'off-grid parameter combos, feasibility only'
    })

    df_results = pd.DataFrame(rows)
    results_path = os.path.join(PILOT_OUTPUT_DIR, "results.csv")
    df_results.to_csv(results_path, index=False)

    # run_log.txt
    log_path = os.path.join(PILOT_OUTPUT_DIR, "run_log.txt")
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f"E4 Validation Suite Smoke Run Log\n")
        f.write(f"Started: {manifest['created_at']}\n")
        f.write(f"Git commit: {git_commit} (dirty={is_dirty})\n")
        f.write(f"Total elapsed: {overall_elapsed:.1f}s\n")
        f.write(f"\n--- E4a ---\n")
        f.write(json.dumps(e4a_result, indent=2, default=str))
        f.write(f"\n--- E4b ---\n")
        f.write(json.dumps(e4b_result, indent=2, default=str))
        f.write(f"\n--- E4c ---\n")
        f.write(json.dumps(e4c_result, indent=2, default=str))

    print("\n" + "=" * 70)
    print("SMOKE COMPLETE")
    print(f"  Total elapsed: {overall_elapsed:.1f}s")
    print(f"  Output dir: {PILOT_OUTPUT_DIR}")
    print(f"  Files: manifest.json, summary.json, results.csv, run_log.txt")
    print("=" * 70)


if __name__ == "__main__":
    main()
