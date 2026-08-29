from __future__ import annotations

import json
from pathlib import Path

from . import config as CFG


SUMMARY = Path(CFG.STUDY02_ROOT) / "artifacts" / "qcp_bias_variance" / "analysis" / "summary.json"


def _summary() -> dict:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_decomposition_identity_and_grid() -> None:
    summary = _summary()
    assert summary["truth_cells_per_route"] == 160
    assert summary["predictions_per_truth_cell"] == 3000
    for values in summary["routes"].values():
        assert abs(values["decomposition_residual"]) < 1e-12


def test_rmsre_order_and_bias_direction() -> None:
    routes = _summary()["routes"]
    assert routes["QCP"]["rmsre"] < routes["Q"]["rmsre"] < routes["P"]["rmsre"]
    assert all(routes[route]["signed_relative_bias"] < 0.0 for route in ("P", "Q", "QCP"))


def test_true_life_scale_range_is_material() -> None:
    limits = _summary()["x95_true_range"]
    assert limits["maximum"] / limits["minimum"] > 6.0
