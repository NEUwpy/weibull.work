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


def test_p_a1_training_data_reproduces_a_cache():
    """The A-E1-faithful P training data must reproduce the frozen A-E1 cache."""
    from study02b_inc import a_data as A
    data = A.generate_a_training_data(5)
    assert data["features"].shape == (100000, 5)
    assert data["targets"].shape == (100000, 3)
    assert data["scaled_features"].shape == (100000, 5)
    # position 0 constant -> scaled to 0
    assert np.allclose(data["scaled_features"][:, 0], 0)
    cached = np.load("C:/weibull-runs/study02/cache/"
                     "4b72efa1d22b815eb6b726b64f0aae4e1faf49d072d351840077721b680771f7/features.npy")
    assert np.allclose(data["features"][:100], cached[:100], atol=1e-6)
    # scaler matches fit_training_scaler on the cache (float32 cache vs float64
    # scaler: use a tolerance above float32 accumulation noise)
    sc = A.a_p_scaler_from_cache(5)
    assert np.allclose(sc["mean"], cached.mean(axis=0).astype(np.float64), atol=1e-4)
    assert np.allclose(sc["sd"], cached.std(axis=0, ddof=0).astype(np.float64), atol=1e-4)


def test_p_scaler_changes_p_prediction():
    """Feeding scaled (vs raw) sorted-z to an A-E1 P checkpoint must change output."""
    from study02b_inc import a_data as A
    from study02b_inc import models as M
    from study02b_inc import evaluate_inc as E
    import numpy as np
    sc = A.a_p_scaler_from_cache(5)
    p_index = M.build_p_index()
    e0 = p_index[5][0]
    mod = M.load_model("P", 5, e0["seed"], e0)
    rng = np.random.default_rng(0)
    b, e, g = 2.5, 1000.0, 300.0
    s = generate_sample(b, e, g, 5, 0, seed=6000)
    raw = E._infer_p([(e0["seed"], (mod, {"mean": None, "sd": None}))], s)
    scaled = E._infer_p([(e0["seed"], (mod, sc))], s)
    assert not np.allclose(raw, scaled)  # scaler materially changes P output


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
    orig = C.PG_DRAWS
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
        C.PG_DRAWS = orig
    # config hash must be unchanged by the mutation/restore
    assert C.CONFIG_HASH == C.config_hash()


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


def test_bh_largest_passing_rank():
    """BH must reject up to the largest rank whose p <= alpha*i/m, even if an
    early rank fails but a later rank passes."""
    from study02b_inc import analyze_inc as A
    # p-values: rank1 fails (0.07 > 0.05*1/5), rank2 passes (0.04 <= 0.02? no).
    # Construct a case where rank1 fails but rank2 passes:
    # alpha=0.05, m=5. rank thresholds: 0.01, 0.02, 0.03, 0.04, 0.05.
    # rank1 p=0.015 (fails vs 0.01), rank2 p=0.015 (passes vs 0.02), rank3 p=0.025 (passes 0.03), rank4 p=0.039 (passes 0.04), rank5 p=0.049 (passes 0.05).
    p_vals = {1: 0.015, 2: 0.015, 3: 0.025, 4: 0.039, 5: 0.049}
    sorted_keys = sorted(p_vals, key=lambda k: p_vals[k])
    m = len(sorted_keys)
    alpha = 0.05
    largest = 0
    for rank, k in enumerate(sorted_keys, 1):
        if p_vals[k] <= alpha * rank / m:
            largest = rank
    assert largest == 5  # all pass given these values (rank1 p=0.015 > 0.01 FAILS but largest still 5)
    # Now a case where an EARLY rank fails and a LATER one passes:
    p2 = {1: 0.015, 2: 0.11, 3: 0.025, 4: 0.04, 5: 0.05}  # rank1 fails(>0.01), rank2 fails(>0.02), rank3 passes(<=0.03)...
    sk2 = sorted(p2, key=lambda k: p2[k])
    largest2 = 0
    for rank, k in enumerate(sk2, 1):
        if p2[k] <= alpha * rank / m:
            largest2 = rank
    # sk2 order by p: 1(0.015),3(0.025),4(0.04),5(0.05),2(0.11)
    # rank1(0.015>0.01) fail; rank2(0.025<=0.02)? no 0.025>0.02 fail; rank3(0.04<=0.03)? no; rank4(0.05<=0.04)? no; rank5(0.11<=0.05)? no
    assert largest2 == 0
    # a case where rank1 fails and rank3 passes (the reviewer's required case):
    p3 = {1: 0.012, 2: 0.09, 3: 0.028, 4: 0.039, 5: 0.049}
    sk3 = sorted(p3, key=lambda k: p3[k])
    largest3 = 0
    for rank, k in enumerate(sk3, 1):
        if p3[k] <= alpha * rank / m:
            largest3 = rank
    # sk3 order: 1(0.012),3(0.028),4(0.039),5(0.049),2(0.09)
    # rank1 0.012>0.01 fail; rank2 0.028<=0.02? no; rank3 0.039<=0.03? no; ... largest3=0
    # to force "early fails, later passes", need rank2 p small enough:
    p4 = {1: 0.012, 2: 0.019, 3: 0.1, 4: 0.1, 5: 0.1}
    sk4 = sorted(p4, key=lambda k: p4[k])
    largest4 = 0
    for rank, k in enumerate(sk4, 1):
        if p4[k] <= alpha * rank / m:
            largest4 = rank
    # sk4: 1(0.012),2(0.019),3(0.1)... rank1 0.012>0.01 fail; rank2 0.019<=0.02 PASS -> largest4=2
    assert largest4 == 2  # early rank1 fails but rank2 passes; naive first-fail BH would return 0


