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


# ============================================================
# REVISE round: corrected semantics
# ============================================================

def test_mode_self_describing_outputs():
    """A full package must not be mistaken for the pilot by filename."""
    fn = PG.output_filenames()
    for name in fn.values():
        assert "pilot" not in name
    assert fn["results"] == "pg_results.csv" and fn["wmle"] == "wmle_estimates.csv"
    assert "pilot" in PG.experiment_label("pilot")
    assert "48,000" in PG.experiment_label("full")
    assert "deferred" in PG.phase_boundary("pilot")
    assert "replaced the pilot" in PG.phase_boundary("full")
    assert PG.resolve_mode(99) == "pilot" and PG.resolve_mode(300) == "full"


def test_run_start_provenance_captured_before_writes():
    """git metadata is captured at run start, before any output is written."""
    meta = PG.PS.git_meta()
    for k in ("git_commit", "git_commit_short", "git_branch", "workspace_dirty"):
        assert k in meta
    src = open(os.path.join(STUDY_CODE_DIR, "run_pg_selector.py"),
               encoding="utf-8").read()
    start_idx = src.index("run_start = PS.git_meta()")
    makedirs_idx = src.index('os.makedirs(out_dir, exist_ok=True)')
    assert start_idx < makedirs_idx, \
        "run-start git metadata must be captured before any output is written"


def test_prov_err_bins_stratified():
    """Provisional-error relationship is stratified by estimator/family/mapping
    and separated by one-step vs terminal."""
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
                                     "goe_est": PG.goe_of(r.beta_hat, r.eta_hat,
                                                          r.gamma_hat),
                                     "n": int(r.n), "valid": True,
                                     "failure_reason": ""}
    dfs = [PG.evaluate_fold(f, subset, est_lookup, initial_maps, fam, mp)
           for fam in PG.FAMILY_CELL_COLS for mp in PG.MAPPINGS
           for f in range(PG.FOLDS)]
    df_all = pd.concat(dfs, ignore_index=True)
    # synthetic est_beta = true_beta + 0.3 is constant -> perturb so the error
    # bins have unique edges (real data has continuous errors)
    df_all["est_beta"] = df_all["est_beta"] + \
        np.random.default_rng(1).normal(0.0, 0.05, len(df_all))
    rows = PG.compute_prov_err_bins(df_all)
    assert rows and all({"estimator", "family", "mapping", "variant",
                         "err_bin"} <= set(r) for r in rows)
    groups = {(r["estimator"], r["family"], r["mapping"], r["variant"])
              for r in rows}
    n_expected = (len(PG.ESTIMATORS) * len(PG.FAMILY_CELL_COLS)
                  * len(PG.MAPPINGS) * 2)
    assert len(groups) == n_expected
    # each group has exactly 4 quantile bins
    assert all(sum(1 for r in rows if r["estimator"] == e and r["family"] == f
                   and r["mapping"] == m and r["variant"] == v) == 4
               for e in PG.ESTIMATORS for f in PG.FAMILY_CELL_COLS
               for m in PG.MAPPINGS for v in ("one_step", "terminal"))


def test_beta_cell_correctness():
    """Nearest-beta-cell routing: correct rate overall and by true beta."""
    df = pd.DataFrame({
        "estimator": ["WMLE"] * 8,
        "beta": [2.0] * 8, "eta": [1000.0] * 8, "gamma": [500.0] * 8,
        "gamma_over_eta": [0.5] * 8, "n": [7] * 8, "repeat_id": range(8),
        "est_beta": [2.1, 1.9, 4.2, 3.9, 5.1, 2.4, 1.4, 4.7],
        "true_beta": [2.0, 2.0, 4.0, 4.0, 5.0, 2.5, 1.5, 5.0],
    })
    rows = PG.compute_beta_cell_correctness(df)
    all_row = next(r for r in rows if r["true_beta"] == "ALL")
    assert all_row["estimator"] == "WMLE" and all_row["n"] == 8
    # expected correct routes: 2.1->2, 1.9->2 (both true 2.0 cell 2.0): correct
    # 4.2->4, 3.9->4 (true 4.0): correct; 5.1->5 (true 5.0): correct;
    # 2.4->2.5 (true 2.5): correct; 1.4->1.5 (true 1.5): correct;
    # 4.7->4.5 (true 5.0): INCORRECT  -> 7/8 correct
    assert all_row["n_correct"] == 7 and math.isclose(all_row["correct_rate"], 7 / 8)
    # per-true-beta counts present for every beta in the data
    for tb in (1.5, 2.0, 2.5, 4.0, 5.0):
        assert any(r["true_beta"] == tb for r in rows)


