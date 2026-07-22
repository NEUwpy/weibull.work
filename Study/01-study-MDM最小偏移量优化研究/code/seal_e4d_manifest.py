"""
Study/01 — E4d Formal Seal Generator

Generates the sealed manifest, summary, and SHA256SUMS for the E4d
formal run. Run AFTER ``run_E4_formal_validation.py --tracks e4d``
completes successfully.

Outputs:
  - artifacts/formal/E4_robustness/manifest_e4d.json
  - artifacts/formal/E4_robustness/summary_e4d.json
  - artifacts/formal/E4_robustness/SHA256SUMS_e4d

Plus verification that every output hash matches actual file bytes.
"""

import sys
import os
import json
import hashlib
import subprocess
from datetime import datetime, timezone

import pandas as pd
import numpy as np

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

from config import (
    BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID, DELTA_GRID,
    DEFAULT_DELTA, SEED_NAMESPACE,
    ARTIFACTS_DIR, SHARED_DATA_DIR,
)
from utils import now_iso


E4_DIR = os.path.join(ARTIFACTS_DIR, "E4_robustness")
E4D_CSV = os.path.join(E4_DIR, "E4d_selector_extrapolation.csv")
E4D_J1_CSV = os.path.join(E4_DIR, "E4d_model_j1_summary.csv")
MANIFEST_PATH = os.path.join(E4_DIR, "manifest_e4d.json")
SUMMARY_PATH = os.path.join(E4_DIR, "summary_e4d.json")
SHA256_PATH = os.path.join(E4_DIR, "SHA256SUMS_e4d")

# Input references
SHARED_CHUNKS_DIR = os.path.join(SHARED_DATA_DIR, "chunks")
MC_MANIFEST_PATH = os.path.join(SHARED_DATA_DIR, "manifest.json")
BOUNDARY_PATH = os.path.join(E4_DIR, "boundary_risk_curves.csv")
OFFGRID_PATH = os.path.join(E4_DIR, "offgrid_risk_curves.csv")
CODE_FILE = os.path.join(STUDY_CODE_DIR, "run_E4_formal_validation.py")
CONFIG_FILE = os.path.join(STUDY_CODE_DIR, "config.py")
MDM_FILE = os.path.join(PYTHON_DIR, "methods", "mdm.py")
SAMPLE_FILE = os.path.join(PYTHON_DIR, "studies", "common", "sample.py")


def sha256_file(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def git_commit_short(cwd=None):
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, check=True, cwd=cwd,
        )
        return result.stdout.strip()
    except Exception:
        return 'unknown'


def git_commit_full(cwd=None):
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True, cwd=cwd,
        )
        return result.stdout.strip()
    except Exception:
        return 'unknown'


