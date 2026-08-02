"""Correct the original B4 core P evidence (R1).

The approved A-E1 V checkpoints were trained on scaler-standardized sorted-z,
but B4 fed raw sorted-z. This recomputes P per-seed predictions on the original
6,400 B4 rows using the A-E1 per-n input scaler (reconstructed from the frozen
A-E1 training caches), reuses the unchanged D/Dctrl per-seed predictions from
the frozen B4 npz, and re-derives the P-vs-D evidence (per-n I + CI, pooled,
BH) with the corrected paired-seed cluster bootstrap.

Output: a corrected summary written under the run dir's ``b4_correction``
folder, plus a per-seed npz with the corrected P columns. Does NOT mutate the
frozen B4 artifacts.

Usage:
    python -m study02b_inc.correct_b4 --out <run-dir>/b4_correction
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
import torch

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

from study02b_inc import config as C
from study02b_inc import data as D
from study02b_inc import a_data as A
from study02b_inc import models as M
from study02b_inc import evaluate_inc as E

B4_DIR = Path("C:/weibull-runs/study02/formal-b/B4-core-20260801-051119")
B4_N_VALUES = [5, 7, 10, 15, 20]


def _git_tip() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                       cwd=str(C.REPO_ROOT), timeout=5)
    return r.stdout.strip() or "unknown"


def _rmse(arr):
    a = np.asarray(arr, dtype=float)
    a = a[np.isfinite(a)]
    return float(np.sqrt(np.mean(a ** 2))) if a.size else np.nan


def run(out_dir: Path, n_boot: int = 2000) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load frozen B4 artifacts.
    b4_npz = np.load(B4_DIR / "per_seed_predictions.npz", allow_pickle=True)
    d_seeds_raw = b4_npz["d_seeds"]
    dc_seeds_raw = b4_npz["dctrl_seeds"]
    b4_keys = [str(k) for k in b4_npz["keys"]]
    with open(B4_DIR / "results.csv", newline="", encoding="utf-8") as f:
        b4_rows = {f"{r['cluster']}_{r['replicate']}_{r['n']}": r
                   for r in csv.DictReader(f)}
    assert len(b4_keys) == 6400 and len(b4_rows) == 6400

    # Regenerate the 6,400 B4 rows (deterministic, shared-n identical) and
    # recompute P per-seed with the A-E1 scaler.
    rows = D.generate_core_rows(n_values=B4_N_VALUES)
    assert len(rows) == 6400
    key_to_idx = {k: i for i, k in enumerate(b4_keys)}
    p_scalers = {}
    for n in B4_N_VALUES:
        p_scalers[n] = A.a_p_scaler_from_cache(n)

    p_index = M.build_p_index()
    models_by_n = {}
    for n in B4_N_VALUES:
        mods = []
        for e in p_index[n]:
            mods.append((e["seed"], (M.load_model("P", n, e["seed"], e), p_scalers[n])))
        models_by_n[n] = mods

    p_seeds_corr = np.full((6400, 10), np.nan, dtype=np.float32)
    for i, r in enumerate(rows):
        key = f"{r.meta['cluster']}_{r.meta['replicate']}_{r.n}"
        j = key_to_idx[key]
        arr = E._infer_p(models_by_n[r.n], r.sample)
        p_seeds_corr[j] = arr[:10]
    # D/Dctrl reuse unchanged from B4.
    np.savez_compressed(out_dir / "b4_corrected_per_seed.npz",
                        keys=np.array(b4_keys, dtype=object),
                        p_seeds=p_seeds_corr, d_seeds=d_seeds_raw,
                        dctrl_seeds=dc_seeds_raw)

    # Build corrected row-level relative errors (ensemble means).
    route_errs = {"P": {}, "D": {}, "Dctrl": {}}
    for key, r in b4_rows.items():
        j = key_to_idx[key]
        xt = float(r["true_x095"])
        for lbl, arr in (("P", p_seeds_corr[j]), ("D", d_seeds_raw[j]),
                         ("Dctrl", dc_seeds_raw[j])):
            m = float(np.nanmean(arr)) if np.isfinite(arr).any() else np.nan
            route_errs[lbl][key] = (m - xt) / xt if np.isfinite(m) else np.nan

    # Per-n point I + paired-seed hierarchical cluster bootstrap.
    rng = np.random.default_rng(C.BOOTSTRAP_SEED)
    per_n, p_vals = {}, {}
    for n in B4_N_VALUES:
        keys_n = [k for k in b4_rows if k.endswith(f"_{n}")]
        pe = np.array([route_errs["P"][k] for k in keys_n])
        de = np.array([route_errs["D"][k] for k in keys_n])
        pr, dr = _rmse(pe), _rmse(de)
        i_point = (pr - dr) / pr if pr > 0 else np.nan

        def _rep():
            ci_b = list(rng.choice(range(64), size=64, replace=True))
            seed_idx = rng.choice(10, size=10, replace=True)
            deb, peb = [], []
            for ci in ci_b:
                for ri in range(20):
                    k = f"{ci}_{ri}_{n}"
                    r = b4_rows.get(k)
                    if r is None:
                        continue
                    xt = float(r["true_x095"])
                    dv = d_seeds_raw[key_to_idx[k]]
                    pv = p_seeds_corr[key_to_idx[k]]
                    dm = float(np.nanmean(dv[seed_idx[:len(dv)]]))
                    pm = float(np.nanmean(pv[seed_idx[:len(pv)]]))
                    if np.isfinite(dm):
                        deb.append((dm - xt) / xt)
                    if np.isfinite(pm):
                        peb.append((pm - xt) / xt)
            drb, prb = _rmse(deb), _rmse(peb)
            return (prb - drb) / prb if prb > 0 else np.nan

        boot = np.array([v for v in (_rep() for _ in range(n_boot)) if np.isfinite(v)])
        lo = float(np.percentile(boot, 2.5))
        hi = float(np.percentile(boot, 97.5))
        per_n[str(n)] = {"I": i_point, "ci_lo": lo, "ci_hi": hi,
                         "P_rmse": pr, "D_rmse": dr,
                         "direction": ("D better" if lo > 0
                                       else ("P better" if hi < 0 else "no difference"))}
        p_vals[n] = 2.0 * min(float(np.mean(boot <= 0)), float(np.mean(boot >= 0)))

    # BH across 5 n.
    sorted_n = sorted(p_vals, key=lambda n: p_vals[n])
    m = len(sorted_n)
    largest = 0
    for rank, n in enumerate(sorted_n, 1):
        if p_vals[n] <= 0.05 * rank / m:
            largest = rank
    for rank, n in enumerate(sorted_n, 1):
        per_n[str(n)]["bh"] = "supported" if rank <= largest else "not_supported"

    p_eq = float(np.mean([per_n[str(n)]["P_rmse"] for n in B4_N_VALUES]))
    d_eq = float(np.mean([per_n[str(n)]["D_rmse"] for n in B4_N_VALUES]))

    summary = {
        "version": "1.0", "kind": "b4_correction", "code_tip": _git_tip(),
        "config_hash": C.CONFIG_HASH,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": ("Original B4 P predictions recomputed with the A-E1 input scaler; "
                 "D/Dctrl/traditional outputs reused unchanged from B4-core-20260801-051119. "
                 "B4's published P-vs-D evidence is superseded by this correction."),
        "input_b4": {"dir": str(B4_DIR), "npz_sha256": hashlib.sha256(
            (B4_DIR / "per_seed_predictions.npz").read_bytes()).hexdigest()},
        "per_n": per_n,
        "pooled_equal_per_n": {"P_rmse": p_eq, "D_rmse": d_eq,
                               "I": (p_eq - d_eq) / p_eq if p_eq > 0 else np.nan},
        "bh_adjustment": {"method": "Benjamini-Hochberg", "alpha": 0.05, "m": m},
    }
    (out_dir / "b4_correction_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary["per_n"], indent=1))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--bootstrap", type=int, default=2000)
    args = ap.parse_args()
    run(Path(args.out), n_boot=args.bootstrap)


if __name__ == "__main__":
    main()
