"""C2 mechanism analyses on existing B evidence (C2-1/C2-2/C2-3).

All inputs come from B4 results.csv + per-seed NPZ + re-inferred P
parameters (data.py). No new training, no new test data. Everything is
deterministic. Output shapes are JSON-serializable summaries.

Statistical conventions (post-review):
- Cluster D-better is defined as cluster-level RMSE(D) < cluster-level RMSE(P),
  with the "majority of rows" variant kept only as a supplementary metric.
- Seed disagreement is a *normalized* spread (ensemble SD / true_x095),
  reported for P and D with a true Spearman correlation vs |rel err|.
- Parameter->x0.95 counterfactual contributions are reported primarily in
  relative-to-target terms (contribution / true_x095), ensembled across the
  10 seeds within each row before aggregating across rows.
"""

from __future__ import annotations

import math
import sys
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

N_VALUES = [5, 7, 10, 15, 20]
R95 = 0.95


def _rmse(errs: np.ndarray) -> float:
    arr = np.asarray(errs, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.sqrt(np.mean(arr ** 2))) if arr.size else float("nan")


def _q(percent: float, values) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.percentile(arr, percent)) if arr.size else float("nan")


def _spearman(x, y) -> float:
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return float("nan")
    rho, _ = spearmanr(x[mask], y[mask])
    return float(rho)


# --------------------------------------------------------------------------- C2-1

