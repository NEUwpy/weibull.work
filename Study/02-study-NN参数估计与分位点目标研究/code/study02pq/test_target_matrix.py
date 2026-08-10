"""目标敏感度矩阵增量的数学与回归测试。"""

from __future__ import annotations

import numpy as np
import torch

from study02pq import losses as LOSS


def _q_from_u(u: torch.Tensor, beta=3.0, eta=1000.0, gamma=500.0, R=0.95):
    b = torch.as_tensor(beta, dtype=u.dtype) * (1.0 + u[0])
    e = torch.as_tensor(eta, dtype=u.dtype) * (1.0 + u[1])
    g = torch.as_tensor(gamma, dtype=u.dtype) + torch.as_tensor(eta, dtype=u.dtype) * u[2]
    truth = LOSS.weibull_quantile(
        torch.as_tensor(beta, dtype=u.dtype),
        torch.as_tensor(eta, dtype=u.dtype),
        torch.as_tensor(gamma, dtype=u.dtype), R)
    pred = LOSS.weibull_quantile(b, e, g, R)
    return ((pred - truth) / truth) ** 2


def test_truth_matrix_is_symmetric_psd_rank_one_and_has_cross_terms():
    for R in (0.90, 0.95, 0.99):
        for beta in (1.5, 3.0, 5.0):
            for gamma in (100.0, 500.0, 1000.0):
                s = LOSS.relative_target_sensitivity_at_truth(
                    torch.tensor(beta, dtype=torch.float64),
                    torch.tensor(1000.0, dtype=torch.float64),
                    torch.tensor(gamma, dtype=torch.float64), R)
                matrix = torch.outer(s, s).numpy()
                assert np.allclose(matrix, matrix.T, atol=1e-14)
                eig = np.linalg.eigvalsh(matrix)
                assert eig[0] >= -1e-12 and eig[1] >= -1e-12 and eig[2] > 0
                assert np.linalg.matrix_rank(matrix, tol=1e-10) == 1
                assert np.max(np.abs(matrix - np.diag(np.diag(matrix)))) > 0


def test_matrix_loss_equals_explicit_quadratic_form():
    beta = torch.tensor([2.0, 4.5], dtype=torch.float64)
    eta = torch.tensor([1000.0, 1000.0], dtype=torch.float64)
    gamma = torch.tensor([250.0, 750.0], dtype=torch.float64)
    u = torch.tensor([[0.10, -0.05, 0.03], [-0.04, 0.08, -0.02]], dtype=torch.float64)
    bh = beta * (1 + u[:, 0]); eh = eta * (1 + u[:, 1]); gh = gamma + eta * u[:, 2]
    got = LOSS.target_matrix_truth_loss(bh, eh, gh, beta, eta, gamma, 0.95)
    s = LOSS.relative_target_sensitivity_at_truth(beta, eta, gamma, 0.95)
    expected = torch.mean(torch.einsum("bi,bij,bj->b", u,
                                       torch.einsum("bi,bj->bij", s, s), u))
    assert torch.allclose(got, expected, atol=1e-14, rtol=1e-12)


def test_q_hessian_at_truth_equals_twice_truth_matrix():
    for R in (0.90, 0.95, 0.99):
        u0 = torch.zeros(3, dtype=torch.float64, requires_grad=True)
        hessian = torch.autograd.functional.hessian(lambda u: _q_from_u(u, R=R), u0)
        s = LOSS.relative_target_sensitivity_at_truth(
            torch.tensor(3.0, dtype=torch.float64),
            torch.tensor(1000.0, dtype=torch.float64),
            torch.tensor(500.0, dtype=torch.float64), R)
        assert torch.allclose(hessian, 2.0 * torch.outer(s, s), atol=1e-10, rtol=1e-9)


def test_dynamic_exact_matrix_is_q_in_forward_and_gradient():
    """一个不 detach 的精确 secant 矩阵只是 Q 的恒等改写。"""
    R = 0.95
    truth = torch.tensor([3.0, 1000.0, 500.0], dtype=torch.float64)
    pred = torch.tensor([3.4, 930.0, 540.0], dtype=torch.float64, requires_grad=True)
    beta, eta, gamma = truth
    bh, eh, gh = pred
    u = torch.stack(((bh - beta) / beta, (eh - eta) / eta, (gh - gamma) / eta))
    t = torch.as_tensor(-np.log(R), dtype=torch.float64) ** (1.0 / beta)
    th = torch.as_tensor(-np.log(R), dtype=torch.float64) ** (1.0 / bh)
    x = gamma + eta * t
    # 精确分解：delta x = delta gamma + delta eta*t + eta_hat*(t_hat-t)。
    secant_beta = (eh * (th - t) / x) / u[0]
    secant = torch.stack((secant_beta, eta * t / x, eta / x))
    matrix_loss = torch.sum(secant * u) ** 2
    direct_loss = ((LOSS.weibull_quantile(bh, eh, gh, R) - x) / x) ** 2
    grad_matrix = torch.autograd.grad(matrix_loss, pred, retain_graph=True)[0]
    grad_direct = torch.autograd.grad(direct_loss, pred)[0]
    assert torch.allclose(matrix_loss, direct_loss, atol=1e-14, rtol=1e-12)
    assert torch.allclose(grad_matrix, grad_direct, atol=1e-12, rtol=1e-10)