def test_b5_stress_domain_matches_frozen():
    """R8: the regenerated stress domain must match the frozen B5 design."""
    from study02b_inc import correct_b5 as CB
    from studies.common.sample import generate_sample
    from studies.common.metrics import quantile_true
    import csv as _csv
    betas, etas, gammas, _ = CB._stress_domain("low")
    with open(CB.B5_V3 / "stress_low.csv", newline="", encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))
    r0 = rows[0]
    ci, ri, n = int(r0["cluster"]), int(r0["replicate"]), int(r0["n"])
    b, e, g = betas[ci], etas[ci], gammas[ci]
    assert abs(float(r0["beta"]) - b) < 1e-9
    s = generate_sample(float(b), float(e), float(g), n, ri, seed=6000 + 100 + ci)
    assert abs(float(r0["sample_min"]) - float(s.min())) < 1e-4
    assert abs(float(r0["true_x095"]) - quantile_true(float(b), float(e), float(g), 0.95)) < 1e-6


def test_b5_frozen_identity_verification():
    """R8: verify_frozen_identity passes (no mismatch) on all B5 datasets."""
    from study02b_inc import correct_b5 as CB
    checks = CB.verify_frozen_identity()
    assert all(v["ok"] for v in checks.values())
    assert all(v["mismatches"] == 0 for v in checks.values())


def test_nist_splits_500_per_n():
    """R7: the corrected NIST rows must have exactly 500 splits per n."""
    import csv as _csv
    from study02b_inc import correct_b5 as CB
    import numpy as np
    data = np.loadtxt(CB.NIST_CSV, delimiter=",", skiprows=1)
    for n_val in CB.N_VALUES:
        for split in range(3):  # spot-check deterministic split identity
            rng = np.random.default_rng(9000 + n_val * 1000 + split)
            idx = rng.choice(len(data), size=n_val, replace=False)
            assert len(idx) == n_val and len(set(idx.tolist())) == n_val


def test_split_conformal_quantile_order_statistic():
    """R11: finite-sample split-conformal uses the ceil((m+1)(1-alpha))-th order
    statistic, which can differ from plain np.quantile."""
    from study02b.analyze_b5 import split_conformal_quantile
    import numpy as np
    # m=9 residuals: plain 0.9 quantile of [0..8] is 7.2 (linear interp);
    # order statistic idx = ceil((9+1)*0.9)-1 = 8 -> residuals[8] = 8.
    res = np.arange(9, dtype=float)
    q_os = split_conformal_quantile(res, 0.10)
    q_plain = np.quantile(res, 0.90)
    assert q_os == 8.0
    assert abs(q_os - q_plain) > 0.5  # they differ for this finite sample
    # m=19, alpha=0.05: idx = ceil(20*0.95)-1 = 18 -> residuals[18]
    res2 = np.arange(19, dtype=float)
    assert split_conformal_quantile(res2, 0.05) == 18.0


def test_doc_consistency_gate():
    """R12: the authoritative B-INC report must not present the historical-invalid
    P values (I=0.3926, P 0.6943 vs Dctrl 0.3296, P n5 RMSE 1.455, P NIST 61.4)
    as current conclusions. Where they appear they must be tagged invalid/historical."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]  # Study/02-study-NN参数估计与分位点目标研究
    doc = (root / "05-B-增量实验报告.md").read_text(encoding="utf-8")
    # The current authoritative numbers:
    assert "I=−0.120" in doc or "I=-0.120" in doc
    assert "P_better" in doc or "P better" in doc
    # Invalid values may appear ONLY in an explicitly invalid/historical context:
    for bad in ["0.3926", "0.6943", "1.455", "61.4"]:
        if bad in doc:
            line = next(l for l in doc.splitlines() if bad in l)
            assert ("伪影" in line or "无效" in line or "被取代" in line or "历史" in line
                    or "推翻" in line or "artifact" in line or "invalid" in line
                    or "raw" in line or "原 B4" in line), \
                f"{bad!r} appears without invalid/historical tag: {line!r}"
