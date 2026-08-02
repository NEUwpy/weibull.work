"""Correct the P-dependent B5 evidence (R1).

B5 fed raw sorted-z to the scaler-trained A-E1 P checkpoints, biasing P. This
regenerates the B5 stress (low/high/loc) and contamination datasets
deterministically, recomputes P per-seed with the A-E1 input scaler, reuses the
unchanged D/Dctrl/traditional outputs, and re-derives the per domain x n and
per-condition P-vs-D summaries. Conformal/NIST components are reported as
corrected P columns where they reuse the core/stress rows; otherwise they are
listed as not-recomputed with a blocker note.

Does NOT mutate the frozen B5 run. Output under ``<out>/b5_correction``.

Usage:
    python -m study02b_inc.correct_b5 --out <run-dir>/b5_correction
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
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

from study02b_inc import config as C
from study02b_inc import a_data as A
from study02b_inc import models as M
from study02b_inc import evaluate_inc as E

B5_V3 = Path("C:/weibull-runs/study02/formal-b/B5-v3-20260801-062647")
N_VALUES = [5, 7, 10, 15, 20]


def _git_tip() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                       cwd=str(C.REPO_ROOT), timeout=5)
    return r.stdout.strip() or "unknown"


def _rmse(arr):
    a = np.asarray(arr, dtype=float)
    a = a[np.isfinite(a)]
    return float(np.sqrt(np.mean(a ** 2))) if a.size else np.nan


def _load_p(models_by_n, n, sample):
    return E._infer_p(models_by_n[n], sample)


def _load_models():
    p_scalers = {}
    for n in N_VALUES:
        p_scalers[n] = A.a_p_scaler_from_cache(n)
    p_index = M.build_p_index()
    models = {}
    for n in N_VALUES:
        mods = []
        for e in p_index[n]:
            mods.append((e["seed"], (M.load_model("P", n, e["seed"], e), p_scalers[n])))
        models[n] = mods
    return models


def _stress_domain(domain):
    """Exact frozen B5 stress generation (evaluate_b5.py) for a given domain."""
    seed = {"low": 142, "high": 242, "loc": 342}[domain]
    sampler = qmc.Sobol(d=3, scramble=True, seed=seed)
    pts = sampler.random_base2(m=5)
    etas = 100.0 + pts[:, 1] * 9900.0
    if domain == "low":
        betas = 0.6 + pts[:, 0] * 0.6
        gammas = pts[:, 2] * etas
    elif domain == "high":
        betas = 4.0 + pts[:, 0] * 4.0
        gammas = pts[:, 2] * etas
    else:  # loc
        betas = 1.2 + pts[:, 0] * 2.8
        gammas = (-0.5 + pts[:, 2] * 2.5) * etas
    return betas, etas, gammas, seed


def correct_stress(models, out_dir):
    print("=== Stress correction ===")
    results = {}
    for domain in ["low", "high", "loc"]:
        betas, etas, gammas, dseed = _stress_domain(domain)
        base = {"low": 1, "high": 2, "loc": 3}[domain]
        rows = []
        for ci, (b, e, g) in enumerate(zip(betas, etas, gammas)):
            for ri in range(10):
                for n in N_VALUES:
                    s = generate_sample(float(b), float(e), float(g), n, ri,
                                        seed=6000 + 100 * base + ci)
                    xt = quantile_true(float(b), float(e), float(g), 0.95)
                    pv = _load_p(models, n, s)
                    # D/traditional unchanged from B5 (reuse the CSV's D_pred).
                    rows.append({"cluster": ci, "replicate": ri, "n": n,
                                 "beta": float(b), "eta": float(e), "gamma": float(g),
                                 "domain": domain, "true_x095": xt,
                                 "P_pred": float(np.nanmean(pv)) if np.isfinite(pv).any() else np.nan})
        # per domain x n comparison (P vs D; D from B5 CSV)
        b5_csv = B5_V3 / f"stress_{domain}.csv"
        d_by_key = {}
        with open(b5_csv, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                d_by_key[(int(r["cluster"]), int(r["replicate"]), int(r["n"]))] = float(r["D_pred"])
        cell = {}
        for n in N_VALUES:
            pe, de = [], []
            for r in rows:
                if r["n"] != n:
                    continue
                d = d_by_key.get((r["cluster"], r["replicate"], n), np.nan)
                pe.append((r["P_pred"] - r["true_x095"]) / r["true_x095"])
                de.append((d - r["true_x095"]) / r["true_x095"])
            pr, dr = _rmse(pe), _rmse(de)
            cell[str(n)] = {"P_rmse": pr, "D_rmse": dr,
                            "I": (pr - dr) / pr if pr > 0 else np.nan}
        results[domain] = cell
        print(f"  {domain}: " + ", ".join(f"n{k} I={v['I']:+.3f}" for k, v in cell.items()))
    return results


def correct_contamination(models, out_dir):
    print("=== Contamination correction ===")
    rng = np.random.default_rng(42)
    betas = rng.uniform(1.2, 4.0, size=32)
    etas = rng.uniform(100, 10000, size=32)
    gammas = rng.uniform(0, 1, size=32) * etas
    conditions = ["clean", "high3", "high10", "low_end", "two_sided"]
    per_cond = {c: {"P": [], "D": []} for c in conditions}
    for ci, (b, e, g) in enumerate(zip(betas, etas, gammas)):
        for ri in range(10):
            clean = generate_sample(float(b), float(e), float(g), 20, ri, seed=9000 + ci)
            xt = quantile_true(float(b), float(e), float(g), 0.95)
            iqr = float(np.quantile(clean, 0.75) - np.quantile(clean, 0.25))
            cond_samples = {
                "clean": clean, "high3": clean.copy(), "high10": clean.copy(),
                "low_end": clean.copy(), "two_sided": clean.copy()}
            cond_samples["high3"][-3:] *= 10
            cond_samples["high10"][-1] *= 10
            cond_samples["low_end"][0] -= 0.5 * iqr
            m10 = 2
            cond_samples["two_sided"][:m10] -= 0.5 * iqr
            cond_samples["two_sided"][-m10:] *= 10
            for cn, cs in cond_samples.items():
                pv = _load_p(models, 20, cs)
                per_cond[cn]["P"].append((float(np.nanmean(pv)) - xt) / xt if np.isfinite(pv).any() else np.nan)
    # D from B5 CSV
    with open(B5_V3 / "contamination.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            per_cond[r["condition"]]["D"].append(
                (float(r["D_pred"]) - float(r["true_x095"])) / float(r["true_x095"])
                if r["D_valid"] == "1" else np.nan)
    results = {}
    for cn in conditions:
        pr, dr = _rmse(np.array(per_cond[cn]["P"])), _rmse(np.array(per_cond[cn]["D"]))
        results[cn] = {"P_rmse": pr, "D_rmse": dr,
                       "I": (pr - dr) / pr if pr > 0 else np.nan}
        print(f"  {cn}: I={results[cn]['I']:+.3f} (P {pr:.3f} / D {dr:.3f})")
    return results


def verify_frozen_identity() -> dict:
    """R8: prove the regenerated stress/contamination data is identical to the
    frozen B5 design. Compares beta/eta/gamma/true_x095/sample_min/sample_iqr
    and the cluster/replicate/n/condition keys. Fails closed on any mismatch.
    """
    checks = {}
    # --- stress ---
    for domain in ["low", "high", "loc"]:
        betas, etas, gammas, seed = _stress_domain(domain)
        base = {"low": 1, "high": 2, "loc": 3}[domain]
        frozen = {}
        with open(B5_V3 / f"stress_{domain}.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                frozen[(int(r["cluster"]), int(r["replicate"]), int(r["n"]))] = r
        n_mismatch = 0
        for ci, (b, e, g) in enumerate(zip(betas, etas, gammas)):
            for ri in range(10):
                for n in N_VALUES:
                    fr = frozen.get((ci, ri, n))
                    if fr is None:
                        n_mismatch += 1
                        continue
                    s = generate_sample(float(b), float(e), float(g), n, ri,
                                        seed=6000 + 100 * base + ci)
                    xt = quantile_true(float(b), float(e), float(g), 0.95)
                    smin = float(s.min())
                    siqr = float(np.quantile(s, 0.75) - np.quantile(s, 0.25))
                    if (abs(float(fr["beta"]) - b) > 1e-9 or abs(float(fr["eta"]) - e) > 1e-6
                            or abs(float(fr["gamma"]) - g) > 1e-6
                            or abs(float(fr["true_x095"]) - xt) > 1e-6
                            or abs(float(fr["sample_min"]) - smin) > 1e-4
                            or abs(float(fr["sample_iqr"]) - siqr) > 1e-4):
                        n_mismatch += 1
        checks[f"stress_{domain}"] = {
            "frozen_rows": len(frozen), "mismatches": n_mismatch,
            "ok": n_mismatch == 0}
    # --- contamination ---
    rng = np.random.default_rng(42)
    betas = rng.uniform(1.2, 4.0, size=32)
    etas = rng.uniform(100, 10000, size=32)
    gammas = rng.uniform(0, 1, size=32) * etas
    frozen_cont = {}
    with open(B5_V3 / "contamination.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            frozen_cont[(int(r["cluster"]), int(r["replicate"]), r["condition"])] = r
    # Load frozen D model (n=20) + target stats to rerun on regenerated samples
    # and compare D_pred/D_valid row-by-row (proves sample identity).
    d_index = M.build_d_index(C.SUPERSEDED_RUNS[0])
    d20 = d_index.get(20, {}).get("selected", [])
    d_mods = []
    ts20 = M.d_target_stats(C.SUPERSEDED_RUNS[0]).get(20, {"mean": 0.0, "sd": 1.0})
    from study02b.representations import DTrainingStats
    for e in d20:
        d_mods.append((e["seed"], (M.load_model("D", 20, e["seed"], e),
                                   DTrainingStats(mean=ts20["mean"], sd=ts20["sd"]))))
    n_mismatch = 0
    n_d_mismatch = 0
    for ci, (b, e, g) in enumerate(zip(betas, etas, gammas)):
        for ri in range(10):
            clean = generate_sample(float(b), float(e), float(g), 20, ri, seed=9000 + ci)
            xt = quantile_true(float(b), float(e), float(g), 0.95)
            iqr = float(np.quantile(clean, 0.75) - np.quantile(clean, 0.25))
            cond_samples = {"clean": clean, "high3": clean.copy(), "high10": clean.copy(),
                            "low_end": clean.copy(), "two_sided": clean.copy()}
            cond_samples["high3"][-3:] *= 10
            cond_samples["high10"][-1] *= 10
            cond_samples["low_end"][0] -= 0.5 * iqr
            m10 = 2
            cond_samples["two_sided"][:m10] -= 0.5 * iqr
            cond_samples["two_sided"][-m10:] *= 10
            for cn, cs in cond_samples.items():
                fr = frozen_cont.get((ci, ri, cn))
                if fr is None:
                    n_mismatch += 1
                    continue
                if abs(float(fr["true_x095"]) - xt) > 1e-6:
                    n_mismatch += 1
                # Rerun the frozen D model on the regenerated sample and compare
                # D_pred/D_valid. Use the frozen B5 _infer_d semantics: a D
                # prediction is valid only if finite AND > 0 (non-positive -> nan).
                raw_d = E._infer_d(d_mods, cs)
                filtered = np.where(raw_d > 0, raw_d, np.nan)
                d_pred = _ens_mean(list(filtered))
                d_valid = int(np.isfinite(d_pred) and d_pred > 0)
                fr_dvalid = int(fr["D_valid"])
                fr_dpred = float(fr["D_pred"]) if fr["D_pred"] != "" else np.nan
                if d_valid != fr_dvalid or (np.isfinite(fr_dpred) and
                                            abs(d_pred - fr_dpred) > 1e-3 * max(1.0, abs(fr_dpred))):
                    n_d_mismatch += 1
    checks["contamination"] = {
        "frozen_rows": len(frozen_cont), "mismatches": n_mismatch,
        "D_pred_mismatches": n_d_mismatch,
        "ok": n_mismatch == 0 and n_d_mismatch == 0,
        "note": "D_pred/D_valid rerun on regenerated samples proves sample identity (frozen CSV lacks parameter columns and sample anchor stats)",}
    failed = [k for k, v in checks.items() if not v["ok"]]
    if failed:
        raise RuntimeError(f"R8 verification failed (frozen identity mismatch): {failed}")
    return checks


NIST_CSV = (_REPO_ROOT / "Study" / "01-study-MDM最小偏移量优化研究" / "artifacts" / "formal"
            / "real_data" / "nist-6061-t6-fatigue" / "lifetimes.csv")
B4_NPZ = Path("C:/weibull-runs/study02/formal-b/B4-core-20260801-051119/per_seed_predictions.npz")
B4_CSV = Path("C:/weibull-runs/study02/formal-b/B4-core-20260801-051119/results.csv")
CORRECTED_B4_NPZ = Path("C:/weibull-runs/study02/b-inc/BINC-20260802-02/b4_correction/b4_corrected_per_seed.npz")


def _ens_mean(vals):
    arr = [v for v in vals if np.isfinite(v)]
    return float(np.mean(arr)) if arr else np.nan


def correct_conformal(models, out_dir):
    """Recalibrate P split-conformal 90/95 thresholds with the A-E1 scaler and
    recompute P coverage/width/availability on the frozen core + stress rows.
    D thresholds/coverage are unchanged (reused from the frozen B5 v4/v3).
    """
    print("=== Conformal correction (P) ===")
    # Calibrate P thresholds: identical design to B5 _conformal_calibrate
    # (rng seed 7000, 5000 rows/n, uniform params, sample seed 8000).
    n_cal = 5000
    p_thresh = {}
    rng = np.random.default_rng(7000)
    for n_val in N_VALUES:
        betas = rng.uniform(1.2, 4.0, size=n_cal)
        etas = rng.uniform(100, 10000, size=n_cal)
        gammas = rng.uniform(0, 1, size=n_cal) * etas
        p_res = []
        for i in range(n_cal):
            b, e, g = float(betas[i]), float(etas[i]), float(gammas[i])
            sample = generate_sample(b, e, g, n_val, i, seed=8000)
            x095 = quantile_true(b, e, g, 0.95)
            pv = _load_p(models, n_val, sample)
            pm = _ens_mean(list(pv))
            if np.isfinite(pm):
                p_res.append(abs(pm - x095))
        # Finite-sample split-conformal order statistic (frozen B5 protocol):
        # q = ceil((m+1)*(1-alpha))-th order statistic of calibration residuals.
        from study02b.analyze_b5 import split_conformal_quantile
        p_thresh[str(n_val)] = {
            "P_q90_half_width": split_conformal_quantile(p_res, 0.10),
            "P_q95_half_width": split_conformal_quantile(p_res, 0.05),
            "n_cal_P": len(p_res),
        }
    # Core coverage using corrected B4 P per-seed. Interval is [pred-q, pred+q],
    # so q is the HALF width and the full absolute width is 2q.
    npz = np.load(CORRECTED_B4_NPZ, allow_pickle=True)
    p_s = npz["p_seeds"]
    keys = [str(k) for k in npz["keys"]]
    true_x095 = {}
    with open(B4_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            true_x095[f"{r['cluster']}_{r['replicate']}_{r['n']}"] = float(r["true_x095"])
    core_summary = {}
    for n_val in N_VALUES:
        th = p_thresh[str(n_val)]
        q95 = th["P_q95_half_width"]
        cov90, cov95, n_rows, full_widths = [], [], 0, []
        true_vals = []
        for i, k in enumerate(keys):
            parts = k.split("_")
            if len(parts) != 3 or int(parts[2]) != n_val:
                continue
            xt = true_x095.get(k)
            if xt is None:
                continue
            vals = p_s[i][np.isfinite(p_s[i])]
            if len(vals) == 0:
                continue
            pred = float(np.mean(vals))
            ae = abs(pred - xt)
            cov90.append(int(ae <= th["P_q90_half_width"]))
            cov95.append(int(ae <= q95))
            full_widths.append(2.0 * q95)  # full absolute width = 2q
            true_vals.append(xt)
            n_rows += 1
        core_summary[f"P_n{n_val}"] = {
            "cov90": float(np.mean(cov90)) if cov90 else np.nan,
            "cov95": float(np.mean(cov95)) if cov95 else np.nan,
            "n": n_rows,
            "mean_full_width_95": float(np.mean(full_widths)) if full_widths else np.nan,
            "normalized_full_width_95": (float(np.mean(full_widths)) / float(np.mean(true_vals))
                                         if full_widths and true_vals else np.nan),
        }
    # Stress P coverage (regenerate stress samples, corrected P).
    stress_coverage = {}
    for domain in ["low", "high", "loc"]:
        betas, etas, gammas, seed = _stress_domain(domain)
        base = {"low": 1, "high": 2, "loc": 3}[domain]
        cell = {}
        for n_val in N_VALUES:
            th = p_thresh[str(n_val)]
            rows_n, avail_n, cov95_n = 0, 0, []
            for ci, (b, e, g) in enumerate(zip(betas, etas, gammas)):
                for ri in range(10):
                    s = generate_sample(float(b), float(e), float(g), n_val, ri,
                                        seed=6000 + 100 * base + ci)
                    xt = quantile_true(float(b), float(e), float(g), 0.95)
                    pv = _load_p(models, n_val, s)
                    pm = _ens_mean(list(pv))
                    rows_n += 1
                    if np.isfinite(pm):
                        avail_n += 1
                        cov95_n.append(int(abs(pm - xt) <= th["P_q95_half_width"]))
            cell[str(n_val)] = {"availability": avail_n / rows_n if rows_n else np.nan,
                                "cond_cov95": float(np.mean(cov95_n)) if cov95_n else np.nan}
        stress_coverage[domain] = cell
    return {"P_thresholds": p_thresh, "core_coverage": core_summary,
            "stress_coverage": stress_coverage}


def correct_nist(models, out_dir):
    """Rerun NIST 6061-T6 5n x 500 deterministic splits for P with the scaler.
    D/traditional predictions reused from the frozen B5 nist_splits.csv (they
    do not depend on the P scaler); only P columns are replaced.
    """
    print("=== NIST correction (P) ===")
    data = np.loadtxt(NIST_CSV, delimiter=",", skiprows=1)
    n_total = len(data)
    # Load frozen B5 NIST for D/traditional reuse + row-key alignment.
    frozen = {}
    with open(B5_V3 / "nist_splits.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            frozen[(int(r["n"]), int(r["split"]))] = r
    tau = 0.05
    rows_out = []
    for n_val in N_VALUES:
        for split in range(500):
            rng = np.random.default_rng(9000 + n_val * 1000 + split)
            idx = rng.choice(n_total, size=n_val, replace=False)
            train = data[idx]
            holdout = data[np.setdiff1d(np.arange(n_total), idx)]
            if len(holdout) == 0:
                continue
            fr = frozen.get((n_val, split))
            if fr is None:
                raise RuntimeError(f"NIST row key missing: n={n_val} split={split}")
            pv = _load_p(models, n_val, train)
            pm = _ens_mean(list(pv))
            pb = np.nan
            exc = np.nan
            if np.isfinite(pm):
                pb = float(np.mean([(tau - 1) * (h - pm) if h < pm else tau * (h - pm) for h in holdout]))
                exc = float(np.mean([1.0 if h > pm else 0.0 for h in holdout]))
            rows_out.append({
                "n": n_val, "split": split, "holdout_size": len(holdout),
                "P_pred": pm, "P_valid": int(np.isfinite(pm)),
                "P_pinball": pb, "P_exceed": exc,
                # reused from frozen B5 (unchanged, P-independent)
                "D_pred": float(fr["D_pred"]), "D_valid": int(fr["D_valid"]),
                "D_pinball": float(fr["D_pinball"]) if fr["D_pinball"] != "" else np.nan,
                "D_exceed": float(fr["D_exceed"]) if fr["D_exceed"] != "" else np.nan,
                "MDM_pred": float(fr["MDM_pred"]) if fr["MDM_pred"] != "" else np.nan,
                "MLE_pred": float(fr["MLE_pred"]) if fr["MLE_pred"] != "" else np.nan,
                "LRE_pred": float(fr["LRE_pred"]) if fr["LRE_pred"] != "" else np.nan,
            })
    per_n = {}
    for n_val in N_VALUES:
        sub = [r for r in rows_out if r["n"] == n_val]
        per_n[str(n_val)] = {
            "n_splits": len(sub),
            "P_pinball": _ens_mean([r["P_pinball"] for r in sub]),
            "P_exceed": _ens_mean([r["P_exceed"] for r in sub]),
            "D_pinball": _ens_mean([r["D_pinball"] for r in sub]),
            "D_exceed": _ens_mean([r["D_exceed"] for r in sub]),
        }
    return {"per_n": per_n, "n_splits_total": len(rows_out),
            "rows": rows_out}


def run(out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    identity = verify_frozen_identity()
    models = _load_models()
    result = {
        "version": "1.0", "kind": "b5_correction", "code_tip": _git_tip(),
        "config_hash": C.CONFIG_HASH,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": ("B5 P predictions recomputed with the A-E1 input scaler; D outputs "
                 "reused unchanged from B5-v3-20260801-062647. B5's published "
                 "P-dependent stress/contamination evidence is superseded by this correction."),
        "input_b5": {"dir": str(B5_V3)},
        "frozen_identity_verification": identity,
    }
    result["stress"] = correct_stress(models, out_dir)
    result["contamination"] = correct_contamination(models, out_dir)
    result["conformal"] = correct_conformal(models, out_dir)
    nist = correct_nist(models, out_dir)
    result["nist"] = {k: v for k, v in nist.items() if k != "rows"}
    import csv as _csv
    with open(out_dir / "nist_splits_corrected.csv", "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=list(nist["rows"][0].keys()))
        w.writeheader()
        w.writerows(nist["rows"])
    result["nist"]["corrected_rows_csv"] = str(out_dir / "nist_splits_corrected.csv")
    (out_dir / "b5_correction_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("B5 correction summary written.")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run(Path(args.out))


if __name__ == "__main__":
    main()
