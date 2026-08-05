"""
Study/01 parameter-guided MDM offset selector (Phase A pilot / Phase B full)

Frozen scientific contract (task study01-param-guided-01, Phase A):

  The L3–L5 oracle selects an MDM offset from the TRUE parameters.  The PG
  (parameter-guided) route keeps the same conditional-mean 26-point loss curves
  but queries them with PROVISIONAL parameter estimates, asking whether
  estimated rather than true parameters retain part of the oracle gain.

Design interpretation (documented; plug-in design):
  - A selector family fixes the conditioning set on the TRUE-parameter grid,
    mirroring one L-layer:
        PG-beta    : curve conditional on beta only             (oracle ref L3)
        PG-beta-n  : curve conditional on (beta, n)             (oracle ref L4)
        PG-full    : curve conditional on (beta, gamma/eta, n)  (oracle ref L5)
  - For each cell the conditional-mean curve is the mean loss over TRAINING-fold
    samples with that true-parameter cell (exactly the L3/L4/L5 training curve).
  - A test sample's provisional estimate is used only to QUERY the curve: it is
    mapped to the nearest grid cell, or the cell curves are interpolated at the
    continuous estimate.  Curves are interpolated, never the selected deltas.

Initial estimators (provisional parameters):
  - MDM-0.1 : the cached MDM estimate at delta=0.1 (same scan; no recompute).
  - WMLE    : weighted-MLE production estimate (python/methods/wmle.py, same
              worker as B2).  B2's per-sample estimation.csv is absent on disk
              (gitignored, not present), so the cache is genuinely insufficient
              and WMLE is recomputed on the pilot subset only.

Two estimate->curve mappings:
  - nearest_grid : assign the estimate to its nearest grid cell; argmin of that
                   cell's conditional-mean curve.
  - interpolated : multilinear interpolation of the cell curves at the
                   continuous estimate; clip only outside the supported grid box
                   and record every clipping event.

Iteration (same sample, cached MDM estimates): initial estimate -> select delta
-> read the cached MDM estimate at that delta -> re-select ... Stop when the
delta is unchanged (fixed point / stable), a previously-seen delta reappears
(cycle), or 10 updates are reached.  A cycle is never averaged and convergence
is never silently forced.  If the INITIAL estimate is invalid, retain delta=0.1
for that sample and record an explicit fallback reason.

Split / scoring:
  - Primary split is the existing `repeat_id mod 5` cross-fit; curves are built
    from training folds only and each sample is scored on its hold-out fold.
  - Loss L_i = ((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2
               + ((gamma_hat-gamma)/eta)^2  (three-parameter definition).
  - J1 = sqrt(mean_i(L_i)); NO /3.

Phase A runs a bounded pilot: repeats 0..PILOT_REPEATS-1 (default 100 -> 16,000
samples, every sample scored once across the 5 folds).  The full 48,000-sample
run is Phase B (`--full`) and is NOT executed in Phase A.

Output: artifacts/formal/pg_selector/
  summary.json, manifest.json, run_log.txt
  variant_summary.csv, oracle_comparison.csv, state_counts.csv,
  clip_diagnostics.csv, prov_param_diag.csv, prov_err_vs_delta.csv,
  beta_cell_correctness.csv, paired_bootstrap.csv,
  key_alignment.json, SHA256SUMS, SHA256SUMS.local_not_in_git
  pg_results.csv (gitignored per-sample traces), wmle_estimates.csv
  (gitignored per-sample WMLE estimates)

Output names are mode-independent (generic); the mode is recorded in the
summary/manifest metadata so a full package cannot be mistaken for the pilot.

Usage:
    python code/run_pg_selector.py                # pilot (repeats 0..99)
    python code/run_pg_selector.py --full         # Phase B full 48,000-sample
    python code/run_pg_selector.py --pilot-repeats N --workers 8
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from multiprocessing import Pool

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
for p in (STUDY_CODE_DIR, PYTHON_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import dim_raw_config as CFG
import analyze_E1_E2_crossfit as CROSSFIT
import run_E6b_dimensional_raw_specialist as E6
import paper_support as PS

CONTRACT_VERSION = "PG_selector_phaseA_v1"
PILOT_REPEATS = 100                      # Phase A pilot: repeats 0..99
N_DELTAS = 26
SAMPLE_KEYS = E6.SAMPLE_KEYS
DELTA_GRID = list(CFG.DELTA_GRID)
DEFAULT_DELTA = CFG.DEFAULT_DELTA
MAX_UPDATES = 10
OUT_DIR = os.path.join(STUDY_ROOT, "artifacts", "formal", "pg_selector")

# Conditioning sets mirror the L3/L4/L5 groups on the true-parameter grid.
FAMILY_CELL_COLS = {
    "PG-beta": ["beta"],
    "PG-beta-n": ["beta", "n"],
    "PG-full": ["beta", "gamma_over_eta", "n"],
}
FAMILY_ORACLE = {"PG-beta": "L3", "PG-beta-n": "L4", "PG-full": "L5"}
ESTIMATORS = ["MDM-0.1", "WMLE"]
MAPPINGS = ["nearest_grid", "interpolated"]
BETA_GRID = list(CFG.BETA_GRID)
GOE_GRID = list(CFG.GAMMA_OVER_ETA_GRID)
N_GRID = list(CFG.N_GRID)
FOLDS = 5


# ============================================================
# Mode / output naming (self-describing packages)
# ============================================================

def output_filenames():
    """Generic, mode-independent output names.

    A 48,000-sample (Phase B) package must not be mistaken for the pilot by
    filename; the mode lives in the summary/manifest metadata instead.
    """
    return {"results": "pg_results.csv", "wmle": "wmle_estimates.csv"}


def experiment_label(mode):
    return ("parameter-guided offset selector - pilot (Phase A, bounded repeats)"
            if mode == "pilot" else
            "parameter-guided offset selector - full (Phase B, 48,000-sample)")


def phase_boundary(mode):
    return ("Phase A pilot only (bounded repeats); full 48,000-sample run deferred"
            if mode == "pilot" else
            "Phase B full 48,000-sample run; final package replaced the pilot "
            "package at this location")


def resolve_mode(repeat_max):
    return "full" if repeat_max >= CFG.REPEATS else "pilot"


# ============================================================
# Data loading (reused 160-combo scan, pilot subset)
# ============================================================

def load_scan_subset(repeat_max):
    """Read the reused 160-combo MC scan restricted to repeat_id < repeat_max."""
    dtypes = {
        "beta": "float64", "eta": "float64", "gamma": "float64",
        "gamma_over_eta": "float64", "n": "int64", "repeat_id": "int64",
        "delta": "float64", "beta_hat": "float64", "eta_hat": "float64",
        "gamma_hat": "float64", "r_squared": "float64",
        "converged": "boolean", "time_ms": "float64",
    }
    frames = []
    for p in E6.list_mdm_chunks():
        d = pd.read_csv(p, dtype=dtypes)
        frames.append(d[d["repeat_id"] < repeat_max])
    if not frames:
        raise FileNotFoundError(f"No chunks under {CFG.CHUNKS_DIR}")
    return pd.concat(frames, ignore_index=True)


def sample_key_tuple(r):
    """Canonical per-sample key: (beta, eta, gamma, gamma_over_eta, n, repeat_id)."""
    return (float(r["beta"]), float(r["eta"]), float(r["gamma"]),
            float(r["gamma_over_eta"]), int(r["n"]), int(r["repeat_id"]))


def build_estimate_lookup(subset, failure_penalty):
    """key -> {delta: (beta_hat, eta_hat, gamma_hat, converged, loss_filled)}."""
    lookup = {}
    for _, r in subset.iterrows():
        key = sample_key_tuple(r)
        d = float(r["delta"])
        loss = float(r["loss"])
        loss_filled = loss if math.isfinite(loss) else float(failure_penalty)
        lookup.setdefault(key, {})[d] = (
            float(r["beta_hat"]), float(r["eta_hat"]), float(r["gamma_hat"]),
            bool(r["converged"]), loss_filled)
    return lookup


# ============================================================
# Estimates / validity
# ============================================================

def is_valid_estimate(beta_hat, eta_hat, gamma_hat):
    """Frozen validity: finite and beta>0, eta>0, gamma>=0 (matches B2)."""
    if any(v is None for v in (beta_hat, eta_hat, gamma_hat)):
        return False
    v = [float(beta_hat), float(eta_hat), float(gamma_hat)]
    if not all(math.isfinite(x) for x in v):
        return False
    if v[0] <= 0 or v[1] <= 0 or v[2] < 0:
        return False
    return True


def goe_of(beta_hat, eta_hat, gamma_hat):
    """Estimated gamma/eta ratio = gamma_hat / eta_hat (both estimated).

    Decision note: PG-full conditions on the *estimated* ratio.  The alternative
    gamma_hat / eta_true is not used; recorded as a design decision for review.
    """
    return float(gamma_hat) / float(eta_hat)


def _est_dict(bh, eh, gh, valid, key, failure_reason=""):
    return {"beta_est": float(bh), "goe_est": goe_of(bh, eh, gh) if valid
            else math.nan, "n": int(key[4]), "valid": bool(valid),
            "failure_reason": failure_reason}


def initial_from_scan(est_lookup, key, delta):
    rec = est_lookup[key].get(float(delta))
    if rec is None:
        return {"valid": False, "failure_reason": f"no_scan_estimate_delta_{delta}"}
    bh, eh, gh, converged, _loss = rec
    valid = bool(converged) and is_valid_estimate(bh, eh, gh)
    return _est_dict(bh, eh, gh, valid, key,
                     "" if valid else "invalid_initial_estimate")


def make_mdm_at(est_lookup, key):
    """mdm_at(delta) -> next estimate dict for the same sample (cached MDM)."""
    def mdm_at(delta):
        rec = est_lookup[key].get(float(delta))
        if rec is None:
            return {"valid": False, "failure_reason": f"no_scan_estimate_delta_{delta}"}
        bh, eh, gh, converged, _loss = rec
        valid = bool(converged) and is_valid_estimate(bh, eh, gh)
        return _est_dict(bh, eh, gh, valid, key,
                         "" if valid else "invalid_mdm_at_selected_delta")
    return mdm_at


# ============================================================
# Conditional-mean cell curves (training folds only)
# ============================================================

def build_cell_curves(train_df, family):
    """Conditional-mean 26-pt loss curve per true-parameter cell.

    Cell = the family's conditioning set on the true-parameter grid.  This is
    exactly the L3/L4/L5 training-fold mean curve (mean of per-sample loss over
    training samples in that cell, per delta).
    """
    cell_cols = FAMILY_CELL_COLS[family]
    mean = (train_df.groupby(cell_cols + ["delta"], dropna=False)["loss"]
            .mean().rename("mean_loss").reset_index())
    curves, counts = {}, {}
    # count SAMPLES per cell (distinct sample rows, not the 26-delta rows)
    cnt = (train_df[cell_cols + ["repeat_id"]].drop_duplicates()
           .groupby(cell_cols, dropna=False).size())
    # normalize group keys to flat tuples (single-column groupby yields a scalar
    # or a 1-tuple depending on pandas version / key type)
    def _norm_key(raw_key):
        if isinstance(raw_key, tuple):
            return tuple(raw_key)
        return (raw_key,)
    for raw_key, n_samp in cnt.items():
        key = _norm_key(raw_key)
        counts[key] = int(n_samp)
    for raw_key, grp in mean.groupby(cell_cols, dropna=False):
        key = _norm_key(raw_key)
        curve = grp.set_index("delta")["mean_loss"].reindex(DELTA_GRID).to_numpy()
        curves[key] = curve.astype(float)
    return curves, counts


def supported_cells(counts, min_cell_count=1):
    return set(k for k, c in counts.items() if c >= min_cell_count)


def nearest_grid_value(v, grid):
    return grid[int(np.argmin(np.abs(np.asarray(grid, dtype=float) - float(v))))]


def cell_from_estimate(est, family):
    """Map a provisional estimate to its nominal nearest-grid cell."""
    beta_c = nearest_grid_value(est["beta_est"], BETA_GRID)
    n = int(est["n"])
    if family == "PG-beta":
        return (beta_c,)
    if family == "PG-beta-n":
        return (beta_c, n)
    goe_c = nearest_grid_value(est["goe_est"], GOE_GRID)
    return (beta_c, goe_c, n)


def nearest_supported_cell(est, family, supported):
    """Deterministic nearest supported cell in continuous-estimate space."""
    if family == "PG-beta":
        def dist(c):
            return abs(c[0] - est["beta_est"])
    elif family == "PG-beta-n":
        def dist(c):
            return abs(c[0] - est["beta_est"]) if c[1] == int(est["n"]) else math.inf
    else:
        def dist(c):
            if c[2] != int(est["n"]):
                return math.inf
            return math.hypot(c[0] - est["beta_est"], c[1] - est["goe_est"])
    cells = sorted(supported)
    return min(cells, key=lambda c: (dist(c), c))


def build_interp_table(curves, supported, family):
    """RegularGridInterpolator per n (or 'all') over the family's continuous axes."""
    interp_by_n, box_by_n = {}, {}
    if family == "PG-beta":
        axis = np.asarray(BETA_GRID, dtype=float)
        vals = np.array([curves.get((b,), np.full(N_DELTAS, np.nan))
                         for b in BETA_GRID])
        interp_by_n["all"] = RegularGridInterpolator(
            (axis,), vals, method="linear", bounds_error=False, fill_value=np.nan)
        sb = [b for (b,) in supported]
        box_by_n["all"] = [(min(sb), max(sb)) if sb else (np.nan, np.nan)]
    else:
        axis = np.asarray(BETA_GRID, dtype=float)
        for n in N_GRID:
            if family == "PG-beta-n":
                vals = np.array([curves.get((b, n), np.full(N_DELTAS, np.nan))
                                 for b in BETA_GRID])
                sn = [b for (b, nn) in supported if nn == n]
                box = [(min(sn), max(sn)) if sn else (np.nan, np.nan)]
            else:  # PG-full: bilinear over (beta, gamma/eta) within n
                ax_g = np.asarray(GOE_GRID, dtype=float)
                vals = np.empty((len(BETA_GRID), len(GOE_GRID), N_DELTAS))
                for i, b in enumerate(BETA_GRID):
                    for j, g in enumerate(GOE_GRID):
                        vals[i, j] = curves.get((b, g, n),
                                                np.full(N_DELTAS, np.nan))
                sup_n = [(b, g) for (b, g, nn) in supported if nn == n]
                if sup_n:
                    box = [(min(b for b, _ in sup_n), max(b for b, _ in sup_n)),
                           (min(g for _, g in sup_n), max(g for _, g in sup_n))]
                else:
                    box = [(np.nan, np.nan), (np.nan, np.nan)]
            interp_by_n[n] = (RegularGridInterpolator(
                (axis,), vals, method="linear", bounds_error=False,
                fill_value=np.nan) if family == "PG-beta-n" else
                RegularGridInterpolator((axis, ax_g), vals, method="linear",
                                        bounds_error=False, fill_value=np.nan))
            box_by_n[n] = box
    return interp_by_n, box_by_n


