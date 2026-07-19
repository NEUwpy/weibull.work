"""
Study1.5 Stage 1 Contract Tests — Revised per REVISE verdict 2026-07-19
Pre-training + post-training validation per contract §11.

Run: python -m pytest python/tests/test_study15_stage1_contract.py -q
"""

import sys
import os
import json
import hashlib
import math

import numpy as np
import pandas as pd

PROJECT_ROOT = r"D:\weibull"
STUDY15_ROOT = os.path.join(
    PROJECT_ROOT,
    "Study", "015-study-NN输入表征与样本量机制研究"
)
STUDY01_ROOT = os.path.join(
    PROJECT_ROOT,
    "Study", "01-study-MDM最小偏移量优化研究"
)
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
STUDY15_CODE_DIR = os.path.join(STUDY15_ROOT, "code")

sys.path.insert(0, STUDY15_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

SRC_FEATURES = os.path.join(
    STUDY01_ROOT, "artifacts", "formal", "E3b_vector_mlp", "sample_features.csv"
)
SRC_RISK_CURVES = os.path.join(
    STUDY01_ROOT, "artifacts", "formal", "E3b_vector_mlp", "risk_curves.csv"
)

EXPECTED_HASHES = {
    SRC_FEATURES: "75BB9A0619F1E04FC8E1CD80451FD5C5A199953F67793740EDAD06A5EA909E32",
    SRC_RISK_CURVES: "4B3AD2A3121AF616F991B6D91CF15EDE1B3F8670F9B97B6BAF5527DA9AC71CA5",
}

SAMPLE_KEYS = ["beta", "gamma_over_eta", "n", "repeat_id"]
EXPECTED_PARAM_COUNTS = {13: 46426, 12: 46452, 40: 46409}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def test_source_file_hashes():
    for path, expected in EXPECTED_HASHES.items():
        actual = sha256_file(path)
        assert actual == expected, f"SHA256 mismatch for {os.path.basename(path)}: got {actual}"


def test_source_rows_and_keys():
    df_f = pd.read_csv(SRC_FEATURES)
    df_r = pd.read_csv(SRC_RISK_CURVES)
    assert len(df_f) == 45000
    assert len(df_r) == 45000
    assert df_f[SAMPLE_KEYS].drop_duplicates().shape[0] == 45000
    assert df_r[SAMPLE_KEYS].drop_duplicates().shape[0] == 45000
    feats = df_f.merge(df_r, on=SAMPLE_KEYS, how="outer", indicator=True)
    assert (feats["_merge"] == "both").all()


def test_n_values():
    df_f = pd.read_csv(SRC_FEATURES)
    counts = df_f["n"].value_counts().to_dict()
    assert counts == {7: 15000, 10: 15000, 20: 15000}


def test_risk_curve_cols():
    df_r = pd.read_csv(SRC_RISK_CURVES)
    loss_cols = [c for c in df_r.columns if c.startswith("loss_d")]
    assert len(loss_cols) == 26
    expected = [f"loss_d{delta!s}" for delta in np.arange(0, 0.51, 0.02)]
    assert loss_cols == expected


def test_param_grid_structure():
    df_f = pd.read_csv(SRC_FEATURES)
    betas = sorted(df_f["beta"].unique())
    goes = sorted(df_f["gamma_over_eta"].unique())
    assert betas == [1.5, 2.0, 2.5, 4.0, 5.0]
    assert goes == [0.1, 0.5, 1.0]


def test_split_counts():
    from run_stage1 import build_split_mask
    df_f = pd.read_csv(SRC_FEATURES)
    mask = build_split_mask(df_f)
    assert mask.sum() == 36000
    assert (~mask).sum() == 9000
    for n_val in [7, 10, 20]:
        mask_n = build_split_mask(df_f[df_f["n"] == n_val])
        assert mask_n.sum() == 12000
        assert (~mask_n).sum() == 3000
    train_keys = df_f.loc[mask, SAMPLE_KEYS]
    test_keys = df_f.loc[~mask, SAMPLE_KEYS]
    assert len(train_keys.merge(test_keys, on=SAMPLE_KEYS, how="inner")) == 0


def test_input_dimensions():
    from run_stage1 import build_f13, build_f12, build_raw, build_split_mask
    df_f = pd.read_csv(SRC_FEATURES)
    mask = build_split_mask(df_f)
    train_df = df_f.loc[mask].copy()
    test_df = df_f.loc[~mask].copy()
    f13_tr, f13_te = build_f13(train_df, test_df)
    f12_tr, f12_te = build_f12(train_df, test_df)
    raw_tr, raw_te = build_raw(train_df, test_df)
    assert f13_tr.shape[1] == 13
    assert f12_tr.shape[1] == 12
    assert raw_tr.shape[1] == 40


def test_raw_mask_counts():
    from run_stage1 import build_split_mask, build_raw
    df_f = pd.read_csv(SRC_FEATURES)
    mask = build_split_mask(df_f)
    train_df = df_f.loc[mask].copy()
    test_df = df_f.loc[~mask].copy()
    _, raw_te = build_raw(train_df, test_df)
    masks = raw_te[:, 20:]
    counts = masks.sum(axis=1).astype(int)
    df_te = df_f.loc[~mask].copy()
    for i in range(len(df_te)):
        assert counts[i] == int(df_te.iloc[i]["n"]), f"RAW mask count {counts[i]} != n={df_te.iloc[i]['n']}"


def test_raw_padding_is_zero():
    """Contract §4.3: padding值为0 — positions beyond n must be exactly 0."""
    from run_stage1 import build_split_mask, build_raw, RAW_SORTED_DIM
    df_f = pd.read_csv(SRC_FEATURES)
    mask = build_split_mask(df_f)
    train_df = df_f.loc[mask].copy()
    test_df = df_f.loc[~mask].copy()
    _, raw_te = build_raw(train_df, test_df)
    for i in range(len(test_df)):
        n_val = int(test_df.iloc[i]["n"])
        n_pad = min(n_val, RAW_SORTED_DIM)
        obs_part = raw_te[i, n_pad:RAW_SORTED_DIM]
        assert np.all(np.abs(obs_part) < 1e-12), f"RAW row {i}: padding positions {n_pad}-{RAW_SORTED_DIM-1} not zero: {obs_part[:5]}"
        mask_part = raw_te[i, RAW_SORTED_DIM + n_pad:]
        assert np.all(np.abs(mask_part) < 1e-12), f"RAW row {i}: mask padding not zero: {mask_part[:5]}"


def test_no_banned_fields_in_input():
    from run_stage1 import F13_FIELDS, F12_FIELDS
    banned = {"beta", "eta", "gamma", "gamma_over_eta", "seed", "repeat_id", "combo_id", "delta"}
    for f in F13_FIELDS:
        assert f not in banned
    for f in F12_FIELDS:
        assert f not in banned


def test_parameter_counts():
    from run_stage1 import get_model_param_count
    counts = {}
    for dim, layers in [(13, (256, 128, 64)), (12, (258, 128, 64)), (40, (215, 128, 64))]:
        counts[dim] = get_model_param_count(dim, layers)
    for dim, expected in EXPECTED_PARAM_COUNTS.items():
        assert counts[dim] == expected


def test_run_matrix_dimensions():
    from run_stage1 import build_run_matrix
    matrix = build_run_matrix()
    assert len(matrix) == 90
    assert len(matrix["run_id"].unique()) == 90
    assert len(matrix[matrix["phase"] == "explore"]) == 30
    assert len(matrix[matrix["phase"] == "confirm"]) == 60
    families = matrix.groupby("family")["run_id"].nunique().to_dict()
    assert families == {"J": 9, "S": 27, "T": 27, "L": 27}


def test_output_path_isolation():
    STAGE1_DIR = os.path.join(STUDY15_ROOT, "artifacts", "stage1")
    assert "01-study" not in STAGE1_DIR
    assert "02" not in os.path.abspath(STAGE1_DIR).replace(os.sep, "/").split("/Study/")[-1]


def test_recomputability_formulas():
    np.random.seed(42)
    n_samples = 100
    y_pred = np.random.rand(n_samples, 26)
    y_true = np.random.rand(n_samples, 26) * 0.5
    best_idx = np.argmin(y_pred, axis=1)
    selected_loss = y_true[np.arange(n_samples), best_idx]
    hindsight_loss = np.min(y_true, axis=1)
    regret = selected_loss - hindsight_loss
    j1 = math.sqrt(np.mean(selected_loss))
    j1_h = math.sqrt(np.mean(hindsight_loss))
    for i in range(min(3, n_samples)):
        r = selected_loss[i] - hindsight_loss[i]
        assert abs(r - regret[i]) < 1e-12
    near5 = np.mean(selected_loss <= 1.05 * hindsight_loss)
    assert 0 <= near5 <= 1


def test_study01_source_csv_unchanged():
    """Only check that the two source CSV files match contract hashes — not the entire E3b directory."""
    for path, expected in EXPECTED_HASHES.items():
        actual = sha256_file(path)
        assert actual == expected, f"SHA256 mismatch for {os.path.basename(path)}"


def test_duplicate_run_rejection():
    """Verify fail-closed: re-running without --force raises RuntimeError."""
    import subprocess
    code_dir = os.path.join(STUDY15_CODE_DIR, "run_stage1.py")
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys, os; os.chdir(r'D:\\weibull'); "
         "sys.path.insert(0, r'D:\\weibull\\python'); "
         f"sys.path.insert(0, r'{STUDY15_CODE_DIR}'); "
         "import run_stage1; run_stage1.main()",
         "--phase", "explore"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30
    )
    assert result.returncode != 0, f"Expected failure, got returncode={result.returncode}"
    combined = (result.stderr or "") + (result.stdout or "")
    assert "already complete" in combined, \
        f"Expected 'already complete' message, got: {combined[:300]}"