def c2_1_n_heterogeneity(rows: list[dict], npz: dict) -> dict:
    """Per-n P/D signed bias, dispersion, RMSE, q90 tail, paired D-better,
    cluster-RMSE D-better, normalized seed spread vs error, beta stratification."""
    keys = list(npz["keys"])
    p_seeds = npz["p_seeds"]; d_seeds = npz["d_seeds"]
    key_to_idx = {k: i for i, k in enumerate(keys)}
    row_by_key = {f"{r['cluster']}_{r['replicate']}_{r['n']}": r for r in rows}

    per_n = {}
    for n in N_VALUES:
        nrows = [r for r in rows if r["n"] == n]
        p_err = np.array([r["P_rel_err"] for r in nrows])
        d_err = np.array([r["D_rel_err"] for r in nrows])
        abs_p = np.abs(p_err); abs_d = np.abs(d_err)

        # paired D-better (row-level absolute error)
        d_better_paired = float(np.mean(abs_d < abs_p))

        # cluster-level: RMSE per cluster (rows per cluster per n = 20)
        clusters = sorted(set(r["cluster"] for r in nrows))
        cluster_p_rmse = {}; cluster_d_rmse = {}
        for c in clusters:
            crows = [r for r in nrows if r["cluster"] == c]
            cp = np.array([r["P_rel_err"] for r in crows])
            cd = np.array([r["D_rel_err"] for r in crows])
            cluster_p_rmse[c] = _rmse(cp)
            cluster_d_rmse[c] = _rmse(cd)
        c_d_better_rmse = sum(1 for c in clusters if cluster_d_rmse[c] < cluster_p_rmse[c])
        # cluster-level I = (P_rmse - D_rmse)/P_rmse
        cluster_i = np.array([(cluster_p_rmse[c] - cluster_d_rmse[c]) / cluster_p_rmse[c]
                              if cluster_p_rmse[c] > 0 else float("nan") for c in clusters])
        cluster_i = cluster_i[np.isfinite(cluster_i)]
        # majority-of-rows variant (supplementary, renamed)
        c_counts = {}
        for c in clusters:
            crows = [r for r in nrows if r["cluster"] == c]
            c_counts[c] = sum(1 for r in crows if abs(r["D_rel_err"]) < abs(r["P_rel_err"]))
        counts = np.array(list(c_counts.values()))

        # normalized seed spread (SD/true_x095) for P and D + Spearman vs |rel err|
        ns_p, ns_d = [], []
        for r in nrows:
            idx = key_to_idx[f"{r['cluster']}_{r['replicate']}_{r['n']}"]
            arr_p = p_seeds[idx]; arr_d = d_seeds[idx]
            xt = r["true_x095"]
            if xt > 0:
                if np.isfinite(arr_p).sum() >= 2:
                    ns_p.append(float(np.std(arr_p[np.isfinite(arr_p)])) / xt)
                if np.isfinite(arr_d).sum() >= 2:
                    ns_d.append(float(np.std(arr_d[np.isfinite(arr_d)])) / xt)
        rho_p = _spearman(ns_p, np.abs(p_err))
        rho_d = _spearman(ns_d, np.abs(d_err))

        # beta stratification: 4 bins
        betas = np.array([r["beta"] for r in nrows])
        bins = np.quantile(betas, [0.25, 0.5, 0.75])
        beta_bins = {}
        for bi in range(4):
            lo = -np.inf if bi == 0 else bins[bi - 1]
            hi = np.inf if bi == 3 else bins[bi]
            sel = (betas >= lo) & (betas < hi)
            if sel.sum() == 0:
                continue
            p_b = p_err[sel]; d_b = d_err[sel]
            pr = _rmse(p_b); dr = _rmse(d_b)
            beta_bins[str(bi)] = {
                "beta_range": [float(lo) if np.isfinite(lo) else None,
                               float(hi) if np.isfinite(hi) else None],
                "n_rows": int(sel.sum()),
                "P_rmse": pr, "D_rmse": dr,
                "I": (pr - dr) / pr if pr > 0 else float("nan"),
            }

        per_n[str(n)] = {
            "n_rows": len(nrows),
            "P": {
                "signed_rel_bias": float(np.mean(p_err)),
                "dispersion_sd": float(np.std(p_err, ddof=1)),
                "rmse": _rmse(p_err),
                "abs_tail_q90": _q(90, abs_p),
                "abs_tail_q99": _q(99, abs_p),
            },
            "D": {
                "signed_rel_bias": float(np.mean(d_err)),
                "dispersion_sd": float(np.std(d_err, ddof=1)),
                "rmse": _rmse(d_err),
                "abs_tail_q90": _q(90, abs_d),
                "abs_tail_q99": _q(99, abs_d),
            },
            "paired_D_better_proportion": d_better_paired,
            "clusters": {
                "n_clusters": len(clusters),
                "n_clusters_rmse_D_better": int(c_d_better_rmse),   # primary: cluster RMSE(D)<RMSE(P)
                "cluster_I_median": float(np.median(cluster_i)) if cluster_i.size else float("nan"),
                "cluster_I_q25": _q(25, cluster_i),
                "cluster_I_q75": _q(75, cluster_i),
                "majority_rows_D_better": int(np.sum(counts > 10)),  # supplementary only
            },
            "seed_spread": {
                "P_normalized_spread_mean": float(np.mean(ns_p)) if ns_p else float("nan"),
                "P_normalized_spread_median": float(np.median(ns_p)) if ns_p else float("nan"),
                "D_normalized_spread_mean": float(np.mean(ns_d)) if ns_d else float("nan"),
                "D_normalized_spread_median": float(np.median(ns_d)) if ns_d else float("nan"),
                "P_spread_vs_err_spearman": rho_p,
                "D_spread_vs_err_spearman": rho_d,
                "n_rows_used": len(ns_p),
            },
            "beta_stratification": beta_bins,
        }

    # pooled (row-level) and equal-per-n pooled
    p_all = np.array([r["P_rel_err"] for r in rows])
    d_all = np.array([r["D_rel_err"] for r in rows])
    p_pooled = _rmse(p_all); d_pooled = _rmse(d_all)
    per_n_rmse_p = np.array([per_n[str(n)]["P"]["rmse"] for n in N_VALUES])
    per_n_rmse_d = np.array([per_n[str(n)]["D"]["rmse"] for n in N_VALUES])
    p_eq = float(np.mean(per_n_rmse_p)); d_eq = float(np.mean(per_n_rmse_d))

    return {
        "per_n": per_n,
        "pooled": {
            "P_rmse": p_pooled, "D_rmse": d_pooled,
            "I_row_pooled": (p_pooled - d_pooled) / p_pooled if p_pooled > 0 else float("nan"),
            "I_equal_per_n": (p_eq - d_eq) / p_eq if p_eq > 0 else float("nan"),
        },
    }


# --------------------------------------------------------------------------- C2-2

def _x095(beta: float, eta: float, gamma: float) -> float:
    return quantile_true(float(beta), float(eta), float(gamma), R95)


def _jacobian(beta: float, eta: float, gamma: float) -> tuple[float, float, float]:
    """d(x095)/d(beta, eta, gamma) at true params, R=0.95."""
    L = -math.log(R95)
    Lb = L ** (1.0 / beta)
    db = eta * Lb * math.log(L) * (-1.0 / (beta * beta))
    de = Lb
    dg = 1.0
    return db, de, dg


