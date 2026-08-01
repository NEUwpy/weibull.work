"""B4: Core test evaluation — preregistered estimator with paired seed bootstrap.

v2: per-row RMSE aggregator, paired seed-index resampling in cluster bootstrap,
traditional-method validity checking, per-n metrics, D-vs-traditional paired effects.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from scipy.stats import qmc

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

from studies.common.sample import generate_sample
from studies.common.metrics import (
    quantile_true, summarize_standard_errors,
    summarize_relative_errors, check_status,
)
from studies.common.runner import run_method
from study02a.models import build_mlp, decode_model_output
from study02a.representations import anchor_sample
from study02a.training import load_checkpoint
from study02b.representations import decode_d_target, unstandardize_d, DTrainingStats
from study02b.training import build_d_mlp

_EXTERNAL_ROOT = Path("C:/weibull-runs/study02/formal-b")
_B3_MANIFEST_PATH = Path("C:/weibull-runs/study02/formal-b/B3-training-20260731-121958/manifest.json")

_N_CLUSTERS = 64
_N_REPLICATES = 20
_N_VALUES = [5, 7, 10, 15, 20]
_N_BOOTSTRAP = 2000
_SEED_TEST_NS = 6000

_P_SEEDS = list(range(420101, 420111))   # 10 P training seeds
_D_SEEDS = list(range(101, 111))          # 10 D training seeds
_DCTRL_SEEDS = list(range(201, 206))      # 5 Dctrl training seeds


def _git_tip() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           text=True, timeout=5, cwd=str(_REPO_ROOT))
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


@dataclass
class TestDataset:
    sample: np.ndarray
    beta: float; eta: float; gamma: float
    true_x095: float


def generate_test_data() -> dict[tuple[int, int, int], TestDataset]:
    sampler = qmc.Sobol(d=3, scramble=True, seed=42)
    points = sampler.random_base2(m=6)
    betas = 1.2 + points[:, 0] * (4.0 - 1.2)
    etas = 100.0 + points[:, 1] * (10000.0 - 100.0)
    rhos = points[:, 2]
    gammas = rhos * etas
    params = [(float(b), float(e), float(g)) for b, e, g in zip(betas, etas, gammas)]
    datasets = {}
    total = _N_CLUSTERS * _N_REPLICATES * len(_N_VALUES)
    count = 0
    for ci, (beta, eta, gamma) in enumerate(params):
        for ri in range(_N_REPLICATES):
            for n in _N_VALUES:
                sample = generate_sample(beta, eta, gamma, n, ri, seed=_SEED_TEST_NS + ci)
                x095 = quantile_true(beta, eta, gamma, 0.95)
                datasets[(ci, ri, n)] = TestDataset(sample=sample, beta=beta, eta=eta, gamma=gamma, true_x095=x095)
                count += 1
                if count % 1000 == 0:
                    print(f"  Generated {count}/{total} test datasets")
    return datasets


# -- Model loading --

def load_all_models(b3_manifest: dict) -> dict:
    ts = b3_manifest.get("target_stats", {})
    p_models = {}
    for e in b3_manifest["p_checkpoints"]["entries"]:
        nv, seed = e["n"], e["seed"]
        p_models[(nv, seed)] = _load_ckpt(e["path"], lambda n=nv: build_mlp(n, [256, 128, 64], "silu", 0.1))

    def _load_group(group):
        models = {}
        for e in b3_manifest["d_checkpoints"]:
            if e["group"] != group: continue
            nv, seed, widths = e["n"], e["seed"], e["widths"]
            s = ts.get(str(nv), {})
            stats = DTrainingStats(mean=s.get("mean", 0.0), sd=s.get("sd", 1.0))
            models[(nv, seed)] = (_load_ckpt(e["path"], lambda n=nv, w=widths: build_d_mlp(n, w, "silu", 0.1)), stats)
        return models

    return {"P": p_models, "D": _load_group("selected"), "Dctrl": _load_group("controlled")}


def _load_ckpt(path, factory):
    state = load_checkpoint(Path(path).read_bytes())
    m = factory(); m.load_state_dict(state); m.eval()
    return m


# -- Per-seed inference (returns arrays of length n_seeds) --

def _infer_p_all(models_dict, n_val, sample) -> np.ndarray:
    seeds = [s for (ns, s) in models_dict if ns == n_val]
    vals = []
    anchor = anchor_sample(sample)
    z = torch.from_numpy(anchor.z.astype(np.float32)).unsqueeze(0)
    for s in seeds:
        with torch.no_grad():
            raw = models_dict[(n_val, s)](z)
        dec = decode_model_output(raw, torch.tensor([anchor.location], dtype=torch.float32), torch.tensor([anchor.scale], dtype=torch.float32))
        bf, ef, gf = float(dec[0,0]), float(dec[0,1]), float(dec[0,2])
        if bf <= 0 or ef <= 0 or not all(np.isfinite([bf, ef, gf])):
            vals.append(np.nan)
        else:
            vals.append(quantile_true(bf, ef, gf, 0.95))
    return np.array(vals)


def _infer_d_all(models_dict, n_val, sample) -> np.ndarray:
    items = [(s, m, st) for (ns, s), (m, st) in models_dict.items() if ns == n_val]
    vals = []
    anchor = anchor_sample(sample)
    z = torch.from_numpy(anchor.z.astype(np.float32)).unsqueeze(0)
    for _, model, stats in items:
        with torch.no_grad():
            raw = float(model(z).item())
        enc = unstandardize_d(np.array([raw]), stats)[0]
        vals.append(decode_d_target(enc, anchor))
    return np.array(vals)


# -- Traditional with validity --

def _infer_traditional(method_id, kwargs, sample, beta, eta, gamma):
    """Returns (x095_pred, status) where status is 'success' or 'failure'."""
    r = run_method(method_id, sample, **kwargs)
    bh, eh, gh = r["beta_hat"], r["eta_hat"], r["gamma_hat"]
    conv = r.get("converged", True)
    if bh is None or eh is None or gh is None:
        return np.nan, "failure"
    status = check_status(float(bh), float(eh), float(gh), beta, eta, gamma,
                          converged=conv, sample_min=float(sample.min()))
    if status == "failure":
        return np.nan, "failure"
    return quantile_true(float(bh), float(eh), float(gh), 0.95), "success"


# -- Main evaluation --

def run_b4(output_dir: str | None = None) -> dict:
    if output_dir is None:
        rid = f"B4-core-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        output_dir = str(_EXTERNAL_ROOT / rid)
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    code_tip = _git_tip()
    print(f"=== B4 Core Test v2 ===")
    print(f"Output: {out}"); print(f"Code tip: {code_tip}")

    print("\n[1/5] Loading models ...")
    b3 = json.loads(_B3_MANIFEST_PATH.read_text(encoding="utf-8"))
    b3_sha = hashlib.sha256(_B3_MANIFEST_PATH.read_bytes()).hexdigest()
    models = load_all_models(b3)
    print(f"  P:{len(models['P'])} D:{len(models['D'])} Dctrl:{len(models['Dctrl'])}")

    print(f"\n[2/5] Generating {_N_CLUSTERS*_N_REPLICATES*len(_N_VALUES)} test datasets ...")
    datasets = generate_test_data()

    # Per-seed predictions storage
    # p_seed_preds[(ci, ri, n)] = array of 10 values
    # d_seed_preds[(ci, ri, n)] = array of 10 values
    # dctrl_seed_preds[(ci, ri, n)] = array of 5 values
    print("\n[3/5] Evaluating routes (per-seed predictions) ...")

    p_seed = {}
    d_seed = {}
    dctrl_seed = {}
    trad_preds: dict[str, dict] = {name: {} for name in ["MDM", "MLE", "LRE"]}
    trad_status: dict[str, dict] = {name: {} for name in ["MDM", "MLE", "LRE"]}

    total = len(datasets)
    count = 0
    for (ci, ri, n), td in datasets.items():
        p_seed[(ci, ri, n)] = _infer_p_all(models["P"], n, td.sample)
        d_seed[(ci, ri, n)] = _infer_d_all(models["D"], n, td.sample)
        dctrl_seed[(ci, ri, n)] = _infer_d_all(models["Dctrl"], n, td.sample)
        for mid, kw, lbl in [("mdm", {"offset": 0.1}, "MDM"), ("mle", {}, "MLE"), ("lre", {}, "LRE")]:
            pred, status = _infer_traditional(mid, kw, td.sample, td.beta, td.eta, td.gamma)
            trad_preds[lbl][(ci, ri, n)] = pred
            trad_status[lbl][(ci, ri, n)] = status
        count += 1
        if count % 1000 == 0:
            print(f"  {count}/{total}")

    # Collapse to ensemble means for summary statistics
    print("\n[4/5] Computing metrics ...")

    def _ens_mean(d, key): return float(np.nanmean(d[key]))

    # Per-route per-row relative errors (ensemble mean)
    route_errs = {name: {} for name in ["P", "D", "Dctrl", "MDM", "MLE", "LRE"]}
    for (ci, ri, n), td in datasets.items():
        route_errs["P"][(ci, ri, n)] = (_ens_mean(p_seed, (ci, ri, n)) - td.true_x095) / td.true_x095
        route_errs["D"][(ci, ri, n)] = (_ens_mean(d_seed, (ci, ri, n)) - td.true_x095) / td.true_x095
        route_errs["Dctrl"][(ci, ri, n)] = (_ens_mean(dctrl_seed, (ci, ri, n)) - td.true_x095) / td.true_x095
        for lbl in ["MDM", "MLE", "LRE"]:
            pv = trad_preds[lbl].get((ci, ri, n), np.nan)
            if np.isfinite(pv):
                route_errs[lbl][(ci, ri, n)] = (pv - td.true_x095) / td.true_x095
            else:
                route_errs[lbl][(ci, ri, n)] = np.nan

    # Per-n summaries
    per_n = {}
    for lbl in ["P", "D", "Dctrl", "MDM", "MLE", "LRE"]:
        per_n[lbl] = {}
        for n in _N_VALUES:
            errs = [route_errs[lbl].get((ci, ri, n), np.nan)
                    for ci in range(_N_CLUSTERS) for ri in range(_N_REPLICATES)]
            valid = [e for e in errs if np.isfinite(e)]
            s = summarize_standard_errors(valid)
            s["n_failure"] = len(errs) - len(valid)
            per_n[lbl][str(n)] = s

    # Write CSV
    csv_path = out / "results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        cols = ["cluster", "replicate", "n", "beta", "eta", "gamma", "true_x095"]
        for lbl in ["P", "D", "Dctrl", "MDM", "MLE", "LRE"]:
            cols.extend([f"{lbl}_mean", f"{lbl}_rel_err"])
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for (ci, ri, n), td in datasets.items():
            row = {"cluster": ci, "replicate": ri, "n": n,
                   "beta": td.beta, "eta": td.eta, "gamma": td.gamma, "true_x095": td.true_x095}
            for lbl in ["P", "D", "Dctrl"]:
                row[f"{lbl}_mean"] = _ens_mean({"x": locals()[f"{lbl.lower()}_seed"][(ci, ri, n)]}, "x") if lbl != "MDM" else 0
            # simpler:
            row["P_mean"] = _ens_mean(p_seed, (ci, ri, n))
            row["P_rel_err"] = route_errs["P"].get((ci, ri, n), np.nan)
            row["D_mean"] = _ens_mean(d_seed, (ci, ri, n))
            row["D_rel_err"] = route_errs["D"].get((ci, ri, n), np.nan)
            row["Dctrl_mean"] = _ens_mean(dctrl_seed, (ci, ri, n))
            row["Dctrl_rel_err"] = route_errs["Dctrl"].get((ci, ri, n), np.nan)
            for lbl in ["MDM", "MLE", "LRE"]:
                row[f"{lbl}_mean"] = trad_preds[lbl].get((ci, ri, n), np.nan)
                row[f"{lbl}_rel_err"] = route_errs[lbl].get((ci, ri, n), np.nan)
            w.writerow(row)
    csv_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()

    # Pooled summaries (valid rows only)
    summaries = {}
    for lbl in ["P", "D", "Dctrl", "MDM", "MLE", "LRE"]:
        errs = [v for v in route_errs[lbl].values() if np.isfinite(v)]
        n_fail = sum(1 for v in route_errs[lbl].values() if not np.isfinite(v))
        s = summarize_standard_errors(errs)
        s["n_failure"] = n_fail
        summaries[lbl] = s
        print(f"  {lbl}: n={s.get('n',0)} rmse={s.get('rmse',np.nan):.6f} failures={n_fail}")

    # --- Bootstrap D vs P ---
    print(f"\n[5/5] Bootstrap ({_N_BOOTSTRAP} reps) with paired seed resampling ...")

    # Pre-compute per-row and per-seed P/D errors (not collapsed)
    # For each dataset: 10 P seeds, 10 D seeds
    # Point estimate: RMSE over all rows within each n, equal weight
    rng = np.random.default_rng(42)

    def _per_n_rmse_d_vs_p(ci_mask, ri_mask, p_dict, d_dict):
        """RMSE within one n: RMSE = sqrt(mean((d_mean - true)^2)) etc.
        Returns (rmse_d, rmse_p) for this n subset."""
        d_errs = []; p_errs = []
        for ci in ci_mask:
            for ri in ri_mask:
                key = (ci, ri, n_val)
                d_vals = d_dict.get(key, np.array([np.nan]))
                p_vals = p_dict.get(key, np.array([np.nan]))
                td = datasets.get(key)
                if td is None: continue
                d_mean = float(np.nanmean(d_vals))
                p_mean = float(np.nanmean(p_vals))
                if np.isfinite(d_mean):
                    d_errs.append(d_mean - td.true_x095)
                if np.isfinite(p_mean):
                    p_errs.append(p_mean - td.true_x095)
        # Absolute RMSE (not relative) then divided by true mean later
        return d_errs, p_errs

    # Point estimate: equal weight across n
    point_per_n = {}
    for n_val in _N_VALUES:
        ci_all = list(range(_N_CLUSTERS))
        ri_all = list(range(_N_REPLICATES))
        d_errs, p_errs = _per_n_rmse_d_vs_p(ci_all, ri_all, d_seed, p_seed)
        d_rmse_abs = np.sqrt(np.mean(np.array(d_errs)**2)) if d_errs else np.nan
        p_rmse_abs = np.sqrt(np.mean(np.array(p_errs)**2)) if p_errs else np.nan
        # Convert to approximate "relative" by dividing by grand mean true_x095 for this n
        true_vals = [datasets[(ci, ri, n_val)].true_x095 for ci in ci_all for ri in ri_all]
        mean_true = np.mean(true_vals)
        point_per_n[n_val] = {
            "d_rmse": d_rmse_abs / mean_true, "p_rmse": p_rmse_abs / mean_true,
        }

    # Pool: equal weight per n
    pooled_d = float(np.mean([point_per_n[n]["d_rmse"] for n in _N_VALUES]))
    pooled_p = float(np.mean([point_per_n[n]["p_rmse"] for n in _N_VALUES]))
    point_i = (pooled_p - pooled_d) / pooled_p if pooled_p > 0 else 0.0

    # Bootstrap
    boot_i = []
    all_ci = list(range(_N_CLUSTERS))
    all_ri = list(range(_N_REPLICATES))
    for b in range(_N_BOOTSTRAP):
        # Resample clusters
        ci_boot = list(rng.choice(all_ci, size=_N_CLUSTERS, replace=True))
        # Within each cluster, resample replicates
        ri_boot = list(rng.choice(all_ri, size=_N_REPLICATES, replace=True))
        # Paired seed resampling: for each dataset, resample seed indices for P and D
        # (same seed indices for both routes = paired)
        per_n_vals = []
        for n_val in _N_VALUES:
            d_errs_b = []; p_errs_b = []
            for ci in ci_boot:
                for ri in ri_boot:
                    key = (ci, ri, n_val)
                    td = datasets.get(key)
                    if td is None: continue
                    # Paired seed resample: pick random seed indices (with replacement)
                    d_arr = d_seed.get(key, np.array([np.nan]))
                    p_arr = p_seed.get(key, np.array([np.nan]))
                    n_seeds = min(len(d_arr), len(p_arr))
                    if n_seeds == 0: continue
                    seed_idx = rng.choice(n_seeds, size=n_seeds, replace=True)
                    d_mean = float(np.nanmean(d_arr[seed_idx]))
                    p_mean = float(np.nanmean(p_arr[seed_idx]))
                    if np.isfinite(d_mean):
                        d_errs_b.append(d_mean - td.true_x095)
                    if np.isfinite(p_mean):
                        p_errs_b.append(p_mean - td.true_x095)
            d_rmse_b = np.sqrt(np.mean(np.array(d_errs_b)**2)) if d_errs_b else np.nan
            p_rmse_b = np.sqrt(np.mean(np.array(p_errs_b)**2)) if p_errs_b else np.nan
            true_vals_n = [datasets[(ci, ri, n_val)].true_x095 for ci in ci_boot for ri in ri_boot]
            mean_true_n = np.mean(true_vals_n)
            per_n_vals.append((d_rmse_b / mean_true_n, p_rmse_b / mean_true_n))
        # Equal weight per n
        bd = float(np.mean([v[0] for v in per_n_vals if np.isfinite(v[0])]))
        bp = float(np.mean([v[1] for v in per_n_vals if np.isfinite(v[1])]))
        if bp > 0 and np.isfinite(bd) and np.isfinite(bp):
            boot_i.append((bp - bd) / bp)

    boot_i = np.array(boot_i)
    ci_lo = float(np.percentile(boot_i, 2.5))
    ci_hi = float(np.percentile(boot_i, 97.5))

    verdict = "no confirmed difference"
    if ci_lo > 0 and point_i >= 0.05: verdict = "supported and material"
    elif ci_lo > 0 and point_i < 0.05: verdict = "supported but small"
    elif ci_hi < 0: verdict = "parameter route better"

    print(f"\n  Pooled rel RMSE: P={pooled_p:.6f} D={pooled_d:.6f}")
    print(f"  I = {point_i:.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Verdict: {verdict}")

    # D vs traditional paired effects (on shared valid rows)
    d_vs_trad = {}
    for lbl in ["MDM", "MLE", "LRE"]:
        shared_errs_d = []; shared_errs_t = []
        for key, td in datasets.items():
            de = route_errs["D"].get(key, np.nan)
            te = route_errs[lbl].get(key, np.nan)
            if np.isfinite(de) and np.isfinite(te):
                shared_errs_d.append(de); shared_errs_t.append(te)
        d_vs_trad[lbl] = {
            "n_shared": len(shared_errs_d),
            "d_rmse": float(np.sqrt(np.mean(np.array(shared_errs_d)**2))) if shared_errs_d else np.nan,
            "t_rmse": float(np.sqrt(np.mean(np.array(shared_errs_t)**2))) if shared_errs_t else np.nan,
            "d_mae": float(np.mean(np.abs(shared_errs_d))) if shared_errs_d else np.nan,
            "t_mae": float(np.mean(np.abs(shared_errs_t))) if shared_errs_t else np.nan,
        }

    # Manifest
    manifest = {
        "version": "2.0",
        "run_id": out.name, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "complete", "code_tip": code_tip,
        "b3_manifest_sha256": b3_sha,
        "design": {
            "n_clusters": _N_CLUSTERS, "n_replicates": _N_REPLICATES,
            "n_values": _N_VALUES, "total_datasets": len(datasets),
            "seed_test_namespace": _SEED_TEST_NS, "bootstrap_replicates": _N_BOOTSTRAP,
            "p_seeds": _P_SEEDS, "d_seeds": _D_SEEDS, "dctrl_seeds": _DCTRL_SEEDS,
        },
        "primary": {
            "improvement_I": point_i, "ci_95_lower": ci_lo, "ci_95_upper": ci_hi,
            "pooled_rmse_P": pooled_p, "pooled_rmse_D": pooled_d,
            "verdict": verdict,
        },
        "per_n": point_per_n,
        "per_route": summaries,
        "per_n_detail": per_n,
        "d_vs_traditional_paired": d_vs_trad,
        "outputs": {"results.csv": {"path": str(csv_path), "sha256": csv_sha, "rows": len(datasets)}},
    }
    mf_path = out / "manifest.json"
    mf_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    mf_sha = hashlib.sha256(mf_path.read_bytes()).hexdigest()
    print(f"\n  Manifest: {mf_path}\n  SHA256: {mf_sha}")
    print(f"\n=== B4 v2 complete ===")
    return manifest


if __name__ == "__main__":
    run_b4()
