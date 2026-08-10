"""P_equal/Q_param 机制闭环的无训练几何分析。

只读复用冻结的 200-cell P/Q 与 24-cell P/M95/Q evidence，严格审计 SHA、
metadata、keys、finite 与 Weibull 支撑域；不创建或修改任何 fit。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import csv
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from . import config as CFG
from . import training as TR


ROOT = Path(CFG.STUDY02_ROOT)
OUT = ROOT / "artifacts" / "pq_mechanism_closure"
MAIN = ROOT / "artifacts" / "pq_iid_main"
S5B_ROOT = ROOT / "artifacts" / "pq_s5b_revision"
MATRIX = ROOT / "artifacts" / "pq_target_matrix_pilot"
PROTOCOL = ROOT / "protocols" / "11-PQ-机制闭环分析合同.md"
S5B_CONFIG = ROOT / "configs" / "pq-s5b-revision-v1.json"
CODE = Path(__file__)
TARGETS = {"B10": 0.90, "B5": 0.95, "B1": 0.99}
KEY_FIELDS = ("keys_beta", "keys_gamma_over_eta", "keys_n")


def load_s5b_protocol() -> dict:
    return json.loads(S5B_CONFIG.read_text(encoding="utf-8"))


def canonical_sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() not in {".npz", ".png", ".pdf"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def raw_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_map(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, rel = line.split(maxsplit=1)
            result[rel.replace("\\", "/")] = digest
    return result


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as archive:
        return {name: archive[name] for name in archive.files}


def point_key(ev: dict[str, np.ndarray]) -> np.ndarray:
    name = "keys_point_or_repeat_id" if "keys_point_or_repeat_id" in ev else "keys_repeat_id"
    return ev[name]


def all_keys(ev: dict[str, np.ndarray]) -> tuple[np.ndarray, ...]:
    return tuple(ev[name] for name in KEY_FIELDS) + (point_key(ev),)


def assert_key_grid(ev: dict[str, np.ndarray], n: int) -> None:
    expected_beta = np.asarray(CFG.BETA_GRID, dtype=np.float64)
    expected_goe = np.asarray(CFG.GAMMA_OVER_ETA_GRID, dtype=np.float64)
    if not np.array_equal(np.unique(ev["keys_beta"]), expected_beta):
        raise AssertionError("beta key grid changed")
    if not np.array_equal(np.unique(ev["keys_gamma_over_eta"]), expected_goe):
        raise AssertionError("gamma/eta key grid changed")
    if not np.array_equal(np.unique(ev["keys_n"]), np.asarray([n])):
        raise AssertionError("n key changed")
    keys = np.column_stack(all_keys(ev))
    if len(keys) != 2400 or len(np.unique(keys, axis=0)) != 2400:
        raise AssertionError("held-out key identity is not the frozen 40 x 60 grid")


def _source_paths(n: int, fold: int, seed: int, route: str) -> tuple[Path, Path, str]:
    fit = TR.fit_id(n, fold, seed, route)
    if seed in {42, 2026, 3407}:
        return (MAIN / "fit_metadata" / f"{fit}.json",
                MAIN / "evidence" / f"{fit}.npz", "main")
    return (S5B_ROOT / "grid_extra" / "fit_metadata" / f"{fit}.json",
            S5B_ROOT / "grid_extra" / "evidence" / f"{fit}.npz", "s5b")


def _matrix_paths(n: int, fold: int, seed: int) -> tuple[Path, Path, str]:
    fit = TR.fit_id(n, fold, seed, "M95")
    return (MATRIX / "fit_metadata" / f"{fit}.json",
            MATRIX / "evidence" / f"{fit}.npz", "matrix")


def audit_sources() -> tuple[dict, list[dict]]:
    """审计所有 400 个 P/Q fits 与 24 个 M95 fits；返回摘要与文件级证据表。"""
    maps = {
        "main": sha_map(MAIN / "SHA256SUMS"),
        "s5b": sha_map(S5B_ROOT / "SHA256SUMS"),
        "matrix": sha_map(MATRIX / "SHA256SUMS"),
    }
    records: list[dict] = []
    counts = {"fits": 0, "rows": 0, "nonfinite_rows": 0,
              "support_violations": 0, "key_grid_failures": 0,
              "sha_failures": 0, "metadata_sha_failures": 0}

    def audit_fit(meta: Path, evidence: Path, source: str, n: int, route: str) -> dict:
        if source == "main":
            meta_rel = meta.relative_to(MAIN).as_posix()
            ev_rel = evidence.relative_to(MAIN).as_posix()
        elif source == "matrix":
            meta_rel = meta.relative_to(MATRIX).as_posix()
            ev_rel = evidence.relative_to(MATRIX).as_posix()
        else:
            meta_rel = meta.relative_to(ROOT).as_posix()
            ev_rel = evidence.relative_to(ROOT).as_posix()
        for path, rel in ((meta, meta_rel), (evidence, ev_rel)):
            got, expected = canonical_sha(path), maps[source].get(rel)
            ok = got == expected
            counts["sha_failures"] += int(not ok)
            records.append({"source": source, "route": route,
                            "path": path.relative_to(ROOT).as_posix(),
                            "sha256": got, "sha_list_match": ok})
            if not ok:
                raise AssertionError(f"SHA mismatch or missing list entry: {path}")
        metadata = json.loads(meta.read_text(encoding="utf-8"))
        meta_ok = metadata.get("evidence_sha256") == raw_sha(evidence)
        counts["metadata_sha_failures"] += int(not meta_ok)
        if not meta_ok:
            raise AssertionError(f"metadata evidence SHA mismatch: {evidence}")
        ev = load_npz(evidence)
        try:
            assert_key_grid(ev, n)
        except AssertionError:
            counts["key_grid_failures"] += 1
            raise
        fields = ("beta_hat", "eta_hat", "gamma_hat", "min_x", "rel_err", "rel_err_sq")
        bad = ~np.all(np.isfinite(np.column_stack([ev[name] for name in fields])), axis=1)
        support = ((ev["beta_hat"] <= 0.0) | (ev["eta_hat"] <= 0.0) |
                   (ev["gamma_hat"].astype(float) >= ev["min_x"].astype(float)))
        counts["fits"] += 1
        counts["rows"] += len(ev["beta_hat"])
        counts["nonfinite_rows"] += int(np.sum(bad))
        counts["support_violations"] += int(np.sum(support))
        if np.any(bad) or np.any(support):
            raise AssertionError(f"finite/support audit failed: {evidence}")
        return ev

    protocol = load_s5b_protocol()
    seeds = [int(v) for v in protocol["seeds"]["all"]]
    pair_count = 0
    for n in CFG.N_GRID:
        for fold in range(CFG.N_FOLDS):
            for seed in seeds:
                pair = []
                for route in ("P", "Q"):
                    pair.append(audit_fit(*_source_paths(n, fold, seed, route), n, route))
                if not all(np.array_equal(a, b) for a, b in zip(all_keys(pair[0]), all_keys(pair[1]))):
                    raise AssertionError("P/Q key pairing mismatch")
                pair_count += 1

    matrix_cells = 0
    for n in CFG.N_GRID:
        for fold in (0, 2):
            for seed in (42, 2026, 3407):
                ep = load_npz(_source_paths(n, fold, seed, "P")[1])
                eq = load_npz(_source_paths(n, fold, seed, "Q")[1])
                em = audit_fit(*_matrix_paths(n, fold, seed), n, "M95")
                if not all(np.array_equal(a, b) for x in (eq, em)
                           for a, b in zip(all_keys(ep), all_keys(x))):
                    raise AssertionError("P/M95/Q key pairing mismatch")
                matrix_cells += 1

    summary = {
        **counts, "pq_pairs": pair_count, "pmq_cells": matrix_cells,
        "all_pass": all(counts[k] == 0 for k in
                        ("nonfinite_rows", "support_violations", "key_grid_failures",
                         "sha_failures", "metadata_sha_failures")),
        "source_sha_lists": {
            "pq_iid_main": canonical_sha(MAIN / "SHA256SUMS"),
            "pq_s5b_revision": canonical_sha(S5B_ROOT / "SHA256SUMS"),
            "pq_target_matrix_pilot": canonical_sha(MATRIX / "SHA256SUMS"),
        },
    }
    return summary, records


def target_error_np(u: np.ndarray, beta: float, eta: float, gamma: float, R: float) -> float:
    ub, ue, ug = np.asarray(u, dtype=np.float64)
    bh, eh, gh = beta * (1.0 + ub), eta * (1.0 + ue), gamma + eta * ug
    a = -np.log(R)
    x0 = gamma + eta * a ** (1.0 / beta)
    return float((gh + eh * a ** (1.0 / bh) - x0) / x0)


def truth_geometry(beta: float, eta: float, gamma: float, R: float) -> tuple[np.ndarray, np.ndarray]:
    """返回 e(u) 在 u=0 的解析梯度和 Hessian。"""
    a = -np.log(R)
    t = a ** (1.0 / beta)
    x0 = gamma + eta * t
    c = -np.log(a) / beta
    s = np.asarray([eta * t * c / x0, eta * t / x0, eta / x0])
    h = np.zeros((3, 3), dtype=np.float64)
    h[0, 0] = eta * t * (c * c - 2.0 * c) / x0
    h[0, 1] = h[1, 0] = eta * t * c / x0
    return s, h


def target_error_torch(u: torch.Tensor, truth: torch.Tensor, R: float) -> torch.Tensor:
    beta, eta, gamma = truth.unbind()
    bh = beta * (1.0 + u[0])
    eh = eta * (1.0 + u[1])
    gh = gamma + eta * u[2]
    a = torch.as_tensor(-np.log(R), dtype=u.dtype, device=u.device)
    x0 = gamma + eta * a ** (1.0 / beta)
    return (gh + eh * a ** (1.0 / bh) - x0) / x0


def secant_matrix_loss(u: torch.Tensor, truth: torch.Tensor, R: float,
                       *, detach: bool = False, order: int = 64) -> torch.Tensor:
    """可微 Gauss-Legendre 路径积分实现 ``(bar_s(u)^T u)^2``。"""
    nodes, weights = np.polynomial.legendre.leggauss(order)
    ts = torch.as_tensor((nodes + 1.0) / 2.0, dtype=u.dtype, device=u.device)
    ws = torch.as_tensor(weights / 2.0, dtype=u.dtype, device=u.device)
    terms = []
    for t, w in zip(ts, ws):
        z = t * u
        e = target_error_torch(z, truth, R)
        g = torch.autograd.grad(e, z, create_graph=True)[0]
        terms.append(w * g)
    bar_s = torch.stack(terms).sum(dim=0)
    if detach:
        bar_s = bar_s.detach()
    return torch.dot(bar_s, u) ** 2


def verification_grid() -> tuple[list[dict], dict]:
    records = []
    max_grad = max_e_hess = max_loss_hess = 0.0
    for target, R in TARGETS.items():
        for beta in CFG.BETA_GRID:
            for goe in CFG.GAMMA_OVER_ETA_GRID:
                truth = torch.tensor([beta, CFG.ETA, goe * CFG.ETA], dtype=torch.float64)
                u0 = torch.zeros(3, dtype=torch.float64, requires_grad=True)
                fn = lambda u: target_error_torch(u, truth, R)
                g_auto = torch.autograd.functional.jacobian(fn, u0).detach().numpy()
                h_auto = torch.autograd.functional.hessian(fn, u0).detach().numpy()
                hl_auto = torch.autograd.functional.hessian(lambda u: fn(u) ** 2, u0).detach().numpy()
                s, h = truth_geometry(beta, CFG.ETA, goe * CFG.ETA, R)
                hl = 2.0 * np.outer(s, s)
                max_grad = max(max_grad, float(np.max(np.abs(g_auto - s))))
                max_e_hess = max(max_e_hess, float(np.max(np.abs(h_auto - h))))
                max_loss_hess = max(max_loss_hess, float(np.max(np.abs(hl_auto - hl))))
                rec = {"target": target, "R": R, "beta": beta,
                       "gamma_over_eta": goe, "x_R_over_eta":
                       goe + (-np.log(R)) ** (1.0 / beta)}
                rec.update({f"s_{name}": float(s[i]) for i, name in enumerate(("beta", "eta", "gamma"))})
                rec["s_norm"] = float(np.linalg.norm(s))
                for i, a in enumerate(("beta", "eta", "gamma")):
                    for j, b in enumerate(("beta", "eta", "gamma")):
                        rec[f"H_e_{a}_{b}"] = float(h[i, j])
                        rec[f"H_LQ_{a}_{b}"] = float(hl[i, j])
                records.append(rec)
    checks = {"n_truth_target_points": len(records), "gradient_max_abs_error": max_grad,
              "target_hessian_max_abs_error": max_e_hess,
              "loss_hessian_max_abs_error": max_loss_hess,
              "all_pass": max(max_grad, max_e_hess, max_loss_hess) < 1e-12}
    return records, checks


def secant_checks() -> dict:
    cases = [
        ([2.0, 1000.0, 250.0], [0.20, -0.10, 0.15], 0.95),
        ([3.5, 1000.0, 500.0], [-0.25, 0.30, -0.20], 0.99),
        ([5.0, 1000.0, 1000.0], [0.45, -0.35, 0.25], 0.90),
        ([1.5, 1000.0, 100.0], [0.60, 0.40, -0.05], 0.95),
    ]
    rows = []
    for truth_values, u_values, R in cases:
        truth = torch.tensor(truth_values, dtype=torch.float64)
        u = torch.tensor(u_values, dtype=torch.float64, requires_grad=True)
        q = target_error_torch(u, truth, R) ** 2
        gq = torch.autograd.grad(q, u, retain_graph=True)[0]
        sec = secant_matrix_loss(u, truth, R)
        gs = torch.autograd.grad(sec, u, retain_graph=True)[0]
        detached = secant_matrix_loss(u, truth, R, detach=True)
        gd = torch.autograd.grad(detached, u)[0]
        rows.append({"truth": truth_values, "u": u_values, "R": R,
                     "forward_abs_error": float(abs(q - sec).detach()),
                     "gradient_max_abs_error": float(torch.max(torch.abs(gq - gs)).detach()),
                     "detach_gradient_max_abs_difference_from_Q":
                     float(torch.max(torch.abs(gq - gd)).detach())})
    return {"cases": rows,
            "max_forward_abs_error": max(r["forward_abs_error"] for r in rows),
            "max_gradient_abs_error": max(r["gradient_max_abs_error"] for r in rows),
            "min_detach_gradient_difference": min(
                r["detach_gradient_max_abs_difference_from_Q"] for r in rows),
            "all_pass": (max(r["forward_abs_error"] for r in rows) < 1e-12 and
                         max(r["gradient_max_abs_error"] for r in rows) < 1e-11 and
                         min(r["detach_gradient_max_abs_difference_from_Q"] for r in rows) > 1e-6)}


def zero_space_checks() -> dict:
    cases = [(1.5, 0.10, 0.95), (3.5, 0.50, 0.95), (5.0, 1.00, 0.99)]
    rows = []
    for beta, goe, R in cases:
        s, h = truth_geometry(beta, CFG.ETA, goe * CFG.ETA, R)
        _, _, vh = np.linalg.svd(s.reshape(1, 3), full_matrices=True)
        basis = vh[1:].T
        projected = basis.T @ h @ basis
        eigenvalues, eigenvectors = np.linalg.eigh(projected)
        v = basis @ eigenvectors[:, int(np.argmax(np.abs(eigenvalues)))]
        v /= np.linalg.norm(v)
        steps = np.logspace(-1, -4, 7)
        q = np.asarray([target_error_np(step * v, beta, CFG.ETA, goe * CFG.ETA, R) ** 2
                        for step in steps])
        m = np.asarray([(s @ (step * v)) ** 2 for step in steps])
        slope = float(np.polyfit(np.log(steps[-4:]), np.log(q[-4:]), 1)[0])
        rows.append({"beta": beta, "gamma_over_eta": goe, "R": R,
                     "direction": v.tolist(), "max_abs_s_dot_v": float(abs(s @ v)),
                     "finite_step": float(steps[0]), "M95_at_finite_step": float(m[0]),
                     "Q_at_finite_step": float(q[0]), "Q_small_step_loglog_slope": slope})
    return {"cases": rows, "all_pass": all(
        r["max_abs_s_dot_v"] < 1e-14 and r["M95_at_finite_step"] < 1e-28 and
        r["Q_at_finite_step"] > 0.0 and abs(r["Q_small_step_loglog_slope"] - 4.0) < 0.08
        for r in rows)}


def row_geometry(ev: dict[str, np.ndarray], R: float = 0.95) -> dict[str, np.ndarray]:
    beta = ev["keys_beta"].astype(np.float64)
    eta = np.full_like(beta, CFG.ETA)
    gamma = ev["keys_gamma_over_eta"].astype(np.float64) * CFG.ETA
    bh, eh, gh = (ev[name].astype(np.float64) for name in ("beta_hat", "eta_hat", "gamma_hat"))
    u = np.column_stack(((bh - beta) / beta, (eh - eta) / eta, (gh - gamma) / eta))
    a = -np.log(R)
    t0, th = a ** (1.0 / beta), a ** (1.0 / bh)
    x0 = gamma + eta * t0
    e = (gh + eh * th - x0) / x0
    c = -np.log(a) / beta
    s0 = np.column_stack((eta * t0 * c / x0, eta * t0 / x0, eta / x0))
    g = np.column_stack((-eh * th * np.log(a) * beta / (bh ** 2 * x0),
                         eta * th / x0, eta / x0))
    ell = np.sum(s0 * u, axis=1)
    rem = e - ell
    s_norm, g_norm = np.linalg.norm(s0, axis=1), np.linalg.norm(g, axis=1)
    u_par = ell / s_norm
    u_sq = np.sum(u * u, axis=1)
    u_perp_sq = np.maximum(u_sq - u_par ** 2, 0.0)
    cosine = np.sum(s0 * g, axis=1) / (s_norm * g_norm)
    angle = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
    c_gamma = (gh - gamma) / x0
    c_eta = 0.5 * (eh - eta) * (t0 + th) / x0
    c_beta = 0.5 * (eta + eh) * (th - t0) / x0
    c_abs = np.abs(c_beta) + np.abs(c_eta) + np.abs(c_gamma)
    cancel = np.divide(c_abs - np.abs(c_beta + c_eta + c_gamma), c_abs,
                       out=np.zeros_like(c_abs), where=c_abs > 0)
    return {"e": e, "e_stored": ev["rel_err"].astype(np.float64), "ell": ell, "rem": rem,
            "u_parallel_sq": u_par ** 2, "u_perp_sq": u_perp_sq,
            "angle_deg": angle, "s_norm_ratio_current_truth": g_norm / s_norm,
            "cancel_exact": cancel}


def cell_geometry(ev: dict[str, np.ndarray]) -> dict[str, float]:
    r = row_geometry(ev)
    target = r["e"] ** 2
    static = r["ell"] ** 2
    cross = 2.0 * r["ell"] * r["rem"]
    remainder = r["rem"] ** 2
    return {
        "n_rows": len(target), "target_mse": float(np.mean(target)),
        "static_local_mse": float(np.mean(static)), "cross_term": float(np.mean(cross)),
        "nonlinear_remainder_mse": float(np.mean(remainder)),
        "u_parallel_energy": float(np.mean(r["u_parallel_sq"])),
        "u_perp_energy": float(np.mean(r["u_perp_sq"])),
        "sensitivity_angle_deg": float(np.mean(r["angle_deg"])),
        "sensitivity_norm_ratio": float(np.mean(r["s_norm_ratio_current_truth"])),
        "mean_exact_compensation": float(np.mean(r["cancel_exact"])),
        "square_identity_max_abs_error": float(np.max(np.abs(target - static - cross - remainder))),
        "stored_relative_error_max_abs_difference": float(np.max(np.abs(r["e"] - r["e_stored"]))),
    }


def analyze_cells() -> tuple[list[dict], list[dict], dict]:
    protocol = load_s5b_protocol()
    seeds = [int(v) for v in protocol["seeds"]["all"]]
    pq = []
    for n in CFG.N_GRID:
        for fold in range(CFG.N_FOLDS):
            for seed in seeds:
                for route in ("P", "Q"):
                    ev = load_npz(_source_paths(n, fold, seed, route)[1])
                    pq.append({"n": n, "fold": fold + 1, "seed": seed, "route": route,
                               **cell_geometry(ev)})
    pmq = []
    for n in CFG.N_GRID:
        for fold in (0, 2):
            for seed in (42, 2026, 3407):
                for route in ("P", "M95", "Q"):
                    path = (_matrix_paths(n, fold, seed)[1] if route == "M95" else
                            _source_paths(n, fold, seed, route)[1])
                    pmq.append({"n": n, "fold": fold + 1, "seed": seed, "route": route,
                                **cell_geometry(load_npz(path))})
    metrics = ["target_mse", "static_local_mse", "cross_term", "nonlinear_remainder_mse",
               "u_parallel_energy", "u_perp_energy", "sensitivity_angle_deg",
               "sensitivity_norm_ratio", "mean_exact_compensation"]

    def route_summary(rows: list[dict]) -> dict:
        out = {}
        for route in dict.fromkeys(row["route"] for row in rows):
            sub = [row for row in rows if row["route"] == route]
            out[route] = {m: float(np.mean([row[m] for row in sub])) for m in metrics}
            out[route]["rrmse"] = float(np.sqrt(out[route]["target_mse"]))
            out[route]["n_cells"] = int(len(sub))
        return out

    pq_summary, pmq_summary = route_summary(pq), route_summary(pmq)
    decomp = {name: pmq_summary["M95"][name] - pmq_summary["P"][name]
              for name in ("target_mse", "static_local_mse", "cross_term",
                           "nonlinear_remainder_mse")}
    decomp["component_sum"] = (decomp["static_local_mse"] + decomp["cross_term"] +
                               decomp["nonlinear_remainder_mse"])
    checks = {
        "pq_cells": int(len(pq) // 2), "pmq_cells": int(len(pmq) // 3),
        "max_square_identity_error": float(max(
            max(row["square_identity_max_abs_error"] for row in pq),
            max(row["square_identity_max_abs_error"] for row in pmq))),
        "max_stored_relative_error_difference": float(max(
            max(row["stored_relative_error_max_abs_difference"] for row in pq),
            max(row["stored_relative_error_max_abs_difference"] for row in pmq))),
    }
    return pq, pmq, {"pq_200": pq_summary, "pmq_24": pmq_summary,
                     "m95_minus_p_exact_mse_decomposition": decomp, "checks": checks}


def make_figure(grid: list[dict], pq: list[dict], pmq: list[dict],
                summary: dict, out: Path) -> None:
    """写无外部绘图库依赖的出版级矢量 SVG（Okabe-Ito 色板）。"""
    width, height = 1200, 850
    panels = [(70, 55, 500, 315), (650, 55, 470, 315),
              (70, 445, 500, 315), (650, 445, 470, 315)]
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#111}'
           '.title{font-size:16px;font-weight:bold}.axis{font-size:13px}.tick{font-size:11px}'
           '.panel{font-size:20px;font-weight:bold}</style>']

    def text(x, y, value, cls="axis", anchor="start", rotate=None):
        tr = f' transform="rotate({rotate} {x} {y})"' if rotate else ""
        svg.append(f'<text x="{x:.2f}" y="{y:.2f}" class="{cls}" text-anchor="{anchor}"{tr}>{value}</text>')

    def axes_box(panel, title, ylabel, xlabel):
        x, y, w, h = panel; left, top, pw, ph = x + 70, y + 40, w - 95, h - 95
        svg.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+ph}" stroke="#222"/>')
        svg.append(f'<line x1="{left}" y1="{top+ph}" x2="{left+pw}" y2="{top+ph}" stroke="#222"/>')
        text(x, y + 18, title[0], "panel")
        text(x + 28, y + 18, title[2:], "title")
        text(left + pw / 2, top + ph + 48, xlabel, anchor="middle")
        text(left - 52, top + ph / 2, ylabel, anchor="middle", rotate=-90)
        return left, top, pw, ph

    # A: sensitivity norm averaged over the five gamma/eta levels.
    left, top, pw, ph = axes_box(panels[0], "A  Target sensitivity varies",
                                 "Mean ||s0||", "Shape beta")
    series = []
    for target, color, dash in (("B10", "#0072B2", ""), ("B5", "#D55E00", "6,4"),
                                ("B1", "#009E73", "2,3")):
        xs = sorted({float(row["beta"]) for row in grid if row["target"] == target})
        ys = np.asarray([np.mean([row["s_norm"] for row in grid
                                 if row["target"] == target and row["beta"] == beta])
                         for beta in xs])
        series.append((target, color, dash, np.asarray(xs), ys))
    ymin = min(float(v.min()) for _, _, _, _, v in series) * .95
    ymax = max(float(v.max()) for _, _, _, _, v in series) * 1.05
    sx = lambda v: left + (v - 1.5) / (5.0 - 1.5) * pw
    sy = lambda v: top + ph - (v - ymin) / (ymax - ymin) * ph
    for j in range(5):
        value = ymin + j * (ymax - ymin) / 4
        yy = sy(value); svg.append(f'<line x1="{left-4}" y1="{yy}" x2="{left}" y2="{yy}" stroke="#222"/>')
        text(left - 8, yy + 4, f"{value:.2f}", "tick", "end")
    for value in (1.5, 2.5, 3.5, 5.0):
        xx = sx(value); text(xx, top + ph + 18, f"{value:g}", "tick", "middle")
    for idx, (target, color, dash, xs, ys) in enumerate(series):
        points = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in zip(xs, ys))
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        svg.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"{dash_attr}/>')
        for x, y in zip(xs, ys):
            svg.append(f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="3" fill="{color}"/>')
        lx, ly = left + pw - 75, top + 18 + idx * 22
        svg.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+25}" y2="{ly}" stroke="{color}" stroke-width="2.5"{dash_attr}/>')
        text(lx + 32, ly + 4, target, "tick")

    # B: 24-cell ablation, seed points retained.
    left, top, pw, ph = axes_box(panels[1], "B  Static M95 does not reproduce Q",
                                 "B5 rRMSE", "Route")
    order, colors = ["P", "M95", "Q"], ["#0072B2", "#CC79A7", "#009E73"]
    means = [float(np.sqrt(np.mean([row["target_mse"] for row in pmq if row["route"] == r])))
             for r in order]
    ymax = max(means) * 1.18; barw = 62
    for j in range(5):
        val = j * ymax / 4; yy = top + ph - val / ymax * ph
        text(left - 8, yy + 4, f"{val:.2f}", "tick", "end")
    for i, (route, color, mean) in enumerate(zip(order, colors, means)):
        cx = left + (i + .5) * pw / 3; yy = top + ph - mean / ymax * ph
        svg.append(f'<rect x="{cx-barw/2}" y="{yy}" width="{barw}" height="{top+ph-yy}" fill="{color}" opacity=".82"/>')
        seeds = sorted({row["seed"] for row in pmq if row["route"] == route})
        by_seed = np.asarray([np.sqrt(np.mean([row["target_mse"] for row in pmq
                                              if row["route"] == route and row["seed"] == seed]))
                              for seed in seeds])
        for k, val in enumerate(by_seed):
            cy = top + ph - float(val) / ymax * ph
            svg.append(f'<circle cx="{cx+(k-1)*7}" cy="{cy}" r="3.3" fill="#111"/>')
        text(cx, top + ph + 18, route, "tick", "middle")

    # C: 200 paired cells exact compensation.
    left, top, pw, ph = axes_box(panels[2], "C  Exact compensation: 200 cells",
                                 "Q compensation", "P compensation")
    wide: dict[tuple[int, int, int], dict[str, float]] = {}
    for row in pq:
        wide.setdefault((row["n"], row["fold"], row["seed"]), {})[row["route"]] = row["mean_exact_compensation"]
    pairs = [(value["P"], value["Q"]) for value in wide.values()]
    lo, hi = min(min(v) for v in pairs), max(max(v) for v in pairs)
    pad = (hi - lo) * .06; lo -= pad; hi += pad
    sx2 = lambda v: left + (v - lo) / (hi - lo) * pw
    sy2 = lambda v: top + ph - (v - lo) / (hi - lo) * ph
    svg.append(f'<line x1="{sx2(lo)}" y1="{sy2(lo)}" x2="{sx2(hi)}" y2="{sy2(hi)}" stroke="#666" stroke-dasharray="6,4"/>')
    for p, q in pairs:
        svg.append(f'<circle cx="{sx2(float(p)):.2f}" cy="{sy2(float(q)):.2f}" r="2.8" fill="#7A5195" opacity=".60"/>')
    for j in range(5):
        val = lo + j * (hi - lo) / 4
        text(sx2(val), top + ph + 18, f"{val:.2f}", "tick", "middle")
        text(left - 8, sy2(val) + 4, f"{val:.2f}", "tick", "end")

    # D: exact M-P squared-error decomposition.
    left, top, pw, ph = axes_box(panels[3], "D  Exact M95 - P MSE decomposition",
                                 "Delta mean squared B5 error", "Component")
    d = summary["m95_minus_p_exact_mse_decomposition"]
    names = ["local", "cross", "remainder", "total"]
    vals = [d["static_local_mse"], d["cross_term"], d["nonlinear_remainder_mse"], d["target_mse"]]
    vmin, vmax = min(vals + [0.0]), max(vals + [0.0]); span = vmax - vmin
    vmin -= .12 * span; vmax += .12 * span
    sy3 = lambda v: top + ph - (v - vmin) / (vmax - vmin) * ph
    zero = sy3(0.0); svg.append(f'<line x1="{left}" y1="{zero}" x2="{left+pw}" y2="{zero}" stroke="#222"/>')
    dcolors = ["#0072B2", "#56B4E9", "#E69F00", "#D55E00"]
    for i, (name, val, color) in enumerate(zip(names, vals, dcolors)):
        cx = left + (i + .5) * pw / 4; yy = sy3(val)
        y0, hh = min(zero, yy), abs(zero - yy)
        svg.append(f'<rect x="{cx-25}" y="{y0}" width="50" height="{hh}" fill="{color}" opacity=".85"/>')
        text(cx, top + ph + 18, name, "tick", "middle")
        text(cx, yy - 7 if val >= 0 else yy + 15, f"{val:.4f}", "tick", "middle")

    text(width / 2, 825,
         "No new training. B: bars = 24-cell equal-cell rRMSE; dots = 3 seed aggregates. B,D: descriptive (no CI). C: 200 paired cells; not SGD causality.",
         "tick", "middle")
    svg.append('</svg>')
    out.with_suffix(".svg").write_text("\n".join(svg), encoding="utf-8")

    # 正式 Study02 环境有 matplotlib 时同时导出 300-dpi PNG 与矢量 PDF；
    # 缺依赖的最小环境仍可稳定生成上面的 SVG 和全部图源。
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        return
    plt.rcParams.update({"font.size": 9, "font.family": "sans-serif",
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 7.4))
    for target, color, style in (("B10", "#0072B2", "-"), ("B5", "#D55E00", "--"),
                                 ("B1", "#009E73", ":")):
        xs = sorted({row["beta"] for row in grid if row["target"] == target})
        ys = [np.mean([row["s_norm"] for row in grid
                       if row["target"] == target and row["beta"] == beta]) for beta in xs]
        axes[0, 0].plot(xs, ys, style, marker="o", label=target, color=color)
    axes[0, 0].set(xlabel=r"Shape $\beta$", ylabel=r"Mean $\|s_0\|$ over $\gamma/\eta$",
                   title="A  Target sensitivity varies")
    axes[0, 0].legend(frameon=False)

    order, colors = ["P", "M95", "Q"], ["#0072B2", "#CC79A7", "#009E73"]
    means = [np.sqrt(np.mean([row["target_mse"] for row in pmq if row["route"] == route]))
             for route in order]
    axes[0, 1].bar(order, means, color=colors, alpha=.82)
    for i, route in enumerate(order):
        seeds = sorted({row["seed"] for row in pmq if row["route"] == route})
        values = [np.sqrt(np.mean([row["target_mse"] for row in pmq
                                   if row["route"] == route and row["seed"] == seed]))
                  for seed in seeds]
        axes[0, 1].scatter(np.full(len(values), i), values, color="black", s=17, zorder=3)
    axes[0, 1].set(ylabel="B5 rRMSE (equal-cell)",
                   title="B  Static M95 does not reproduce Q")

    wide = {}
    for row in pq:
        wide.setdefault((row["n"], row["fold"], row["seed"]), {})[row["route"]] = row["mean_exact_compensation"]
    pvals = [value["P"] for value in wide.values()]
    qvals = [value["Q"] for value in wide.values()]
    axes[1, 0].scatter(pvals, qvals, s=12, alpha=.6, color="#7A5195")
    lo, hi = min(pvals + qvals), max(pvals + qvals)
    axes[1, 0].plot([lo, hi], [lo, hi], "--", color="0.35", linewidth=1)
    axes[1, 0].set(xlabel="P exact compensation", ylabel="Q exact compensation",
                   title="C  Exact compensation across 200 cells")

    d = summary["m95_minus_p_exact_mse_decomposition"]
    names = ["local", "cross", "remainder", "total"]
    vals = [d["static_local_mse"], d["cross_term"], d["nonlinear_remainder_mse"], d["target_mse"]]
    axes[1, 1].bar(names, vals, color=["#0072B2", "#56B4E9", "#E69F00", "#D55E00"])
    axes[1, 1].axhline(0, color="black", linewidth=.8)
    axes[1, 1].set(ylabel=r"M95 $-$ P mean squared B5 error",
                   title="D  Exact M95 - P MSE decomposition")
    fig.text(.5, .012, "No new training. B: bars = 24-cell equal-cell rRMSE; dots = 3 seed aggregates. "
             "B,D: descriptive (no CI). C: 200 paired cells; not SGD causality.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .035, 1, 1))
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)


def write_proof_text(proofs: dict, summary: dict) -> None:
    d = summary["m95_minus_p_exact_mse_decomposition"]
    text = f"""# P/Q 机制闭环：证明与验证记录

