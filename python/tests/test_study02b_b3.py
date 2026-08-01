"""Focused tests for B3 P-index, fit accounting, target_stats, and manifest."""

from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pytest
import torch


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
    compute_target_stats_for_n,
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
from study02a.models import build_mlp
from study02a.training import load_checkpoint


# -- P index --

def test_p_index_count():
    p_index = build_p_index()
    assert len(p_index) == _P_FIT_COUNT == 50


def test_p_index_fit_id_range():
    p_index = build_p_index()
    fit_ids = [e["fit_id"] for e in p_index]
    assert fit_ids[0] == f"G3-fit-{_P_FIT_START:04d}"
    assert fit_ids[-1] == f"G3-fit-{_P_FIT_END:04d}"


def test_p_index_required_fields():
    """Every P entry must have n, seed, plan_row_sha256, sha256, path, size_bytes."""
    p_index = build_p_index()
    for entry in p_index:
        for field in ("fit_id", "path", "sha256", "size_bytes",
                      "n", "seed", "plan_row_sha256", "route"):
            assert field in entry, f"missing field {field} in {entry['fit_id']}"
        assert len(entry["sha256"]) == 64
        assert len(entry["plan_row_sha256"]) == 64
        assert entry["size_bytes"] > 0
        assert isinstance(entry["n"], int) and entry["n"] in {5, 7, 10, 15, 20}
        assert isinstance(entry["seed"], int)


def test_p_index_grid_integrity():
    """Exactly 10 distinct formal seeds per n, 5 n values 脳 10 seeds = 50."""
    p_index = build_p_index()
    by_n: dict[int, set[int]] = {}
    for entry in p_index:
        n_val = entry["n"]
        seed = entry["seed"]
        by_n.setdefault(n_val, set()).add(seed)
    assert set(by_n.keys()) == set(_N_VALUES)
    for n_val in _N_VALUES:
        seeds = by_n[n_val]
        assert len(seeds) == 10, f"n={n_val}: expected 10 seeds, got {len(seeds)} {sorted(seeds)}"


def test_p_index_sha256_is_valid_hex():
    p_index = build_p_index()
    for entry in p_index:
        assert all(c in "0123456789abcdef" for c in entry["sha256"])


def test_p_index_load_and_decode():
    """A P checkpoint can be loaded with m12 [256,128,64] and forward-passed."""
    p_index = build_p_index()
    entry = p_index[0]  # G3-fit-0299, n=5
    ckpt_bytes = Path(entry["path"]).read_bytes()
    state = load_checkpoint(ckpt_bytes)
    model = build_mlp(
        input_dim=entry["n"], widths=[256, 128, 64],
        activation="silu", dropout=0.1,
    )
    model.load_state_dict(state)
    model.eval()
    with torch.no_grad():
        out = model(torch.randn(1, entry["n"]))
    assert out.shape == (1, 3)


# -- target_stats --

def test_compute_target_stats_for_all_n():
    """Target stats must be computable for all five n values."""
    for n in _N_VALUES:
        stats = compute_target_stats_for_n(n)
        assert stats["n"] == n
        assert isinstance(stats["mean"], float)
        assert isinstance(stats["sd"], float)
        assert np.isfinite(stats["mean"])
        assert stats["sd"] >= 0


def test_target_stats_deterministic():
    """Same n, same stats — deterministic generation."""
    s1 = compute_target_stats_for_n(10)
    s2 = compute_target_stats_for_n(10)
    assert s1["mean"] == s2["mean"]
    assert s1["sd"] == s2["sd"]


# -- Fit accounting --

def test_fit_accounting_constants():
    n_selected = len(_N_VALUES) * len(_SELECTED_SEEDS)
    n_controlled = len(_N_VALUES) * len(_CONTROLLED_SEEDS)
    assert n_selected == 50
    assert n_controlled == 25
    assert n_selected + n_controlled == 75
    assert 12 + 75 == 87


def test_selected_widths():
    assert _SELECTED_WIDTHS == [64, 32]


def test_controlled_widths():
    assert _CONTROLLED_WIDTHS == [256, 128, 64]


def test_n_values():
    assert _N_VALUES == [5, 7, 10, 15, 20]


def test_b3_fit_record_to_dict():
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
    manifest = {
        "version": "1.0",
        "run_id": "test",
        "status": "complete",
        "code_tip": "abc123",
        "target_stats": {
            "10": {"n": 10, "mean": 0.5, "sd": 1.0},
        },
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
    assert decoded["target_stats"]["10"]["mean"] == 0.5
