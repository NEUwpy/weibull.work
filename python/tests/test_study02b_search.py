"""Focused tests for B2 selection logic, frozen-group validation, and manifest."""

from pathlib import Path
import hashlib
import json
import sys
import tempfile

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
PYTHON = REPO_ROOT / "python"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
if str(PYTHON) not in sys.path:
    sys.path.insert(0, str(PYTHON))

from study02b.search import (
    FitRecord,
    CandidateMean,
    SelectionResult,
    select_winner,
    build_outputs_inventory,
    _FROZEN_GROUPS,
    _FROZEN_SCREENING_SEED_SET,
    _FROZEN_WIDTHS,
)


def _make_record(arch_id, widths, loss, seed, rel_rmse,
                 param_count=1000, rmse=100.0):
    return FitRecord(
        architecture_id=arch_id,
        widths=widths,
        loss=loss,
        seed=seed,
        best_validation_loss=0.3,
        best_epoch=50,
        actual_epochs=100,
        early_stop_reason="patience_exhausted",
        param_count=param_count,
        checkpoint_sha256="abc123",
        checkpoint_bytes=b"fake_ckpt",
        decoded_rmse=rmse,
        decoded_rel_rmse=rel_rmse,
        decoded_bias=1.0,
        decoded_mae=50.0,
        n_valid=1000,
        n_total=1000,
    )


def _frozen_12_records(rel_rmses=None):
    """Build exactly 12 records matching the frozen groups and seeds."""
    if rel_rmses is None:
        rel_rmses = {
            ("a_64_32", "huber"): [0.253117, 0.252716, 0.253182],
            ("a_64_32", "mse"):   [0.260132, 0.263239, 0.262831],
            ("a_m12", "huber"):   [0.252279, 0.253056, 0.252299],
            ("a_m12", "mse"):     [0.260492, 0.262843, 0.260856],
        }
    records = []
    for (arch_id, loss), values in rel_rmses.items():
        widths = _FROZEN_WIDTHS[arch_id]
        param_count = 2817 if arch_id == "a_64_32" else 11777
        for seed, rel_rmse in zip([101, 202, 303], values):
            records.append(_make_record(
                arch_id, list(widths), loss, seed, rel_rmse,
                param_count=param_count,
            ))
    return records


# -- Normal selection --

def test_select_winner_clear_best():
    rel = {
        ("a_64_32", "huber"): [0.200, 0.200, 0.200],
        ("a_64_32", "mse"):   [0.250, 0.250, 0.250],
        ("a_m12", "huber"):   [0.220, 0.220, 0.220],
        ("a_m12", "mse"):     [0.270, 0.270, 0.270],
    }
    result = select_winner(_frozen_12_records(rel))
    assert result.winner_id == "a_64_32:huber"
    assert not result.tie_break_applied


def test_select_winner_tie_break_switches_to_smaller():
    rel = {
        ("a_m12", "huber"):   [0.200, 0.200, 0.200],
        ("a_64_32", "huber"): [0.201, 0.201, 0.201],
        ("a_64_32", "mse"):   [0.250, 0.250, 0.250],
        ("a_m12", "mse"):     [0.260, 0.260, 0.260],
    }
    result = select_winner(_frozen_12_records(rel))
    assert result.tie_break_applied
    assert result.winner_id == "a_64_32:huber"


def test_select_winner_no_tie_break_if_above_1pct():
    rel = {
        ("a_64_32", "huber"): [0.200, 0.200, 0.200],
        ("a_m12", "huber"):   [0.210, 0.210, 0.210],
        ("a_64_32", "mse"):   [0.250, 0.250, 0.250],
        ("a_m12", "mse"):     [0.260, 0.260, 0.260],
    }
    result = select_winner(_frozen_12_records(rel))
    assert not result.tie_break_applied
    assert result.winner_id == "a_64_32:huber"


def test_select_winner_zero_best_no_tie_break():
    rel = {
        ("a_64_32", "huber"): [0.0, 0.0, 0.0],
        ("a_m12", "huber"):   [0.0, 0.0, 0.0],
        ("a_64_32", "mse"):   [0.250, 0.250, 0.250],
        ("a_m12", "mse"):     [0.260, 0.260, 0.260],
    }
    result = select_winner(_frozen_12_records(rel))
    assert not result.tie_break_applied


# -- Validation: count, groups, seeds, widths, metrics --

def test_wrong_fit_count_raises():
    records = [_make_record("a_64_32", [64, 32], "huber", 101, 0.20, 2800)]
    with pytest.raises(ValueError, match="12 fits"):
        select_winner(records)


def test_unknown_group_raises():
    records = _frozen_12_records()
    # Replace a_64_32/huber seed 101 with unknown arch
    records[0] = _make_record("a_unknown", [32, 16], "huber", 101, 0.20, 1000)
    with pytest.raises(ValueError, match="Frozen groups mismatch"):
        select_winner(records)


