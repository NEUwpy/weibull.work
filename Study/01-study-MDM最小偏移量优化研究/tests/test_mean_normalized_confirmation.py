"""Minimum contract tests for the formal mean-normalized confirmation."""

import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import sys

import numpy as np


STUDY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(STUDY_ROOT, "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6
import run_b1_mean_normalized_unseen_beta as E8B1
import derive_mean_normalized_quantiles as E8Q
import check_mean_normalized_e2e_scale as E8S
import prepare_mean_normalized_main_evidence as E8M


E8_FORMAL_ROOT = (Path(STUDY_ROOT) / "artifacts" / "formal" /
                  "E8_mean_normalized_selector")


def test_mean_normalized_map_is_exact_scale_invariant_and_key_preserving():
    key = (2.5, 1000.0, 500.0, 0.5, 7, 3)
    sample = np.array([8.0, 2.0, 3.0, 15.0, 6.0, 10.0, 5.0])
    expected = np.sort(sample) / np.mean(sample)
    base = E8B1.mean_normalized_map({key: sample})
    assert set(base) == {key}
    assert np.allclose(base[key], expected)
    for factor in (1e-3, 1.0, 1e3):
        got = E8B1.mean_normalized_map({key: factor * sample})[key]
        assert np.allclose(got, expected, rtol=0.0, atol=1e-12)


def test_unseen_beta_contract_is_complete_and_disjoint():
    folds = E8B1.B1.get_beta_folds()
    assert len(folds) == len(CFG.BETA_GRID) == 8
    assert {fold["held_out_beta"] for fold in folds} == set(CFG.BETA_GRID)
    for fold in folds:
        train = set(fold["train_combos"])
        test = set(fold["test_combos"])
        assert not train.intersection(test)
        assert len(train) == 140 and len(test) == 20
        assert {combo[0] for combo in test} == {fold["held_out_beta"]}
        assert fold["held_out_beta"] not in {combo[0] for combo in train}


def test_confirmation_reuses_e6_training_and_train_only_scalers():
    source = inspect.getsource(E8B1.run_beta_fold)
    assert "E6.pivot_raw_vector" in source
    assert "E6.train_specialist" in source
    assert "E6.evaluate_selection" in source
    assert "StandardScaler" not in source

    train_source = inspect.getsource(E6.train_specialist)
    assert "input_scaler.fit_transform(X_train)" in train_source
    assert "input_scaler.transform(X_test)" in train_source
    assert "target_scaler.fit_transform(Y_train)" in train_source
    assert "fit_transform(X_test)" not in train_source


def test_confirmation_contract_keeps_frozen_models_and_metric():
    assert E8B1.SEEDS == [42, 2026, 3407]
    assert list(CFG.N_GRID) == [7, 10, 15, 20]
    assert list(CFG.MLP_HIDDEN_LAYERS) == [256, 128, 64]
    assert len(CFG.DELTA_GRID) == 26
    assert CFG.DEFAULT_DELTA == 0.1
    assert E8B1.MODEL_NAME == "Mean-Normalized-MLP"


def test_quantile_formula_and_metrics_use_reliability_definition():
    beta, eta, gamma = 2.0, 1000.0, 250.0
    reliability = 0.95
    expected = gamma + eta * (-np.log(reliability)) ** (1.0 / beta)
    assert np.isclose(E8Q.B3.true_quantile(beta, eta, gamma, reliability), expected)
    assert E8Q.B3.QUANTILE_R == {"x0.90": 0.90, "x0.95": 0.95,
                                "x0.99": 0.99}


def test_quantile_derivation_reuses_selection_and_mdm_scan():
    source = inspect.getsource(E8Q.run)
    assert "SELECTION_EXPECTED_SHA256" in source
    assert "B3.mdm_estimates_for" in source
    assert "PS.default_and_l6" in source
    assert "run_method" not in source
    assert "MLPRegressor" not in source


def test_sealed_deployment_forward_is_scale_invariant():
    model, model_sha = E8S.load_model(7)
    assert len(model_sha) == 64
    sample = np.array([8.0, 2.0, 3.0, 15.0, 6.0, 10.0, 5.0])
    delta, curve = E8S.select_delta(sample, model)
    assert delta in CFG.DELTA_GRID
    for factor in E8S.SCALES:
        got_delta, got_curve = E8S.select_delta(sample * factor, model)
        assert got_delta == delta
        assert np.allclose(got_curve, curve, rtol=0.0, atol=1e-12)


def test_scale_check_is_small_and_uses_production_mdm():
    source = inspect.getsource(E8S.run)
    assert len(E8S.PROBES) == 4
    assert {probe[2] for probe in E8S.PROBES} == set(CFG.N_GRID)
    assert "run_method(" in source
    assert '"mdm"' in source
    assert "MLPRegressor" not in source
    assert "sha256_file_lf" in source
    assert '"hash_policy": "SHA256 of LF-normalized bytes"' in source


def test_main_evidence_is_repackaging_not_an_experiment():
    source = inspect.getsource(E8M.run)
    assert E8M.SOURCE_RESULT_SHA256 == (
        "b67578fe3a6e02c606ce0ba0bf224f4ce8a7acbf48de1fd87ef1739e368ad7db"
    )
    assert "PS.default_and_l6" in source
    assert "run_method" not in source
    assert "MLPRegressor" not in source
    assert "PS.sha256_file_lf" in source
    assert '"hash_policy": "SHA256 of LF-normalized bytes"' in source


def test_all_tracked_e8_ledgers_verify_lf_normalized_files():
    """Every tracked E8 ledger must bind its current LF-normalized files."""
    required_packages = {
        "specialist", "unseen_beta", "quantiles", "scale_equivariance"
    }
    ledgers = {
        path.parent.name: path
        for path in E8_FORMAL_ROOT.glob("*/SHA256SUMS")
    }
    assert required_packages.issubset(ledgers), (
        f"missing E8 ledgers: {sorted(required_packages - set(ledgers))}"
    )

    record_pattern = re.compile(r"^([0-9a-f]{64})  ([^\r\n]+)$")
    for package in sorted(required_packages):
        ledger = ledgers[package]
        seen = set()
        records = ledger.read_text(encoding="utf-8").splitlines()
        assert records, f"empty ledger: {ledger}"
        for line in records:
            match = record_pattern.fullmatch(line)
            assert match, f"malformed ledger record in {ledger}: {line!r}"
            expected, relative = match.groups()
            assert relative not in seen, f"duplicate ledger path: {ledger}:{relative}"
            seen.add(relative)
            target = ledger.parent / relative
            assert target.is_file(), f"missing ledger file: {target}"
            normalized = target.read_bytes().replace(b"\r\n", b"\n")
            actual = hashlib.sha256(normalized).hexdigest()
            assert actual == expected, (
                f"LF-normalized SHA256 mismatch: {package}/{relative}: "
                f"{actual} != {expected}"
            )

    # The two E8 producers revised here also expose per-file hashes inside
    # their manifests; bind those records to the same LF-normalized contract.
    for package in ("specialist", "scale_equivariance"):
        manifest_path = E8_FORMAL_ROOT / package / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["hash_policy"] == "SHA256 of LF-normalized bytes"
        for relative, expected in manifest["files"].items():
            target = manifest_path.parent / relative
            assert target.is_file(), f"missing manifest file: {target}"
            normalized = target.read_bytes().replace(b"\r\n", b"\n")
            actual = hashlib.sha256(normalized).hexdigest()
            assert actual == expected, (
                f"manifest LF-normalized SHA256 mismatch: {package}/{relative}: "
                f"{actual} != {expected}"
            )
