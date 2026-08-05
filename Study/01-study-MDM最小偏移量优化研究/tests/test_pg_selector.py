"""Contract tests for the Study/01 Phase A parameter-guided offset selector.

Covers:
  - J1 = sqrt(mean(L_i)), three-parameter loss, NO /3
  - nearest-grid cell assignment and conditional-mean curves from TRAINING folds only
  - split isolation (repeat_id mod 5; test fold never enters its own rule)
  - continuous interpolation of LOSS CURVES (not selected deltas) + clipping
  - iteration: fixed point / cycle / max-iteration / invalid-terminal
  - invalid initial estimate -> fallback to delta=0.1 with recorded reason
  - sample-key multiplicity and same-sample alignment

Self-contained (synthetic data; no generated artifacts / large caches).
"""

import os
import sys
import math
import numpy as np
import pandas as pd

STUDY_CODE_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "code")
PYTHON_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "python")
for p in (STUDY_CODE_DIR, PYTHON_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_pg_selector as PG

DELTA_GRID = PG.DELTA_GRID
BETA_GRID = PG.BETA_GRID


def loss_curve_parabola(center, scale=1.0):
    return np.array([scale * (d - center) ** 2 for d in DELTA_GRID])


def argmin_delta(curve):
    return DELTA_GRID[int(np.argmin(np.asarray(curve)))]


# ============================================================
# J1 definition
# ============================================================

def test_j1_no_division():
    losses = pd.Series([0.04, 0.09, 0.16])
    assert math.isclose(PG.j1_from_loss(losses), math.sqrt(0.29 / 3.0))
    # no /3: sqrt of mean, not sqrt(mean/3) nor sqrt(sum)/3
    assert not math.isclose(PG.j1_from_loss(losses), math.sqrt(0.29 / 9.0))


# ============================================================
# Nearest-grid cell assignment
# ============================================================

def test_nearest_grid_value():
    grid = PG.BETA_GRID
    assert PG.nearest_grid_value(1.51, grid) == 1.5
    assert PG.nearest_grid_value(2.49, grid) == 2.5
    assert PG.nearest_grid_value(5.4, grid) == 5.0
    assert PG.nearest_grid_value(0.8, grid) == 1.5


def test_cell_from_estimate_family():
    est = {"beta_est": 2.13, "goe_est": 0.9, "n": 10}
    assert PG.cell_from_estimate(est, "PG-beta") == (2.0,)
    assert PG.cell_from_estimate(est, "PG-beta-n") == (2.0, 10)
    assert PG.cell_from_estimate(est, "PG-full") == (2.0, 1.0, 10)


# ============================================================
# Conditional-mean curves are TRAINING folds only
# ============================================================

def _make_train_df():
    """Small synthetic training fold on real grid values."""
    rows = []
    for b in (1.5, 2.0, 2.5):
        for goe in (0.1, 0.5):
            for n in (7, 10):
                for rid in range(4):
                    center = 0.2 + 0.05 * (b - 1.5)  # beta-dependent optimum
                    for j, d in enumerate(DELTA_GRID):
                        loss = (d - center) ** 2 + (rid % 3) * 0.001
                        rows.append({"beta": float(b), "eta": 1000.0,
                                     "gamma": float(goe * 1000.0),
                                     "gamma_over_eta": float(goe), "n": int(n),
                                     "repeat_id": int(rid), "delta": float(d),
                                     "loss": float(loss)})
    return pd.DataFrame(rows)


def test_build_cell_curves_train_only():
    train = _make_train_df()
    curves, counts = PG.build_cell_curves(train, "PG-beta")
    # every beta cell supported
    assert set(k for k in curves) == set((float(b),) for b in (1.5, 2.0, 2.5))
    # cell curve == mean over training samples with that true beta
    for b in (1.5, 2.0, 2.5):
        sub = train[train["beta"] == b]
        expected = sub.groupby("delta")["loss"].mean().reindex(DELTA_GRID).to_numpy()
        assert np.allclose(curves[(float(b),)], expected)
    # curves for fold 0 use ONLY the four training folds (repeat_id % 5 != 0)
    train_fold0 = train[train["repeat_id"] % 5 != 0]
    curves_f0, counts_f0 = PG.build_cell_curves(train_fold0, "PG-beta")
    assert counts_f0[(2.0,)] == counts[(2.0,)] - 1  # fold-0 sample excluded
    sub = train_fold0[train_fold0["beta"] == 2.0]
    expected = sub.groupby("delta")["loss"].mean().reindex(DELTA_GRID).to_numpy()
    assert np.allclose(curves_f0[(2.0,)], expected)


def test_fold_partition():
    n_repeats = 25
    fold_of = np.array([r % 5 for r in range(n_repeats)])
    for f in range(5):
        tr = set(np.where(fold_of != f)[0])
        te = set(np.where(fold_of == f)[0])
        assert not (tr & te)
        assert len(te) == n_repeats // 5


# ============================================================
# Mapping: nearest-grid and interpolation/clipping
# ============================================================

def test_nearest_grid_lookup_and_clip_to_supported():
    curves = {(b,): loss_curve_parabola(0.1) for b in BETA_GRID}
    curves[(2.5,)] = loss_curve_parabola(0.3)
    counts = {(b,): 1 for b in BETA_GRID}
    lookup = PG.make_lookup(curves, counts, "PG-beta", "nearest_grid")
    # inside support: nearest cell curve, no clip
    curve, clipped = lookup({"beta_est": 2.13, "n": 7})
    assert not clipped
    assert np.allclose(curve, curves[(2.0,)])
    # unsupported nearest cell -> clip to nearest supported cell, flag True
    counts_no25 = dict(counts)
    counts_no25[(2.5,)] = 0
    lookup2 = PG.make_lookup(curves, counts_no25, "PG-beta", "nearest_grid")
    curve2, clipped2 = lookup2({"beta_est": 2.4, "n": 7})
    assert clipped2
    assert np.allclose(curve2, curves[(2.0,)])  # 2.0 closer than 3.0


def test_interp_interpolates_curves_not_deltas():
    """argmin(interpolated curve) differs from interp(argmin cells)."""
    curves = {}
    for b in BETA_GRID:
        if b == 2.0:
            curves[(b,)] = loss_curve_parabola(0.1, scale=100.0)
        elif b == 2.5:
            curves[(b,)] = loss_curve_parabola(0.3, scale=1.0)
        else:
            curves[(b,)] = loss_curve_parabola(0.2)
    counts = {(b,): 1 for b in BETA_GRID}
    lookup = PG.make_lookup(curves, counts, "PG-beta", "interpolated")
    curve, clipped = lookup({"beta_est": 2.25, "n": 7})
    assert not clipped
    assert len(curve) == len(DELTA_GRID)
    # 0.5 * 100*(d-0.1)^2 + 0.5*(d-0.3)^2 -> argmin at d = 10.3/101 = 0.102
    # -> nearest grid 0.10
    assert argmin_delta(curve) == 0.1
    # interpolating the cell argmins would give (0.1+0.3)/2 = 0.2 -> NOT 0.1
    assert argmin_delta(curve) != 0.2


def test_interp_clip_outside_support():
    curves = {(b,): loss_curve_parabola(0.2) for b in BETA_GRID}
    counts = {(b,): 1 for b in BETA_GRID}
    lookup = PG.make_lookup(curves, counts, "PG-beta", "interpolated")
    # inside box -> no clip
    _, clipped_in = lookup({"beta_est": 3.0, "n": 7})
    assert not clipped_in
    # above box -> clip to upper supported cell, event recorded
    curve_out, clipped_out = lookup({"beta_est": 5.4, "n": 7})
    assert clipped_out
    assert np.allclose(curve_out, curves[(5.0,)])
    # below box -> clip to lower supported cell
    curve_low, clipped_low = lookup({"beta_est": 0.7, "n": 7})
    assert clipped_low
    assert np.allclose(curve_low, curves[(1.5,)])


# ============================================================
# Iteration states
# ============================================================

def test_trajectory_fixed_point():
    def lookup(est):
        curve = loss_curve_parabola(0.3 if est["beta_est"] >= 2.0 else 0.3)
        return curve, False
    def mdm_at(delta):
        return {"beta_est": 1.8, "n": 7, "valid": True, "failure_reason": ""}
    traj = PG.run_trajectory(
        {"beta_est": 1.8, "goe_est": 0.5, "n": 7, "valid": True,
         "failure_reason": ""}, lookup, mdm_at)
    assert traj["state"] == "fixed_point"
    assert traj["one_step_delta"] == traj["terminal_delta"] == 0.3
    assert traj["n_updates"] == 1


def test_trajectory_cycle():
    """d0 -> d1 -> d0: cycle, never averaged, terminal = repeated delta."""
    def lookup(est):
        return (loss_curve_parabola(0.1) if est["beta_est"] < 2.0
                else loss_curve_parabola(0.3)), False
    def mdm_at(delta):
        # 0.1 -> estimate >2 ; 0.3 -> estimate <2  (a 2-cycle)
        beta = 2.5 if delta == 0.1 else 1.8
        return {"beta_est": beta, "n": 7, "valid": True, "failure_reason": ""}
    traj = PG.run_trajectory(
        {"beta_est": 1.8, "goe_est": 0.5, "n": 7, "valid": True,
         "failure_reason": ""}, lookup, mdm_at)
    assert traj["state"] == "cycle"
    assert traj["terminal_delta"] == 0.1   # repeated delta, NOT averaged to 0.2
    assert traj["terminal_delta"] != 0.2
    assert traj["one_step_delta"] == 0.1


def test_trajectory_max_iteration():
    """10 updates without fixed point or cycle -> max_iteration."""
    def lookup(est):
        idx = int(est["beta_est"])
        curve = np.full(len(DELTA_GRID), 1e6)
        curve[idx] = 0.0
        return curve, False
    def mdm_at(delta):
        i = DELTA_GRID.index(float(delta))
        return {"beta_est": (i + 1) % 12, "n": 7, "valid": True,
                "failure_reason": ""}
    traj = PG.run_trajectory(
        {"beta_est": 0.0, "goe_est": 0.5, "n": 7, "valid": True,
         "failure_reason": ""}, lookup, mdm_at, max_updates=10)
    assert traj["state"] == "max_iteration"
    assert traj["n_updates"] == 10
    assert traj["one_step_delta"] == DELTA_GRID[0]
    assert traj["terminal_delta"] == DELTA_GRID[10]


def test_trajectory_fallback_invalid_initial():
    traj = PG.run_trajectory(
        {"beta_est": math.nan, "goe_est": math.nan, "n": 7, "valid": False,
         "failure_reason": "invalid_initial_estimate"}, lambda e: (None, False),
        lambda d: None)
    assert traj["state"] == "fallback"
    assert traj["terminal_delta"] == PG.DEFAULT_DELTA == 0.1
    assert traj["fallback_reason"] == "invalid_initial_estimate"


def test_trajectory_invalid_terminal():
    """Initial valid but MDM at the selected delta invalid -> stop at that delta."""
    def lookup(est):
        return loss_curve_parabola(0.2), False
    def mdm_at(delta):
        return {"beta_est": math.nan, "n": 7, "valid": False,
                "failure_reason": "invalid_mdm_at_selected_delta"}
    traj = PG.run_trajectory(
        {"beta_est": 2.0, "goe_est": 0.5, "n": 7, "valid": True,
         "failure_reason": ""}, lookup, mdm_at)
    assert traj["state"] == "invalid_terminal"
    assert traj["terminal_delta"] == 0.2
    assert traj["one_step_delta"] == 0.2


def test_argmin_tie_picks_lowest_delta():
    curve = np.full(len(DELTA_GRID), 1e6)
    curve[3] = 0.0
    curve[5] = 0.0
    assert argmin_delta(curve) == DELTA_GRID[3]  # first (lowest) on tie


# ============================================================
# End-to-end alignment on a small synthetic subset
# ============================================================

def _make_subset():
    """Synthetic scan: complete 26-delta curves for a few combos."""
    rows = []
    for b in (1.5, 2.0, 2.5):
        for goe in (0.1, 0.5):
            for n in (7, 10):
                for rid in range(10):
                    center = 0.2 + 0.05 * (b - 1.5)
                    for j, d in enumerate(DELTA_GRID):
                        loss = (d - center) ** 2
                        rows.append({
                            "beta": float(b), "eta": 1000.0,
                            "gamma": float(goe * 1000.0),
                            "gamma_over_eta": float(goe), "n": int(n),
                            "repeat_id": int(rid), "delta": float(d),
                            "loss": float(loss),
                            "beta_hat": float(b + 0.3), "eta_hat": 1050.0,
                            "gamma_hat": float(goe * 1000.0 + 50.0),
                            "converged": True})
    return pd.DataFrame(rows)


def test_evaluate_fold_and_key_alignment():
    subset = _make_subset()
    n_samples = subset[PG.SAMPLE_KEYS].drop_duplicates().shape[0]
    penalty = float(np.nanpercentile(subset["loss"].dropna(), 99))
    est_lookup = PG.build_estimate_lookup(subset, penalty)
    initial_maps = {"MDM-0.1": {}, "WMLE": {}}
    for r in subset[subset["delta"] == PG.DEFAULT_DELTA].itertuples(index=False):
        key = (float(r.beta), float(r.eta), float(r.gamma),
               float(r.gamma_over_eta), int(r.n), int(r.repeat_id))
        initial_maps["MDM-0.1"][key] = PG.initial_from_scan(
            est_lookup, key, PG.DEFAULT_DELTA)
        initial_maps["WMLE"][key] = {"beta_est": float(r.beta_hat),
                                     "goe_est": PG.goe_of(r.beta_hat,
                                                         r.eta_hat,
                                                         r.gamma_hat),
                                     "n": int(r.n), "valid": True,
                                     "failure_reason": ""}
    dfs = []
    for family in PG.FAMILY_CELL_COLS:
        for mapping in PG.MAPPINGS:
            for fold in range(PG.FOLDS):
                df = PG.evaluate_fold(fold, subset, est_lookup, initial_maps,
                                      family, mapping)
                # both estimators scored per test sample
                assert len(df) == n_samples // PG.FOLDS * len(PG.ESTIMATORS)
                dfs.append(df)
    df_all = pd.concat(dfs, ignore_index=True)
    ka = PG.check_key_alignment(df_all, n_samples)
    assert ka["alignment_ok"] is True
    assert ka["duplicate_rows"] == 0
    assert ka["n_result_rows"] == n_samples * len(PG.ESTIMATORS) * \
        len(PG.FAMILY_CELL_COLS) * len(PG.MAPPINGS)
    # fallback path never triggers here (all estimates valid)
    assert (df_all["state"] == "fallback").sum() == 0
    # every terminal loss is finite and read from the same sample's cached MDM
    assert df_all["terminal_loss"].notna().all()


def test_evaluate_fold_train_only_no_leak():
    """A test-fold sample's own loss curve never drives its selection.

    Fold-0 test samples get a distinctive optimum at delta=0.5 while every
    training-fold sample keeps the 0.1 optimum.  If the fold-0 sample's own loss
    leaked into its rule, the selection would move toward 0.5; without leakage it
    stays at the training-rule 0.1.
    """
    subset = _make_subset()
    # overwrite loss curves of fold-0 samples (repeat_id % 5 == 0) with 0.5 optimum
    mask0 = subset["repeat_id"] % 5 == 0
    for j, d in enumerate(DELTA_GRID):
        subset.loc[mask0 & (subset["delta"] == d), "loss"] = (d - 0.5) ** 2
    n_samples = subset[PG.SAMPLE_KEYS].drop_duplicates().shape[0]
    penalty = float(np.nanpercentile(subset["loss"].dropna(), 99))
    est_lookup = PG.build_estimate_lookup(subset, penalty)
    initial_maps = {"MDM-0.1": {}, "WMLE": {}}
    for r in subset[subset["delta"] == PG.DEFAULT_DELTA].itertuples(index=False):
        key = (float(r.beta), float(r.eta), float(r.gamma),
               float(r.gamma_over_eta), int(r.n), int(r.repeat_id))
        initial_maps["MDM-0.1"][key] = PG.initial_from_scan(
            est_lookup, key, PG.DEFAULT_DELTA)
        initial_maps["WMLE"][key] = {"beta_est": float(r.beta_hat),
                                     "goe_est": PG.goe_of(r.beta_hat, r.eta_hat,
                                                          r.gamma_hat),
                                     "n": int(r.n), "valid": True,
                                     "failure_reason": ""}
    df0 = PG.evaluate_fold(0, subset, est_lookup, initial_maps, "PG-beta",
                           "nearest_grid")
    test0 = df0[df0["repeat_id"] % 5 == 0]
    # selection comes from the training-fold cell curve (0.1 optimum), not 0.5
    assert (test0["terminal_delta"] < 0.4).all(), \
        "fold-0 sample selection moved toward its own 0.5 optimum -> leak"


def test_mdm01_initial_from_scan():
    subset = _make_subset()
    est_lookup = PG.build_estimate_lookup(
        subset, float(np.nanpercentile(subset["loss"].dropna(), 99)))
    key = (2.0, 1000.0, 500.0, 0.5, 7, 0)
    init = PG.initial_from_scan(est_lookup, key, 0.1)
    assert init["valid"] is True
    assert math.isclose(init["beta_est"], 2.3)
    # goe_est = gamma_hat / eta_hat = (0.5*1000+50) / 1050
    assert math.isclose(init["goe_est"], 550.0 / 1050.0)


def test_is_valid_estimate_frozen():
    assert PG.is_valid_estimate(2.0, 1000.0, 500.0)
    assert not PG.is_valid_estimate(0.0, 1000.0, 500.0)     # beta <= 0
    assert not PG.is_valid_estimate(2.0, -1.0, 500.0)       # eta <= 0
    assert not PG.is_valid_estimate(2.0, 1000.0, -0.1)      # gamma < 0
    assert not PG.is_valid_estimate(None, 1000.0, 500.0)    # missing
    assert not PG.is_valid_estimate(math.inf, 1000.0, 500.0)  # non-finite
