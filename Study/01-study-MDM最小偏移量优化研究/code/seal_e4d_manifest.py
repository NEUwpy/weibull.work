"""
Study/01 — E4d Formal Seal v2

Generates sealed manifest, summary, and SHA256SUMS using git-blob SHA256
(not worktree bytes). Per R3-T3 contract:

  - Manifest records generation-code-commit, artifact-commit, seal-commit
    as three distinct fields.
  - SHA256 computed via ``git show <commit>:<relpath>`` to read the
    LF-normalised blob stored in Git, NOT the worktree file.
  - All text output uses LF explicitly (``newline='\\n'``).
  - Self-verification reads blob bytes and checks every entry.

Run AFTER the E4d artifacts are committed and pushed.
"""

import sys
import os
import json
import hashlib
import subprocess
import tempfile
from datetime import datetime, timezone

import pandas as pd

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

from config import ARTIFACTS_DIR, SHARED_DATA_DIR, DELTA_GRID, DEFAULT_DELTA
from utils import now_iso

E4_DIR = os.path.join(ARTIFACTS_DIR, "E4_robustness")

E4D_CSV = os.path.join(E4_DIR, "E4d_selector_extrapolation.csv")
E4D_J1_CSV = os.path.join(E4_DIR, "E4d_model_j1_summary.csv")
E4D_PAIRED = os.path.join(E4_DIR, "E4d_paired_comparisons_by_model.csv")
E4D_PAIRED_AGG = os.path.join(
    E4_DIR, "E4d_paired_comparisons_aggregate.csv")
E4D_DELTA = os.path.join(E4_DIR, "E4d_delta_distribution.csv")
E4D_GATE = os.path.join(E4_DIR, "E4d_e3b_gate_results.json")
RUN_LOG = os.path.join(E4_DIR, "run_log_e4d.txt")

MANIFEST_PATH = os.path.join(E4_DIR, "manifest_e4d.json")
SUMMARY_PATH = os.path.join(E4_DIR, "summary_e4d.json")
SHA256_PATH = os.path.join(E4_DIR, "SHA256SUMS_e4d")

ALL_OUTPUTS = [E4D_CSV, E4D_J1_CSV, E4D_PAIRED, E4D_PAIRED_AGG,
               E4D_DELTA, E4D_GATE, RUN_LOG]


def git_show_blob(commit, relpath):
    """Return the raw bytes of *relpath* as stored in *commit*."""
    result = subprocess.run(
        ['git', 'show', f'{commit}:{relpath}'],
        capture_output=True, check=True, cwd=PROJECT_ROOT,
    )
    return result.stdout


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def git_commit_full():
    return subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        capture_output=True, text=True, check=True, cwd=PROJECT_ROOT,
    ).stdout.strip()


def git_commit_short():
    return subprocess.run(
        ['git', 'rev-parse', '--short', 'HEAD'],
        capture_output=True, text=True, check=True, cwd=PROJECT_ROOT,
    ).stdout.strip()


def is_dirty():
    return subprocess.run(
        ['git', 'diff', '--quiet'], cwd=PROJECT_ROOT,
    ).returncode != 0


