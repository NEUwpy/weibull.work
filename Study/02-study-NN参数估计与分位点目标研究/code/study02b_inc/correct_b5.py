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
    if domain == "low":
        seed, b0, b1 = 142, 0.6, 1.2
    elif domain == "high":
        seed, b0, b1 = 242, 4.0, 8.0
    else:
        seed, b0, b1 = 342, 1.2, 4.0
    sampler = qmc.Sobol(d=3, scramble=True, seed=seed)
    pts = sampler.random_base2(m=5)
    betas = b0 + pts[:, 0] * (b1 - b0)
    etas = 100.0 + pts[:, 1] * 9900.0
    gammas = pts[:, 2] * etas
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


def run(out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    models = _load_models()
    result = {
        "version": "1.0", "kind": "b5_correction", "code_tip": _git_tip(),
        "config_hash": C.CONFIG_HASH,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": ("B5 P predictions recomputed with the A-E1 input scaler; D outputs "
                 "reused unchanged from B5-v3-20260801-062647. B5's published "
                 "P-dependent stress/contamination evidence is superseded by this correction."),
        "input_b5": {"dir": str(B5_V3)},
    }
    result["stress"] = correct_stress(models, out_dir)
    result["contamination"] = correct_contamination(models, out_dir)
    # Conformal/NIST depend on P thresholds/splits; flagged as not-recomputed here.
    result["conformal"] = {"status": "not_recomputed",
                           "note": "requires recalibrating P conformal thresholds and re-evaluating core/stress coverage; listed as a remaining P-dependent correction, see report"}
    result["nist"] = {"status": "not_recomputed",
                      "note": "requires re-running the 500-split NIST P evaluation; listed as a remaining P-dependent correction, see report"}
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