def lookup_interp(est, family, interp_by_n, box_by_n, curves, supported):
    """Interpolate the cell loss curves at the continuous estimate; clip outside support."""
    if family == "PG-beta":
        nkey = "all"
        point = [float(est["beta_est"])]
    else:
        nkey = int(est["n"])
        point = [float(est["beta_est"])] if family == "PG-beta-n" else \
            [float(est["beta_est"]), float(est["goe_est"])]
    interp = interp_by_n[nkey]
    box = box_by_n[nkey]
    curve = np.asarray(interp([point]))[0]
    if not np.isnan(curve).any():
        return curve, False
    # outside the supported box (or an unsupported interior cell): clip
    cp = list(point)
    for i, (lo, hi) in enumerate(box):
        if not (np.isnan(lo) or np.isnan(hi)):
            cp[i] = min(max(cp[i], lo), hi)
    curve2 = np.asarray(interp([cp]))[0]
    if not np.isnan(curve2).any():
        return curve2, True
    ncell = nearest_supported_cell(est, family, supported)
    return curves[ncell], True


def make_lookup(curves, counts, family, mapping, min_cell_count=1):
    """Return lookup(est) -> (26-pt curve, clipped_bool)."""
    supported = supported_cells(counts, min_cell_count)
    if mapping == "nearest_grid":
        def lookup(est):
            cell = cell_from_estimate(est, family)
            if cell in supported:
                return curves[cell], False
            ncell = nearest_supported_cell(est, family, supported)
            return curves[ncell], True
    else:
        interp_by_n, box_by_n = build_interp_table(curves, supported, family)

        def lookup(est):
            return lookup_interp(est, family, interp_by_n, box_by_n,
                                 curves, supported)
    return lookup


