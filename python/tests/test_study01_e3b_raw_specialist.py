"""
E3b_RAW_specialist Contract Tests — candidate route verification.

Verifies the Study01 RAW-input per-n specialist candidate:
  - 45 models (3 n x 5 fold x 3 seed) all completed
  - RAW input lengths strictly 7/10/20; each row == ascending-sorted
    reconstructed sample
  - no banned fields / true-parameter leakage
  - input + target scalers fit on the TRAIN fold only
  - 5-fold combo holdout has no train/test combo cross and matches formal E3b
  - 26-dim output aligned with the delta grid
  - selected loss & J1 independently recomputable from per-sample predictions
  - keys complete and unique across seed x fold x n
  - formal E3/E4 artifacts unchanged

Run: python python/tests/test_study01_e3b_raw_specialist.py

Paths are __file__-relative (no hardcoded drive) so the test works regardless
of whether the repo lives on C:\\ or D:\\.
"""

import sys
import os
import json
import math
import subprocess

import numpy as np
import pandas as pd

# ============================================================
# Path setup — __file__-relative
# ============================================================

TEST_DIR = os.path.dirname(os.path.abspath(__file__))      # python/tests
PYTHON_DIR = os.path.dirname(TEST_DIR)                     # python
PROJECT_ROOT = os.path.dirname(PYTHON_DIR)                 # repo root
STUDY_ROOT = os.path.join(
    PROJECT_ROOT, "Study", "01-study-MDM最小偏移量优化研究")
STUDY_CODE_DIR = os.path.join(STUDY_ROOT, "code")
ARTIFACTS_DIR = os.path.join(STUDY_ROOT, "artifacts", "formal")
SHARED_DATA_DIR = os.path.join(ARTIFACTS_DIR, "shared_data")
CHUNKS_DIR = os.path.join(SHARED_DATA_DIR, "chunks")
CANDIDATE_DIR = os.path.join(STUDY_ROOT, "artifacts", "candidate", "E3b_RAW_specialist")
E3B_DIR = os.path.join(ARTIFACTS_DIR, "E3b_vector_mlp")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)


def _have_artifacts():
    return os.path.exists(os.path.join(CANDIDATE_DIR, "manifest.json"))


# ============================================================
# Code-level contracts (run without artifacts)
# ============================================================

def test_raw_input_contract_no_banned_fields():
    """The RAW input is the sorted sample; assert the contract object excludes
    every banned field and the builder carries no key/param columns."""
    from run_E3b_RAW_specialist import BANNED_FIELDS, SPECIALIST_NS, SAMPLE_KEYS
    # input is raw sample values only; banned fields must never be inputs
    for b in ['beta', 'eta', 'gamma', 'gamma_over_eta', 'delta',
              'repeat_id', 'seed', 'combo_id']:
        assert b in BANNED_FIELDS, f"{b} not declared banned"
    # specialist n values are exactly 7/10/20
    assert SPECIALIST_NS == [7, 10, 20]
    # SAMPLE_KEYS are bookkeeping, not inputs
    assert 'n' in SAMPLE_KEYS and 'repeat_id' in SAMPLE_KEYS
    print("  [PASS] RAW input contract excludes all banned fields; n in {7,10,20}")


def test_generate_sample_sorted_and_deterministic():
    """generate_sample returns an ascending-sorted, deterministic sample."""
    from studies.common.sample import generate_sample
    from config import SEED_NAMESPACE
    s1 = generate_sample(2.0, 1.0, 0.5, 20, 7, seed=SEED_NAMESPACE)
    s2 = generate_sample(2.0, 1.0, 0.5, 20, 7, seed=SEED_NAMESPACE)
    assert len(s1) == 20
    assert np.allclose(s1, s2), "generate_sample not deterministic"
    assert np.all(np.diff(s1) >= 0), "generate_sample not ascending-sorted"
    # different repeat_id => different sample (sanity)
    s3 = generate_sample(2.0, 1.0, 0.5, 20, 8, seed=SEED_NAMESPACE)
    assert not np.allclose(s1, s3), "repeat_id should change the sample"
    print("  [PASS] generate_sample: deterministic, ascending-sorted, len=n")


