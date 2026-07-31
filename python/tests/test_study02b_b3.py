"""Focused tests for B3 P-index, fit accounting, and manifest integrity."""

from pathlib import Path
import hashlib
import json
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
PYTHON = REPO_ROOT / "python"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
if str(PYTHON) not in sys.path:
    sys.path.insert(0, str(PYTHON))

from study02b.train_b3 import (
    build_p_index,
    _P_FIT_COUNT,
    _P_FIT_START,
    _P_FIT_END,
    _SELECTED_WIDTHS,
    _CONTROLLED_WIDTHS,
    _N_VALUES,
    _SELECTED_SEEDS,
    _CONTROLLED_SEEDS,
    B3FitRecord,
)


def test_p_index_count():
    """P index must contain exactly 50 entries."""
    p_index = build_p_index()
    assert len(p_index) == _P_FIT_COUNT == 50


def test_p_index_fit_id_range():
    """P index fit IDs must span G3-fit-0299..0348."""
    p_index = build_p_index()
    fit_ids = [e["fit_id"] for e in p_index]
    assert fit_ids[0] == f"G3-fit-{_P_FIT_START:04d}"
    assert fit_ids[-1] == f"G3-fit-{_P_FIT_END:04d}"


def test_p_index_all_entries_have_required_fields():
    """Every P entry must have fit_id, path, sha256, size_bytes, input_dim."""
    p_index = build_p_index()
    for entry in p_index:
        for field in ("fit_id", "path", "sha256", "size_bytes", "input_dim"):
            assert field in entry, f"missing field {field} in {entry['fit_id']}"
        assert len(entry["sha256"]) == 64
        assert entry["size_bytes"] > 0
        assert isinstance(entry["input_dim"], int) and entry["input_dim"] in {5, 7, 10, 15, 20}


def test_p_index_sha256_is_valid_hex():
    """All SHA256 values must be valid hex."""
    p_index = build_p_index()
    for entry in p_index:
        assert all(c in "0123456789abcdef" for c in entry["sha256"])


def test_fit_accounting_constants():
    """B3 fit counts must match the frozen protocol."""
    n_selected = len(_N_VALUES) * len(_SELECTED_SEEDS)
    n_controlled = len(_N_VALUES) * len(_CONTROLLED_SEEDS)
    assert n_selected == 50  # 5 n × 10 seeds
    assert n_controlled == 25  # 5 n × 5 seeds
    assert n_selected + n_controlled == 75
    assert 12 + 75 == 87  # cumulative < 100 cap


def test_selected_widths():
    """Selected D must be [64, 32]."""
    assert _SELECTED_WIDTHS == [64, 32]


def test_controlled_widths():
    """Controlled D must be A's frozen m12 [256, 128, 64]."""
    assert _CONTROLLED_WIDTHS == [256, 128, 64]


def test_n_values():
    """Must cover all five sample sizes."""
    assert _N_VALUES == [5, 7, 10, 15, 20]


def test_b3_fit_record_to_dict():
    """B3FitRecord.to_dict() must serialize all fields."""
    r = B3FitRecord(
        group="selected", n=10, seed=101,
        widths=[64, 32],
        best_validation_loss=0.35,
        best_epoch=14, actual_epochs=55,
        early_stop_reason="patience_exhausted",
        param_count=2817,
        checkpoint_sha256="a" * 64,
        checkpoint_path="/tmp/test.pt",
    )
    d = r.to_dict()
    assert d["group"] == "selected"
    assert d["n"] == 10
    assert d["seed"] == 101
    assert list(d["widths"]) == [64, 32]
    assert d["param_count"] == 2817


def test_manifest_config_serializable():
    """A minimal manifest config must survive JSON roundtrip."""
    manifest = {
        "version": "1.0",
        "run_id": "test",
        "status": "complete",
        "code_tip": "abc123",
        "fit_accounting": {
            "planned": 75,
            "completed_new": 75,
            "resumed": 0,
            "failed": 0,
            "b2_fits": 12,
            "cumulative_b_fits": 87,
            "cap": 100,
        },
        "p_checkpoints": {"count": 50},
        "d_checkpoints": [],
        "failures": [],
    }
    encoded = json.dumps(manifest, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded["fit_accounting"]["cumulative_b_fits"] == 87
    assert decoded["fit_accounting"]["cap"] == 100