def c2_2_propagation(p_params: dict, datasets: dict) -> dict:
    """Counterfactual parameter->x0.95 error propagation for P.

    Primary quantities are RELATIVE to the row's true_x095:
      rel_contrib_p = (x(beta_hat,eta,gamma) - xt) / xt  etc.
    Within each row the 10-seed counterfactual contributions are ensembled
    (mean) BEFORE aggregating across rows; per-seed results are reported
    separately only as training-instability diagnostics. Non-additivity and
    the Jacobian residual are likewise in relative terms. Raw-scale
    contributions are kept only as a supplementary reference.
    """
    per_n = {}
    # B4 alignment check: combined ensemble-relative error vs B4 P_rel_err
    align_rows = []
    for (ci, ri, n), arr in p_params.items():
        td = datasets[(ci, ri, n)]
        b, e, g = td["beta"], td["eta"], td["gamma"]
        xt = _x095(b, e, g)
        seeds = []
        for s in range(arr.shape[0]):
            bs, es, gs = arr[s]
            if not np.isfinite([bs, es, gs]).all():
                continue
            d_beta = _x095(bs, e, g) - xt
            d_eta = _x095(b, es, g) - xt
            d_gamma = _x095(b, e, gs) - xt
            d_combined = _x095(bs, es, gs) - xt
            db, de, dg = _jacobian(b, e, g)
            jac_approx = db * (bs - b) + de * (es - e) + dg * (gs - g)
            seeds.append({
                "rb": d_beta / xt, "re": d_eta / xt, "rg": d_gamma / xt,
                "rc": d_combined / xt,
                "jac_resid_rel": (d_combined - jac_approx) / xt,
                # raw-scale supplements
                "d_beta": d_beta, "d_eta": d_eta, "d_gamma": d_gamma, "d_combined": d_combined,
            })
        if not seeds:
            continue
        # ensemble within row (mean across seeds)
        arr = {k: float(np.mean([sd[k] for sd in seeds])) for k in
               ["rb", "re", "rg", "rc", "jac_resid_rel",
                "d_beta", "d_eta", "d_gamma", "d_combined"]}
        arr["n"] = n; arr["beta"] = b; arr["xt"] = xt
        per_n.setdefault(str(n), []).append(arr)
        align_rows.append((xt, arr["rc"], arr["rb"], arr["re"], arr["rg"]))

    # aggregate per n
    per_n_agg = {}
    for n in N_VALUES:
        rows_n = per_n[str(n)]
        rbs = [r["rb"] for r in rows_n]; res = [r["re"] for r in rows_n]
        rgs = [r["rg"] for r in rows_n]; rcs = [r["rc"] for r in rows_n]
        jr = [r["jac_resid_rel"] for r in rows_n]
        per_n_agg[str(n)] = {
            "n_rows": len(rows_n),
            "relative_mean_signed": {
                "beta": float(np.mean(rbs)), "eta": float(np.mean(res)),
                "gamma": float(np.mean(rgs)), "combined": float(np.mean(rcs)),
            },
            "relative_mean_abs": {
                "beta": float(np.mean(np.abs(rbs))), "eta": float(np.mean(np.abs(res))),
                "gamma": float(np.mean(np.abs(rgs))), "combined": float(np.mean(np.abs(rcs))),
            },
            "nonadditivity_relative": {
                # combined vs (beta+eta+gamma) — ensemble-relative, NOT a causal share
                "mean_abs": float(np.mean(np.abs(np.array(rcs) - (np.array(rbs) + np.array(res) + np.array(rgs))))),
                "mean_signed": float(np.mean(np.array(rcs) - (np.array(rbs) + np.array(res) + np.array(rgs)))),
            },
            "jacobian_reference_relative": {
                "mean_jac_resid_abs": float(np.mean(np.abs(jr))),
            },
            "raw_scale_supplement_mean_abs": {
                "beta": float(np.mean(np.abs([r["d_beta"] for r in rows_n]))),
                "eta": float(np.mean(np.abs([r["d_eta"] for r in rows_n]))),
                "gamma": float(np.mean(np.abs([r["d_gamma"] for r in rows_n]))),
                "combined": float(np.mean(np.abs([r["d_combined"] for r in rows_n]))),
            },
        }

    return {"per_n": per_n_agg, "n_aligned_rows": len(align_rows)}


def c2_2_b4_alignment(p_params: dict, datasets: dict, rows: list[dict]) -> dict:
    """Cross-check combined ensemble-relative counterfactual vs B4 P_rel_err.

    The ensemble-relative combined error (within-row mean of (x_all-xt)/xt)
    is compared row-by-row to B4's P_rel_err = (P_mean - true)/true.
    """
    row_by_key = {f"{r['cluster']}_{r['replicate']}_{r['n']}": r for r in rows}
    diffs = []
    for (ci, ri, n), arr in p_params.items():
        k = f"{ci}_{ri}_{n}"
        r = row_by_key.get(k)
        if r is None:
            continue
        td = datasets[(ci, ri, n)]
        b, e, g = td["beta"], td["eta"], td["gamma"]
        xt = _x095(b, e, g)
        rcs = []
        for s in range(arr.shape[0]):
            bs, es, gs = arr[s]
            if np.isfinite([bs, es, gs]).all():
                rcs.append((_x095(bs, es, gs) - xt) / xt)
        if rcs:
            mine = float(np.mean(rcs))
            b4 = float(r["P_rel_err"])
            diffs.append(abs(mine - b4))
    return {
        "n_rows": len(diffs),
        "max_abs_diff": float(max(diffs)) if diffs else float("nan"),
        "mean_abs_diff": float(np.mean(diffs)) if diffs else float("nan"),
    }