# ============================================================
# Iteration (fixed point / cycle / max-iteration / fallback)
# ============================================================

def run_trajectory(initial, lookup, mdm_at, max_updates=MAX_UPDATES):
    """One sample's selection trajectory.

    Returns a dict with state, one_step_delta, terminal_delta, clip_events,
    n_updates and fallback_reason.  A cycle is never averaged; convergence is
    never forced.
    """
    def out(state, one, terminal, clip, updates, reason=""):
        return {"state": state, "one_step_delta": float(one),
                "terminal_delta": float(terminal), "clip_events": int(clip),
                "n_updates": int(updates), "fallback_reason": reason}

    est = initial
    if not est.get("valid"):
        return out("fallback", DEFAULT_DELTA, DEFAULT_DELTA, 0, 0,
                   est.get("failure_reason", "invalid_initial_estimate"))

    deltas, clip_total = [], 0
    for step in range(max_updates + 1):
        curve, clipped = lookup(est)
        if clipped:
            clip_total += 1
        curve = np.asarray(curve, dtype=float)
        if not np.isfinite(curve).any():
            return out("no_supported_curve", DEFAULT_DELTA, DEFAULT_DELTA,
                       clip_total, step)
        finite = np.where(np.isfinite(curve), curve, np.inf)
        d = DELTA_GRID[int(np.argmin(finite))]
        if deltas and d == deltas[-1]:
            return out("fixed_point", deltas[0], d, clip_total, step)
        if d in deltas:
            return out("cycle", deltas[0], d, clip_total, step)
        deltas.append(d)
        if step == max_updates:
            return out("max_iteration", deltas[0], d, clip_total, step)
        est = mdm_at(d)
        if not est.get("valid"):
            return out("invalid_terminal", deltas[0], d, clip_total, step + 1,
                       est.get("failure_reason", ""))
    # unreachable
    return out("no_supported_curve", DEFAULT_DELTA, DEFAULT_DELTA, clip_total, 0)


