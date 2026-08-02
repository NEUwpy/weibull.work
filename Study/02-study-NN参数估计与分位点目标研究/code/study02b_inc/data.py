"""Deterministic data generation for the incremental B run.

Training data (per missing n):
- P:      A-E1 core_continuous distribution (log-uniform beta/eta, uniform rho),
          new documented draw namespace.
- D/Dctrl:B3 distribution (uniform beta/eta/rho), identical seed scheme to B3.

Test data:
- dense-n core: exact B4 Sobol parameter clusters x replicates x n, same
  sample namespace so the shared n reproduce B4 sample-for-sample.
- parameter grid: fixed (beta, rho, eta, n) cells with common-random-number
  draws (seed = PG_SAMPLE_NS + draw_index, draw index shared across cells).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.stats import qmc

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

from studies.common.sample import generate_sample
from studies.common.metrics import quantile_true
from study02a.representations import anchor_sample, encode_targets
from study02b.representations import encode_d_target, compute_d_stats, standardize_d

from study02b_inc import config as C


# ---------------------------------------------------------------------------
# Training data
# ---------------------------------------------------------------------------

def _draw_p_params(rng, total):
    betas = np.exp(rng.uniform(np.log(C.P_BETA_RANGE[0]), np.log(C.P_BETA_RANGE[1]), size=total))
    etas = np.exp(rng.uniform(np.log(C.P_ETA_RANGE[0]), np.log(C.P_ETA_RANGE[1]), size=total))
    rhos = rng.uniform(C.P_RHO_RANGE[0], C.P_RHO_RANGE[1], size=total)
    return betas, etas, rhos * etas


def _draw_d_params(rng, total):
    betas = rng.uniform(1.2, 4.0, size=total)
    etas = rng.uniform(100.0, 10000.0, size=total)
    rhos = rng.uniform(0.0, 1.0, size=total)
    return betas, etas, rhos * etas


def generate_training_data(route: str, n: int) -> dict:
    """Generate 100k train + 20k val rows for the D route (B3 scheme).

    The P route now uses study02b_inc.a_data (A-E1-faithful design + scaler);
    it must NOT go through this function. Route must be "D".
    """
    if route != "D":
        raise ValueError("generate_training_data supports only the D route; "
                         "the P route uses study02b_inc.a_data")
    total = C.N_TRAIN + C.N_VAL
    rng = np.random.default_rng(n * 100 + 1)  # B3 scheme
    betas, etas, gammas = _draw_d_params(rng, total)
    sample_ns_train, sample_ns_val = C.D_SAMPLE_NS_TRAIN, C.D_SAMPLE_NS_VAL

    samples, x095s, anchors = [], [], []
    for i in range(total):
        b, e, g = float(betas[i]), float(etas[i]), float(gammas[i])
        ns = sample_ns_train if i < C.N_TRAIN else sample_ns_val
        rid = i if i < C.N_TRAIN else i - C.N_TRAIN
        s = generate_sample(b, e, g, n, rid, seed=ns)
        samples.append(s)
        x095s.append(quantile_true(b, e, g, 0.95))
        anchors.append(anchor_sample(s))

    features = np.array([a.z for a in anchors], dtype=np.float32)

    raw = np.array([
        encode_d_target(float(x), a) for x, a in zip(x095s, anchors)
    ], dtype=np.float32)
    stats = compute_d_stats(raw[:C.N_TRAIN])
    targets = standardize_d(raw, stats).astype(np.float32).reshape(-1, 1)
    return {
        "features": features, "targets": targets,
        "target_stats": {"mean": stats.mean, "sd": stats.sd},
        "beta": betas, "eta": etas, "gamma": gammas,
    }


def target_stats_for_n(n: int) -> dict:
    data = generate_training_data("D", n)
    return {"n": n, "mean": data["target_stats"]["mean"], "sd": data["target_stats"]["sd"]}


# ---------------------------------------------------------------------------
# Test rows (unified metadata model)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TestRow:
    sample: np.ndarray
    beta: float
    eta: float
    gamma: float
    true_x095: float
    n: int
    block: str                    # "core" | "grid"
    meta: dict                    # core: {cluster, replicate}; grid: {cell, draw}

    @property
    def rho(self) -> float:
        return self.gamma / self.eta if self.eta != 0 else 0.0


def generate_core_rows(n_values=None) -> list[TestRow]:
    """B4-identical Sobol parameter clusters x replicates x n."""
    n_values = n_values or C.N_VALUES
    sampler = qmc.Sobol(d=3, scramble=True, seed=C.CORE_SOBOL_SCRAMBLE)
    pts = sampler.random_base2(m=C.CORE_SOBOL_M)
    betas = C.CORE_BETA_RANGE[0] + pts[:, 0] * (C.CORE_BETA_RANGE[1] - C.CORE_BETA_RANGE[0])
    etas = C.CORE_ETA_RANGE[0] + pts[:, 1] * (C.CORE_ETA_RANGE[1] - C.CORE_ETA_RANGE[0])
    gammas = pts[:, 2] * etas
    out = []
    for ci, (b, e, g) in enumerate(zip(betas, etas, gammas)):
        for ri in range(C.CORE_N_REPLICATES):
            for n in n_values:
                s = generate_sample(float(b), float(e), float(g), n, ri, seed=C.CORE_SAMPLE_NS + ci)
                out.append(TestRow(
                    sample=s, beta=float(b), eta=float(e), gamma=float(g),
                    true_x095=quantile_true(float(b), float(e), float(g), 0.95),
                    n=int(n), block="core", meta={"cluster": ci, "replicate": ri},
                ))
    return out


@dataclass(frozen=True)
class GridCell:
    beta: float
    rho: float
    eta: float
    n: int
    gamma: float
    cell_index: int


def param_grid_cells() -> list[GridCell]:
    cells = []
    idx = 0
    for beta in C.PG_BETA:
        for rho in C.PG_RHO:
            for n in C.PG_N:
                cells.append(GridCell(float(beta), float(rho), float(C.PG_ETA), int(n),
                                      float(rho * C.PG_ETA), idx))
                idx += 1
    for beta in C.PG_ETA_SWEEP["beta"]:
        for rho in C.PG_ETA_SWEEP["rho"]:
            for n in C.PG_ETA_SWEEP["n"]:
                for eta in C.PG_ETA_SWEEP["eta"]:
                    cells.append(GridCell(float(beta), float(rho), float(eta), int(n),
                                          float(rho * eta), idx))
                    idx += 1
    return cells


def generate_grid_rows(cells: list[GridCell] | None = None,
                       max_cells: int | None = None) -> list[TestRow]:
    """Common-random-number draws per cell (seed = PG_SAMPLE_NS + draw)."""
    cells = cells if cells is not None else param_grid_cells()
    if max_cells:
        cells = cells[:max_cells]
    out = []
    for cell in cells:
        for d in range(C.PG_DRAWS):
            s = generate_sample(cell.beta, cell.eta, cell.gamma, cell.n, d,
                                seed=C.PG_SAMPLE_NS + d)
            out.append(TestRow(
                sample=s, beta=cell.beta, eta=cell.eta, gamma=cell.gamma,
                true_x095=quantile_true(cell.beta, cell.eta, cell.gamma, 0.95),
                n=int(cell.n), block="grid",
                meta={"cell": cell.cell_index, "draw": d},
            ))
    return out


def grid_cell_map() -> dict[int, GridCell]:
    return {c.cell_index: c for c in param_grid_cells()}