def test_existing_p_and_q_route_contracts_are_unchanged():
    p, pk = LOSS.build_route_loss("P")
    q, qk = LOSS.build_route_loss("Q", target_R=0.95)
    m, mk = LOSS.build_route_loss("M95", target_R=0.95)
    assert callable(p) and callable(q) and callable(m)
    assert (pk, qk, mk) == ("params", "x_R", "params")


def test_unapproved_matrix_routes_are_rejected():
    import pytest
    with pytest.raises(ValueError):
        LOSS.build_route_loss("M90", target_R=0.90)
    with pytest.raises(ValueError):
        LOSS.build_route_loss("MAGIC", target_R=0.95)
    with pytest.raises(ValueError):
        LOSS.build_route_loss("M95", target_R=0.99)


def test_selected_source_evidence_is_sha_bound_finite_and_legal():
    import pytest
    if LOSS.CFG.PROTOCOL_VERSION != "iid-v1":
        pytest.skip("source evidence audit is specific to PQ_PROTOCOL=iid-v1")
    from study02pq import target_matrix_pilot as PILOT
    audit = PILOT._audit_source_selection()
    assert audit["n_metadata"] == audit["n_evidence"] == 48
    assert audit["n_rows"] == 48 * 2400
    assert audit["nonfinite_values"] == audit["support_violations"] == 0
    assert len(audit["selected_files"]) == 96


def test_resume_rejects_wrong_route(monkeypatch, tmp_path):
    import hashlib
    import json
    import pytest
    if LOSS.CFG.PROTOCOL_VERSION != "iid-v1":
        pytest.skip("matrix resume path is specific to PQ_PROTOCOL=iid-v1")
    from study02pq import target_matrix_pilot as PILOT

    root = tmp_path / "pilot"
    (root / "fit_metadata").mkdir(parents=True)
    (root / "evidence").mkdir()
    fit = "n7_f1_s42_rM95"
    ev_path = root / "evidence" / f"{fit}.npz"
    one = np.array([1.0], dtype=np.float32)
    np.savez_compressed(
        ev_path, keys_beta=np.array([2.0]), keys_gamma_over_eta=np.array([0.5]),
        keys_n=np.array([7], dtype=np.int32), keys_repeat_id=np.array([0], dtype=np.int32),
        beta_hat=one, eta_hat=one, gamma_hat=one, x95_hat=one, x95_true=one,
        min_x=np.array([2.0], dtype=np.float32), rel_err=np.zeros(1, dtype=np.float32),
        rel_err_sq=np.zeros(1, dtype=np.float32))
    digest = hashlib.sha256(ev_path.read_bytes()).hexdigest()
    meta = {"route": "M90", "target_R": 0.95, "evidence_sha256": digest}
    (root / "fit_metadata" / f"{fit}.json").write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr(PILOT, "ART_ROOT", root)
    with pytest.raises(RuntimeError, match="route"):
        PILOT._fit_complete_verified(fit, PILOT._implementation_shas())


def test_matrix_validator_rejects_corrupt_evidence_sha(monkeypatch, tmp_path):
    import json
    import pytest
    if LOSS.CFG.PROTOCOL_VERSION != "iid-v1":
        pytest.skip("matrix evidence path is specific to PQ_PROTOCOL=iid-v1")
    from study02pq import target_matrix_pilot as PILOT

    root = tmp_path / "pilot"
    (root / "fit_metadata").mkdir(parents=True)
    (root / "evidence").mkdir()
    fit = "n7_f1_s42_rM95"
    ev_path = root / "evidence" / f"{fit}.npz"
    one = np.array([1.0], dtype=np.float32)
    np.savez_compressed(
        ev_path, keys_beta=np.array([2.0]), keys_gamma_over_eta=np.array([0.5]),
        keys_n=np.array([7], dtype=np.int32), keys_repeat_id=np.array([0], dtype=np.int32),
        beta_hat=one, eta_hat=one, gamma_hat=one, x95_hat=one, x95_true=one,
        min_x=np.array([2.0], dtype=np.float32), rel_err=np.zeros(1, dtype=np.float32),
        rel_err_sq=np.zeros(1, dtype=np.float32))
    implementation = PILOT._implementation_shas()
    meta = {
        "route": "M95", "target_R": 0.95, "evidence_sha256": "0" * 64,
        "matrix_contract_id": PILOT.PILOT["contract_id"],
        "matrix_config_sha256": PILOT._sha(PILOT.CONFIG_PATH),
        "matrix_implementation_sha256": implementation,
    }
    (root / "fit_metadata" / f"{fit}.json").write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr(PILOT, "ART_ROOT", root)
    with pytest.raises(RuntimeError, match="SHA"):
        PILOT._fit_complete_verified(fit, implementation)
