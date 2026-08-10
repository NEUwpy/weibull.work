"""pq-mechanism-closure-v1 的数学与证据回归测试。"""

from __future__ import annotations

import numpy as np
import torch

from . import config as CFG
from . import mechanism_closure as MC


def test_truth_geometry_matches_autograd_on_frozen_grid():
    grid, checks = MC.verification_grid()
    assert len(grid) == 40 * 3
    assert checks["all_pass"]
    assert checks["loss_hessian_max_abs_error"] < 1e-12


def test_p_equal_geometry_is_equal_coefficient_in_u_coordinates():
    u = torch.tensor([0.2, -0.3, 0.4], dtype=torch.float64, requires_grad=True)
    loss = torch.dot(u, u)
    grad = torch.autograd.grad(loss, u, create_graph=True)[0]
    hessian = torch.autograd.functional.hessian(lambda x: torch.dot(x, x), u)
    assert torch.allclose(grad, 2.0 * u)
    assert torch.allclose(hessian, 2.0 * torch.eye(3, dtype=torch.float64))


def test_q_truth_hessian_is_rank_one_target_matrix():
    s, _ = MC.truth_geometry(3.5, CFG.ETA, 0.5 * CFG.ETA, 0.95)
    h = 2.0 * np.outer(s, s)
    assert np.linalg.matrix_rank(h, tol=1e-12) == 1
    assert np.all(np.linalg.eigvalsh(h) >= -1e-14)


def test_dynamic_secant_forward_and_gradient_equal_q():
    checks = MC.secant_checks()
    assert checks["all_pass"]
    assert checks["min_detach_gradient_difference"] > 1e-6


def test_static_matrix_has_finite_zero_space_counterexample_and_fourth_order_q():
    checks = MC.zero_space_checks()
    assert checks["all_pass"]
    for case in checks["cases"]:
        assert case["M95_at_finite_step"] < 1e-28
        assert case["Q_at_finite_step"] > 0.0
        assert abs(case["Q_small_step_loglog_slope"] - 4.0) < 0.08


def test_row_squared_decomposition_is_exact():
    meta, path, _ = MC._source_paths(10, 0, 42, "P")
    assert meta.is_file()
    cell = MC.cell_geometry(MC.load_npz(path))
    total = cell["static_local_mse"] + cell["cross_term"] + cell["nonlinear_remainder_mse"]
    assert abs(cell["target_mse"] - total) < 1e-14
    assert cell["square_identity_max_abs_error"] < 1e-14


def test_frozen_source_sha_keys_finite_and_support_audit():
    audit, files = MC.audit_sources()
    assert audit["all_pass"]
    assert audit["pq_pairs"] == 200
    assert audit["pmq_cells"] == 24
    assert audit["fits"] == 424
    assert audit["rows"] == 424 * 2400
    assert len(files) == 424 * 2


def test_estimands_stay_separate_and_have_expected_cells():
    pq, pmq, summary = MC.analyze_cells()
    assert len(pq) == 200 * 2
    assert len(pmq) == 24 * 3
    assert summary["checks"]["pq_cells"] == 200
    assert summary["checks"]["pmq_cells"] == 24
    d = summary["m95_minus_p_exact_mse_decomposition"]
    assert abs(d["target_mse"] - d["component_sum"]) < 1e-14