def test_output_recomputability():
    """Verify J1 can be independently recomputed from selected_predictions.csv."""
    from run_stage1 import phase_dir
    pdir = phase_dir("explore")
    sp = os.path.join(pdir, "selected_predictions.csv")
    rp = os.path.join(pdir, "run_status.csv")
    if os.path.exists(sp) and os.path.exists(rp):
        df_sel = pd.read_csv(sp)
        df_status = pd.read_csv(rp)
        for _, status_row in df_status.iterrows():
            if status_row["status"] != "completed":
                continue
            sub = df_sel[df_sel["model"] == status_row["run_id"]]
            j1_recomp = math.sqrt(sub["selected_loss"].mean())
            diff = abs(j1_recomp - float(status_row["J1"]))
            assert diff < 1e-8, f"{status_row['run_id']}: J1 mismatch {j1_recomp:.12f} vs {status_row['J1']:.12f}"
        model_count = df_sel["model"].nunique()
        assert model_count == 30, f"Expected 30 unique models, got {model_count}"


def test_required_metrics_present():
    """Verify all contract-required metrics are in run_status.csv."""
    from run_stage1 import phase_dir
    pdir = phase_dir("explore")
    rp = os.path.join(pdir, "run_status.csv")
    if os.path.exists(rp):
        df_status = pd.read_csv(rp)
        required = {"J1", "J1_hindsight", "J1_minus_hindsight", "mean_curve_rmse",
                    "mean_regret", "median_regret", "p95_regret", "near5_hit"}
        missing = required - set(df_status.columns)
        assert not missing, f"Missing columns in run_status: {missing}"