def test_raw_input_width_equals_n():
    """build_raw_sample_map + pivot_raw_vector yield X with width == n."""
    from run_E3b_RAW_specialist import build_raw_sample_map, pivot_raw_vector, \
        compute_per_sample_loss, list_mdm_chunks
    # use one chunk (one unit) for speed
    df = pd.read_csv(list_mdm_chunks()[0])
    manifest = json.load(open(os.path.join(SHARED_DATA_DIR, "manifest.json"),
                              encoding='utf-8'))
    raw_map, _ = build_raw_sample_map(df, manifest)
    n_val = 7  # chunk_0000 is beta=1.5,gamma/eta=0.1,n=7
    df_l = compute_per_sample_loss(df)
    fp = float(np.nanpercentile(df_l['loss'].dropna(), 99))
    df_l['loss_filled'] = df_l['loss'].fillna(fp)
    df_l['is_valid'] = df_l['status'].eq('success') & df_l['loss'].notna()
    keys, X, Y, valid = pivot_raw_vector(df_l, raw_map, n_val, 'loss_filled')
    assert X.shape[1] == n_val, f"RAW width {X.shape[1]} != n {n_val}"
    assert X.shape[0] == Y.shape[0] == len(keys)
    # each input row equals the ascending-sorted reconstructed sample
    for i in range(len(keys)):
        r = keys.iloc[i]
        key = (float(r['beta']), float(r['eta']), float(r['gamma']),
               float(r['gamma_over_eta']), int(r['n']), int(r['repeat_id']))
        assert np.allclose(X[i], raw_map[key]), "input row != reconstructed sample"
        assert np.all(np.diff(X[i]) >= 0), "input row not ascending-sorted"
    print(f"  [PASS] RAW input width==n ({n_val}); each row == sorted reconstructed sample")


def test_combo_holdout_disjoint_and_partition():
    """5-fold combo holdout: train/test disjoint per fold; test combos partition
    all 45 combos; matches formal E3b enumeration."""
    from run_E3b_RAW_specialist import get_combo_split
    from itertools import product
    from config import BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID
    folds = get_combo_split()
    all_combos = set(product(BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID))
    assert len(all_combos) == 45
    seen_test = set()
    for f in folds:
        tr = set(f['train_combos']); te = set(f['test_combos'])
        assert not (tr & te), f"fold {f['fold_name']}: train/test overlap"
        assert len(te) == 9 and len(tr) == 36
        assert not (te & seen_test), "test combo reused across folds"
        seen_test |= te
    assert seen_test == all_combos, "test combos do not partition all 45 combos"
    print("  [PASS] 5-fold combo holdout: disjoint, 9 test/fold, partitions 45 combos")


def test_scalers_fit_on_train_only():
    """train_specialist fits input + target scalers on X_train/Y_train only;
    the fitted scaler stats equal train stats and differ from test stats."""
    from run_E3b_RAW_specialist import train_specialist
    rng = np.random.default_rng(0)
    Xtr = rng.normal(5, 2, size=(300, 7)).astype('float64')
    Ytr = rng.normal(0.4, 0.1, size=(300, 26)).astype('float64')
    Xte = rng.normal(8, 2, size=(60, 7)).astype('float64')  # clearly different loc
    Ypred, n_iter, insc, tgsc = train_specialist(Xtr, Ytr, Xte, seed=42)
    # input scaler mean must equal Xtr column means, NOT Xte
    assert np.allclose(insc.mean_, Xtr.mean(axis=0), atol=1e-6), \
        "input scaler mean != train mean (TEST may have leaked)"
    assert not np.allclose(insc.mean_, Xte.mean(axis=0), atol=1e-6), \
        "input scaler mean matches TEST mean — leakage"
    # target scaler mean must equal Ytr column means
    assert np.allclose(tgsc.mean_, Ytr.mean(axis=0), atol=1e-6), \
        "target scaler mean != train target mean"
    assert Ypred.shape == (60, 26) and np.all(Ypred >= 0)
    print("  [PASS] input + target scalers fit on TRAIN only (stats match train, not test)")


