"""Production tests for the S5B major-revision experiment."""

from __future__ import annotations

import numpy as np

from study02pq import data as DATA
from study02pq import model as MODEL
from study02pq import s5b_revision as S5B
from study02pq import training as TR


def test_s5b_protocol_counts_and_seed_freeze():
    cfg = S5B.load_protocol()
    seeds = cfg["seeds"]
    assert len(seeds["all"]) == 10
    assert seeds["all"][:3] == seeds["existing"] == [42, 2026, 3407]
    assert len(seeds["new"]) == 7 and not set(seeds["new"]) & set(seeds["existing"])
    assert cfg["grid_extension"]["new_fits"] == 7 * 4 * 5 * 2 == 280
    assert cfg["continuous_within_range"]["fits"] == 10 * 4 * 5 * 3 == 600
    assert cfg["execution"]["new_fits"] == 880


def test_continuous_master_bounds_reproducibility_and_split():
    a = S5B.build_continuous_master(points_per_n=50)
    b = S5B.build_continuous_master(points_per_n=50)
    assert np.array_equal(a.keys, b.keys)
    assert DATA.sample_bytes_sha(a, np.arange(len(a.keys))) == \
        DATA.sample_bytes_sha(b, np.arange(len(b.keys)))
    assert a.keys[:, 0].min() >= 1.5 and a.keys[:, 0].max() <= 5.0
    assert a.keys[:, 1].min() >= 0.1 and a.keys[:, 1].max() <= 1.0
    for n in [7, 10, 15, 20]:
        all_test = set()
        for fold in range(5):
            tr, va, te = DATA.split_continuous_fold(a, n, fold)
            assert (len(tr), len(va), len(te)) == (30, 10, 10)
            assert not set(tr) & set(va) and not set(tr) & set(te) and not set(va) & set(te)
            assert not all_test & set(te)
            all_test |= set(te)
        assert len(all_test) == 50


def test_qdirect_has_same_initialized_hidden_trunk_as_param_model():
    for n in [7, 20]:
        param = MODEL.build_model(n, 42)
        direct = MODEL.build_scalar_model(n, 42)
        assert MODEL.trunk_params_sha(param) == MODEL.trunk_params_sha(direct)
        assert sum(p.numel() for p in param.parameters()) != sum(p.numel() for p in direct.parameters())


def test_crossed_bootstrap_direction_and_pairing():
    # Q has exactly 25% smaller MSE in every matched cell -> 13.397% rRMSE improvement.
    p = np.arange(1, 1 + 4 * 5 * 10, dtype=float).reshape(4, 5, 10) / 100 + 1
    q = 0.75 * p
    out = S5B.crossed_bootstrap(p, q, n_boot=2000, seed=123)
    expected = 1 - np.sqrt(0.75)
    assert np.isclose(out["relative_improvement"], expected)
    assert np.allclose(out["relative_improvement_ci95"], [expected, expected])
    assert out["mean_mse_difference_comparison_minus_baseline"] < 0


def test_qdirect_smoke_outputs_are_finite_and_paired():
    master = S5B.build_continuous_master(points_per_n=25)
    result = S5B.train_one_direct_fit(7, 0, 17, master, max_epochs=2, patience=1)
    meta, pred = result["meta"], result["predictions"]
    assert meta["route_label"] == "Q_direct"
    assert meta["n_test"] == 5
    assert np.isfinite(pred["x95_hat"]).all()
    assert np.isfinite(pred["rel_err_sq"]).all()
    tr, va, te = DATA.split_continuous_fold(master, 7, 0)
    assert meta["train_rows_sha"] == DATA.sha_rows(tr)
    assert meta["val_rows_sha"] == DATA.sha_rows(va)
    assert meta["test_rows_sha"] == DATA.sha_rows(te)


def test_param_routes_support_continuous_split_and_remain_paired():
    master = S5B.build_continuous_master(points_per_n=25)
    p = TR.train_one_fit(7, 0, 17, "P", master, max_epochs=2, patience=1,
                         split_strategy="continuous_sobol")
    q = TR.train_one_fit(7, 0, 17, "Q", master, max_epochs=2, patience=1,
                         split_strategy="continuous_sobol")
    for key in ("init_param_sha", "batch_order_sha", "network_sha", "scaler_sha",
                "train_rows_sha", "val_rows_sha", "test_rows_sha", "sample_bytes_sha"):
        assert p["meta"][key] == q["meta"][key]
    assert p["meta"]["split_strategy"] == q["meta"]["split_strategy"] == \
        "continuous_sobol"
    assert p["meta"]["support_legality_ok"] and q["meta"]["support_legality_ok"]
