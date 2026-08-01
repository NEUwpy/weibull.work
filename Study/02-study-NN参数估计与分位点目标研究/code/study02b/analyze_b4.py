"""B4 v5 derived analysis — uses immutable v4 artifacts, corrects paired seed bootstrap.

Reads existing results.csv + per_seed_predictions.npz from B4-core-20260801-051119.
Recomputes D-vs-P CI with TRUE paired seed bootstrap (single seed_idx for both routes).
Adds per-n hierarchical bootstrap with BH-adjusted support markings.
No inference rerun.
"""

from __future__ import annotations

import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EXTERNAL_ROOT = Path("C:/weibull-runs/study02/formal-b")
_V4_DIR = _EXTERNAL_ROOT / "B4-core-20260801-051119"

_N_CLUSTERS, _N_REPLICATES = 64, 20
_N_VALUES = [5, 7, 10, 15, 20]
_N_BOOTSTRAP = 2000


def _git_tip():
    r = subprocess.run(["git","rev-parse","HEAD"], capture_output=True, text=True, cwd=str(_REPO_ROOT))
    return r.stdout.strip() or "unknown"


def run_analyze(output_dir=None):
    if output_dir is None:
        output_dir = str(_EXTERNAL_ROOT / f"B4-analyze-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    code_tip = _git_tip()
    print(f"=== B4 Derived Analysis v5 ===")
    print(f"Output: {out}"); print(f"Code tip: {code_tip}")

    # Verify input hashes
    csv_path = _V4_DIR / "results.csv"
    npz_path = _V4_DIR / "per_seed_predictions.npz"
    csv_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    npz_sha = hashlib.sha256(npz_path.read_bytes()).hexdigest()
    print(f"Input results.csv: {csv_sha}")
    print(f"Input per_seed_predictions.npz: {npz_sha}")

    # Load per-seed predictions
    per_seed = np.load(npz_path, allow_pickle=True)
    # Reconstruct keys
    keys_raw = per_seed["keys"]
    p_seeds_raw = per_seed["p_seeds"]   # (6400, 10)
    d_seeds_raw = per_seed["d_seeds"]   # (6400, 10)
    dc_seeds_raw = per_seed["dctrl_seeds"]  # (6400, 5)
    per_seed.close()

    # Build lookup: (ci, ri, n) → index in arrays
    n_rows = len(keys_raw)
    key_to_idx = {}
    for i, k in enumerate(keys_raw):
        parts = str(k).split("_")
        if len(parts) == 3:
            ci, ri, n = int(parts[0]), int(parts[1]), int(parts[2])
            key_to_idx[(ci, ri, n)] = i

    # Load true x0.95 from CSV
    import csv as csv_mod
    true_x095 = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv_mod.DictReader(f)
        for row in reader:
            ci, ri, n = int(row["cluster"]), int(row["replicate"]), int(row["n"])
            true_x095[(ci, ri, n)] = float(row["true_x095"])

    print(f"Loaded {len(key_to_idx)} rows from per-seed artifact")
    print(f"Loaded {len(true_x095)} true values from CSV")

    rng = np.random.default_rng(42)

    # -- CORRECTED paired seed bootstrap --
    # Use a SINGLE seed_idx for both P and D routes
    def _hierarchical_bootstrap_paired(datasets_list, rng):
        """One rep: cluster resample + ONE seed multiset for both P and D."""
        ci_all = list(range(_N_CLUSTERS))
        ci_b = list(rng.choice(ci_all, size=_N_CLUSTERS, replace=True))
        n_seeds = 10
        seed_idx = rng.choice(n_seeds, size=n_seeds, replace=True)  # SAME for P and D

        per_n_vals = []
        for n_val in _N_VALUES:
            d_errs_n = []; p_errs_n = []
            for ci in ci_b:
                for ri in range(_N_REPLICATES):
                    key = (ci, ri, n_val)
                    idx = key_to_idx.get(key)
                    td = true_x095.get(key)
                    if idx is None or td is None or td == 0: continue
                    p_vals = p_seeds_raw[idx]
                    d_vals = d_seeds_raw[idx]
                    # Apply SAME seed_idx to both
                    p_mean = float(np.nanmean(p_vals[seed_idx]))
                    d_mean = float(np.nanmean(d_vals[seed_idx]))
                    if np.isfinite(d_mean):
                        d_errs_n.append((d_mean - td) / td)
                    if np.isfinite(p_mean):
                        p_errs_n.append((p_mean - td) / td)
            dr = float(np.sqrt(np.mean(np.array(d_errs_n)**2))) if d_errs_n else np.nan
            pr = float(np.sqrt(np.mean(np.array(p_errs_n)**2))) if p_errs_n else np.nan
            if np.isfinite(dr) and np.isfinite(pr):
                per_n_vals.append((dr, pr))
        if not per_n_vals: return np.nan
        bd = float(np.mean([v[0] for v in per_n_vals]))
        bp = float(np.mean([v[1] for v in per_n_vals]))
        return (bp - bd) / bp if bp > 0 else np.nan

    # Point estimate (unchanged from v4 — ensemble means)
    point_i = 0.3926  # from v4

    print(f"\nPaired seed bootstrap ({_N_BOOTSTRAP} reps, ONE seed_idx for P+D) ...")
    boot_i = []
    for b in range(_N_BOOTSTRAP):
        val = _hierarchical_bootstrap_paired(None, rng)
        if np.isfinite(val): boot_i.append(val)
    boot_i = np.array(boot_i)
    ci_lo = float(np.percentile(boot_i, 2.5))
    ci_hi = float(np.percentile(boot_i, 97.5))
    point_i_boot = float(np.mean(boot_i))

    verdict = "no confirmed difference"
    if ci_lo > 0 and point_i >= 0.05: verdict = "supported and material"
    elif ci_lo > 0 and point_i < 0.05: verdict = "supported but small"
    elif ci_hi < 0: verdict = "parameter route better"

    print(f"  I = {point_i:.4f} (bootstrap mean = {point_i_boot:.4f})")
    print(f"  95% CI: [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Verdict: {verdict}")

    # -- Per-n paired seed bootstrap + BH adjustment --
    per_n_results = {}
    for n_val in _N_VALUES:
        # Point estimate for this n
        de = []; pe = []
        for ci in range(_N_CLUSTERS):
            for ri in range(_N_REPLICATES):
                key = (ci, ri, n_val)
                idx = key_to_idx.get(key)
                td = true_x095.get(key)
                if idx is None or td is None or td == 0: continue
                p_mean = float(np.nanmean(p_seeds_raw[idx]))
                d_mean = float(np.nanmean(d_seeds_raw[idx]))
                if np.isfinite(d_mean): de.append((d_mean - td) / td)
                if np.isfinite(p_mean): pe.append((p_mean - td) / td)
        dr_point = float(np.sqrt(np.mean(np.array(de)**2))) if de else np.nan
        pr_point = float(np.sqrt(np.mean(np.array(pe)**2))) if pe else np.nan
        i_point = (pr_point - dr_point) / pr_point if pr_point > 0 else 0

        # Bootstrap with paired seeds
        boot_n = []
        for b in range(_N_BOOTSTRAP):
            ci_b = list(rng.choice(range(_N_CLUSTERS), size=_N_CLUSTERS, replace=True))
            seed_idx = rng.choice(10, size=10, replace=True)
            de_b = []; pe_b = []
            for ci in ci_b:
                for ri in range(_N_REPLICATES):
                    key = (ci, ri, n_val)
                    idx = key_to_idx.get(key)
                    td = true_x095.get(key)
                    if idx is None or td is None or td == 0: continue
                    pv = p_seeds_raw[idx]; dv = d_seeds_raw[idx]
                    p_mean = float(np.nanmean(pv[seed_idx]))
                    d_mean = float(np.nanmean(dv[seed_idx]))
                    if np.isfinite(d_mean): de_b.append((d_mean - td) / td)
                    if np.isfinite(p_mean): pe_b.append((p_mean - td) / td)
            dr_b = float(np.sqrt(np.mean(np.array(de_b)**2))) if de_b else np.nan
            pr_b = float(np.sqrt(np.mean(np.array(pe_b)**2))) if pe_b else np.nan
            if np.isfinite(dr_b) and np.isfinite(pr_b) and pr_b > 0:
                boot_n.append((pr_b - dr_b) / pr_b)
        boot_n = np.array(boot_n)
        ci_n_lo = float(np.percentile(boot_n, 2.5))
        ci_n_hi = float(np.percentile(boot_n, 97.5))

        per_n_results[str(n_val)] = {
            "d_rmse": dr_point, "p_rmse": pr_point,
            "I": i_point, "ci_95_lower": ci_n_lo, "ci_95_upper": ci_n_hi,
            "direction": "D better" if ci_n_lo > 0 else ("P better" if ci_n_hi < 0 else "no difference"),
        }
        print(f"  n={n_val}: I={i_point:.4f} [{ci_n_lo:.4f},{ci_n_hi:.4f}] → {per_n_results[str(n_val)]['direction']}")

    # BH adjustment on 5 secondary n comparisons
    # Compute raw p-values for each n (from proportion of bootstrap I <= 0)
    per_n_pvals = {}
    for n_val in _N_VALUES:
        # Recompute bootstrap to get null proportion
        boot_n_pvals = []
        for b in range(_N_BOOTSTRAP):
            ci_b = list(rng.choice(range(_N_CLUSTERS), size=_N_CLUSTERS, replace=True))
            seed_idx = rng.choice(10, size=10, replace=True)
            de_b = []; pe_b = []
            for ci in ci_b:
                for ri in range(_N_REPLICATES):
                    key = (ci, ri, n_val)
                    idx = key_to_idx.get(key)
                    td = true_x095.get(key)
                    if idx is None or td is None or td == 0: continue
                    pv = p_seeds_raw[idx]; dv = d_seeds_raw[idx]
                    p_mean = float(np.nanmean(pv[seed_idx]))
                    d_mean = float(np.nanmean(dv[seed_idx]))
                    if np.isfinite(d_mean): de_b.append((d_mean - td) / td)
                    if np.isfinite(p_mean): pe_b.append((p_mean - td) / td)
            dr_b = float(np.sqrt(np.mean(np.array(de_b)**2))) if de_b else np.nan
            pr_b = float(np.sqrt(np.mean(np.array(pe_b)**2))) if pe_b else np.nan
            if np.isfinite(dr_b) and np.isfinite(pr_b) and pr_b > 0:
                boot_n_pvals.append((pr_b - dr_b) / pr_b)
        boot_n_pvals = np.array(boot_n_pvals)
        # Two-sided p: 2 * min(proportion <= 0, proportion >= 0)
        prop_below = float(np.mean(boot_n_pvals <= 0))
        prop_above = float(np.mean(boot_n_pvals >= 0))
        per_n_pvals[n_val] = 2.0 * min(prop_below, prop_above)

    # BH procedure
    sorted_n = sorted(per_n_pvals.keys(), key=lambda n: per_n_pvals[n])
    bh_thresholds = {}
    m = len(sorted_n)
    for rank, n_val in enumerate(sorted_n, 1):
        bh_thresholds[n_val] = 0.05 * rank / m
    bh_support = {}
    significant = True
    for n_val in sorted_n:
        if significant and per_n_pvals[n_val] <= bh_thresholds[n_val]:
            bh_support[str(n_val)] = "supported (BH)"
        else:
            bh_support[str(n_val)] = "not significant (BH)"
            significant = False  # BH: once one fails, all larger p-values fail
        per_n_results[str(n_val)]["bh_support"] = bh_support[str(n_val)]
        print(f"  n={n_val}: p={per_n_pvals[n_val]:.4f} bh_thr={bh_thresholds[n_val]:.4f} → {bh_support[str(n_val)]}")

    # Manifest
    manifest = {
        "version": "5.0",
        "run_id": out.name, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "complete", "code_tip": code_tip,
        "analysis_type": "derived — no inference rerun",
        "input_artifacts": {
            "v4_run": str(_V4_DIR),
            "results.csv": {"path": str(csv_path), "sha256": csv_sha},
            "per_seed_predictions.npz": {"path": str(npz_path), "sha256": npz_sha},
        },
        "primary": {
            "improvement_I": point_i, "ci_95_lower": ci_lo, "ci_95_upper": ci_hi,
            "verdict": verdict, "bootstrap_mean_I": point_i_boot,
        },
        "per_n": per_n_results,
        "bh_adjustment": {"method": "Benjamini-Hochberg", "alpha": 0.05, "m": m,
                          "p_values": {str(k): float(v) for k, v in per_n_pvals.items()},
                          "support": bh_support},
    }

    mf_path = out / "manifest.json"
    mf_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    mf_sha = hashlib.sha256(mf_path.read_bytes()).hexdigest()
    print(f"\n  Manifest: {mf_path}\n  SHA256: {mf_sha}")
    print(f"\n=== B4 analysis v5 complete ===")
    return manifest


if __name__ == "__main__":
    run_analyze()