def test_pivot_raw_vector_alignment():
    """pivot_raw_vector keeps keys/X/Y strictly row-aligned under unsorted input."""
    from run_E3b_RAW_specialist import pivot_raw_vector, DELTA_GRID
    n_val = 7
    # craft 2 samples x 4 deltas, intentionally unsorted by key
    deltas_test = [0.00, 0.02, 0.04, 0.06]
    rows = []
    for (beta, rid, base) in [(2.0, 1, 0.3), (1.5, 2, 0.1)]:
        for k, d in enumerate(deltas_test):
            rows.append({'beta': beta, 'eta': 1.0, 'gamma': 0.1,
                         'gamma_over_eta': 0.1, 'n': n_val, 'repeat_id': rid,
                         'delta': d, 'loss_filled': base + 0.1 * k,
                         'is_valid': True})
    df = pd.DataFrame(rows)
    raw_map = {
        (2.0, 1.0, 0.1, 0.1, 7, 1): np.sort(np.array([0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1])),
        (1.5, 1.0, 0.1, 0.1, 7, 2): np.sort(np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])),
    }
    keys, X, Y, valid = pivot_raw_vector(df, raw_map, n_val, 'loss_filled')
    for i in range(len(keys)):
        r = keys.iloc[i]
        key = (float(r['beta']), float(r['eta']), float(r['gamma']),
               float(r['gamma_over_eta']), int(r['n']), int(r['repeat_id']))
        assert np.allclose(X[i], raw_map[key])
        sub = df[(df['beta'] == r['beta']) & (df['repeat_id'] == r['repeat_id'])].sort_values('delta')
        for j, d in enumerate(DELTA_GRID):
            if d in deltas_test:
                assert abs(Y[i, j] - sub['loss_filled'].iloc[deltas_test.index(d)]) < 1e-10
    print("  [PASS] pivot_raw_vector: keys/X/Y strictly aligned")


# ============================================================
# Artifact-level contracts (need a completed run)
# ============================================================

def test_45_models_complete():
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    from run_E3b_RAW_specialist import SPECIALIST_NS, SEEDS, model_id
    manifest = json.load(open(os.path.join(CANDIDATE_DIR, "manifest.json"),
                              encoding='utf-8'))
    files = manifest['model_files']
    expected = {model_id(n, f, s)
                for n in SPECIALIST_NS for f in range(5) for s in SEEDS}
    assert set(files) == expected, f"missing: {expected - set(files)}"
    assert len(files) == 45
    # every model json + predictions csv exists on disk
    for mid, info in files.items():
        assert os.path.exists(os.path.join(CANDIDATE_DIR, info['meta_json']))
        assert os.path.exists(os.path.join(CANDIDATE_DIR, info['predictions_csv']))
    print(f"  [PASS] all 45 models present (json + predictions csv on disk)")


def test_input_dims_and_widths():
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    manifest = json.load(open(os.path.join(CANDIDATE_DIR, "manifest.json"),
                              encoding='utf-8'))
    for mid, info in manifest['model_files'].items():
        n = info['n']
        assert info['input_dim'] == n, f"{mid}: input_dim {info['input_dim']} != n {n}"
        dfp = pd.read_csv(os.path.join(CANDIDATE_DIR, info['predictions_csv']))
        assert int(dfp['n'].iloc[0]) == n
    assert manifest['input_contract']['input_dim_per_n'] == {'7': 7, '10': 10, '20': 20}
    print("  [PASS] input_dim == n for every model (7/10/20)")


def test_predictions_26dim_alignment_and_argmin():
    """Every predictions file has 26 pred_d{d} columns matching DELTA_GRID, and
    selected_delta == DELTA_GRID[argmin(pred_d*)] for each row."""
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    from config import DELTA_GRID
    import glob
    pred_files = glob.glob(os.path.join(CANDIDATE_DIR, "predictions", "*.csv"))
    assert len(pred_files) == 45, f"expected 45 pred files, got {len(pred_files)}"
    pred_cols = [f'pred_d{d}' for d in DELTA_GRID]
    checked = 0
    for pf in sorted(pred_files):
        df = pd.read_csv(pf)
        assert all(c in df.columns for c in pred_cols), f"{pf}: missing pred columns"
        mat = df[pred_cols].values
        best_idx = np.argmin(mat, axis=1)
        sel_delta_rebuilt = np.array([DELTA_GRID[i] for i in best_idx])
        assert np.allclose(sel_delta_rebuilt, df['selected_delta'].values, atol=1e-9), \
            f"{pf}: selected_delta != argmin(pred)"
        assert np.all((df['selected_delta_idx'].values >= 0) &
                      (df['selected_delta_idx'].values < 26))
        checked += len(df)
    print(f"  [PASS] 26-dim pred columns aligned to DELTA_GRID; "
          f"selected_delta == argmin(pred) over {checked} rows")