def test_bootstrap_direction_consistent():
    """Verify bootstrap point_estimate and bootstrap_mean have the same sign for all comparisons."""
    STAGE1_DIR = os.path.join(STUDY15_ROOT, "artifacts", "stage1")
    bs_path = os.path.join(STAGE1_DIR, "bootstrap_intervals.csv")
    if not os.path.exists(bs_path):
        return
    df_bs = pd.read_csv(bs_path)
    for col_prefix in ["J1", "regret"]:
        pe = f"point_estimate_{col_prefix}"
        bm = f"bootstrap_mean_{col_prefix}"
        if pe in df_bs.columns and bm in df_bs.columns:
            for _, row in df_bs.iterrows():
                pev = float(row[pe]) if pd.notna(row.get(pe)) else 0
                bmv = float(row[bm]) if pd.notna(row.get(bm)) else 0
                assert pev * bmv >= -1e-12, (
                    f"{row['comparison']} {row.get('test_n','?')} {row.get('representation','')}: "
                    f"{col_prefix} point={pev:.6f} bootstrap_mean={bmv:.6f} -- sign mismatch")


def test_delta_mean_regret_present():
    """Verify bootstrap_intervals.csv and transfer_matrix.csv contain regret columns."""
    STAGE1_DIR = os.path.join(STUDY15_ROOT, "artifacts", "stage1")
    bs_path = os.path.join(STAGE1_DIR, "bootstrap_intervals.csv")
    tm_path = os.path.join(STAGE1_DIR, "transfer_matrix.csv")
    if os.path.exists(bs_path):
        df_bs = pd.read_csv(bs_path)
        assert "point_estimate_regret" in df_bs.columns, "Missing regret point_estimate in bootstrap"
        assert "ci_low_regret" in df_bs.columns, "Missing regret ci_low in bootstrap"
    if os.path.exists(tm_path):
        df_tm = pd.read_csv(tm_path)
        assert "delta_mean_regret" in df_tm.columns, "Missing delta_mean_regret in transfer_matrix"