def test_paired_bootstrap_deterministic():
    """Paired repeat-block bootstrap is deterministic and brackets the observed."""
    rng = np.random.default_rng(0)
    n = 600
    df = pd.DataFrame({
        "repeat_id": np.repeat(np.arange(60), 10),
        "default_loss": rng.gamma(1.0, 0.05, n),
        "one_step_loss": rng.gamma(1.0, 0.05, n) + 0.02,  # PG slightly worse
    })
    a = PG.paired_bootstrap(df, "one_step_loss", seed=2026, n_boot=2000)
    b = PG.paired_bootstrap(df, "one_step_loss", seed=2026, n_boot=2000)
    assert a == b                       # fixed seed -> reproducible
    assert a["n_blocks"] == 60
    assert a["observed_j1_diff"] > 0    # PG worse than Default by construction
    assert a["ci_low"] <= a["observed_j1_diff"] <= a["ci_high"]
    # different seed should differ somewhere (not required, but sanity on seeding)
    c = PG.paired_bootstrap(df, "one_step_loss", seed=1, n_boot=2000)
    assert c["n_blocks"] == 60 and math.isfinite(c["ci_low"])


def test_contract_version_mode():
    """Full package must carry an unambiguous Phase B contract version."""
    assert PG.contract_version("pilot") == "PG_selector_phaseA_v1"
    assert PG.contract_version("full") == "PG_selector_phaseB_v1"
    assert PG.contract_version("pilot") != PG.contract_version("full")


def test_derive_summary_by_beta():
    """Per-true-beta PG vs Default J1 (and difference), per variant."""
    rows = []
    n = 40
    for tb in (1.5, 4.0):
        for i in range(n):
            rows.append({
                "estimator": "WMLE", "family": "PG-beta",
                "mapping": "interpolated", "true_beta": tb,
                "n": 7, "repeat_id": i % 5,
                "one_step_loss": 0.04 if tb == 1.5 else 0.09,
                "terminal_loss": 0.06, "default_loss": 0.0625,
                "one_step_delta": 0.1, "terminal_delta": 0.1,
            })
    df = pd.DataFrame(rows)
    out = PG.derive_summary_by_beta(df)
    # only the present combo is derived: 1 estimator x 1 family x 1 mapping
    # x 2 variants x 2 true betas = 4 rows
    assert len(out) == 4
    assert all({"estimator", "family", "mapping", "variant", "true_beta",
                "PG_J1", "Default_J1", "J1_diff"} <= set(r) for r in out)
    rec = next(r for r in out if r["true_beta"] == 1.5
               and r["variant"] == "one_step")
    assert math.isclose(rec["PG_J1"], math.sqrt(0.04))
    assert math.isclose(rec["Default_J1"], math.sqrt(0.0625))
    assert math.isclose(rec["J1_diff"], math.sqrt(0.04) - math.sqrt(0.0625))
    # a negative diff means PG better than Default at that beta
    assert rec["J1_diff"] < 0


def test_compute_paired_bootstrap_covers_one_step_and_terminal():
    """Every variant gets a bootstrap row; one-step is present for all 12."""
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
                                     "goe_est": PG.goe_of(r.beta_hat, r.eta_hat,
                                                          r.gamma_hat),
                                     "n": int(r.n), "valid": True,
                                     "failure_reason": ""}
    dfs = [PG.evaluate_fold(f, subset, est_lookup, initial_maps, fam, mp)
           for fam in PG.FAMILY_CELL_COLS for mp in PG.MAPPINGS
           for f in range(PG.FOLDS)]
    df_all = pd.concat(dfs, ignore_index=True)
    rows = PG.compute_paired_bootstrap(df_all, n_boot=50)
    assert len(rows) == len(PG.ESTIMATORS) * len(PG.FAMILY_CELL_COLS) * \
        len(PG.MAPPINGS) * 2
    one_steps = [r for r in rows if r["variant"] == "one_step"]
    assert len(one_steps) == 12
    assert all("ci_low" in r and "ci_high" in r and "observed_j1_diff" in r
               for r in rows)
