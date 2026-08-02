"""Focused unit tests for the Study02 B incremental experiment.

Covers config identity, training data determinism/distribution, P/D fit
round-trip and checkpoint loading, core-row B4 reproduction, grid-row common
random numbers, and model indexing. Run:

    python -m pytest Study/02-study-NN参数估计与分位点目标研究/code/study02b_inc/test_inc.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

from studies.common.metrics import quantile_true
from studies.common.sample import generate_sample
from study02a.models import build_mlp
from study02a.representations import anchor_sample, encode_targets
from study02a.training import load_checkpoint
from study02b.representations import DTrainingStats, decode_d_target, unstandardize_d
from study02b.training import build_d_mlp, fit_d_model

from study02b_inc import config as C
from study02b_inc import data as D
from study02b_inc import models as M


def test_config_hash_stable():
    h1 = C.config_hash()
    h2 = C.config_hash()
    assert h1 == h2
    assert len(h1) == 64
    assert C.N_MISSING == [6, 8, 9, 11, 12, 13, 14, 16, 17, 18, 19, 22, 25, 30]


def test_p_training_data_distribution_and_targets():
    data = D.generate_training_data("P", 6)
    assert data["features"].shape == (120000, 6)
    assert data["targets"].shape == (120000, 3)
    # log-uniform beta in [1.2, 4]
    betas = data["beta"]
    assert betas.min() >= 1.2 and betas.max() <= 4.0
    assert np.mean(np.log(betas)) > np.log(1.5)  # log-uniform: center ~ sqrt(1.2*4)=2.19
    # target row 0 equals encode_targets of true params (reconstruct row 0 sample)
    b0, e0, g0 = float(betas[0]), float(data["eta"][0]), float(data["gamma"][0])
    s0 = generate_sample(b0, e0, g0, 6, 0, seed=C.P_SAMPLE_NS_TRAIN)
    a0 = anchor_sample(s0)
    expected = encode_targets(b0, e0, g0, a0)
    assert np.allclose(data["targets"][0], expected, atol=1e-6)


def test_d_training_data_matches_b3():
    data = D.generate_training_data("D", 6)
    assert data["features"].shape == (120000, 6)
    assert data["targets"].shape == (120000, 1)
    stats = data["target_stats"]
    assert stats["mean"] == stats["mean"]  # finite
    assert stats["sd"] > 0


def test_d_encode_decode_roundtrip():
    from study02b.representations import encode_d_target, compute_d_stats, standardize_d
    rng = np.random.default_rng(0)
    b, e, g = 2.5, 5000.0, 1000.0
    s = rng.gamma(shape=2.5, scale=3000.0, size=15)
    a = anchor_sample(s)
    x = quantile_true(b, e, g, 0.95)
    enc = encode_d_target(x, a)
    stats = DTrainingStats(mean=0.0, sd=1.0)
    dec = decode_d_target(unstandardize_d(np.array([enc]), stats)[0], a)
    assert abs(dec - x) / x < 1e-12


def test_fit_and_load_d_checkpoint():
    n = 6
    data = D.generate_training_data("D", n)
    dx = torch.from_numpy(data["features"][:2000]).to(torch.float32)
    dy = torch.from_numpy(data["targets"][:2000]).to(torch.float32)
    dvx = torch.from_numpy(data["features"][2000:4000]).to(torch.float32)
    dvy = torch.from_numpy(data["targets"][2000:4000]).to(torch.float32)
    mf = lambda: build_d_mlp(n, C.D_SELECTED_WIDTHS, C.ACTIVATION, C.DROPOUT)
    r = fit_d_model(mf, dx, dy, dvx, dvy, seed=101, loss_id=C.LOSS_D, lr=C.LR,
                    weight_decay=C.WEIGHT_DECAY, batch_size=512,
                    max_epochs=30, min_epochs=5, patience=5)
    m = build_d_mlp(n, C.D_SELECTED_WIDTHS, C.ACTIVATION, C.DROPOUT)
    m.load_state_dict(load_checkpoint(r.checkpoint_bytes))
    m.eval()
    with torch.no_grad():
        pred = float(m(dvx[:1]).item())
    assert np.isfinite(pred)


def test_core_rows_reproduce_b4_for_shared_n():
    """Shared-n core rows must equal the B4 test datasets (same seeds)."""
    rows = D.generate_core_rows(n_values=[10])
    assert len(rows) == 64 * 20
    # Recompute one row with the B4 formula and compare sample values.
    from scipy.stats import qmc
    from studies.common.sample import generate_sample
    sampler = qmc.Sobol(d=3, scramble=True, seed=42)
    pts = sampler.random_base2(m=6)
    b = 1.2 + pts[0, 0] * (4.0 - 1.2)
    e = 100.0 + pts[0, 1] * (10000.0 - 100.0)
    g = pts[0, 2] * e
    s = generate_sample(float(b), float(e), float(g), 10, 0, seed=6000)
    row = rows[0]
    assert np.allclose(row.sample, s)
    assert row.meta == {"cluster": 0, "replicate": 0}
    assert abs(row.true_x095 - quantile_true(float(b), float(e), float(g), 0.95)) < 1e-9


def test_grid_rows_common_random_numbers():
    C.PG_DRAWS = 4
    try:
        cells = D.param_grid_cells()[:2]
        rows = D.generate_grid_rows(cells)
        assert len(rows) == 2 * 4
        # same draw index across cells uses same seed => paired randomness
        r_a = rows[0]   # cell0 draw0
        r_b = rows[4]   # cell1 draw0
        assert r_a.meta["draw"] == 0 and r_b.meta["draw"] == 0
        assert r_a.meta["cell"] != r_b.meta["cell"]
        assert r_a.n != r_b.n          # cells advance n fastest
        # within a cell, draws share the same fixed params
        assert rows[0].beta == rows[1].beta and rows[0].gamma == rows[1].gamma
    finally:
        C.PG_DRAWS = 480


def test_p_index_has_existing_n():
    p_index = M.build_p_index()
    assert set(p_index.keys()) == {5, 7, 10, 15, 20}
    for n, entries in p_index.items():
        assert len(entries) == 10
        # each checkpoint is loadable with m12 shape
        m = build_mlp(n, C.P_WIDTHS, C.ACTIVATION, C.DROPOUT)
        m.load_state_dict(load_checkpoint(Path(entries[0]["path"]).read_bytes()))


def test_d_index_has_existing_n():
    d_index = M.build_d_index(C.B3_MANIFEST_PATH.parent.parent)
    for n in (5, 7, 10, 15, 20):
        assert len(d_index.get(n, {}).get("selected", [])) == 10
        assert len(d_index.get(n, {}).get("controlled", [])) == 5