# --------------------------------------------------------------------------- C2-3

def c2_3_target_alignment(rows: list[dict], npz: dict) -> dict:
    """Effect size and seed sensitivity from P/Dctrl/D row-level + per-seed
    results. Checks whether the 5-seed Dctrl distribution could plausibly
    reverse the direction (0.3296 vs 0.6943). Directional controlled evidence
    for the direct-target treatment package (output dim + loss are part of the
    treatment itself; no residual confounder is separable in this design)."""
    keys = list(npz["keys"])
    p_seeds = npz["p_seeds"]; d_seeds = npz["d_seeds"]; dctrl_seeds = npz["dctrl_seeds"]
    key_to_idx = {k: i for i, k in enumerate(keys)}
    row_by_key = {f"{r['cluster']}_{r['replicate']}_{r['n']}": r for r in rows}

    def route_rmse(per_seed_arr):
        errs_all = []
        per_n_r = {}
        for n in N_VALUES:
            errs_n = []
            for r in row_by_key.values():
                if r["n"] != n:
                    continue
                k = f"{r['cluster']}_{r['replicate']}_{r['n']}"
                idx = key_to_idx[k]
                mean = float(np.nanmean(per_seed_arr[idx]))
                e = (mean - r["true_x095"]) / r["true_x095"]
                errs_n.append(e)
            errs_all.extend(errs_n)
            per_n_r[str(n)] = _rmse(np.array(errs_n))
        return _rmse(np.array(errs_all)), float(np.mean(list(per_n_r.values()))), per_n_r

    p_pooled, p_eq, p_per_n = route_rmse(p_seeds)
    d_pooled, d_eq, d_per_n = route_rmse(d_seeds)
    dc_pooled, dc_eq, dc_per_n = route_rmse(dctrl_seeds)

    def per_seed_rmse(arr_2d):
        out = {}
        for s in range(arr_2d.shape[1]):
            errs = []
            for idx in range(arr_2d.shape[0]):
                k = keys[idx]
                r = row_by_key[k]
                v = arr_2d[idx, s]
                if np.isfinite(v):
                    errs.append((v - r["true_x095"]) / r["true_x095"])
            out[str(s)] = _rmse(np.array(errs))
        return out

    dc_seed_rmse = per_seed_rmse(dctrl_seeds)
    p_seed_rmse = per_seed_rmse(p_seeds)
    dc_seed_vals = np.array(list(dc_seed_rmse.values()))
    p_seed_vals = np.array(list(p_seed_rmse.values()))

    return {
        "effect_size": {
            "P_rmse_rowpooled": p_pooled, "D_rmse_rowpooled": d_pooled,
            "Dctrl_rmse_rowpooled": dc_pooled,
            "P_eq_per_n": p_eq, "Dctrl_eq_per_n": dc_eq,
        },
        "seed_sensitivity": {
            "P_per_seed_rmse": p_seed_rmse,
            "Dctrl_per_seed_rmse": dc_seed_rmse,
        },
        "direction_reversal_check": {
            "P_ensemble_rmse_rowpooled": p_pooled,
            "Dctrl_ensemble_rmse_rowpooled": dc_pooled,
            "P_seed_rmse_min": float(p_seed_vals.min()),
            "P_seed_rmse_max": float(p_seed_vals.max()),
            "Dctrl_seed_rmse_min": float(dc_seed_vals.min()),
            "Dctrl_seed_rmse_max": float(dc_seed_vals.max()),
            "worst_Dctrl_seed_below_best_P_seed": bool(dc_seed_vals.max() < p_seed_vals.min()),
            "gap_P_ensemble_minus_Dctrl_ensemble": p_pooled - dc_pooled,
        },
        "conclusions": {
            "claim_strength": "directional controlled evidence for the direct-target treatment package",
            "note": "output dimension and loss are part of the treatment package; not separable residual confounders within this design; Dctrl 5 seeds vs P/D 10 seeds asymmetry",
        },
    }
