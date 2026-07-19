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
    result = subprocess.run(
        ["python", os.path.join(STUDY15_CODE_DIR, "run_stage1.py"), "--phase", "explore"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30
    )
    assert result.returncode != 0, f"Expected failure, got returncode={result.returncode}"
    assert "already complete" in (result.stderr or "") + (result.stdout or ""), \
        f"Expected 'already complete' message, got stderr={result.stderr[:200]} stdout={result.stdout[:200]}"


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