## 数学恒等式

在无量纲坐标 $u=((\\hat\\beta-\\beta)/\\beta,(\\hat\\eta-\\eta)/\\eta,
(\\hat\\gamma-\\gamma)/\\eta)$ 中，`P_equal` 为 $L_P=\\|u\\|^2$，所以
$\\nabla L_P=2u$、$H_P=2I$。令相对目标误差为 $e(u)$，则
$L_Q=e(u)^2$、$\\nabla L_Q=2e(u)g(u)$。在真值 $u=0$ 处，$e(0)=0$，故
$H_Q(0)=2s_0s_0^T$；M95 正是 $(s_0^Tu)^2$，是逐真值点固定、对预测位置静态的
秩一局部二次代理，存在二维零空间。

沿线段的微积分基本定理给出 $e(u)=\\int_0^1g(tu)^Tu\\,dt=\\bar s(u)^Tu$，
因此 $L_Q=u^T[\\bar s(u)\\bar s(u)^T]u$。只有保留 $\\bar s(u)$ 对 $u$ 的导数时，
其梯度才与 Q 相同；detach 后虽前向值相同，却是另一 surrogate。

## 数值验证

- 40 个冻结真值点 × B10/B5/B1：梯度最大误差 `{proofs['grid']['gradient_max_abs_error']:.3e}`，
  目标 Hessian 最大误差 `{proofs['grid']['target_hessian_max_abs_error']:.3e}`，
  Q-loss 真值 Hessian 最大误差 `{proofs['grid']['loss_hessian_max_abs_error']:.3e}`。