def test_missing_seed_raises():
    records = [r for r in _frozen_12_records()
               if not (r.architecture_id == "a_64_32" and r.loss == "huber" and r.seed == 303)]
    with pytest.raises(ValueError, match="12 fits"):
        select_winner(records)


def test_wrong_seed_value_raises():
    rel = {
        ("a_64_32", "huber"): [0.20, 0.20, 0.20],
        ("a_64_32", "mse"):   [0.25, 0.25, 0.25],
        ("a_m12", "huber"):   [0.22, 0.22, 0.22],
        ("a_m12", "mse"):     [0.26, 0.26, 0.26],
    }
    records = _frozen_12_records(rel)
    # Replace seed 303 in a_64_32/huber with 999
    for i, r in enumerate(records):
        if r.architecture_id == "a_64_32" and r.loss == "huber" and r.seed == 303:
            records[i] = _make_record("a_64_32", [64, 32], "huber", 999, 0.20, 2817)
            break
    with pytest.raises(ValueError, match="expected seeds"):
        select_winner(records)


def test_inconsistent_widths_raises():
    records = _frozen_12_records()
    for i, r in enumerate(records):
        if r.architecture_id == "a_64_32" and r.loss == "huber" and r.seed == 202:
            records[i] = _make_record("a_64_32", [32, 16], "huber", 202, 0.253, 2817)
            break
    with pytest.raises(ValueError, match="inconsistent widths"):
        select_winner(records)


def test_inconsistent_param_count_raises():
    records = _frozen_12_records()
    for i, r in enumerate(records):
        if r.architecture_id == "a_64_32" and r.loss == "huber" and r.seed == 202:
            records[i] = _make_record("a_64_32", [64, 32], "huber", 202, 0.253, 9999)
            break
    with pytest.raises(ValueError, match="inconsistent param_count"):
        select_winner(records)


def test_negative_rel_rmse_raises():
    records = _frozen_12_records()
    for i, r in enumerate(records):
        if r.architecture_id == "a_64_32" and r.loss == "huber" and r.seed == 101:
            records[i] = _make_record("a_64_32", [64, 32], "huber", 101, -0.1, 2817)
            break
    with pytest.raises(ValueError, match="finite and non-negative"):
        select_winner(records)


def test_nan_rel_rmse_raises():
    records = _frozen_12_records()
    for i, r in enumerate(records):
        if r.architecture_id == "a_64_32" and r.loss == "huber" and r.seed == 101:
            records[i] = _make_record("a_64_32", [64, 32], "huber", 101, float("nan"), 2817)
            break
    with pytest.raises(ValueError, match="finite and non-negative"):
        select_winner(records)


# -- Production outputs-inventory test (real files, no training) --

def test_build_outputs_inventory_with_real_files():
    """Exercise build_outputs_inventory against real temp files.

    Writes checkpoints and verifies that the returned inventory contains
    correct paths, byte sizes, and SHA256 values for every file.
    """
    records = _frozen_12_records()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        # Write fake checkpoint files matching the expected naming convention
        for r in records:
            ckpt_name = f"checkpoint_{r.architecture_id}_{r.loss}_seed{r.seed}.pt"
            ckpt_path = out / ckpt_name
            ckpt_path.write_bytes(r.checkpoint_bytes)

        inventory = build_outputs_inventory(out, records)

        # fits.csv checks
        assert "fits.csv" in inventory
        csv_info = inventory["fits.csv"]
        assert (out / "fits.csv").exists()
        assert csv_info["size_bytes"] > 0
        assert len(csv_info["sha256"]) == 64
        assert all(c in "0123456789abcdef" for c in csv_info["sha256"])
        # Verify fits.csv has correct line count
        lines = (out / "fits.csv").read_text(encoding="utf-8").rstrip("\n").split("\n")
        assert lines[0].startswith("architecture_id")  # header
        assert len(lines) == 13  # header + 12 fits

        # checkpoint checks
        ckpts = inventory["checkpoints"]
        assert len(ckpts) == 12

        for c in ckpts:
            assert c["size_bytes"] == len(b"fake_ckpt")
            assert len(c["sha256"]) == 64
            assert all(k in c for k in (
                "name", "path", "size_bytes", "sha256",
                "architecture_id", "loss", "seed",
            ))
            # Verify the file exists and hashes match actual file content
            ckpt_path = Path(c["path"])
            assert ckpt_path.exists()
            actual_sha = hashlib.sha256(ckpt_path.read_bytes()).hexdigest()
            assert c["sha256"] == actual_sha

        # JSON roundtrip: the inventory must survive serialization
        encoded = json.dumps(inventory, sort_keys=True)
        decoded = json.loads(encoded)
        assert decoded["checkpoints"][0]["sha256"] == ckpts[0]["sha256"]


def test_ordering_is_correct():
    result = select_winner(_frozen_12_records())
    means = [c.mean_rel_rmse for c in result.all_candidates]
    assert means == sorted(means)
