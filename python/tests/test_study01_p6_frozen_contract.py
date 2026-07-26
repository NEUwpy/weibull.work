"""
Contract self-tests for P6 frozen configuration.

Verifies internal consistency of the frozen contract BEFORE any
method comparison is run. These tests gate P6 readiness.
"""

import sys
import os
import json
import hashlib
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = next((PROJECT_ROOT / "Study").glob("01-study-MDM*"))
STUDY_CODE_DIR = STUDY_ROOT / "code"
REAL_DATA_DIR = STUDY_ROOT / "artifacts" / "formal" / "real_data"
NIST_DIR = REAL_DATA_DIR / "nist-6061-t6-fatigue"

sys.path.insert(0, str(STUDY_CODE_DIR))


def test_p6_frozen_config_exists():
    """P6 frozen config JSON must exist with revised version."""
    config_path = REAL_DATA_DIR / "p6_frozen_config.json"
    assert config_path.exists(), f"Missing: {config_path}"
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    assert cfg["contract_version"] == "P6-v1.1-FROZEN-REVISED"


def test_p6_frozen_contract_exists():
    """P6 frozen contract markdown must exist."""
    contract_path = REAL_DATA_DIR / "P6_FROZEN_CONTRACT.md"
    assert contract_path.exists(), f"Missing: {contract_path}"


def test_data_source_files_exist():
    """All required data source files must be present."""
    assert (NIST_DIR / "source.json").exists(), "Missing source.json"
    assert (NIST_DIR / "lifetimes.csv").exists(), "Missing lifetimes.csv"
    assert (NIST_DIR / "BIRNSAUN.DAT").exists(), "Missing BIRNSAUN.DAT"
    assert (NIST_DIR / "convert_birnsaun_to_lifetimes.py").exists(), (
        "Missing conversion script"
    )


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


def test_p8a_authorization_closed_after_seal():
    """P6 guard released after P7 APPROVE; P8a authorization sealed closed."""
    import run_real_data_validation as rv
    assert rv._P6_PLACEHOLDER_GUARD is False, (
        "P6 placeholder guard must be released after P7 Codex APPROVE"
    )
    assert rv._P8A_FORMAL_AUTHORIZED is False, (
        "P8A_FORMAL_AUTHORIZED must be False in final sealed state"
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
    # Revised contract checks
    assert cfg["evaluation"]["tie_tolerance"] == 1e-9
    assert "one_sample_two_sided_ks_distance" in cfg["evaluation"]["primary_metric"]
    assert "failure_handling" in cfg
    assert cfg["failure_handling"]["imputation"] == "D = 1 for failed repeats, marked failed=True"
    assert cfg["evaluation"]["aggregation"]["no_median_model"] is True
    # License should NOT claim U.S. government work under §105
    assert "not a nist-authored" in cfg["dataset"]["data_status"].lower()


def test_source_json_median_corrected():
    """source.json median must be 1416 (not 1419)."""
    with open(NIST_DIR / "source.json", 'r', encoding='utf-8') as f:
        src = json.load(f)
    assert src["value_range"]["median"] == 1416.0, (
        f"Median should be 1416, got {src['value_range']['median']}"
    )


def test_source_json_license_not_claims_us_gov_work():
    """source.json must NOT claim §105 U.S. government work for third-party data."""
    with open(NIST_DIR / "source.json", 'r', encoding='utf-8') as f:
        src = json.load(f)
    assert "17 U.S.C. § 105" not in src.get("license_name", ""), (
        "Third-party data hosted by NIST must not be labeled as U.S. government work"
    )


def test_conversion_script_reproduces_lifetimes_csv(tmp_path):
    """Running convert_birnsaun_to_lifetimes.py must reproduce lifetimes.csv.

    Uses tmp_path to avoid overwriting the formal lifetimes.csv artifact.
    """
    import shutil
    script = str(NIST_DIR / "convert_birnsaun_to_lifetimes.py")
    # Copy BIRNSAUN.DAT to temp dir; script reads from its own dir by default,
    # so we run from NIST_DIR and let it write to tmp_path via env override.
    # Strategy: run from tmp_path with a copy of BIRNSAUN.DAT.
    dat_src = NIST_DIR / "BIRNSAUN.DAT"
    dat_dst = tmp_path / "BIRNSAUN.DAT"
    shutil.copy2(str(dat_src), str(dat_dst))
    script_dst = tmp_path / "convert_birnsaun_to_lifetimes.py"
    shutil.copy2(script, str(script_dst))
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    result = subprocess.run(
        [sys.executable, str(script_dst)],
        capture_output=True, text=True, encoding='utf-8',
        timeout=30, cwd=str(tmp_path), env=env,
    )
    assert result.returncode == 0, (
        f"Conversion script failed:\n{result.stderr}"
    )
    assert "SHA256 verified" in result.stdout, (
        "Conversion script did not verify output SHA256"
    )
    # Verify the output CSV exists in tmp_path
    csv_out = tmp_path / "lifetimes.csv"
    assert csv_out.exists(), "Conversion script did not produce lifetimes.csv"


def test_contract_defines_failure_handling():
    """Contract must define estimation failure handling before any comparison."""
    with open(REAL_DATA_DIR / "p6_frozen_config.json", 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    fh = cfg["failure_handling"]
    assert "detection" in fh
    assert len(fh["detection"]) >= 4
    assert "imputation" in fh
    assert "primary_analysis" in fh
    assert "complete_case_sensitivity" in fh
    assert "prohibition" in fh


def test_contract_metric_is_one_sample_two_sided_ks():
    """Primary metric must be one-sample two-sided KS with piecewise CDF."""
    with open(REAL_DATA_DIR / "p6_frozen_config.json", 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    definition = cfg["evaluation"]["primary_metric_definition"]
    assert "i/m" in definition, "Missing right-continuous ECDF term i/m"
    assert "(i-1)/m" in definition, "Missing left-continuous ECDF term (i-1)/m"
    assert "y_(i)" in definition or "y_{(i)}" in definition, (
        "Missing sorted holdout notation y_(i)"
    )
    assert ("y<=" in definition.replace(" ", "") or
            "y <=" in definition or
            "y \\leq" in definition), (
        "Missing piecewise CDF: must define F(y)=0 for y <= gamma_hat"
    )
    assert "exp" in definition, (
        "Missing Weibull CDF exponential term"
    )


def test_nn_aggregation_no_median_model():
    """NN aggregation must NOT define a single 'median model'."""
    with open(REAL_DATA_DIR / "p6_frozen_config.json", 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    agg = cfg["evaluation"]["aggregation"]
    assert agg["no_median_model"] is True
    assert "per-model" in agg["nn_step1_per_model"].lower() or \
           "per_model" in agg["nn_step1_per_model"]
    assert "distribution" in agg["nn_step2_cross_model"].lower()


def test_tie_tolerance_frozen():
    """Tie tolerance must be frozen at 1e-9."""
    with open(REAL_DATA_DIR / "p6_frozen_config.json", 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    assert cfg["evaluation"]["tie_tolerance"] == 1e-9
