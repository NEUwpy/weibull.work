"""
Study/01 — Delta Upper-Bound Sensitivity Audit (R2)

Targeted audit per frozen contract 07-剩余实验目标与规划.md §4.2:

  - Preserve original 0.00-0.50 grid products unchanged.
  - Extension grid: 0.52-1.00, step 0.02 (25 new deltas).
  - Primary cohort: samples whose hindsight best delta = 0.50.
  - Auxiliary cohort: samples whose hindsight best delta = 0.48.
  - All improvement claims are conditioned on "original optimal was 0.50"
    (or 0.48) — never generalised to the full population.

Inputs:
  - Authoritative main-grid MC chunks (existing 0.00-0.50 cache)
  - Production MDM method (python/methods/mdm.py)
  - Frozen config (DELTA_GRID, BETA_GRID, etc.)

Outputs:
  - artifacts/formal/delta_upper_bound_audit/
    extended_results.csv       per-sample MDM results for 0.52-1.00
    merged_curves.csv           original (0.00-0.50) + extended per sample
    cohort_summary.csv          per-cohort migration & regret summary
    manifest.json
    run_log.txt
"""

import sys
import os
import json
import hashlib
import time
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# Path setup
STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

from config import (
    BETA_GRID, ETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID,
    DELTA_GRID, DEFAULT_DELTA, R_MAIN, SEED_NAMESPACE,
    ARTIFACTS_DIR, SHARED_DATA_DIR,
)
from utils import now_iso
from studies.common.sample import generate_sample

# MDM method
from methods.mdm import MDM

# ── Constants ──
EXTENSION_START = 0.52
EXTENSION_END = 1.00
EXTENSION_STEP = 0.02
EXTENSION_GRID = [
    round(EXTENSION_START + EXTENSION_STEP * i, 2)
    for i in range(int((EXTENSION_END - EXTENSION_START) / EXTENSION_STEP) + 1)
]  # [0.52, 0.54, ..., 1.00]

TARGET_COHORT_DELTAS = [0.50, 0.48]  # order: primary first

OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "delta_upper_bound_audit")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MAIN_CHUNKS_DIR = os.path.join(SHARED_DATA_DIR, "chunks")
MC_MANIFEST_PATH = os.path.join(SHARED_DATA_DIR, "manifest.json")

log_lines = []


def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    log_lines.append(line)


def sha256_file(path):
    """Streaming SHA256 digest."""
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def load_mc_chunks():
    """Load all 45 authoritative main-grid MC chunks."""
    chunk_files = sorted(
        os.path.join(MAIN_CHUNKS_DIR, f)
        for f in os.listdir(MAIN_CHUNKS_DIR)
        if f.startswith("chunk_") and f.endswith("_mdm.csv")
    )
    if len(chunk_files) != 45:
        raise RuntimeError(
            f"Expected 45 MDM chunks, found {len(chunk_files)}"
        )
    frames = []
    for cf in chunk_files:
        df = pd.read_csv(cf)
        frames.append(df)
    df_all = pd.concat(frames, ignore_index=True, sort=False)
    log(f"Loaded {len(df_all)} rows from {len(chunk_files)} chunks")
    return df_all, chunk_files


def compute_loss(df):
    """Standard Study01 loss from relative errors."""
    r_beta = (df['beta_hat'] - df['beta']) / df['beta']
    r_eta = (df['eta_hat'] - df['eta']) / df['eta']
    r_gamma = (df['gamma_hat'] - df['gamma']) / df['eta']
    df = df.copy()
    df['loss'] = r_beta**2 + r_eta**2 + r_gamma**2
    df['loss'] = df['loss'].replace([np.inf, -np.inf], np.nan)
    return df


def identify_cohort_samples(df_mc_loss):
    """Return sample-keys for the primary (delta=0.50) and auxiliary (0.48)
    cohorts from the existing 0.00-0.50 grid cache.

    For each sample, the hindsight-best delta is the one with minimum true loss
    in the existing grid. Samples where that minimum is at delta=0.50 form the
    primary cohort; samples at delta=0.48 form the auxiliary cohort.
    """
    sample_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    df_valid = df_mc_loss.dropna(subset=['loss'])
    if len(df_valid) == 0:
        return {}, {}, None

    # Per-sample best delta in the existing 0.00-0.50 grid
    best_per_sample = (
        df_valid.groupby(sample_keys)
        .apply(lambda g: g.loc[g['loss'].idxmin(), 'delta'], include_groups=False)
        .reset_index(name='best_delta')
    )

    cohorts = {}
    for target_delta in TARGET_COHORT_DELTAS:
        cohort = best_per_sample[
            np.isclose(best_per_sample['best_delta'], target_delta)
        ]
        cohort_keys = set(
            tuple(row[col] for col in sample_keys)
            for _, row in cohort.iterrows()
        )
        cohorts[target_delta] = cohort_keys
        log(
            f"  Cohort δ={target_delta}: {len(cohort_keys)} samples "
            f"({len(cohort_keys) / max(len(best_per_sample), 1) * 100:.1f}%)"
        )
    return cohorts, best_per_sample


