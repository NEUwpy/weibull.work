"""P+Q auxiliary-parameter loss and sealed-screening regression tests."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from . import data as DATA
from . import losses as LOSS
from . import training as TR


def _tiny_master(repeats: int = 15):
    return DATA.build_master(
        beta_grid=[1.5, 2.5], gamma_grid=[100.0], n_grid=[7], repeats=repeats,
        seed_namespace="study02_qp_test",
    )


def test_qp_objective_is_q_plus_lambda_p_and_checkpoint_is_q():
    out = torch.tensor([[0.2, 6.0, -0.3], [0.8, 6.5, 0.4]], dtype=torch.float64)
    params = torch.tensor([[2.0, 1000.0, 100.0], [3.0, 1000.0, 250.0]],
                          dtype=torch.float64)
    min_x = torch.tensor([250.0, 400.0], dtype=torch.float64)
    q, p = LOSS.parameter_target_loss_components(out, params, min_x)
    objective, kind = LOSS.build_route_loss("QP", lambda_p=0.01)
    selection, selection_kind = LOSS.build_selection_loss("QP", lambda_p=0.01)
    assert kind == selection_kind == "params"
    assert torch.allclose(objective(out, params, min_x), q + 0.01 * p)
    assert torch.allclose(selection(out, params, min_x), q)


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_qp_rejects_invalid_lambda(bad):
    with pytest.raises(ValueError):
        LOSS.build_route_loss("QP", lambda_p=bad)


def test_qp_screening_records_history_without_test_access(monkeypatch):
    master = _tiny_master()
    monkeypatch.setattr(DATA.CFG, "BETA_GRID", [1.5, 2.5])
    monkeypatch.setattr(DATA.CFG, "GAMMA_GRID", [100.0])
    result = TR.train_one_fit(
        7, 0, 42, "QP", master, max_epochs=3, batch_size=16, patience=2,
        split_strategy="repeat_stratified", lambda_p=0.001,
        record_history=True, evaluate_test=False,
    )
    meta = result["meta"]
    assert meta["route"] == "QP"
    assert meta["route_loss"] == "Q_plus_lambda_P"
    assert meta["checkpoint_loss"] == "Q"
    assert meta["lambda_p"] == 0.001
    assert meta["test_evaluated"] is False
    assert "predictions" not in result and "rrmse_x95" not in meta
    assert 1 <= len(result["history"]) <= 3
    expected = {"epoch", "train_objective", "val_objective",
                "train_q_loss", "val_q_loss", "train_p_loss", "val_p_loss"}
    assert expected == set(result["history"][0])
    assert all(np.isfinite(list(row.values())).all() for row in result["history"])


def test_q_and_zero_lambda_qp_share_pairing_and_validation_target(monkeypatch):
    master = _tiny_master()
    monkeypatch.setattr(DATA.CFG, "BETA_GRID", [1.5, 2.5])
    monkeypatch.setattr(DATA.CFG, "GAMMA_GRID", [100.0])
    common = dict(
        max_epochs=3, batch_size=16, patience=2,
        split_strategy="repeat_stratified", evaluate_test=False,
    )
    q = TR.train_one_fit(7, 0, 42, "Q", master, **common)
    qp = TR.train_one_fit(7, 0, 42, "QP", master, lambda_p=0.0, **common)
    for key in ["init_param_sha", "batch_order_sha", "network_sha", "scaler_sha",
                "train_rows_sha", "val_rows_sha", "test_rows_sha"]:
        assert q["meta"][key] == qp["meta"][key]
    assert np.isclose(q["meta"]["best_val_loss"], qp["meta"]["best_val_loss"],
                      rtol=1e-12, atol=1e-14)


def test_qcp_uses_q_for_selection_and_requires_constraint_arguments(monkeypatch):
    out = torch.tensor([[0.2, 6.0, -0.3]], dtype=torch.float64)
    params = torch.tensor([[2.0, 1000.0, 100.0]], dtype=torch.float64)
    min_x = torch.tensor([250.0], dtype=torch.float64)
    q, _ = LOSS.parameter_target_loss_components(out, params, min_x)
    objective, kind = LOSS.build_route_loss("QCP")
    selection, selection_kind = LOSS.build_selection_loss("QCP")
    assert kind == selection_kind == "params"
    assert torch.allclose(objective(out, params, min_x), q)
    assert torch.allclose(selection(out, params, min_x), q)

    master = _tiny_master()
    monkeypatch.setattr(DATA.CFG, "BETA_GRID", [1.5, 2.5])
    monkeypatch.setattr(DATA.CFG, "GAMMA_GRID", [100.0])
    common = dict(max_epochs=2, batch_size=16, patience=2,
                  split_strategy="repeat_stratified", evaluate_test=False)
    with pytest.raises(ValueError):
        TR.train_one_fit(7, 0, 42, "QCP", master, **common)
    with pytest.raises(ValueError):
        TR.train_one_fit(7, 0, 42, "QCP", master,
                         p_constraint_limit=0.1, constraint_rho=0.0, **common)


def test_qcp_records_adaptive_constraint_state_without_test_access(monkeypatch):
    master = _tiny_master()
    monkeypatch.setattr(DATA.CFG, "BETA_GRID", [1.5, 2.5])
    monkeypatch.setattr(DATA.CFG, "GAMMA_GRID", [100.0])
    result = TR.train_one_fit(
        7, 0, 42, "QCP", master, max_epochs=3, batch_size=16, patience=2,
        split_strategy="repeat_stratified", p_constraint_limit=0.08,
        constraint_rho=0.1, record_history=True, evaluate_test=False,
    )
    meta = result["meta"]
    assert meta["route"] == "QCP"
    assert meta["checkpoint_loss"] == "Q"
    assert meta["constraint_form"] == "Q_min_subject_to_P_limit"
    assert meta["p_constraint_limit"] == 0.08
    assert meta["constraint_rho"] == 0.1
    assert meta["test_evaluated"] is False
    assert "predictions" not in result
    row = result["history"][0]
    for key in ["p_constraint_limit", "constraint_violation", "dual_multiplier"]:
        assert key in row and np.isfinite(row[key])
