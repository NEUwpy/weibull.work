"""Analysis entry point for the incremental B run.

Reads frozen row-level outputs (core/grid results.csv + per-seed npz) and
produces:
- dense-n core: per-n P/D/Dctrl bias/dispersion/RMSE, I(n) with hierarchical
  paired-seed cluster bootstrap CI, BH-adjusted per-n support, beta-stratified
  I, normalized seed spread, P parameter counterfactuals (C2-2 extension).
- parameter grid: per-cell I with bootstrap CI, beta/rho marginals, and a
  variance decomposition separating between-region mixing from within-cell
  Monte Carlo noise.

Rerunning on the same artifacts reproduces the summaries deterministically.

Usage:
    python -m study02b_inc.analyze_inc --run-dir <dir> [--out <dir>] [--bootstrap N]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

from studies.common.metrics import quantile_true

from study02b_inc import config as C

R95 = 0.95
ROUTES = ["P", "D", "Dctrl"]


def _f(x) -> float:
    """CSV cell -> float (empty string means non-finite)."""
    if x == "" or x is None:
        return float("nan")
    return float(x)


def _rmse(errs: np.ndarray) -> float:
    arr = np.asarray(errs, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.sqrt(np.mean(arr ** 2))) if arr.size else float("nan")


def _bias(errs: np.ndarray) -> float:
    arr = np.asarray(errs, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.mean(arr)) if arr.size else float("nan")


def _sd(errs: np.ndarray) -> float:
    arr = np.asarray(errs, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.std(arr, ddof=1)) if arr.size > 1 else float("nan")


def _q(pct: float, values) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.percentile(arr, pct)) if arr.size else float("nan")


def _spearman(x, y) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 3:
        return float("nan")
    rho, _ = spearmanr(x[m], y[m])
    return float(rho)


def _git_tip() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                       cwd=str(C.REPO_ROOT), timeout=5)
    return r.stdout.strip() or "unknown"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_core(run_dir: Path) -> tuple[list[dict], dict]:
    rows = load_csv(run_dir / "eval" / "core_results.csv")
    npz = np.load(run_dir / "eval" / "core_per_seed.npz", allow_pickle=True)
    return rows, {
        "keys": npz["keys"], "p": npz["p_seeds"], "d": npz["d_seeds"],
        "dc": npz["dctrl_seeds"],
    }


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _core_metrics(rows: list[dict], n_values: list[int], npz: dict) -> dict:
    """Per-n bias/SD/RMSE/q90 + I for P/D/Dctrl, plus beta stratification."""
    key_to_idx = {str(k): i for i, k in enumerate(npz["keys"])}
    per_n = {}
    for n in n_values:
        nrows = [r for r in rows if int(r["n"]) == n]
        p_err = np.array([_f(r["P_rel_err"]) for r in nrows], dtype=float)
        d_err = np.array([_f(r["D_rel_err"]) for r in nrows], dtype=float)
        dc_err = np.array([_f(r["Dctrl_rel_err"]) for r in nrows], dtype=float)

        # cluster-level RMSE D-better + cluster I
        clusters = sorted({int(r["cluster"]) for r in nrows})
        cl_p, cl_d = {}, {}
        for c in clusters:
            cp = np.array([_f(r["P_rel_err"]) for r in nrows if int(r["cluster"]) == c])
            cd = np.array([_f(r["D_rel_err"]) for r in nrows if int(r["cluster"]) == c])
            cl_p[c] = _rmse(cp)
            cl_d[c] = _rmse(cd)
        c_rmse_d_better = sum(1 for c in clusters if cl_d[c] < cl_p[c])
        cl_i = np.array([(cl_p[c] - cl_d[c]) / cl_p[c] if cl_p[c] > 0 else np.nan
                         for c in clusters])
        cl_i = cl_i[np.isfinite(cl_i)]

        # beta stratification (quartile bins)
        betas = np.array([float(r["beta"]) for r in nrows])
        bins = np.quantile(betas, [0.25, 0.5, 0.75])
        beta_bins = {}
        for bi in range(4):
            lo = -np.inf if bi == 0 else bins[bi - 1]
            hi = np.inf if bi == 3 else bins[bi]
            sel = (betas >= lo) & (betas < hi)
            if sel.sum() == 0:
                continue
            pb, db = p_err[sel], d_err[sel]
            pr, dr = _rmse(pb), _rmse(db)
            beta_bins[str(bi)] = {
                "beta_range": [float(lo) if np.isfinite(lo) else None,
                               float(hi) if np.isfinite(hi) else None],
                "n_rows": int(sel.sum()),
                "P_rmse": pr, "D_rmse": dr,
                "I": (pr - dr) / pr if pr > 0 else np.nan,
            }

        # normalized seed spread (SD/true) vs |err|
        ns_p, ns_d, abs_p, abs_d = [], [], [], []
        for r in nrows:
            idx = key_to_idx[f"{r['row_idx']}"]
            xt = float(r["true_x095"])
            if xt > 0:
                ap = npz["p"][idx]; ad = npz["d"][idx]
                if np.isfinite(ap).sum() >= 2:
                    ns_p.append(float(np.std(ap[np.isfinite(ap)])) / xt)
                    abs_p.append(abs(_f(r["P_rel_err"])))
                if np.isfinite(ad).sum() >= 2:
                    ns_d.append(float(np.std(ad[np.isfinite(ad)])) / xt)
                    abs_d.append(abs(_f(r["D_rel_err"])))

        def _stat(err, pref):
            return {
                f"{pref}_bias": _bias(err), f"{pref}_sd": _sd(err),
                f"{pref}_rmse": _rmse(err), f"{pref}_q90": _q(90, np.abs(err)),
                f"{pref}_q99": _q(99, np.abs(err)),
            }

        d_better_paired = float(np.mean(np.abs(d_err) < np.abs(p_err)))
        i_point = ( _rmse(p_err) - _rmse(d_err)) / _rmse(p_err) if _rmse(p_err) > 0 else np.nan
        per_n[str(n)] = {
            "n_rows": len(nrows),
            **_stat(p_err, "P"), **_stat(d_err, "D"), **_stat(dc_err, "Dctrl"),
            "paired_D_better": d_better_paired,
            "cluster_rmse_D_better": int(c_rmse_d_better),
            "cluster_I_median": float(np.median(cl_i)) if cl_i.size else np.nan,
            "cluster_I_q25": _q(25, cl_i), "cluster_I_q75": _q(75, cl_i),
            "I": i_point,
            "seed_spread": {
                "P_norm_mean": float(np.mean(ns_p)) if ns_p else np.nan,
                "D_norm_mean": float(np.mean(ns_d)) if ns_d else np.nan,
                "P_spread_err_spearman": _spearman(ns_p, abs_p),
                "D_spread_err_spearman": _spearman(ns_d, abs_d),
            },
            "beta_stratification": beta_bins,
        }
    return per_n


def _row_index(rows):
    return {(int(r["cluster"]), int(r["replicate"]), int(r["n"])): r for r in rows}


def analyze_core(run_dir: Path, n_boot: int, out: Path) -> dict:
    print("=== Core analysis ===")
    rows, npz = _load_core(run_dir)
    # Attach row_idx into the CSV rows (they are positional).
    for i, r in enumerate(rows):
        r["row_idx"] = i

    per_n = _core_metrics(rows, C.N_VALUES, npz)

    # Point I per n and pooled (equal-per-n)
    rng = np.random.default_rng(C.BOOTSTRAP_SEED)
    per_n_boot = {}
    p_vals_n = {}
    row_by_key = _row_index(rows)
    key_to_idx = {str(k): i for i, k in enumerate(npz["keys"])}
    for n in C.N_VALUES:
        boot_i = []
        ci_all = list(range(C.CORE_N_CLUSTERS))
        for _ in range(n_boot):
            ci_b = list(rng.choice(ci_all, size=len(ci_all), replace=True))
            # PAIRED positional seed-index resample for P and D (approved B4 contract).
            seed_idx = rng.choice(len(C.P_FIT_SEEDS), size=len(C.P_FIT_SEEDS), replace=True)
            de, pe = [], []
            for ci in ci_b:
                for ri in range(C.CORE_N_REPLICATES):
                    r = row_by_key.get((ci, ri, n))
                    if r is None:
                        continue
                    idx = key_to_idx[f"{r['row_idx']}"]
                    xt = float(r["true_x095"])
                    if xt == 0:
                        continue
                    dv = npz["d"][idx]; pv = npz["p"][idx]
                    dm = float(np.nanmean(dv[seed_idx[:len(dv)]]))
                    pm = float(np.nanmean(pv[seed_idx[:len(pv)]]))
                    if np.isfinite(dm):
                        de.append((dm - xt) / xt)
                    if np.isfinite(pm):
                        pe.append((pm - xt) / xt)
            dr, pr = _rmse(de), _rmse(pe)
            if pr > 0:
                boot_i.append((pr - dr) / pr)
        boot_i = np.array(boot_i)
        lo = float(np.percentile(boot_i, 2.5)); hi = float(np.percentile(boot_i, 97.5))
        per_n_boot[str(n)] = {
            "I": per_n[str(n)]["I"], "ci_lo": lo, "ci_hi": hi,
            "direction": "D better" if lo > 0 else ("P better" if hi < 0 else "no difference"),
        }
        p_vals_n[n] = 2.0 * min(float(np.mean(boot_i <= 0)), float(np.mean(boot_i >= 0)))

    # Standard BH across the n comparisons: find the largest rank i with
    # p(i) <= alpha*i/m and reject all hypotheses up to i.
    sorted_n = sorted(p_vals_n, key=lambda n: p_vals_n[n])
    m = len(sorted_n)
    alpha = 0.05
    largest_reject = 0
    for rank, n in enumerate(sorted_n, 1):
        if p_vals_n[n] <= alpha * rank / m:
            largest_reject = rank
    bh = {str(n): ("supported" if rank <= largest_reject else "not_supported")
          for rank, n in enumerate(sorted_n, 1)}
    for n in sorted_n:
        per_n_boot[str(n)]["bh"] = bh[str(n)]

    # pooled equal-per-n point estimate
    p_eq = float(np.mean([per_n[str(n)]["P_rmse"] for n in C.N_VALUES]))
    d_eq = float(np.mean([per_n[str(n)]["D_rmse"] for n in C.N_VALUES]))
    i_eq = (p_eq - d_eq) / p_eq if p_eq > 0 else np.nan

    return {
        "per_n": per_n_boot,
        "per_n_detail": per_n,
        "pooled_equal_per_n": {"P_rmse": p_eq, "D_rmse": d_eq, "I": i_eq},
        "n_values": C.N_VALUES,
        "bh_adjustment": {"method": "Benjamini-Hochberg", "alpha": 0.05, "m": m,
                          "p_values": {str(k): float(v) for k, v in p_vals_n.items()}},
    }


# ---------------------------------------------------------------------------
# Parameter-grid analysis
# ---------------------------------------------------------------------------

def analyze_grid(run_dir: Path, n_boot: int, out: Path) -> dict:
    print("=== Parameter grid analysis ===")
    rows = load_csv(run_dir / "eval" / "grid_results.csv")
    npz = np.load(run_dir / "eval" / "grid_per_seed.npz", allow_pickle=True)
    npz = {"keys": npz["keys"], "p": npz["p_seeds"], "d": npz["d_seeds"],
           "dc": npz["dctrl_seeds"]}
    key_to_idx = {str(k): i for i, k in enumerate(npz["keys"])}
    cell_map = {c.cell_index: c for c in C_GRID_CELLS()}

    # Aggregate per cell: per-draw, per-seed predictions.
    from collections import defaultdict
    cells = defaultdict(list)
    for r in rows:
        cells[int(r["cell"])].append(r)
    rng = np.random.default_rng(C.BOOTSTRAP_SEED)
    n_seeds = len(C.P_FIT_SEEDS)

    # Per-cell arrays: P_pred (n_draws, n_seeds), D_pred, true_x095.
    def _cell_arrays(cidx):
        crows = sorted(cells[cidx], key=lambda r: int(r["draw"]))
        n_draws = len(crows)
        P = np.full((n_draws, n_seeds), np.nan)
        Dp = np.full((n_draws, n_seeds), np.nan)
        xt = np.zeros(n_draws)
        for j, r in enumerate(crows):
            idx = key_to_idx[f"{r['row_idx']}"]
            P[j] = npz["p"][idx]
            Dp[j] = npz["d"][idx]
            xt[j] = float(r["true_x095"])
        return P, Dp, xt

    main_cells = [c for c in cell_map.values() if c.eta == C.PG_ETA and c.cell_index in cells]
    cell_arrays = {c.cell_index: _cell_arrays(c.cell_index) for c in main_cells}

    # Point estimates (full 360 draws, full 10-seed means).
    per_cell = {}
    for cidx, (P, Dp, xt) in cell_arrays.items():
        with np.errstate(divide="ignore", invalid="ignore"):
            pe = np.where(xt != 0, (np.nanmean(P, axis=1) - xt) / xt, np.nan)
            de = np.where(xt != 0, (np.nanmean(Dp, axis=1) - xt) / xt, np.nan)
        pr = float(np.sqrt(np.nanmean(pe ** 2)))
        dr = float(np.sqrt(np.nanmean(de ** 2)))
        per_cell[str(cidx)] = {
            "beta": cell_map[cidx].beta, "rho": cell_map[cidx].rho,
            "eta": cell_map[cidx].eta, "n": cell_map[cidx].n,
            "n_draws": int(len(pe)), "P_rmse": pr, "D_rmse": dr,
            "I": (pr - dr) / pr if pr > 0 else np.nan,
        }

    # Paired bootstrap CI: ONE draw-id multiset + ONE paired seed-id multiset
    # applied to all cells (preserves common-random-number structure and the
    # approved B paired-seed contract).
    boot_store = {cid: [] for cid in cell_arrays}
    n_draws = max(a[0].shape[0] for a in cell_arrays.values())
    for _ in range(n_boot):
        draw_idxs = rng.integers(0, n_draws, size=(n_draws,))
        seed_idxs = rng.integers(0, n_seeds, size=(n_seeds,))
        for cid, (P, Dp, xt) in cell_arrays.items():
            Pm = P[draw_idxs][:, seed_idxs].mean(axis=1)
            Dm = Dp[draw_idxs][:, seed_idxs].mean(axis=1)
            xtb = xt[draw_idxs]
            with np.errstate(divide="ignore", invalid="ignore"):
                pe = np.where(xtb != 0, (Pm - xtb) / xtb, np.nan)
                de = np.where(xtb != 0, (Dm - xtb) / xtb, np.nan)
            pr = float(np.sqrt(np.nanmean(pe ** 2)))
            dr = float(np.sqrt(np.nanmean(de ** 2)))
            if np.isfinite(pr) and pr > 0:
                boot_store[cid].append((pr - dr) / pr)
    for cid, vals in boot_store.items():
        vals = np.array(vals)
        per_cell[str(cid)]["ci_lo"] = float(np.percentile(vals, 2.5)) if len(vals) else np.nan
        per_cell[str(cid)]["ci_hi"] = float(np.percentile(vals, 97.5)) if len(vals) else np.nan

    # Stratum-pooled marginals (R2): pool row-level relative errors within the
    # stratum, then RMSE and I. Never average cell-level I ratios.
    def _stratum_pooled(pred_err_key, n, eta, over_key, over_val):
        sub = [r for r in rows if int(r["n"]) == n and abs(float(r["eta"]) - eta) < 1e-9
               and (over_key is None or abs(float(r[over_key]) - over_val) < 1e-9)]
        if not sub:
            return np.nan
        pr = _rmse(np.array([_f(r["P_rel_err"]) for r in sub]))
        dr = _rmse(np.array([_f(r["D_rel_err"]) for r in sub]))
        return (pr - dr) / pr if pr > 0 else np.nan

    n_marginal_beta = {}
    n_marginal_rho = {}
    for n in C.PG_N:
        n_marginal_beta[str(n)] = {
            str(float(b)): _stratum_pooled("P_rel_err", n, C.PG_ETA, "beta", float(b))
            for b in C.PG_BETA}
        n_marginal_rho[str(n)] = {
            str(float(rh)): _stratum_pooled("P_rel_err", n, C.PG_ETA, "rho", float(rh))
            for rh in C.PG_RHO}

    # Descriptive heterogeneity signal (R3): between-cell spread of cell I vs
    # mean within-cell SE. NOT a formal variance decomposition; does not
    # "prove" cancellation. Reported as a descriptive signal only.
    variance_decomp = {}
    for n in C.PG_N:
        cell_vals = [v for v in per_cell.values()
                     if v["n"] == n and v["eta"] == C.PG_ETA]
        i_arr = np.array([v["I"] for v in cell_vals])
        se_arr = np.array([(v["ci_hi"] - v["ci_lo"]) / 3.92 for v in cell_vals])
        fin_i = i_arr[np.isfinite(i_arr)]
        fin_se = se_arr[np.isfinite(se_arr)]
        between_var = float(np.var(fin_i)) if fin_i.size > 1 else np.nan
        within_mean_var = float(np.mean(fin_se ** 2)) if fin_se.size else np.nan
        variance_decomp[str(n)] = {
            "n_cells": len(cell_vals),
            "between_cell_var": between_var,
            "within_cell_mean_var": within_mean_var,
            "ratio_between_over_within": (between_var / within_mean_var)
                if within_mean_var and within_mean_var > 0 else np.nan,
            "note": "descriptive signal only, not a formal variance decomposition",
        }

    return {
        "per_cell": per_cell,
        "n_marginal_beta": n_marginal_beta,
        "n_marginal_rho": n_marginal_rho,
        "variance_decomposition": variance_decomp,
        "bootstrap_note": "paired draw-id + paired seed-index resample, CRN preserved",
    }


def C_GRID_CELLS():
    from study02b_inc import data as D
    return D.param_grid_cells()


# ---------------------------------------------------------------------------
# P parameter propagation (C2-2 extension as a function of n)
# ---------------------------------------------------------------------------

def analyze_propagation(run_dir: Path, out: Path) -> dict:
    """Re-infer P per-seed params on the core and compute counterfactuals."""
    import torch
    from study02a.models import build_mlp, decode_model_output
    from study02a.representations import anchor_sample
    from study02a.training import load_checkpoint
    from study02b_inc import models as M

    print("=== P parameter propagation analysis ===")
    rows = load_csv(run_dir / "eval" / "core_results.csv")
    p_index = M.build_p_index(run_dir)
    n_boot = C.N_BOOTSTRAP

    p_scalers = M.p_scalers(run_dir)
    per_n = {}
    for n in C.N_VALUES:
        # load models for this n once
        mods = []
        for e in p_index.get(n, []):
            m = build_mlp(n, C.P_WIDTHS, C.ACTIVATION, C.DROPOUT)
            m.load_state_dict(load_checkpoint(Path(e["path"]).read_bytes()))
            m.eval()
            mods.append(m)
        if not mods:
            continue
        sc = p_scalers.get(n, {"mean": None, "sd": None})
        rows_n = [r for r in rows if int(r["n"]) == n]
        rbs, res, rgs, rcs, jr = [], [], [], [], []
        n_used = 0
        for r in rows_n:
            b, e, g = float(r["beta"]), float(r["eta"]), float(r["gamma"])
            xt = quantile_true(b, e, g, R95)
            if xt <= 0:
                continue
            a = anchor_sample(_regen_sample(r))
            zraw = a.z.astype(np.float32)
            if sc.get("mean") is not None and len(sc["mean"]) == zraw.shape[0]:
                mean = np.array(sc["mean"], dtype=np.float32)
                sd = np.array(sc["sd"], dtype=np.float32)
                safe = np.where(sd != 0, sd, 1.0)
                zraw = np.where(sd != 0, (zraw - mean) / safe, 0.0)
            z = torch.from_numpy(zraw).unsqueeze(0)
            seed_vals = []
            with torch.no_grad():
                for m in mods:
                    raw = m(z)
                    dec = decode_model_output(raw, torch.tensor([a.location]),
                                              torch.tensor([a.scale]))
                    bs, es, gs = float(dec[0, 0]), float(dec[0, 1]), float(dec[0, 2])
                    if bs > 0 and es > 0 and np.isfinite([bs, es, gs]).all():
                        seed_vals.append(_contributions(bs, es, gs, b, e, g, xt))
            if seed_vals:
                mean = {k: float(np.mean([sv[k] for sv in seed_vals])) for k in seed_vals[0]}
                rbs.append(mean["rb"]); res.append(mean["re"]); rgs.append(mean["rg"])
                rcs.append(mean["rc"]); jr.append(mean["jr"])
                n_used += 1
        per_n[str(n)] = {
            "n_rows": n_used,
            "rel_mean_signed": {"beta": float(np.mean(rbs)) if rbs else np.nan,
                                "eta": float(np.mean(res)) if res else np.nan,
                                "gamma": float(np.mean(rgs)) if rgs else np.nan,
                                "combined": float(np.mean(rcs)) if rcs else np.nan},
            "rel_mean_abs": {"beta": float(np.mean(np.abs(rbs))) if rbs else np.nan,
                             "eta": float(np.mean(np.abs(res))) if res else np.nan,
                             "gamma": float(np.mean(np.abs(rgs))) if rgs else np.nan,
                             "combined": float(np.mean(np.abs(rcs))) if rcs else np.nan},
            "nonadditivity_abs": float(np.mean(np.abs(np.array(rcs) - (np.array(rbs) + np.array(res) + np.array(rgs))))) if rbs else np.nan,
            "jac_resid_abs": float(np.mean(np.abs(jr))) if jr else np.nan,
        }
    return {"per_n": per_n}


def _regen_sample(r):
    """Regenerate the core sample for a row (deterministic from stored fields)."""
    from studies.common.sample import generate_sample
    return generate_sample(float(r["beta"]), float(r["eta"]), float(r["gamma"]),
                           int(r["n"]), int(r["replicate"]), seed=C.CORE_SAMPLE_NS + int(r["cluster"]))


def _contributions(bs, es, gs, b, e, g, xt):
    L = -math.log(R95)
    Lb = L ** (1.0 / b)
    db = e * Lb * math.log(L) * (-1.0 / (b * b))
    de = Lb
    dg = 1.0
    d_beta = quantile_true(bs, e, g, R95) - xt
    d_eta = quantile_true(b, es, g, R95) - xt
    d_gamma = quantile_true(b, e, gs, R95) - xt
    d_comb = quantile_true(bs, es, gs, R95) - xt
    jac = db * (bs - b) + de * (es - e) + dg * (gs - g)
    return {
        "rb": d_beta / xt, "re": d_eta / xt, "rg": d_gamma / xt,
        "rc": d_comb / xt, "jr": (d_comb - jac) / xt,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_BLOCK_FILES = {"core": "core_summary.json", "grid": "grid_summary.json",
                "propagation": "propagation_summary.json"}


def run_analyze(run_dir: Path, out: Path | None = None, n_boot: int | None = None,
                blocks: list[str] | None = None) -> dict:
    run_dir = Path(run_dir)
    out = out or (run_dir / "analysis")
    out.mkdir(parents=True, exist_ok=True)
    n_boot = n_boot or C.N_BOOTSTRAP
    blocks = blocks or ["core", "grid", "propagation"]

    result = {"run_id": run_dir.name, "code_tip": _git_tip(),
              "config_hash": C.CONFIG_HASH,
              "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "n_bootstrap": n_boot}
    for block in blocks:
        blk_file = out / _BLOCK_FILES[block]
        if blk_file.exists():
            cached = json.loads(blk_file.read_text(encoding="utf-8"))
            if cached.get("config_hash") == C.CONFIG_HASH and \
               cached.get("n_bootstrap") == n_boot:
                result[block] = cached
                print(f"[{block}] using cached result")
                continue
        if block == "core":
            val = analyze_core(run_dir, n_boot, out)
        elif block == "grid":
            val = analyze_grid(run_dir, n_boot, out)
        else:
            val = analyze_propagation(run_dir, out)
        val["config_hash"] = C.CONFIG_HASH
        val["n_bootstrap"] = n_boot
        result[block] = val
        blk_file.write_text(json.dumps(val, indent=2, ensure_ascii=False), encoding="utf-8")

    mf = out / "analysis_summary.json"
    mf.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Analysis summary: {mf}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--bootstrap", type=int, default=None)
    ap.add_argument("--blocks", nargs="*", default=None)
    args = ap.parse_args()
    run_analyze(Path(args.run_dir), Path(args.out) if args.out else None,
                n_boot=args.bootstrap, blocks=args.blocks)


if __name__ == "__main__":
    main()