def run_mdm_for_sample(sample, delta):
    """Run the production MDM on one sample for one delta value.

    Returns a dict with parameter estimates and convergence info, or
    failure/skip flags with NaN estimates.
    """
    result = {
        'delta': delta, 'beta_hat': np.nan, 'eta_hat': np.nan,
        'gamma_hat': np.nan, 'r_squared': np.nan, 'converged': False,
        'time_ms': np.nan, 'status': 'failure',
    }
    try:
        mdm = MDM(sample)
        t0 = time.perf_counter()
        mdm_result = mdm.run(offset=delta)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        result.update({
            'beta_hat': float(mdm_result.get('beta', np.nan)),
            'eta_hat': float(mdm_result.get('eta', np.nan)),
            'gamma_hat': float(mdm_result.get('gamma', np.nan)),
            'r_squared': float(mdm_result.get('r_squared', np.nan)),
            'converged': bool(mdm_result.get('converged', False)),
            'time_ms': elapsed_ms,
            'status': 'success',
        })
    except Exception as exc:
        result['status'] = f'error:{type(exc).__name__}'
    return result


def run_extended_mdm(cohort_keys, seed_ns=SEED_NAMESPACE):
    """Run MDM for cohort samples on the extended delta grid (0.52-1.00).

    Returns a DataFrame with the same column schema as the authoritative MC
    chunks, plus a 'cohort' column identifying the target delta.
    """
    if not cohort_keys:
        return pd.DataFrame()

    sample_keys = sorted(cohort_keys)
    total_runs = len(sample_keys) * len(EXTENSION_GRID)
    log(f"  Running MDM for {len(sample_keys)} samples × "
        f"{len(EXTENSION_GRID)} deltas = {total_runs} runs...")

    rows = []
    t0 = time.time()
    sample_cols = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']

    for idx, key_tuple in enumerate(sample_keys):
        sample_dict = dict(zip(sample_cols, key_tuple))
        beta = float(sample_dict['beta'])
        eta = float(sample_dict['eta'])
        gamma = float(sample_dict['gamma'])
        n_val = int(sample_dict['n'])
        rid = int(sample_dict['repeat_id'])

        # Generate deterministic sample
        sample = generate_sample(beta, eta, gamma, n_val, rid, seed=seed_ns)

        for delta in EXTENSION_GRID:
            result = run_mdm_for_sample(sample, delta)
            row = {
                'beta': beta, 'eta': eta, 'gamma': gamma,
                'gamma_over_eta': sample_dict['gamma_over_eta'],
                'n': n_val, 'repeat_id': rid,
                **result,
            }
            rows.append(row)

        if (idx + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = (idx + 1) * len(EXTENSION_GRID) / elapsed
            eta_s = (len(sample_keys) - idx - 1) * len(EXTENSION_GRID) / rate
            log(f"    Progress: {idx + 1}/{len(sample_keys)} samples "
                f"({rate:.0f} runs/s, ETA {eta_s:.0f}s)")

    elapsed = time.time() - t0
    log(f"  Completed {len(rows)} runs in {elapsed:.1f}s "
        f"({total_runs / elapsed:.1f} runs/s)")
    return pd.DataFrame(rows)


def merge_and_analyze(df_original, df_extended, cohort_delta, best_per_sample):
    """Merge original 0.00-0.50 cache with extended results, then compute
    per-sample migration and regret statistics.

    All claims are conditioned on the original best delta being *cohort_delta*.
    """
    sample_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']

    # Filter original to cohort samples only
    cohort_mask = np.isclose(
        best_per_sample['best_delta'], cohort_delta
    )
    cohort_best = best_per_sample[cohort_mask]
    cohort_key_set = set(
        tuple(row[col] for col in sample_keys)
        for _, row in cohort_best.iterrows()
    )

    # Only keep original rows for cohort samples
    df_orig_cohort = df_original[
        df_original.apply(
            lambda r: (float(r.beta), float(r.eta), float(r.gamma),
                       float(r.gamma_over_eta), int(r.n), int(r.repeat_id))
            in cohort_key_set,
            axis=1,
        )
    ].copy()

    # Combine
    common_cols = [
        'beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id',
        'delta', 'beta_hat', 'eta_hat', 'gamma_hat',
        'r_squared', 'converged', 'time_ms', 'status',
    ]
    df_combined = pd.concat(
        [
            df_orig_cohort[common_cols],
            df_extended[common_cols],
        ],
        ignore_index=True, sort=False,
    )

    # Compute loss
    df_combined = compute_loss(df_combined)
    df_valid = df_combined.dropna(subset=['loss'])

    # Per-sample analysis
    results = []
    for key_tuple in sorted(cohort_key_set):
        sample_dict = dict(zip(sample_keys, key_tuple))
        beta = float(sample_dict['beta'])
        eta = float(sample_dict['eta'])
        gamma = float(sample_dict['gamma'])
        goe = float(sample_dict['gamma_over_eta'])
        n_val = int(sample_dict['n'])
        rid = int(sample_dict['repeat_id'])

        sample_mask = (
            (df_valid['beta'] == beta) &
            np.isclose(df_valid['gamma_over_eta'], goe) &
            (df_valid['n'] == n_val) &
            (df_valid['repeat_id'] == rid)
        )
        sample_df = df_valid[sample_mask]

        # Original best (constrained to 0.00-0.50)
        orig_mask = sample_df['delta'] <= 0.50
        if orig_mask.sum() == 0:
            continue
        orig_best_idx = sample_df.loc[orig_mask, 'loss'].idxmin()
        orig_best_delta = float(sample_df.loc[orig_best_idx, 'delta'])
        orig_best_loss = float(sample_df.loc[orig_best_idx, 'loss'])

        # Extended best (all deltas 0.00-1.00)
        extended_best_idx = sample_df['loss'].idxmin()
        extended_best_delta = float(sample_df.loc[extended_best_idx, 'delta'])
        extended_best_loss = float(sample_df.loc[extended_best_idx, 'loss'])

        migrated = extended_best_delta > 0.50
        loss_improvement = orig_best_loss - extended_best_loss

        results.append({
            'beta': beta, 'gamma_over_eta': goe, 'n': n_val,
            'repeat_id': rid,
            'cohort_delta': cohort_delta,
            'orig_best_delta': orig_best_delta,
            'orig_best_loss': orig_best_loss,
            'extended_best_delta': extended_best_delta,
            'extended_best_loss': extended_best_loss,
            'migrated': migrated,
            'loss_improvement': loss_improvement,
            'rel_improvement': (
                loss_improvement / orig_best_loss
                if orig_best_loss > 1e-12 else 0.0
            ),
        })

    df_results = pd.DataFrame(results)
    return df_results


def summarize_cohort(df_results, cohort_delta):
    """Compute cohort-level summary statistics."""
    if len(df_results) == 0:
        return {'cohort_delta': cohort_delta, 'n_samples': 0}

    n_migrated = int(df_results['migrated'].sum())
    n_total = len(df_results)
    migration_rate = n_migrated / n_total if n_total > 0 else 0.0

    migrated_df = df_results[df_results['migrated']]
    non_migrated_df = df_results[~df_results['migrated']]

    summary = {
        'cohort_delta': cohort_delta,
        'n_samples': n_total,
        'n_migrated': int(n_migrated),
        'migration_rate': migration_rate,
        'mean_loss_improvement': float(df_results['loss_improvement'].mean()),
        'mean_rel_improvement': float(df_results['rel_improvement'].mean()),
        'median_loss_improvement': float(
            df_results['loss_improvement'].median()
        ),
    }

    if n_migrated > 0:
        summary.update({
            'migrated_mean_new_delta': float(
                migrated_df['extended_best_delta'].mean()
            ),
            'migrated_median_new_delta': float(
                migrated_df['extended_best_delta'].median()
            ),
            'migrated_mean_loss_improvement': float(
                migrated_df['loss_improvement'].mean()
            ),
        })

    # Distribution of new best deltas
    delta_counts = (
        df_results['extended_best_delta']
        .value_counts()
        .sort_index()
        .to_dict()
    )
    summary['extended_best_delta_distribution'] = {
        str(k): int(v) for k, v in sorted(delta_counts.items())
    }

    return summary


def main():
    log("=" * 70)
    log("Study/01 Delta Upper-Bound Sensitivity Audit (R2)")
    log(f"Started: {now_iso()}")
    log(f"Output: {OUTPUT_DIR}")
    log(f"Extension grid: {EXTENSION_GRID[0]}–{EXTENSION_GRID[-1]} "
        f"(step {EXTENSION_STEP}, {len(EXTENSION_GRID)} points)")
    log("=" * 70)

    # ── 1. Identify cohorts ──
    log("Step 1: Loading MC chunks and identifying cohorts...")
    df_mc, chunk_files = load_mc_chunks()
    df_mc_loss = compute_loss(df_mc)
    cohorts, best_per_sample = identify_cohort_samples(df_mc_loss)

    if not cohorts:
        log("ERROR: No cohort samples identified")
        return

    # ── 2. Hash sample key sets (before viewing extended results) ──
    log("Step 2: Hashing cohort sample key sets...")
    sample_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    cohort_hashes = {}
    for delta, keys in cohorts.items():
        frozen = sorted(
            [float(k[0]), float(k[1]), float(k[2]), float(k[3]),
             int(k[4]), int(k[5])]
            for k in keys
        )
        cohort_hashes[str(delta)] = sha256_bytes(
            json.dumps(frozen, sort_keys=True).encode()
        )
        log(f"  Cohort δ={delta}: SHA256={cohort_hashes[str(delta)]}")

    # ── 3. Run extended MDM ──
    log("Step 3: Running MDM on extended delta grid...")
    all_extended = []
    for target_delta in TARGET_COHORT_DELTAS:
        keys = cohorts.get(target_delta, set())
        if not keys:
            log(f"  Skipping cohort δ={target_delta} (no samples)")
            continue
        log(f"  Processing cohort δ={target_delta} "
            f"({len(keys)} samples)...")
        df_ext = run_extended_mdm(keys)
        df_ext['cohort'] = target_delta
        all_extended.append(df_ext)

    if all_extended:
        df_extended_all = pd.concat(all_extended, ignore_index=True, sort=False)
    else:
        df_extended_all = pd.DataFrame()

    # ── 4. Save extended results ──
    ext_path = os.path.join(OUTPUT_DIR, "extended_results.csv")
    if len(df_extended_all) > 0:
        df_extended_all.to_csv(ext_path, index=False)
        log(f"  Saved: {ext_path} ({len(df_extended_all)} rows)")
    else:
        log("  WARNING: No extended results produced")

    # ── 5. Merge and analyze per cohort ──
    log("Step 4: Merging and analyzing per-cohort...")
    all_cohort_results = []
    cohort_summaries = []

    for target_delta in TARGET_COHORT_DELTAS:
        keys = cohorts.get(target_delta, set())
        if not keys:
            continue
        df_ext_cohort = df_extended_all[
            df_extended_all['cohort'] == target_delta
        ] if len(df_extended_all) > 0 else pd.DataFrame()

        df_cohort = merge_and_analyze(
            df_mc_loss, df_ext_cohort, target_delta, best_per_sample
        )

        if len(df_cohort) > 0:
            all_cohort_results.append(df_cohort)

        summary = summarize_cohort(df_cohort, target_delta)
        cohort_summaries.append(summary)

        log(
            f"  Cohort δ={target_delta}: "
            f"migration={summary.get('migration_rate', 0):.1%} "
            f"({summary.get('n_migrated', 0)}/{summary.get('n_samples', 0)}), "
            f"mean improvement={summary.get('mean_loss_improvement', 0):.6f}"
        )

    # ── 6. Save merged results ──
    if all_cohort_results:
        df_merged = pd.concat(all_cohort_results, ignore_index=True, sort=False)
        merged_path = os.path.join(OUTPUT_DIR, "merged_curves.csv")
        df_merged.to_csv(merged_path, index=False)
        log(f"  Saved: {merged_path} ({len(df_merged)} rows)")

    # ── 7. Save cohort summary ──
    if cohort_summaries:
        summary_path = os.path.join(OUTPUT_DIR, "cohort_summary.csv")
        pd.DataFrame(cohort_summaries).to_csv(summary_path, index=False)
        log(f"  Saved: {summary_path}")

    # ── 8. Save manifest ──
    manifest = {
        "experiment": "delta_upper_bound_audit",
        "created_at": now_iso(),
        "extension_grid": EXTENSION_GRID,
        "original_grid": DELTA_GRID,
        "target_cohorts": TARGET_COHORT_DELTAS,
        "cohort_hashes": cohort_hashes,
        "input_chunks": {
            "count": len(chunk_files),
            "sha256": sha256_bytes(
                b"".join(
                    sha256_file(cf).encode() for cf in sorted(chunk_files)
                )
            ),
        },
        "contract": (
            "All improvement claims are conditional on the original "
            "best delta being in the target cohort. No whole-grid "
            "sufficiency claims are supported without a full "
            "population extension."
        ),
    }
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, sort_keys=True,
                  ensure_ascii=False)

    # ── 9. Save run log ──
    log_path = os.path.join(OUTPUT_DIR, "run_log.txt")
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines) + '\n')
    log(f"  Saved: {log_path}")

    log("=" * 70)
    log("Delta upper-bound audit complete.")
    log(f"Output directory: {OUTPUT_DIR}")
    log("=" * 70)


if __name__ == '__main__':
    main()