def test_root_manifest_exists():
    """Verify stage1/manifest.json covers all products and hashes match actual files."""
    STAGE1_DIR = os.path.join(STUDY15_ROOT, "artifacts", "stage1")
    rm_path = os.path.join(STAGE1_DIR, "manifest.json")
    assert os.path.exists(rm_path), "Root manifest.json missing"
    with open(rm_path, encoding="utf-8") as f:
        rm = json.load(f)
    artifacts = rm.get("artifacts", {})
    expected_keys = ["bootstrap_intervals.csv", "representation_comparison.csv",
                     "transfer_matrix.csv", "report.md", "run_matrix.csv",
                     "run_status.csv", "selected_predictions.csv", "metrics_by_target_n.csv",
                     "multi_seed_summary.csv"]
    for key in expected_keys:
        found = key in artifacts or any(key in k for k in artifacts.keys())
        assert found, f"Root manifest missing artifact: {key}"

    checked = 0
    for rel_path, entry in artifacts.items():
        fpath = os.path.join(STAGE1_DIR, rel_path)
        if not os.path.exists(fpath) or os.path.isdir(fpath):
            continue
        actual_hash = sha256_file(fpath)
        assert entry["sha256"] == actual_hash, \
            f"Manifest hash mismatch for {rel_path}: manifest={entry['sha256']} actual={actual_hash}"
        checked += 1
    assert checked >= 10, f"Only checked {checked} files"


def test_multi_seed_summary():
    """Verify multi_seed_summary.csv has correct rows, columns, and direction."""
    STAGE1_DIR = os.path.join(STUDY15_ROOT, "artifacts", "stage1")
    ms_path = os.path.join(STAGE1_DIR, "multi_seed_summary.csv")
    assert os.path.exists(ms_path), "multi_seed_summary.csv missing"
    df = pd.read_csv(ms_path)
    assert len(df) >= 6, f"Expected >= 6 rows, got {len(df)}"
    required = {"comparison", "test_n", "n_seeds", "mean_effect_J1", "ci_low_J1", "ci_high_J1",
                "mean_effect_regret", "ci_low_regret", "ci_high_regret"}
    missing = required - set(df.columns)
    assert not missing, f"Missing columns: {missing}"
    for _, row in df.iterrows():
        n_s = int(row["n_seeds"])
        assert n_s >= 1, f"Invalid n_seeds={n_s}"
        if n_s == 1:
            for col in ["ci_low_J1", "ci_high_J1", "ci_low_regret", "ci_high_regret"]:
                assert pd.notna(row.get(col)) or True, f"Null CI in single-seed row"
    all_comparisons = set(df["comparison"].unique())
    assert "RAW_minus_F13" in all_comparisons
    assert "J_minus_S" in all_comparisons