- 动态割线路径积分：前向最大误差 `{proofs['secant']['max_forward_abs_error']:.3e}`，
  梯度最大误差 `{proofs['secant']['max_gradient_abs_error']:.3e}`；detach 梯度与 Q 的
  最小差异 `{proofs['secant']['min_detach_gradient_difference']:.3e}`。
- 自动零空间反例全部通过：M95 为零而有限步真实 Q 大于零；小步长 Q 的 log-log
  阶数接近 4（因为 $e=O(h^2)$、$e^2=O(h^4)$）。

## 终态证据与边界

200 个 P/Q 单元与 24 个 P/M95/Q 单元分别聚合。M95−P 的真实 B5 MSE 差为
`{d['target_mse']:.8g}`，精确分解为局部项 `{d['static_local_mse']:.8g}`、交叉项
`{d['cross_term']:.8g}`、非线性余项平方 `{d['nonlinear_remainder_mse']:.8g}`，三项和
`{d['component_sum']:.8g}`。这些是终态几何恒等式与预设探索性消融，不分别识别零空间、
曲率或 SGD 轨迹的因果贡献，也不声称所有目标感知参数度量均无效。
"""
    (OUT / "proofs.md").write_text(text, encoding="utf-8")


def write_sha_list() -> None:
    files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    lines = [f"{canonical_sha(path)}  {path.relative_to(OUT).as_posix()}" for path in files]
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    analysis = OUT / "analysis"
    analysis.mkdir(exist_ok=True)
    audit, source_files = audit_sources()
    grid, grid_checks = verification_grid()
    secant = secant_checks()
    zero = zero_space_checks()
    pq, pmq, estimands = analyze_cells()
    if not (audit["all_pass"] and grid_checks["all_pass"] and secant["all_pass"] and zero["all_pass"]):
        raise AssertionError("mechanism closure verification failed")
    if estimands["checks"]["max_square_identity_error"] > 1e-12:
        raise AssertionError("squared decomposition identity exceeded tolerance")

    write_csv(analysis / "source_file_audit.csv", source_files)
    write_csv(analysis / "truth_geometry_B10_B5_B1.csv", grid)
    write_csv(analysis / "pq_200_cells.csv", pq)
    write_csv(analysis / "pmq_24_cells.csv", pmq)
    proofs = {"grid": grid_checks, "secant": secant, "zero_space": zero}
    (analysis / "proof_checks.json").write_text(json.dumps(proofs, indent=2), encoding="utf-8")
    (analysis / "source_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    (analysis / "summary.json").write_text(json.dumps(estimands, indent=2), encoding="utf-8")
    make_figure(grid, pq, pmq, estimands, analysis / "mechanism_closure")
    write_proof_text(proofs, estimands)
    manifest = {
        "contract_id": "pq-mechanism-closure-v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT,
                                             text=True).strip(),
        "no_training": True, "source_evidence_modified": False,
        "code_sha256": canonical_sha(CODE), "protocol_sha256": canonical_sha(PROTOCOL),
        "source_sha_lists": audit["source_sha_lists"],
        "estimands": {"pq_confirmatory_geometry_cells": 200,
                      "pmq_exploratory_ablation_cells": 24, "pooled_together": False},
        "checks": {"source_audit": audit["all_pass"], "analytic_geometry": grid_checks["all_pass"],
                   "dynamic_secant": secant["all_pass"], "zero_space": zero["all_pass"],
                   "square_identity_max_abs_error": estimands["checks"]["max_square_identity_error"]},
        "sha256_rule": "text LF-normalized; NPZ/PNG/PDF raw bytes",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_sha_list()
    print(json.dumps({"audit": audit, "proofs": proofs, "estimands": estimands}, indent=2))


if __name__ == "__main__":
    main()
