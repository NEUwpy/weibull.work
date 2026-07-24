"""
Contract self-tests for P6 frozen configuration.

Verifies internal consistency of the frozen contract BEFORE any
method comparison is run. These tests gate P6 readiness.
"""

import sys
import os
import json
import hashlib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = next((PROJECT_ROOT / "Study").glob("01-study-MDM*"))
STUDY_CODE_DIR = STUDY_ROOT / "code"
REAL_DATA_DIR = STUDY_ROOT / "artifacts" / "formal" / "real_data"
NIST_DIR = REAL_DATA_DIR / "nist-6061-t6-fatigue"

sys.path.insert(0, str(STUDY_CODE_DIR))


def test_p6_frozen_config_exists():
    """P6 frozen config JSON must exist."""
    config_path = REAL_DATA_DIR / "p6_frozen_config.json"
    assert config_path.exists(), f"Missing: {config_path}"
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    assert cfg["contract_version"] == "P6-v1.0-FROZEN"


def test_p6_frozen_contract_exists():
    """P6 frozen contract markdown must exist."""
    contract_path = REAL_DATA_DIR / "P6_FROZEN_CONTRACT.md"
    assert contract_path.exists(), f"Missing: {contract_path}"


def test_data_source_files_exist():
    """All required data source files must be present."""
    assert (NIST_DIR / "source.json").exists(), "Missing source.json"
    assert (NIST_DIR / "lifetimes.csv").exists(), "Missing lifetimes.csv"
    assert (NIST_DIR / "BIRNSAUN.DAT").exists(), "Missing BIRNSAUN.DAT"


def test_lifetimes_csv_sha256_matches_contract():
    """lifetimes.csv SHA256 must match frozen contract value."""
    csv_path = NIST_DIR / "lifetimes.csv"
    with open(csv_path, 'rb') as f:
        raw = f.read()
    normalized = raw.replace(b'\r\n', b'\n')
    sha = hashlib.sha256(normalized).hexdigest()
    expected = "43c85155bdfeafd21e2366610e88a3f4e1a09e36466fb22d34729dc60418ee12"
    assert sha == expected, (
        f"lifetimes.csv SHA256 mismatch!\n"
        f"  Expected: {expected}\n"
        f"  Got:      {sha}"
    )


def test_birnsaun_dat_sha256_matches_contract():
    """BIRNSAUN.DAT SHA256 must match frozen contract value."""
    dat_path = NIST_DIR / "BIRNSAUN.DAT"
    with open(dat_path, 'rb') as f:
        raw = f.read()
    normalized = raw.replace(b'\r\n', b'\n')
    sha = hashlib.sha256(normalized).hexdigest()
    expected = "7814c533818517d8b824c56213abac2b4076786a13a66d85a8481a32bbccf127"
    assert sha == expected, (
        f"BIRNSAUN.DAT SHA256 mismatch!\n"
        f"  Expected: {expected}\n"
        f"  Got:      {sha}"
    )


def test_admission_gate_passes():
    """Admission gate must pass with frozen thresholds."""
    from real_data_gate import run_real_data_gate
    result = run_real_data_gate(str(NIST_DIR))
    assert result.passed, f"Gate failed: {result.reason}"
    assert result.diagnostics['n_loaded'] == 101
    assert result.diagnostics['r_squared'] >= 0.70


def test_n_lifetimes_is_101():
    """Dataset must have exactly 101 lifetimes."""
    import pandas as pd
    df = pd.read_csv(NIST_DIR / "lifetimes.csv")
    assert len(df) == 101, f"Expected 101 rows, got {len(df)}"
    assert 'failure_time' in df.columns
    assert df['failure_time'].notna().all()
    assert (df['failure_time'] > 0).all()


def test_e4d_manifest_exists_and_has_15_models():
    """E4d contract must exist with exactly 15 models."""
    manifest_path = (
        STUDY_ROOT / "artifacts" / "formal" / "E4_robustness"
        / "manifest_e4d.json"
    )
    assert manifest_path.exists(), f"Missing E4d manifest: {manifest_path}"
    with open(manifest_path, 'r', encoding='utf-8') as f:
        m = json.load(f)
    tc = m["training_contract"]
    assert tc["total_models"] == 15
    assert tc["folds"] == 5
    assert tc["seeds"] == [42, 2026, 3407]


def test_l2_delta_source_exists():
    """L2 delta table source must exist."""
    l2_path = (
        STUDY_ROOT / "artifacts" / "formal" / "E1_E2_crossfit"
        / "selected_deltas.csv"
    )
    assert l2_path.exists(), f"Missing L2 delta source: {l2_path}"


def test_l2_deltas_match_contract():
    """L2 per-n frozen values must match source data."""
    import pandas as pd
    l2_path = (
        STUDY_ROOT / "artifacts" / "formal" / "E1_E2_crossfit"
        / "selected_deltas.csv"
    )
    df = pd.read_csv(l2_path)
    l2 = df[df['layer'] == 'L2']

    # Majority vote across folds for each n
    for n_val, expected_delta in [(7, 0.10), (10, 0.10), (20, 0.08)]:
        n_rows = l2[l2['n'] == n_val]
        mode_delta = n_rows['delta_star'].mode().values[0]
        assert mode_delta == expected_delta, (
            f"L2 delta for n={n_val}: expected {expected_delta}, "
            f"mode is {mode_delta}"
        )


def test_source_json_required_fields():
    """source.json must have all required provenance fields."""
    with open(NIST_DIR / "source.json", 'r', encoding='utf-8') as f:
        src = json.load(f)
    required = [
        'dataset_id', 'source_url', 'license_name', 'download_sha256',
        'n_total', 'n_uncensored', 'material', 'test_condition',
        'failure_mode', 'censoring_semantics',
    ]
    for field in required:
        assert field in src, f"source.json missing field: {field}"
    assert src['n_total'] == 101
    assert src['n_uncensored'] == 101


def test_p6_placeholder_guard_active():
    """P6 run script must still have active fail-closed guard."""
    import run_real_data_validation as rv
    assert rv._P6_PLACEHOLDER_GUARD is True, (
        "P6 placeholder guard must remain active until P7 complete"
    )


def test_frozen_config_consistent_with_contract():
    """Machine-readable config must be consistent with contract doc."""
    with open(REAL_DATA_DIR / "p6_frozen_config.json", 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    assert cfg["dataset"]["n_total"] == 101
    assert cfg["dataset"]["n_uncensored"] == 101
    assert cfg["admission_gate"]["gate_passed"] is True
    assert cfg["admission_gate"]["min_uncensored_lifetimes"] == 60
    assert cfg["methods"]["l2"]["delta_by_n"]["7"] == 0.10
    assert cfg["methods"]["l2"]["delta_by_n"]["10"] == 0.10
    assert cfg["methods"]["l2"]["delta_by_n"]["20"] == 0.08
    assert cfg["methods"]["nn"]["n_models"] == 15
    assert cfg["methods"]["nn"]["seeds"] == [42, 2026, 3407]
    assert cfg["experimental_design"]["train_n_values"] == [7, 10, 20]
    assert cfg["experimental_design"]["repeats_per_n"] == 500