# ============================================================
# Per-fold scoring
# ============================================================

def evaluate_fold(fold, subset, est_lookup, initial_maps, family, mapping):
    """Score one fold's test samples for one (family, mapping) and both estimators."""
    train_df = subset[subset["repeat_id"] % FOLDS != fold]
    test_keys = (subset[subset["repeat_id"] % FOLDS == fold][SAMPLE_KEYS]
                 .drop_duplicates())
    curves, counts = build_cell_curves(train_df, family)
    lookup = make_lookup(curves, counts, family, mapping)
    rows = []
    for _, r in test_keys.iterrows():
        key = sample_key_tuple(r)
        est_lookup_key = est_lookup[key]
        # Default (delta=0.1) loss for this same sample, used for paired
        # PG-vs-Default robustness (fold-independent).
        l_default, _v_default = loss_at(est_lookup_key, DEFAULT_DELTA)
        for estimator in ESTIMATORS:
            init = initial_maps[estimator][key]
            traj = run_trajectory(init, lookup, make_mdm_at(est_lookup, key))
            l_one, v_one = loss_at(est_lookup_key, traj["one_step_delta"])
            l_term, v_term = loss_at(est_lookup_key, traj["terminal_delta"])
            rows.append({
                "beta": float(r["beta"]), "eta": float(r["eta"]),
                "gamma": float(r["gamma"]),
                "gamma_over_eta": float(r["gamma_over_eta"]),
                "n": int(r["n"]), "repeat_id": int(r["repeat_id"]),
                "fold": int(fold),
                "estimator": estimator, "family": family, "mapping": mapping,
                "state": traj["state"], "clip_events": traj["clip_events"],
                "n_updates": traj["n_updates"],
                "one_step_delta": traj["one_step_delta"],
                "one_step_loss": l_one, "one_step_valid": bool(v_one),
                "terminal_delta": traj["terminal_delta"],
                "terminal_loss": l_term, "terminal_valid": bool(v_term),
                "default_loss": l_default,
                "init_valid": bool(init.get("valid")),
                "fallback_reason": init.get("failure_reason", ""),
                "est_beta": float(init["beta_est"]) if init.get("valid") else math.nan,
                "est_goe": float(init["goe_est"]) if init.get("valid") else math.nan,
                "true_beta": float(r["beta"]),
                "true_goe": float(r["gamma_over_eta"]),
            })
    return pd.DataFrame(rows)


def loss_at(est_lookup_key, delta):
    rec = est_lookup_key.get(float(delta))
    if rec is None:
        return math.nan, False
    loss = float(rec[4])
    if not math.isfinite(loss):
        return math.nan, False
    return loss, True


# ============================================================
# Metrics
# ============================================================

def j1_from_loss(loss_series):
    loss = pd.to_numeric(loss_series, errors="coerce").dropna()
    return math.sqrt(float(loss.mean()))


def variant_metrics(df, loss_col, valid_col):
    out = {"J1": j1_from_loss(df[loss_col]),
           "failure_rate": float(1.0 - df[valid_col].astype(bool).mean()),
           "n_samples": int(len(df))}
    for n, g in df.groupby("n"):
        out[f"J1_n{int(n)}"] = j1_from_loss(g[loss_col])
    return out


def beta_cell_matches(est_beta, true_beta):
    """Whether the provisional estimate routes to the true beta's grid cell."""
    return nearest_grid_value(est_beta, BETA_GRID) == nearest_grid_value(
        true_beta, BETA_GRID)


def paired_bootstrap(df, loss_col, seed=2026, n_boot=2000):
    """Deterministic paired repeat-block bootstrap: PG vs Default J1 difference.

    Clusters by `repeat_id` (repeat block = the samples sharing one repeat_id
    across all combos).  Resample blocks with replacement (fixed seed), recompute
    the pooled J1 for PG and Default over the resampled union, and report the
    2.5/97.5 percentile interval of the J1 difference (positive = PG worse).
    Also reports the fraction of repeat blocks where PG's block-level J1 is worse
    than Default's.  `df` must have `repeat_id`, `default_loss` and `loss_col`.
    """
    d = df[["repeat_id", loss_col, "default_loss"]].dropna().copy()
    pg = d[loss_col].to_numpy(float)
    de = d["default_loss"].to_numpy(float)
    block_ids = d["repeat_id"].to_numpy(int)
    uniq = np.unique(block_ids)
    n_blocks = len(uniq)
    # per-block sums and counts
    pg_sum = np.array([pg[block_ids == u].sum() for u in uniq])
    de_sum = np.array([de[block_ids == u].sum() for u in uniq])
    cnt = np.array([(block_ids == u).sum() for u in uniq])
    j1 = lambda s, c: np.sqrt(s / c)        # noqa: E731  (scalar or array)
    obs = float(j1(pg.sum(), len(pg)) - j1(de.sum(), len(de)))
    n_worse = int(np.sum(j1(pg_sum, cnt) > j1(de_sum, cnt)))
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n_blocks, size=n_blocks)
        diffs[b] = float(j1(pg_sum[idx].sum(), cnt[idx].sum()) - j1(
            de_sum[idx].sum(), cnt[idx].sum()))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"observed_j1_diff": float(obs), "ci_low": float(lo),
            "ci_high": float(hi), "n_boot": int(n_boot), "seed": int(seed),
            "n_blocks": int(n_blocks), "n_blocks_pg_worse": int(n_worse),
            "frac_blocks_pg_worse": float(n_worse / n_blocks)}