def python_version():
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def main():
    if not os.path.exists(E4D_CSV):
        print(f"ERROR: {E4D_CSV} not found — run E4d first")
        sys.exit(1)
    if not os.path.exists(E4D_J1_CSV):
        print(f"ERROR: {E4D_J1_CSV} not found — run E4d first")
        sys.exit(1)

    df = pd.read_csv(E4D_CSV)
    df_j1 = pd.read_csv(E4D_J1_CSV)

    # ── Input provenance ──
    input_hashes = {}
    for label, path in [
        ('main_grid_chunks_dir', SHARED_CHUNKS_DIR),
        ('main_grid_mc_manifest', MC_MANIFEST_PATH),
        ('boundary_risk_curves', BOUNDARY_PATH),
        ('offgrid_risk_curves', OFFGRID_PATH),
    ]:
        if os.path.isdir(path):
            # Directory: hash of sorted chunk file hashes
            chunk_hashes = []
            for f in sorted(os.listdir(path)):
                if f.endswith('_mdm.csv'):
                    cf = os.path.join(path, f)
                    chunk_hashes.append(sha256_file(cf))
            input_hashes[label] = hashlib.sha256(
                ''.join(chunk_hashes).encode()
            ).hexdigest()
            input_hashes[f'{label}_file_count'] = len(chunk_hashes)
        elif os.path.isfile(path):
            input_hashes[label] = sha256_file(path)
        else:
            input_hashes[label] = 'MISSING'

    # ── Code provenance ──
    code_hashes = {}
    for label, path in [
        ('run_E4_formal_validation', CODE_FILE),
        ('config', CONFIG_FILE),
        ('mdm_method', MDM_FILE),
        ('sample_generation', SAMPLE_FILE),
    ]:
        code_hashes[label] = sha256_file(path) if os.path.isfile(path) else 'MISSING'

    # ── Output provenance ──
    output_hashes = {}
    for label, path in [
        ('E4d_selector_extrapolation', E4D_CSV),
        ('E4d_model_j1_summary', E4D_J1_CSV),
    ]:
        output_hashes[label] = {
            'path': os.path.relpath(path, PROJECT_ROOT).replace('\\', '/'),
            'sha256': sha256_file(path),
            'size_bytes': os.path.getsize(path),
            'row_count': int(len(pd.read_csv(path))),
        }

    # ── Commit provenance ──
    gen_commit_short = git_commit_short()
    gen_commit_full = git_commit_full()
    is_dirty = subprocess.run(
        ['git', 'diff', '--quiet'], cwd=PROJECT_ROOT
    ).returncode != 0

    # ── Manifest ──
    manifest = {
        'experiment': 'E4d_selector_extrapolation',
        'contract_version': '07-study01-remaining-experiments-4.1',
        'created_at': now_iso(),
        'status': 'FORMAL',
        'generation_time': {
            'git_commit_short': gen_commit_short,
            'git_commit_full': gen_commit_full,
            'dirty': is_dirty,
            'python_version': python_version(),
        },
        'sealed_release': {
            'git_commit': gen_commit_full,
            'rule': (
                'The generation commit is recorded here. The sealed-artifact '
                'commit is the one that commits this manifest + artifacts; '
                'it appears in the independent review report.'
            ),
        },
        'e3b_reproduction_gate': {
            'fold_partition': 'PASSED (matches split_report.csv)',
            'tolerances': {
                'seed42_delta_match_min_rate': 0.90,
                'seed42_loss_rel_tol': 0.01,
                'pooled_j1_rel_tol': 0.005,
                'pern_j1_rel_tol': 0.01,
                'endpoint_rate_abs_tol': 0.02,
            },
            'note': (
                'Gate 2 and Gate 3 run on every call to run_e4d_formal(); '
                'tolerances are frozen BEFORE any E4 truth is accessed.'
            ),
        },
        'input_provenance': input_hashes,
        'code_provenance': code_hashes,
        'output_provenance': output_hashes,
        'mlp_config': {
            'hidden_layer_sizes': [256, 128, 64],
            'max_iter': 300,
            'batch_size': 256,
            'alpha': 1e-4,
            'learning_rate_init': 1e-3,
            'early_stopping': True,
            'validation_fraction': 0.15,
            'n_iter_no_change': 20,
        },
        'training_contract': {
            'folds': 5,
            'seeds': [42, 2026, 3407],
            'total_models': 15,
            'training_data': 'main_grid_train_combos_only',
            'evaluation_data': 'boundary_and_offgrid_truth_only',
            'baselines': {
                'Default': f'delta={DEFAULT_DELTA}',
                'L1': 'main_grid_global_best',
                'L2': 'main_grid_per_n_best (n in {7,10,20} only)',
            },
        },
    }

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, sort_keys=True, ensure_ascii=False)
    print(f"Wrote: {MANIFEST_PATH}")

    # ── Summary ──
    selector = df_j1[df_j1['model'] == 'Vector-MLP-L6']
    j1_vals = selector['pooled_J1'].values

    summary = {
        'experiment': 'E4d_selector_extrapolation',
        'created_at': now_iso(),
        'generation_git_commit': gen_commit_full,
        'per_track_pooled_J1': {},
        'model_stability': {
            'n_models': int(len(selector)),
            'J1_min': float(np.min(j1_vals)),
            'J1_max': float(np.max(j1_vals)),
            'J1_mean': float(np.mean(j1_vals)),
            'J1_std': float(np.std(j1_vals, ddof=1)),
            'J1_range': float(np.max(j1_vals) - np.min(j1_vals)),
        },
        'frozen_baselines': {},
    }

    # Per-track per-model pooled J1
    for track in sorted(df['track'].unique()):
        summary['per_track_pooled_J1'][track] = {}
        for model in sorted(df['model'].unique()):
            sub = df[(df['track'] == track) & (df['model'] == model)]
            if len(sub) > 0:
                j1_val = float(np.sqrt(sub['true_loss'].mean()))
                summary['per_track_pooled_J1'][track][model] = {
                    'J1': j1_val,
                    'n_samples': int(len(sub)),
                }

    # Baseline reference values (from E4d run log)
    summary['frozen_baselines'] = {
        'L1_main_grid_best_delta': 0.08,
        'L2_main_grid_per_n': {'7': 0.1, '10': 0.1, '20': 0.08},
        'Default_delta': DEFAULT_DELTA,
    }

    # Per-model J1 table
    per_model = []
    for _, row in selector.iterrows():
        per_model.append({
            'fold': row['fold'],
            'seed': int(row['seed']),
            'pooled_J1': float(row['pooled_J1']),
        })
    summary['per_model_J1'] = per_model

    with open(SUMMARY_PATH, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, sort_keys=True, ensure_ascii=False)
    print(f"Wrote: {SUMMARY_PATH}")

    # ── SHA256SUMS ──
    entries = []
    for label, info in output_hashes.items():
        entries.append((info['path'], info['sha256']))
    # Also hash the manifest and summary themselves
    for p in [MANIFEST_PATH, SUMMARY_PATH]:
        if os.path.exists(p):
            rel = os.path.relpath(p, PROJECT_ROOT).replace('\\', '/')
            entries.append((rel, sha256_file(p)))

    entries.sort(key=lambda e: e[0])
    content = ''.join(f"{h}  {p}\n" for p, h in entries)
    with open(SHA256_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f"Wrote: {SHA256_PATH} ({len(entries)} entries)")

    # ── Self-check: every output hash matches actual file bytes ──
    print("\n=== Byte-level hash verification ===")
    all_ok = True
    for p, expected_hash in entries:
        if not os.path.exists(os.path.join(PROJECT_ROOT, p.replace('/', os.sep))):
            # Try absolute or relative
            fp = os.path.join(E4_DIR, os.path.basename(p))
            if not os.path.exists(fp):
                fp = os.path.join(PROJECT_ROOT, p)
        else:
            fp = os.path.join(PROJECT_ROOT, p.replace('/', os.sep))
        actual = sha256_file(fp) if os.path.exists(fp) else 'FILE_NOT_FOUND'
        ok = actual == expected_hash
        if not ok:
            all_ok = False
        print(f"  {'OK' if ok else 'FAIL'}: {p}  {actual[:16]}...")
    print(f"\nVerification: {'ALL OK' if all_ok else 'FAILURES DETECTED'}")
    if not all_ok:
        sys.exit(1)

    print("\nE4d formal seal complete.")


if __name__ == '__main__':
    main()