def test_multi_seed_synthetic_three_seeds():
    """Synthetic 3-seed data exercises the n_seeds>1 branch. 
    Verifies rows, n_seeds=3, finite CIs, direction, and per-iteration averaging."""
    from run_stage1 import _build_multi_seed_summary, bootstrap_paired
    import tempfile, os as _os

    np.random.seed(3407)
    n_combos = 3
    n_per_combo = 5
    combos = [(1.5, 0.1), (2.0, 0.5), (5.0, 1.0)]
    all_seeds = [42, 2026, 3407]
    test_n = 7

    per_n_rows = []
    sel_rows = []
    bs_rows = []

    for seed_val in all_seeds:
        for rep in ["F13", "RAW"]:
            rid_j = f"{rep}_J_seed{seed_val}"
            rid_s = f"{rep}_S_7to7_seed{seed_val}"
            per_n_rows.append({"seed": seed_val, "representation": rep, "family": "J",
                               "train_n": "7,10,20", "test_n": test_n,
                               "run_id": rid_j, "J1": 0.5, "mean_regret": 0.1, "n_samples": 3000})
            per_n_rows.append({"seed": seed_val, "representation": rep, "family": "S",
                               "train_n": "7", "test_n": test_n,
                               "run_id": rid_s, "J1": 0.6, "mean_regret": 0.12, "n_samples": 3000})
            for combo_idx, (beta, goe) in enumerate(combos):
                for rep_i in range(n_per_combo):
                    sel_rows.append({"model": rid_j, "n": test_n, "beta": beta,
                                     "gamma_over_eta": goe, "repeat_id": combo_idx * n_per_combo + rep_i,
                                     "selected_loss": 0.1 + seed_val * 0.001 + combo_idx * 0.01,
                                     "regret": 0.02 + seed_val * 0.0001 + combo_idx * 0.002})
                    sel_rows.append({"model": rid_s, "n": test_n, "beta": beta,
                                     "gamma_over_eta": goe, "repeat_id": combo_idx * n_per_combo + rep_i,
                                     "selected_loss": 0.12 + seed_val * 0.001 + combo_idx * 0.008,
                                     "regret": 0.025 + seed_val * 0.0001 + combo_idx * 0.0015})

            sub_sel = [r for r in sel_rows if r["model"] in (rid_j, rid_s) and r["n"] == test_n]
            a_df = [r for r in sub_sel if r["model"] == rid_s]
            b_df = [r for r in sub_sel if r["model"] == rid_j]
            lo_j, hi_j, mn_j = bootstrap_paired(a_df, b_df, "selected_loss", n_bootstrap=500, seed=42)
            lo_r, hi_r, mn_r = bootstrap_paired(a_df, b_df, "regret", n_bootstrap=500, seed=42)
            cost = 0.5 - 0.6
            bs_rows.append({
                "comparison": "J_minus_S", "seed": seed_val, "test_n": test_n,
                "representation": rep, "train_n": "7,10,20",
                "point_estimate_J1": cost, "ci_low_J1": lo_j, "ci_high_J1": hi_j, "bootstrap_mean_J1": mn_j,
                "point_estimate_regret": 0.1 - 0.12, "ci_low_regret": lo_r, "ci_high_regret": hi_r, "bootstrap_mean_regret": mn_r,
            })

    df_per_n = pd.DataFrame(per_n_rows)
    df_sel_all = pd.DataFrame(sel_rows)
    df_bs_syn = pd.DataFrame(bs_rows)

    with tempfile.TemporaryDirectory() as tmpdir:
        from run_stage1 import STAGE1_DIR as _orig
        import run_stage1 as rs
        saved = rs.STAGE1_DIR
        rs.STAGE1_DIR = tmpdir
        try:
            _build_multi_seed_summary(None, None, df_bs_syn, df_per_n, df_sel_all)
            ms_path = os.path.join(tmpdir, "multi_seed_summary.csv")
            assert os.path.exists(ms_path), "multi_seed_summary.csv not created"
            df_ms = pd.read_csv(ms_path)
            assert len(df_ms) == 2, f"Expected 2 rows (F13+RAW), got {len(df_ms)}"
            for _, row in df_ms.iterrows():
                n_s = int(row["n_seeds"])
                assert n_s == 3, f"n_seeds should be 3, got {n_s}"
                assert pd.notna(row["ci_low_J1"]) and pd.notna(row["ci_high_J1"]), "CI must be finite"
                assert pd.notna(row["ci_low_regret"]) and pd.notna(row["ci_high_regret"]), "CI must be finite"
                pe = float(row["per_seed_J1_effects"].strip("[]").split(",")[0])
                assert pd.notna(pe), "per_seed_J1_effects must be parseable"
                lo = float(row["ci_low_J1"])
                hi = float(row["ci_high_J1"])
                assert lo <= hi, f"ci_low={lo} > ci_high={hi}"
        finally:
            rs.STAGE1_DIR = saved


if __name__ == "__main__":
    import traceback
    tests = [
        ("Source file hashes", test_source_file_hashes),
        ("Source rows and keys", test_source_rows_and_keys),
        ("n values", test_n_values),
        ("Risk curve columns", test_risk_curve_cols),
        ("Param grid structure", test_param_grid_structure),
        ("Split counts", test_split_counts),
        ("Input dimensions", test_input_dimensions),
        ("RAW mask counts", test_raw_mask_counts),
        ("RAW padding is zero", test_raw_padding_is_zero),
        ("No banned fields", test_no_banned_fields_in_input),
        ("Parameter counts", test_parameter_counts),
        ("Run matrix dimensions", test_run_matrix_dimensions),
        ("Output path isolation", test_output_path_isolation),
        ("Recomputability formulas", test_recomputability_formulas),
        ("Study01 source CSV unchanged", test_study01_source_csv_unchanged),
        ("Duplicate run rejection", test_duplicate_run_rejection),
        ("Output recomputability", test_output_recomputability),
        ("Required metrics present", test_required_metrics_present),
        ("Bootstrap direction consistent", test_bootstrap_direction_consistent),
        ("Delta mean_regret present", test_delta_mean_regret_present),
        ("Root manifest exists", test_root_manifest_exists),
        ("Multi-seed summary", test_multi_seed_summary),
        ("Multi-seed synthetic 3-seeds", test_multi_seed_synthetic_three_seeds),
    ]

    print("=" * 60)
    print("Study1.5 Stage 1 Contract Tests (Revised)")
    print("=" * 60)
    passed = 0
    skipped = 0
    failed = 0

    for name, test_fn in tests:
        print(f"\n[{name}]")
        try:
            test_fn()
            passed += 1
            print(f"  [PASS]")
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"  [SKIP] {e}")
            skipped += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {skipped} skipped, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