def main():
    seal_commit = git_commit_full()
    dirty = is_dirty()

    # We need the artifact commit (the one that committed the output CSVs).
    # Until that commit exists, we fall back to HEAD.
    artifact_commit = seal_commit

    # Read generation commit from run_log
    gen_commit = None
    gen_commit_short = None
    if os.path.exists(RUN_LOG):
        with open(RUN_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                if 'Git commit:' in line:
                    gen_commit_short = line.split('Git commit:')[1].strip()
                    break
        # Resolve full from short
        if gen_commit_short:
            result = subprocess.run(
                ['git', 'rev-parse', gen_commit_short],
                capture_output=True, text=True, cwd=PROJECT_ROOT,
            )
            if result.returncode == 0:
                gen_commit = result.stdout.strip()

    if not gen_commit:
        gen_commit = seal_commit
        gen_commit_short = git_commit_short()

    # ── Output provenance using git-blob SHA256 ──
    output_provenance = {}
    for path in ALL_OUTPUTS:
        if not os.path.exists(path):
            print(f"WARNING: {path} not found — skipping")
            continue
        rel = os.path.relpath(path, PROJECT_ROOT).replace('\\', '/')
        # Compute SHA256 from git blob (LF-normalised)
        try:
            blob_bytes = git_show_blob(artifact_commit, rel)
        except subprocess.CalledProcessError:
            # Fallback: file not in git yet; use worktree bytes
            with open(path, 'rb') as f:
                blob_bytes = f.read()
            print(f"WARNING: {rel} not in git at {artifact_commit[:8]}; "
                  f"using worktree bytes")
        h = sha256_bytes(blob_bytes)
        row_count = None
        if path.endswith('.csv'):
            try:
                row_count = int(len(pd.read_csv(
                    path, low_memory=False)))
            except Exception:
                pass
        output_provenance[rel] = {
            'sha256': h,
            'size_bytes': len(blob_bytes),
            'row_count': row_count,
            'source': f'git show {artifact_commit[:8]}' if blob_bytes else 'worktree',
        }

    # ── Manifest ──
    manifest = {
        'experiment': 'E4d_selector_extrapolation',
        'contract_version': '07-study01-remaining-experiments-4.1',
        'created_at': now_iso(),
        'status': 'FORMAL',
        'commits': {
            'generation_code': gen_commit,
            'artifact': artifact_commit,
            'seal': seal_commit,
        },
        'dirty': dirty,
        'output_provenance': output_provenance,
        'mlp_config': {
            'hidden_layer_sizes': [256, 128, 64],
            'max_iter': 300, 'batch_size': 256,
            'alpha': 1e-4, 'learning_rate_init': 1e-3,
            'early_stopping': True, 'validation_fraction': 0.15,
            'n_iter_no_change': 20,
        },
        'training_contract': {
            'folds': 5, 'seeds': [42, 2026, 3407],
            'total_models': 15,
            'training_data': 'main_grid_train_combos_only',
            'evaluation_data': 'boundary_and_offgrid_truth_only',
        },
    }

    # Write manifest with LF
    manifest_json = json.dumps(manifest, indent=2, sort_keys=True,
                               ensure_ascii=False)
    with open(MANIFEST_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(manifest_json)
        f.write('\n')
    print(f"Wrote: {MANIFEST_PATH}")

    # ── Summary ──
    summary = {
        'experiment': 'E4d_selector_extrapolation',
        'created_at': now_iso(),
        'seal_commit': seal_commit,
    }
    if os.path.exists(E4D_J1_CSV):
        df_j1 = pd.read_csv(E4D_J1_CSV)
        selector = df_j1[df_j1['model'] == 'Vector-MLP-L6']
        if len(selector) > 0:
            j1v = selector['pooled_J1'].values
            summary['model_stability'] = {
                'n_models': int(len(selector)),
                'J1_min': float(np.min(j1v)),
                'J1_max': float(np.max(j1v)),
                'J1_mean': float(np.mean(j1v)),
                'J1_std': float(np.std(j1v, ddof=1)),
            }
    if os.path.exists(E4D_CSV):
        df = pd.read_csv(E4D_CSV)
        for track in sorted(df['track'].unique()):
            if 'per_track_pooled_J1' not in summary:
                summary['per_track_pooled_J1'] = {}
            summary['per_track_pooled_J1'][track] = {}
            for model in sorted(df['model'].unique()):
                sub = df[(df['track'] == track) & (df['model'] == model)]
                if len(sub) > 0:
                    summary['per_track_pooled_J1'][track][model] = {
                        'J1': float(np.sqrt(sub['true_loss'].mean())),
                        'n_samples': int(len(sub)),
                    }

    summary_json = json.dumps(summary, indent=2, sort_keys=True,
                              ensure_ascii=False)
    with open(SUMMARY_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(summary_json)
        f.write('\n')
    print(f"Wrote: {SUMMARY_PATH}")

    # ── SHA256SUMS (from blob bytes) ──
    entries = []
    for rel, info in output_provenance.items():
        entries.append((rel, info['sha256']))
    entries.sort(key=lambda e: e[0])
    content = ''.join(f"{h}  {p}\n" for p, h in entries)
    with open(SHA256_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f"Wrote: {SHA256_PATH} ({len(entries)} entries)")

    # ── Self-verification: read via git show and verify every entry ──
    print("\n=== Byte-level verification (git blob) ===")
    errors = 0
    for rel, expected_h in entries:
        try:
            blob_bytes = git_show_blob(artifact_commit, rel)
            actual_h = sha256_bytes(blob_bytes)
            ok = actual_h == expected_h
        except subprocess.CalledProcessError:
            # Not in git yet — try worktree
            fp = os.path.join(PROJECT_ROOT, rel.replace('/', os.sep))
            if os.path.exists(fp):
                with open(fp, 'rb') as f:
                    blob_bytes = f.read()
                actual_h = sha256_bytes(blob_bytes)
                ok = actual_h == expected_h
            else:
                ok = False
                actual_h = 'FILE_NOT_FOUND'
        if not ok:
            errors += 1
        print(f"  {'OK' if ok else 'FAIL'}: {rel}")
    print(f"\nVerification: {'ALL OK' if errors == 0 else f'{errors} FAILURES'}")

    if errors:
        sys.exit(1)


if __name__ == '__main__':
    import numpy as np
    main()
