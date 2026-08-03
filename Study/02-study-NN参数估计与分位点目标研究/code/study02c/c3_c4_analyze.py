"""C3 (alternative explanations) and C4 (conditional validity) analyses.

C3-1: D availability vs effective-row error, per stress domain x n.
C3-2: MLE survivor bias — what subset the shared-valid comparison selects.
C3-3: close the Dctrl-seed new-training gate (evidence from C2).
C4:   evidence-driven conditional selection table (task need x domain x n).

Reuses B4 results.csv + B5-v3 stress CSVs; no training, no new data.
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

B_FORMAL = Path("C:/weibull-runs/study02/formal-b")
B5_V3_DIR = B_FORMAL / "B5-v3-20260801-062647"
B5_V6_MANIFEST = B_FORMAL / "B5-v6-20260801-073535" / "manifest.json"
B4_RESULTS = B_FORMAL / "B4-core-20260801-051119" / "results.csv"
N_VALUES = [5, 7, 10, 15, 20]
DOMAINS = ["low", "high", "loc"]
# Availability is a transparent engineering classification threshold, NOT a
# statistical significance threshold. 0.90 means "acceptable for deployment" as a
# policy choice; cells at 0.897 vs 0.903 fall on different sides purely because of
# this cutoff, not because of a natural break.
AVAIL_OK_THRESHOLD = 0.90


def _rmse(errs) -> float:
    arr = np.asarray(errs, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.sqrt(np.mean(arr ** 2))) if arr.size else float("nan")


def _load_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _rel_err(pred, true):
    if true == 0 or not math.isfinite(pred):
        return float("nan")
    return (pred - true) / true


# --------------------------------------------------------------------------- C3-1

def _load_b5_v6_bh() -> dict:
    """Load B5-v6 BH decisions (authority for supported / no-confirmed-difference).

    B5-v6 is hash-bound; supported/no-confirmed-difference MUST come from its
    15-cell BH decisions, not from any unadjusted 95% CI recomputed here.
    """
    import json
    m = json.loads(B5_V6_MANIFEST.read_text(encoding="utf-8"))
    bh = {}
    for domain in DOMAINS:
        for n in N_VALUES:
            cell = m["stress"][domain].get(f"n{n}")
            if cell is None:
                continue
            bh[f"{domain}_n{n}"] = {
                "support": cell.get("bh", {}).get("support"),
                "direction": cell.get("bh", {}).get("direction"),
                "paired_loss_direction": cell.get("paired_loss", {}).get("direction"),
                "q": cell.get("bh", {}).get("q"),
            }
    return bh


def c3_1_availability_vs_error() -> dict:
    """Per domain x n: availability, common-valid error, B5-v6 BH decision and
    a transparent joint decision category.

    Main table columns: availability P/D + common-valid RMSE P/D + BH
    direction/support + joint category. Route-valid RMSE is kept only as a
    supplementary diagnostic (different denominators; not directly comparable
    with common-valid). Decision uses B5-v6 BH as authority:

      - supported (BH) + D better  -> supported_avail_ok  (D availability >= 0.90)
                                     supported_avail_risk (D availability <  0.90)
      - supported (BH) + P better  -> p_better_common_valid
      - not significant (BH)       -> no_confirmed_difference, regardless of
                                      the unadjusted direction
      - otherwise                  -> not_comparable
    """
    bh = _load_b5_v6_bh()
    results = {}
    for domain in DOMAINS:
        rows = _load_csv(B5_V3_DIR / f"stress_{domain}.csv")
        domain_res = {}
        for n in N_VALUES:
            subset = [r for r in rows if int(r["n"]) == n]
            n_total = len(subset)
            p_valid_rows = [r for r in subset if int(r.get("P_valid", 0)) == 1]
            d_valid_rows = [r for r in subset if int(r.get("D_valid", 0)) == 1]
            p_avail = len(p_valid_rows) / n_total if n_total else float("nan")
            d_avail = len(d_valid_rows) / n_total if n_total else float("nan")

            # route-valid conditional RMSE (each route on its OWN valid rows) —
            # supplementary only; denominators differ so not comparable with
            # common-valid.
            p_rmse = _rmse([_rel_err(float(r["P_pred"]), float(r["true_x095"])) for r in p_valid_rows])
            d_rmse = _rmse([_rel_err(float(r["D_pred"]), float(r["true_x095"])) for r in d_valid_rows])

            # common-valid paired loss (squared relative error) — main comparison
            d_sq = []; p_sq = []
            for r in subset:
                if int(r.get("P_valid", 0)) and int(r.get("D_valid", 0)):
                    tv = float(r["true_x095"])
                    dp, pp = float(r["D_pred"]), float(r["P_pred"])
                    if tv == 0 or not (math.isfinite(dp) and math.isfinite(pp)):
                        continue
                    d_sq.append(((dp - tv) / tv) ** 2)
                    p_sq.append(((pp - tv) / tv) ** 2)
            common_rmse_D = _rmse([math.sqrt(x) for x in d_sq]) if d_sq else float("nan")
            common_rmse_P = _rmse([math.sqrt(x) for x in p_sq]) if p_sq else float("nan")

            # B5-v6 BH is the authority for support/direction
            key = f"{domain}_n{n}"
            bcell = bh.get(key, {})
            support_label = bcell.get("support")
            direction = bcell.get("direction") or bcell.get("paired_loss_direction")

            category = "not_comparable"
            if support_label == "supported (BH)":
                if direction == "D better":
                    category = ("supported_avail_ok" if d_avail >= AVAIL_OK_THRESHOLD
                                else "supported_avail_risk")
                elif direction == "P better":
                    category = "p_better_common_valid"
            elif support_label == "not significant (BH)":
                category = "no_confirmed_difference"

            # invalid concentration: beta/eta/gamma/true_x095 distribution of D-invalid rows
            d_invalid = [r for r in subset if int(r.get("D_valid", 0)) == 0]
            invalid_profile = {}
            if d_invalid:
                for k in ["beta", "eta", "gamma", "true_x095"]:
                    vals = [float(r[k]) for r in d_invalid if math.isfinite(float(r[k]))]
                    all_vals = [float(r[k]) for r in subset if math.isfinite(float(r[k]))]
                    invalid_profile[k] = {
                        "invalid_mean": float(np.mean(vals)) if vals else float("nan"),
                        "all_mean": float(np.mean(all_vals)) if all_vals else float("nan"),
                    }

            domain_res[f"n{n}"] = {
                "n_total": n_total,
                "availability": {"P": p_avail, "D": d_avail,
                                 "P_n_valid": len(p_valid_rows), "D_n_valid": len(d_valid_rows),
                                 "avail_ok_threshold": AVAIL_OK_THRESHOLD,
                                 "note": ("engineering classification threshold, "
                                          "not a statistical significance threshold")},
                "common_valid": {
                    "n_rows": len(d_sq),
                    "rmse_D": common_rmse_D,
                    "rmse_P": common_rmse_P,
                },
                "route_valid_rmse_supplementary": {
                    "P": p_rmse, "D": d_rmse,
                    "note": ("different denominators (each route on its own valid rows); "
                             "NOT directly comparable with common-valid RMSE"),
                },
                "bh_decision": {
                    "support": support_label,
                    "direction": direction,
                    "q": bcell.get("q"),
                },
                "decision_category": category,
                "d_invalid_profile": invalid_profile,
            }
        results[domain] = domain_res
    return results


# --------------------------------------------------------------------------- C3-2

def c3_2_mle_survivor_bias() -> dict:
    """Describe MLE failure by n and feasible parameter region; compare D
    (and P/MDM/LRE where safely comparable) on MLE-valid vs MLE-invalid rows.

    The point is to characterize what subset shared-valid comparison selects,
    not to impute MLE's unknown precision on failure rows.
    """
    rows = _load_csv(B4_RESULTS)
    results = {}
    for n in N_VALUES:
        subset = [r for r in rows if int(r["n"]) == n]
        mle_valid = [r for r in subset if r.get("MLE_mean", "") not in ("", "nan")]
        mle_invalid = [r for r in subset if r.get("MLE_mean", "") in ("", "nan")]
        mle_fail_rate = len(mle_invalid) / len(subset) if subset else float("nan")

        # error distributions on the two subsets for routes that are comparable
        def subset_rmse(route, sset):
            errs = [_rel_err(float(r[f"{route}_mean"]), float(r["true_x095"]))
                    for r in sset if math.isfinite(float(r[f"{route}_mean"]))]
            return _rmse(errs)

        # beta feasibility: is MLE failure concentrated in feasible (beta range) region
        beta_valid = [float(r["beta"]) for r in mle_valid]
        beta_invalid = [float(r["beta"]) for r in mle_invalid]
        eta_valid = [float(r["eta"]) for r in mle_valid]
        eta_invalid = [float(r["eta"]) for r in mle_invalid]

        results[str(n)] = {
            "n_rows": len(subset),
            "mle_valid_rows": len(mle_valid),
            "mle_invalid_rows": len(mle_invalid),
            "mle_failure_rate": mle_fail_rate,
            "subset_comparison": {
                "D_rmse_on_MLE_valid": subset_rmse("D", mle_valid),
                "D_rmse_on_MLE_invalid": subset_rmse("D", mle_invalid),
                "P_rmse_on_MLE_valid": subset_rmse("P", mle_valid),
                "P_rmse_on_MLE_invalid": subset_rmse("P", mle_invalid),
                "MDM_rmse_on_MLE_valid": subset_rmse("MDM", mle_valid),
                "MDM_rmse_on_MLE_invalid": subset_rmse("MDM", mle_invalid),
                "LRE_rmse_on_MLE_valid": subset_rmse("LRE", mle_valid),
                "LRE_rmse_on_MLE_invalid": subset_rmse("LRE", mle_invalid),
            },
            "mle_failure_beta": {
                "valid_mean": float(np.mean(beta_valid)) if beta_valid else float("nan"),
                "invalid_mean": float(np.mean(beta_invalid)) if beta_invalid else float("nan"),
            },
            "mle_failure_eta": {
                "valid_mean": float(np.mean(eta_valid)) if eta_valid else float("nan"),
                "invalid_mean": float(np.mean(eta_invalid)) if eta_invalid else float("nan"),
            },
        }
    return results


# --------------------------------------------------------------------------- C3-3

def c3_3_close_training_gate() -> dict:
    """Close the Dctrl-seed new-training gate using C2 evidence.

    C2-3 already showed Dctrl per-seed RMSE in [0.3255,0.3321] vs P in
    [0.5371,0.8387]; worst Dctrl seed < best P seed. So supplementing Dctrl
    seeds cannot reasonably reverse the direction. No new training is needed.
    """
    return {
        "gate": "closed",
        "reason": "Dctrl 5-seed RMSE range [0.3255, 0.3321] is far below and disjoint from "
                  "P 10-seed range [0.5371, 0.8387]; worst Dctrl seed (0.3321) < best P seed "
                  "(0.5371). Direction is robust to seed resampling.",
        "evidence_source": "C2-3 direction_reversal_check (run C2-mechanism-20260801-152548)",
        "new_training_requested": False,
    }


# --------------------------------------------------------------------------- C4

def c4_conditional_selection(c3_1, c3_2, c2_1_pooled=None, b4_core=None) -> dict:
    """Evidence-driven conditional selection table (revised).

    Axes: task need (x0.95 only vs full params) x domain (core / low / high /
    loc) x n. Core supported strata and stress-high are kept separate; the
    stress-low/loc cells are listed individually by B5-v6 BH direction. Rules
    are explicit; no universal ranking.
    """
    # C3-1 gives per-cell category; use it to enumerate stress cells precisely.
    stress_cells = {}
    for dom in c3_1:
        for n in N_VALUES:
            c = c3_1[dom].get(f"n{n}", {})
            cat = c.get("decision_category")
            avail_d = c.get("availability", {}).get("D")
            stress_cells[f"{dom} n{n}"] = {
                "category": cat,
                "D_availability": avail_d,
                "bh_direction": (c.get("bh_decision") or {}).get("direction"),
                "bh_support": (c.get("bh_decision") or {}).get("support"),
            }

    rules = {
        "core": {
            "supported_strata": ("n=5/15/20 are the core cells where D is supported vs P "
                                 "(per B4 BH); 'high beta' is a stress-domain trait and is "
                                 "kept separate from the core n strata"),
            "n7_10": "no confirmed difference on core; decide by information need and risk, "
                     "not by forcing an accuracy rank between D and P",
            "traditional_baseline": "MDM/LRE are stronger traditional baselines on core; "
                                    "D is not the default overall first choice",
            "full_params_need": ("if full beta/eta/gamma needed, P has functional value "
                                 "(100% legal, 0 support violation) but n=5 parameter "
                                 "precision is limited; 'output legal' != 'parameter accurate'"),
            "interval_evidence": "core split-conformal 90/95 coverage near nominal; valid "
                                 "in-domain risk cue only",
        },
        "stress": {
            "cells": stress_cells,
            "notes": {
                "low_n10": ("B5-v6 BH-supported P better on common-valid rows; "
                            "D is NOT the better route in this cell"),
                "low_n7_n15": "not significant (BH) -> no confirmed difference",
                "loc_n7_n10_n15": "not significant (BH) -> no confirmed difference "
                                  "(incl. loc n15 whose unadjusted direction was 'D better'; "
                                  "BH is authoritative)",
                "other_supported": ("remaining supported (BH) cells are classified by D "
                                    "availability into supported_avail_ok / supported_avail_risk"),
            },
            "D_status": "conditional common-valid precision supports D in some cells, but D "
                        "availability drops (low n5 58%); separate precision from availability",
            "interval_evidence": "conformal on stress diagnoses coverage failure, provides no "
                                 "OOD guarantee",
            "nist_contamination": "NIST single-material and contamination results cannot "
                                  "substitute for known-truth cross-material precision validation",
            "b5_v6_interpretation": ("B5-v6 stress summary should be read by direction "
                                     "(low n10 is BH-supported P better); this corrects the "
                                     "interpretation, not the underlying row-level evidence"),
        },
        "decision_principle": (
            "No universal ranking. Pick by: (1) task needs only x0.95 or full params; "
            "(2) domain (core vs stress-low/loc/high); (3) n; (4) accuracy + availability + "
            "interval + traditional baseline together. On stress, conditional common-valid "
            "precision is not the same as deployability because availability may be the "
            "binding risk."
        ),
    }
    return rules