def compute_prov_err_bins(df_all):
    """Stratified provisional-beta-error bins (estimator/family/mapping/variant).

    Relationship of provisional-parameter error to the selected delta is only
    interpretable within one estimator/family/mapping and separated by
    one-step vs terminal, so the table carries all four dimensions.
    """
    err_bin_rows = []
    for estimator in ESTIMATORS:
        for family in FAMILY_CELL_COLS:
            for mapping in MAPPINGS:
                for variant, dcol in (("one_step", "one_step_delta"),
                                      ("terminal", "terminal_delta")):
                    lcol = dcol.replace("delta", "loss")
                    sub = df_all[(df_all["estimator"] == estimator)
                                 & (df_all["family"] == family)
                                 & (df_all["mapping"] == mapping)].copy()
                    sub["abs_beta_err"] = (sub["est_beta"] - sub["true_beta"]).abs()
                    sub = sub.dropna(subset=["abs_beta_err", dcol])
                    if not len(sub):
                        continue
                    sub["err_bin"] = pd.qcut(sub["abs_beta_err"], 4,
                                             labels=["q1", "q2", "q3", "q4"],
                                             duplicates="drop")
                    for b, g in sub.groupby("err_bin", observed=True):
                        err_bin_rows.append({
                            "estimator": estimator, "family": family,
                            "mapping": mapping, "variant": variant,
                            "err_bin": str(b),
                            "err_low": float(g["abs_beta_err"].min()),
                            "err_high": float(g["abs_beta_err"].max()),
                            "n": int(len(g)),
                            "mean_selected_delta": float(g[dcol].mean()),
                            "mean_loss": float(g[lcol].mean()),
                            "J1": j1_from_loss(g[lcol]),
                        })
    return err_bin_rows


def compute_beta_cell_correctness(df_all):
    """Nearest-beta-cell correctness (does the estimate route to the true cell?).

    One row per sample (per estimator).  Reports the overall correct rate and
    the rate with counts by true beta, so a paper can state how often noisy or
    biased provisional beta estimates misroute a sample to the wrong cell.
    """
    cell_rows = []
    for estimator in ESTIMATORS:
        sub = df_all[df_all["estimator"] == estimator].dropna(
            subset=["est_beta", "true_beta"])
        sub = sub.drop_duplicates(subset=SAMPLE_KEYS)
        if len(sub) == 0:
            continue
        est_cell = sub["est_beta"].apply(
            lambda v: nearest_grid_value(v, BETA_GRID))
        true_cell = sub["true_beta"].apply(
            lambda v: nearest_grid_value(v, BETA_GRID))
        ok = (est_cell == true_cell).astype(float)
        cell_rows.append({"estimator": estimator, "true_beta": "ALL",
                          "n": int(len(sub)), "n_correct": int(ok.sum()),
                          "correct_rate": float(ok.mean())})
        for b, g in sub.groupby("true_beta"):
            gok = (est_cell.loc[g.index] == true_cell.loc[g.index]).astype(float)
            cell_rows.append({"estimator": estimator, "true_beta": float(b),
                              "n": int(len(g)), "n_correct": int(gok.sum()),
                              "correct_rate": float(gok.mean())})
    return cell_rows


def compute_paired_bootstrap(df_all, n_boot=2000, seed=2026):
    """PG vs Default paired bootstrap for every variant (one-step + terminal)."""
    rows = []
    for estimator in ESTIMATORS:
        for family in FAMILY_CELL_COLS:
            for mapping in MAPPINGS:
                sub = df_all[(df_all["estimator"] == estimator)
                             & (df_all["family"] == family)
                             & (df_all["mapping"] == mapping)]
                for variant, lcol in (("one_step", "one_step_loss"),
                                      ("terminal", "terminal_loss")):
                    rows.append({"estimator": estimator, "family": family,
                                 "mapping": mapping, "variant": variant,
                                 **paired_bootstrap(sub, lcol, seed=seed,
                                                    n_boot=n_boot)})
    return rows


# ============================================================
# Main
# ============================================================

def log_lines():
    buf = []

    def _log(msg):
        print(msg, flush=True)
        buf.append(msg)
    return _log, buf