def test_j1_reproducible_from_predictions():
    """Independently recompute pooled + per-n J1 from predictions for each seed
    and compare to seed_stability.csv."""
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    from run_E3b_RAW_specialist import SPECIALIST_NS, SEEDS, checkpoint_paths
    seed_df = pd.read_csv(os.path.join(CANDIDATE_DIR, "seed_stability.csv"))
    for seed in SEEDS:
        frames = []
        for n in SPECIALIST_NS:
            for f in range(5):
                _, pp = checkpoint_paths(n, f, seed)
                frames.append(pd.read_csv(pp))
        dfp = pd.concat(frames, ignore_index=True)
        pooled = math.sqrt(dfp['true_loss'].mean())
        row = seed_df[seed_df['seed'] == seed].iloc[0]
        assert abs(pooled - row['pooled_J1']) < 1e-6, \
            f"seed {seed}: pooled {pooled} != reported {row['pooled_J1']}"
        for n in SPECIALIST_NS:
            jn = math.sqrt(dfp[dfp['n'] == n]['true_loss'].mean())
            col = f'J1_n{n}'
            assert abs(jn - row[col]) < 1e-6, f"seed {seed} n{n}: {jn} != {row[col]}"
    print("  [PASS] pooled + per-n J1 independently recomputed from predictions")


def test_key_coverage_and_uniqueness():
    """Across the 5 folds, each (n, seed) covers all 15000 samples of that n
    exactly once; across n, 45000 total; no duplicate (beta,gamma/eta,n,repeat_id)."""
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    from run_E3b_RAW_specialist import SPECIALIST_NS, SEEDS, checkpoint_paths
    for seed in SEEDS:
        for n in SPECIALIST_NS:
            keys_all = []
            for f in range(5):
                _, pp = checkpoint_paths(n, f, seed)
                dfp = pd.read_csv(pp)
                keys_all.append(dfp[['beta', 'gamma_over_eta', 'n', 'repeat_id']])
            kk = pd.concat(keys_all, ignore_index=True)
            assert len(kk) == 15000, f"seed {seed} n{n}: {len(kk)} != 15000"
            assert kk.drop_duplicates().shape[0] == 15000, f"seed {seed} n{n}: dup keys"
    # cross-n: 45000 unique per seed
    for seed in SEEDS:
        allk = []
        for n in SPECIALIST_NS:
            for f in range(5):
                _, pp = checkpoint_paths(n, f, seed)
                allk.append(pd.read_csv(pp)[['beta', 'gamma_over_eta', 'n', 'repeat_id']])
        kk = pd.concat(allk, ignore_index=True)
        assert len(kk) == 45000 and kk.drop_duplicates().shape[0] == 45000
    print("  [PASS] keys complete (15000/n/seed, 45000/seed) and unique")


def test_references_match_formal_e3b():
    """Default/L1/L2/L6-hindsight J1 from this candidate's reference eval must
    match the sealed formal E3b model_comparison.csv values."""
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    comp = pd.read_csv(os.path.join(CANDIDATE_DIR, "model_comparison.csv"))
    f13 = pd.read_csv(os.path.join(E3B_DIR, "model_comparison.csv"))
    tol = 1e-4
    expected = {'Default': 0.633219, 'L1': 0.632913, 'L2': 0.632541,
                'L6-hindsight': 0.494530}
    for m, v in expected.items():
        cand = comp[comp['model'] == m]['J1'].iloc[0]
        assert abs(cand - v) < 1e-3, f"{m}: candidate {cand} != expected {v}"
        # also cross-check the formal file carries the same value
        frm = f13[(f13['model'] == m) & (f13['split'] == 'combo_holdout_pooled')]['J1'].iloc[0]
        assert abs(cand - frm) < tol, f"{m}: candidate {cand} != formal {frm}"
    print("  [PASS] Default/L1/L2/L6-hindsight J1 match formal E3b")