def run_experiment(repeat_max=PILOT_REPEATS, workers=8, force_rerun=False,
                   mode=None):
    mode = mode or resolve_mode(repeat_max)
    # Run-start provenance is captured BEFORE any output is written, so
    # workspace_dirty reflects the pre-run tree (not the files we are about to
    # create/overwrite).
    run_start = PS.git_meta()
    out_dir = OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    log, buf = log_lines()
    log("=" * 72)
    log(f"Study/01 {experiment_label(mode)}")
    log(f"mode={mode}  repeat_max={repeat_max}  "
        f"(samples = 160 x {repeat_max} x {len(DELTA_GRID)} deltas)")
    log(f"run_start: branch={run_start['git_branch']} "
        f"commit={run_start['git_commit'][:8]} clean={not run_start['workspace_dirty']}")
    log(f"Output: {out_dir}")
    log("=" * 72)
    t_start = time.time()

    log("\n[1/7] Loading reused 160-combo scan (pilot subset)...")
    df_mc = load_scan_subset(repeat_max)
    subset = E6.compute_per_sample_loss(df_mc)
    n_samples = subset[SAMPLE_KEYS].drop_duplicates().shape[0]
    log(f"  {len(subset):,} scan rows; {n_samples} unique samples; "
        f"deltas={sorted(subset['delta'].unique())}")
    assert len(subset["delta"].unique()) == N_DELTAS

    # failure penalty (p99 of training loss) — does not trigger in this data
    penalty = float(np.nanpercentile(subset["loss"].dropna(), 99))
    log(f"  failure_penalty (p99, not triggered): {penalty:.6f}")

    log("\n[2/7] Building estimate lookup + MDM-0.1 initial estimates...")
    est_lookup = build_estimate_lookup(subset, penalty)
    initial_maps = {"MDM-0.1": {}}
    for r in subset[subset["delta"] == DEFAULT_DELTA].itertuples(index=False):
        key = (float(r.beta), float(r.eta), float(r.gamma),
               float(r.gamma_over_eta), int(r.n), int(r.repeat_id))
        initial_maps["MDM-0.1"][key] = initial_from_scan(est_lookup, key,
                                                         DEFAULT_DELTA)
    n_invalid_mdm01 = sum(1 for v in initial_maps["MDM-0.1"].values()
                          if not v["valid"])
    log(f"  MDM-0.1 initial estimates: {len(initial_maps['MDM-0.1'])}; "
        f"invalid={n_invalid_mdm01}")

    log(f"\n[3/7] WMLE initial estimates ({n_samples} samples)...")
    wmle_df = compute_wmle(subset[SAMPLE_KEYS].drop_duplicates(),
                           workers=workers, force_rerun=force_rerun)
    initial_maps["WMLE"] = {}
    wmle_valid = 0
    for _, r in wmle_df.iterrows():
        key = (float(r["beta"]), float(r["eta"]), float(r["gamma"]),
               float(r["gamma_over_eta"]), int(r["n"]), int(r["repeat_id"]))
        valid = bool(r["valid"])
        if valid:
            wmle_valid += 1
        initial_maps["WMLE"][key] = {
            "beta_est": float(r["beta_hat"]),
            "goe_est": goe_of(r["beta_hat"], r["eta_hat"], r["gamma_hat"])
            if valid else math.nan,
            "n": int(r["n"]), "valid": valid,
            "failure_reason": str(r["failure_reason"]) if not valid else "",
        }
    log(f"  WMLE estimates: {len(initial_maps['WMLE'])}; "
        f"{len(initial_maps['WMLE']) - wmle_valid} invalid/fallback")
    n_wmle_fail = len(initial_maps["WMLE"]) - wmle_valid

    log("\n[4/7] Same-sample oracle L1–L5 cross-fit on the pilot subset...")
    oracle = CROSSFIT.run_crossfit(CROSSFIT.prepare_scan(subset), n_folds=FOLDS,
                                   default_delta=DEFAULT_DELTA)
    oracle_pooled = oracle["pooled_metrics"]
    oracle_by_n = oracle["by_n_metrics"]
    for _, row in oracle_pooled.iterrows():
        log(f"  oracle {row['layer']}: J1={float(row['J1']):.6f}")
    oracle_j1 = {r["layer"]: float(r["J1"]) for _, r in oracle_pooled.iterrows()}
    oracle_n_j1 = {}
    for _, r in oracle_by_n.iterrows():
        oracle_n_j1.setdefault(str(r["layer"]), {})[int(r["n"])] = float(r["J1"])

    log("\n[5/7] PG selector evaluation (2 estimators x 3 families x 2 mappings)...")
    all_rows = []
    for family in FAMILY_CELL_COLS:
        for mapping in MAPPINGS:
            for fold in range(FOLDS):
                df = evaluate_fold(fold, subset, est_lookup, initial_maps,
                                   family, mapping)
                # both initial estimators are scored for every test sample
                assert len(df) == n_samples // FOLDS * len(ESTIMATORS)
                all_rows.append(df)
            log(f"  done {family}/{mapping}")
    df_all = pd.concat(all_rows, ignore_index=True)
    df_all.to_csv(os.path.join(out_dir, output_filenames()["results"]), index=False)
    log(f"  per-sample rows: {len(df_all):,} "
        f"({len(df_all) // len(ESTIMATORS) // len(FAMILY_CELL_COLS) // len(MAPPINGS)} "
        f"samples x variants)")

    log("\n[6/7] Aggregating...")
    summary_rows, state_rows, clip_rows = [], [], []
    for estimator in ESTIMATORS:
        for family in FAMILY_CELL_COLS:
            for mapping in MAPPINGS:
                for variant, lc, vc in (("one_step", "one_step_loss",
                                         "one_step_valid"),
                                        ("terminal", "terminal_loss",
                                         "terminal_valid")):
                    sub = df_all[(df_all["estimator"] == estimator)
                                 & (df_all["family"] == family)
                                 & (df_all["mapping"] == mapping)]
                    m = variant_metrics(sub, lc, vc)
                    summary_rows.append({"estimator": estimator, "family": family,
                                         "mapping": mapping, "variant": variant,
                                         **m})
                    # state counts (state is per trajectory; shared by variants)
                    if variant == "terminal":
                        st = sub.groupby("state").size()
                        rec = {"estimator": estimator, "family": family,
                               "mapping": mapping,
                               "n_samples": int(len(sub))}
                        for s in ("fixed_point", "cycle", "max_iteration",
                                  "fallback", "invalid_terminal",
                                  "no_supported_curve"):
                            rec[f"n_{s}"] = int(st.get(s, 0))
                        rec["stable_or_fixed_point"] = int(st.get("fixed_point", 0))
                        rec["n_fallback"] = int(st.get("fallback", 0))
                        rec["n_clipped_samples"] = int((sub["clip_events"] > 0).sum())
                        rec["n_clip_events"] = int(sub["clip_events"].sum())
                        state_rows.append(rec)
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(os.path.join(out_dir, "variant_summary.csv"), index=False)
    df_state = pd.DataFrame(state_rows)
    df_state.to_csv(os.path.join(out_dir, "state_counts.csv"), index=False)

    # clip diagnostics (per estimator/family/mapping, terminal)
    clip_rows = []
    for estimator in ESTIMATORS:
        for family in FAMILY_CELL_COLS:
            for mapping in MAPPINGS:
                sub = df_all[(df_all["estimator"] == estimator)
                             & (df_all["family"] == family)
                             & (df_all["mapping"] == mapping)]
                clip_rows.append({
                    "estimator": estimator, "family": family, "mapping": mapping,
                    "n_samples": int(len(sub)),
                    "n_clipped_samples": int((sub["clip_events"] > 0).sum()),
                    "n_clip_events": int(sub["clip_events"].sum()),
                    "mean_clip_per_sample": float(sub["clip_events"].mean()),
                })
    df_clip = pd.DataFrame(clip_rows)
    df_clip.to_csv(os.path.join(out_dir, "clip_diagnostics.csv"), index=False)

    # oracle comparison (same pilot test samples)
    oracle_rows = []
    for estimator in ESTIMATORS:
        for family in FAMILY_CELL_COLS:
            for mapping in MAPPINGS:
                for variant, lc in (("one_step", "one_step_loss"),
                                    ("terminal", "terminal_loss")):
                    sub = df_all[(df_all["estimator"] == estimator)
                                 & (df_all["family"] == family)
                                 & (df_all["mapping"] == mapping)]
                    pg_j1 = j1_from_loss(sub[lc])
                    oracle_layer = FAMILY_ORACLE[family]
                    default_j1 = oracle_j1["Default"]
                    l2_j1 = oracle_j1["L2"]
                    oracle_layer_j1 = oracle_j1[oracle_layer]
                    oracle_gain = default_j1 - oracle_layer_j1
                    pg_gain = default_j1 - pg_j1
                    rec = {"estimator": estimator, "family": family,
                           "mapping": mapping, "variant": variant,
                           "PG_J1": pg_j1, "default_J1": default_j1,
                           "l2_J1": l2_j1, "oracle_layer": oracle_layer,
                           "oracle_J1": oracle_layer_j1,
                           "oracle_gain": oracle_gain, "pg_gain": pg_gain,
                           "recovery_pct": (pg_gain / oracle_gain * 100.0
                                            if oracle_gain > 0 else math.nan)}
                    for n in N_GRID:
                        rec[f"PG_J1_n{n}"] = j1_from_loss(sub[sub["n"] == n][lc])
                        rec[f"oracle_J1_n{n}"] = oracle_n_j1.get(oracle_layer, {}).get(n, math.nan)
                    oracle_rows.append(rec)
    df_oracle = pd.DataFrame(oracle_rows)
    df_oracle.to_csv(os.path.join(out_dir, "oracle_comparison.csv"), index=False)

    # provisional-parameter bias/error + relationship to selected delta
    prov_rows = []
    for estimator in ESTIMATORS:
        sub = df_all[df_all["estimator"] == estimator]
        beta_err = (sub["est_beta"] - sub["true_beta"]).dropna()
        goe_err = (sub["est_goe"] - sub["true_goe"]).dropna()
        abs_err = (sub["est_beta"] - sub["true_beta"]).abs().dropna()
        sel = sub.loc[abs_err.index, "terminal_delta"]
        prov_rows.append({
            "estimator": estimator,
            "bias_beta": float(beta_err.mean()), "rmse_beta": float(math.sqrt(
                (beta_err ** 2).mean())), "mae_beta": float(beta_err.abs().mean()),
            "bias_goe": float(goe_err.mean()), "rmse_goe": float(math.sqrt(
                (goe_err ** 2).mean())), "mae_goe": float(goe_err.abs().mean()),
            "spearman_abs_beta_err_vs_delta": float(sel.corr(
                abs_err, method="spearman")),
        })
    pd.DataFrame(prov_rows).to_csv(os.path.join(out_dir, "prov_param_diag.csv"),
                                   index=False)

    # provisional-error vs selected delta (stratified) / beta-cell correctness /
    # paired PG-vs-Default bootstrap — see module-level compute_* helpers.
    err_bin_rows = compute_prov_err_bins(df_all)
    pd.DataFrame(err_bin_rows).to_csv(os.path.join(out_dir, "prov_err_vs_delta.csv"),
                                      index=False)
    cell_rows = compute_beta_cell_correctness(df_all)
    pd.DataFrame(cell_rows).to_csv(
        os.path.join(out_dir, "beta_cell_correctness.csv"), index=False)
    boot_rows = compute_paired_bootstrap(df_all)
    pd.DataFrame(boot_rows).to_csv(
        os.path.join(out_dir, "paired_bootstrap.csv"), index=False)

    log("\n[7/7] Alignment, summary, provenance...")
    key_alignment = check_key_alignment(df_all, n_samples)
    PS.atomic_write_json(key_alignment, os.path.join(out_dir, "key_alignment.json"))

    # reference full-design cross-fit layers (context, not same-sample)
    full_layers_path = os.path.join(STUDY_ROOT, "artifacts", "formal",
                                    "E6_dimensional_raw", "specialist",
                                    "crossfit_layers.csv")
    full_design_ref = {}
    if os.path.exists(full_layers_path):
        fl = pd.read_csv(full_layers_path)
        full_design_ref = {str(r["layer"]): float(r["J1"])
                           for _, r in fl.iterrows()}

    git_meta = PS.git_meta()
    summary = {
        "experiment": f"Study/01 {experiment_label(mode)}",
        "mode": mode, "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repeat_max": repeat_max, "n_samples": n_samples,
        "run_start_git": run_start,
        "design_interpretation": (
            "plug-in: cell curves are the L3/L4/L5 training-fold conditional-mean "
            "curves on the true-parameter grid; a sample's provisional estimate "
            "only chooses which curve to query (nearest grid cell or interpolated)"),
        "goe_estimate": "gamma_hat / eta_hat (both estimated); "
                        "alternative gamma_hat / eta_true recorded as open decision",
        "variant_summary": df_summary.to_dict(orient="records"),
        "oracle_comparison": df_oracle.to_dict(orient="records"),
        "state_counts": df_state.to_dict(orient="records"),
        "clip_diagnostics": df_clip.to_dict(orient="records"),
        "provisional_param_diag": prov_rows,
        "beta_cell_correctness": pd.DataFrame(cell_rows).to_dict(orient="records"),
        "paired_bootstrap": pd.DataFrame(boot_rows).to_dict(orient="records"),
        "oracle_pilot_j1": oracle_j1,
        "full_design_crossfit_reference": full_design_ref,
        "wmle": {"n_estimates": n_samples, "n_invalid_fallback": n_wmle_fail,
                 "note": ("B2 estimation.csv absent on disk; WMLE recomputed with "
                          "the B2 frozen worker (production wmle.py)")},
        "failure_penalty": float(penalty),
        **git_meta,
    }
    PS.atomic_write_json(summary, os.path.join(out_dir, "summary.json"))

    # bind the actual WMLE worker and the reused sealed scan source
    wmle_worker_path = os.path.join(STUDY_CODE_DIR, "run_b2_traditional_ref.py")
    wmle_prod_path = os.path.join(PYTHON_DIR, "methods", "wmle.py")
    scan_manifest_path = CFG.MC_MANIFEST_PATH
    scan_sums_path = os.path.join(CFG.SHARED_DATA_DIR, "data_sha256sums.txt")
    manifest = {
        "contract_version": CONTRACT_VERSION,
        "mode": mode, "experiment": experiment_label(mode),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_start_git": run_start,
        "code_entry": "code/run_pg_selector.py",
        "code_sha256": PS.code_sha256(sys.modules[__name__], CFG, CROSSFIT,
                                      E6, PS),
        "wmle_worker_sha256": {
            os.path.basename(wmle_worker_path):
                PS.sha256_file_lf(wmle_worker_path)},
        "wmle_prod_sha256": {
            os.path.basename(wmle_prod_path):
                PS.sha256_file_lf(wmle_prod_path)},
        "design": {
            "split": "repeat_id mod 5 cross-fit; curves from training folds only",
            "families": FAMILY_CELL_COLS,
            "oracle_ref": FAMILY_ORACLE,
            "initial_estimators": ESTIMATORS,
            "mappings": MAPPINGS,
            "max_updates": MAX_UPDATES,
            "stop_rules": ["delta unchanged (fixed point / stable)",
                           "cycle (previously-seen delta reappears)",
                           "10 updates reached", "invalid initial estimate -> delta=0.1"],
            "cycle_handling": "never averaged; convergence never forced",
            "clip_rule": "clip only outside training support; every event recorded",
            "interpolate": "loss curves, never selected delta values",
            "J1": "sqrt(mean_i(L_i)), three-parameter loss, NO /3",
            "primary": "one-step selection; terminal iteration is a diagnostic "
                       "of feedback deterioration (frozen Phase B decision)",
        },
        "data_source": {
            "reused": "artifacts/formal/E5_normalized_raw/shared_data/ "
                      "(160-combo new design; repeats < repeat_max)",
            "scan_manifest": {
                "path": scan_manifest_path,
                "sha256": PS.sha256_file_lf(scan_manifest_path)},
            "scan_data_checksums": {
                "path": scan_sums_path,
                "sha256": PS.sha256_file_lf(scan_sums_path)},
            "wmle_cache_note": ("B2 artifacts/formal/E6_dimensional_raw/"
                                "traditional_ref/estimation.csv absent on disk; "
                                "genuinely insufficient -> WMLE recomputed with "
                                "the frozen B2 worker (production wmle.py)"),
        },
        "output_files": [
            "summary.json", "manifest.json", "run_log.txt",
            "variant_summary.csv", "oracle_comparison.csv", "state_counts.csv",
            "clip_diagnostics.csv", "prov_param_diag.csv",
            "prov_err_vs_delta.csv", "beta_cell_correctness.csv",
            "paired_bootstrap.csv", "key_alignment.json",
            f"{output_filenames()['results']} (gitignored)",
            f"{output_filenames()['wmle']} (gitignored)",
            "SHA256SUMS", "SHA256SUMS.local_not_in_git",
        ],
        "phase_boundary": phase_boundary(mode),
        **git_meta,
    }
    PS.atomic_write_json(manifest, os.path.join(out_dir, "manifest.json"))

    with open(os.path.join(out_dir, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(f"{output_filenames()['results']}\n{output_filenames()['wmle']}\n")
    for p in (os.path.join(out_dir, "summary.json"),
              os.path.join(out_dir, "manifest.json"),
              os.path.join(out_dir, "variant_summary.csv"),
              os.path.join(out_dir, "oracle_comparison.csv"),
              os.path.join(out_dir, "state_counts.csv"),
              os.path.join(out_dir, "clip_diagnostics.csv"),
              os.path.join(out_dir, "prov_param_diag.csv"),
              os.path.join(out_dir, "prov_err_vs_delta.csv"),
              os.path.join(out_dir, "beta_cell_correctness.csv"),
              os.path.join(out_dir, "paired_bootstrap.csv"),
              os.path.join(out_dir, "key_alignment.json")):
        PS.lf_normalize(p)

    with open(os.path.join(out_dir, "run_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(buf))
    n_tracked, n_local = PS.write_sha256sums(out_dir)
    log(f"  Provenance: SHA256SUMS tracked={n_tracked} "
        f"local_not_in_git={n_local}")
    elapsed = time.time() - t_start
    log(f"\nDone in {elapsed:.1f}s. Outputs in {out_dir}")
    return summary, manifest


def compute_wmle(sample_keys, workers=8, force_rerun=False):
    """WMLE estimates with the B2 frozen worker (same sample keys).

    Cache path is the generic `wmle_estimates.csv` (mode-independent; verified
    against the exact requested sample-key set before reuse).
    """
    from run_b2_traditional_ref import _estimate_one
    est_path = os.path.join(OUT_DIR, output_filenames()["wmle"])
    if os.path.exists(est_path) and not force_rerun:
        df = pd.read_csv(est_path)
        got = set(map(tuple, df[SAMPLE_KEYS].values))
        want = set(map(tuple, sample_keys[SAMPLE_KEYS].values))
        if got == want and len(df) == len(sample_keys):
            print(f"  [wmle] loaded existing {len(df)} estimates from disk")
            return df
        print(f"  [wmle] cached file mismatch (got {len(got)}, want {len(want)}); "
              f"recomputing")
    tasks = [(row, "WMLE") for _, row in sample_keys.iterrows()]
    t0 = time.time()
    with Pool(processes=workers) as pool:
        results = pool.map(_estimate_one, tasks, chunksize=256)
    df = pd.DataFrame(results)
    df.to_csv(est_path, index=False)
    print(f"  [wmle] computed {len(df)} estimates in {time.time() - t0:.1f}s "
          f"(workers={workers})")
    return df


def check_key_alignment(df_all, n_samples):
    """Exact sample-key multiplicity and same-sample alignment."""
    n_variants = len(ESTIMATORS) * len(FAMILY_CELL_COLS) * len(MAPPINGS)
    expected = n_samples * n_variants
    dup = int(df_all.duplicated(subset=SAMPLE_KEYS + ["estimator", "family",
                                                      "mapping"]).sum())
    missing = 0
    for _, g in df_all.groupby(["estimator", "family", "mapping"]):
        if len(g) != n_samples:
            missing += 1
    return {
        "n_samples": int(n_samples), "n_variants": n_variants,
        "n_result_rows": int(len(df_all)),
        "expected_rows": int(expected),
        "duplicate_rows": dup,
        "variant_groups_with_wrong_count": missing,
        "same_sample_alignment": (
            "terminal/one-step loss read from the cached MDM estimate of the "
            "same sample key; fallback uses delta=0.1 for that same sample"),
        "alignment_ok": dup == 0 and missing == 0 and len(df_all) == expected,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true",
                    help="Phase B: full 48,000-sample run")
    ap.add_argument("--pilot-repeats", type=int, default=PILOT_REPEATS)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force-rerun", action="store_true")
    args = ap.parse_args()
    repeats = CFG.REPEATS if args.full else args.pilot_repeats
    mode = "full" if args.full else "pilot"
    run_experiment(repeat_max=repeats, workers=args.workers,
                   force_rerun=args.force_rerun, mode=mode)