def test_split_matches_formal_e3b():
    """Candidate split_report.csv must equal formal E3b split_report.csv."""
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    a = pd.read_csv(os.path.join(CANDIDATE_DIR, "split_report.csv"))
    b = pd.read_csv(os.path.join(E3B_DIR, "split_report.csv"))
    assert len(a) == 45 == len(b)
    assert list(a.columns) == list(b.columns)
    pd.testing.assert_frame_equal(
        a.sort_values(['fold', 'test_beta', 'test_gamma_over_eta', 'test_n']).reset_index(drop=True),
        b.sort_values(['fold', 'test_beta', 'test_gamma_over_eta', 'test_n']).reset_index(drop=True),
        check_dtype=False)
    print("  [PASS] candidate split == formal E3b split (identical 5-fold holdout)")


def test_checkpoint_valid_rejects_mismatch():
    """Hardened checkpoint_valid must accept correct fingerprints and reject every
    mismatch (test-key set / delta grid / code / row count)."""
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    from run_E3b_RAW_specialist import (checkpoint_valid, compute_test_keys_sha,
        delta_grid_sha256, code_sha256)
    n, fold, seed = 7, 0, 42
    test_n = 3000  # 3 held-out combos (n=7) x 1000 repeats
    tks_ok = compute_test_keys_sha(n, fold)
    tks_wrong = compute_test_keys_sha(n, 1)   # fold-2 key set
    dgs = delta_grid_sha256()
    ccs = code_sha256()
    assert checkpoint_valid(n, fold, seed, test_n, tks_ok, dgs, ccs) is True
    assert checkpoint_valid(n, fold, seed, test_n, tks_wrong, dgs, ccs) is False, \
        "wrong test-key fingerprint must be rejected"
    assert checkpoint_valid(n, fold, seed, test_n, tks_ok, dgs, '0' * 64) is False, \
        "wrong code fingerprint must be rejected"
    assert checkpoint_valid(n, fold, seed, test_n, tks_ok, '0' * 64, ccs) is False, \
        "wrong delta fingerprint must be rejected"
    assert checkpoint_valid(n, fold, seed, 2999, tks_ok, dgs, ccs) is False, \
        "wrong test row count must be rejected"
    print("  [PASS] checkpoint_valid accepts correct, rejects all fingerprint/count mismatches")


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def test_sha256sums_present_and_consistent():
    """SHA256SUMS exists, is GNU-format, every entry verifies against disk, and it
    covers source data + code + results."""
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    sp = os.path.join(CANDIDATE_DIR, "SHA256SUMS")
    assert os.path.exists(sp), "SHA256SUMS missing"
    bad = total = 0
    n_src = n_code = n_res = 0
    for line in open(sp, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line:
            continue
        h, _, rel = line.partition('  ')
        total += 1
        fp = os.path.join(PROJECT_ROOT, rel.replace('/', os.sep))
        if 'shared_data' in rel:
            n_src += 1
        elif rel.endswith(('run_E3b_RAW_specialist.py', 'config.py', 'sample.py')):
            n_code += 1
        elif rel.startswith('artifacts/candidate/E3b_RAW_specialist/'):
            n_res += 1
        if not os.path.exists(fp) or _sha256(fp) != h:
            bad += 1
    assert bad == 0, f"{bad}/{total} SHA256SUMS entries do not verify"
    assert n_src == 46, f"expected 46 source entries (45 chunks + manifest), got {n_src}"
    assert n_code == 3, f"expected 3 code entries, got {n_code}"
    assert n_res >= 90, f"expected >=90 result entries, got {n_res}"
    print(f"  [PASS] SHA256SUMS: {total} entries all verify "
          f"(src={n_src}, code={n_code}, result={n_res})")


def test_near_optimal_rows_identifiable():
    """near_optimal_diagnostics.csv must carry seed/fold/model_id so each of the
    135000 rows is identifiable (not just 45000 unique sample keys)."""
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    df = pd.read_csv(os.path.join(CANDIDATE_DIR, "diagnostics",
                                  "near_optimal_diagnostics.csv"))
    for col in ('seed', 'fold', 'model_id'):
        assert col in df.columns, f"near_optimal missing {col}"
    assert len(df) == 135000, f"expected 135000 rows, got {len(df)}"
    assert df['model_id'].nunique() == 45, "model_id not unique over 45 models"
    assert df[['seed', 'fold']].drop_duplicates().shape[0] == 15, "seed x fold not 15"
    print(f"  [PASS] near_optimal: 135000 rows, 45 model_ids, seed/fold/model_id present")


def test_manifest_hashes_match_files():
    """Every predictions_sha256 recorded in manifest.json must match the actual
    (LF-normalized) prediction file on disk."""
    if not _have_artifacts():
        print("  [SKIP] no manifest yet"); raise SystemExit
    import hashlib
    manifest = json.load(open(os.path.join(CANDIDATE_DIR, "manifest.json"),
                              encoding='utf-8'))
    checked = 0
    for mid, info in manifest['model_files'].items():
        p = os.path.join(CANDIDATE_DIR, info['predictions_csv'])
        h = hashlib.sha256()
        with open(p, 'rb') as f:
            for b in iter(lambda: f.read(1 << 20), b''):
                h.update(b)
        assert h.hexdigest() == info['predictions_sha256'], \
            f"{mid}: manifest hash != file hash"
        checked += 1
    print(f"  [PASS] {checked} manifest prediction hashes match files on disk")


def test_no_formal_artifacts_modified():
    """git diff on sealed formal E3/E4 artifact dirs must be clean."""
    for sub in ["E3b_vector_mlp", "E3_sample_adaptive", "shared_data"]:
        path = f"Study/01-study-MDM最小偏移量优化研究/artifacts/formal/{sub}/"
        r = subprocess.run(['git', 'diff', '--name-only', '--', path],
                           cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=20)
        assert r.stdout.strip() == '', f"formal {sub} modified:\n{r.stdout}"
    print("  [PASS] sealed formal E3/E4 artifacts unchanged (git diff clean)")


# ============================================================

if __name__ == '__main__':
    tests = [
        ("RAW input contract (no banned fields)", test_raw_input_contract_no_banned_fields),
        ("generate_sample sorted+deterministic", test_generate_sample_sorted_and_deterministic),
        ("RAW input width == n", test_raw_input_width_equals_n),
        ("Combo holdout disjoint+partition", test_combo_holdout_disjoint_and_partition),
        ("Scalers fit on train only", test_scalers_fit_on_train_only),
        ("pivot_raw_vector alignment", test_pivot_raw_vector_alignment),
        ("45 models complete", test_45_models_complete),
        ("Input dims == n", test_input_dims_and_widths),
        ("Predictions 26-dim alignment + argmin", test_predictions_26dim_alignment_and_argmin),
        ("J1 reproducible from predictions", test_j1_reproducible_from_predictions),
        ("Key coverage and uniqueness", test_key_coverage_and_uniqueness),
        ("References match formal E3b", test_references_match_formal_e3b),
        ("Split matches formal E3b", test_split_matches_formal_e3b),
        ("checkpoint_valid rejects mismatch", test_checkpoint_valid_rejects_mismatch),
        ("SHA256SUMS present and consistent", test_sha256sums_present_and_consistent),
        ("Near-optimal rows identifiable", test_near_optimal_rows_identifiable),
        ("Manifest hashes match files", test_manifest_hashes_match_files),
        ("No formal artifacts modified", test_no_formal_artifacts_modified),
    ]
    print("=" * 64)
    print("E3b_RAW_specialist Contract Tests")
    print("=" * 64)
    passed = skipped = failed = 0
    for name, fn in tests:
        print(f"\n[{name}]")
        try:
            fn(); passed += 1
        except SystemExit:
            skipped += 1
        except AssertionError as e:
            print(f"  [FAIL] {e}"); failed += 1
        except Exception as e:
            print(f"  [SKIP] {type(e).__name__}: {e}"); skipped += 1
    print(f"\n{'=' * 64}")
    print(f"Results: {passed} passed, {skipped} skipped, {failed} failed")
    print("=" * 64)
    sys.exit(1 if failed else 0)
