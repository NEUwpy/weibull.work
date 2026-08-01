"""B4: Core test evaluation on 6,400 frozen paired datasets.

Routes: P, D, controlled-D, MDM, MLE, LRE.
Primary: D vs P x0.95 improvement with 95% CI via paired cluster bootstrap.
Outputs row-level CSV + summary JSON to external run directory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

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
from studies.common.metrics import quantile_true, summarize_standard_errors
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


def _git_tip() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           text=True, timeout=5, cwd=str(_REPO_ROOT))
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


# -- Test data generation with true values --

@dataclass
class TestDataset:
    sample: np.ndarray
    beta: float
    eta: float
    gamma: float
    true_x095: float


def generate_test_data() -> dict[tuple[int, int, int], TestDataset]:
    """64 Sobol clusters 脳 20 reps 脳 5 n = 6400 datasets with true x0.95."""
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
                sample = generate_sample(beta, eta, gamma, n, ri,
                                         seed=_SEED_TEST_NS + ci)
                x095 = quantile_true(beta, eta, gamma, 0.95)
                datasets[(ci, ri, n)] = TestDataset(
                    sample=sample, beta=beta, eta=eta, gamma=gamma,
                    true_x095=x095,
                )
                count += 1
                if count % 1000 == 0:
                    print(f"  Generated {count}/{total} test datasets")
    return datasets


# -- Model loading --

def _load_ckpt(path, model_factory):
    state = load_checkpoint(Path(path).read_bytes())
    model = model_factory()
    model.load_state_dict(state)
    model.eval()
    return model


def load_all_models(b3_manifest: dict) -> dict:
    """Load P, D, controlled-D models from B3 manifest. Returns lookup dicts."""
    ts = b3_manifest.get("target_stats", {})

    # P models: 3-output m12
    p_models: dict[tuple[int, int], any] = {}
    for e in b3_manifest["p_checkpoints"]["entries"]:
        nv, seed = e["n"], e["seed"]
        p_models[(nv, seed)] = _load_ckpt(
            e["path"], lambda n=nv: build_mlp(n, [256, 128, 64], "silu", 0.1))

    # D models
    def _load_group(group):
        models = {}
        for e in b3_manifest["d_checkpoints"]:
            if e["group"] != group:
                continue
            nv, seed, widths = e["n"], e["seed"], e["widths"]
            s = ts.get(str(nv), {})
            stats = DTrainingStats(mean=s.get("mean", 0.0), sd=s.get("sd", 1.0))
            models[(nv, seed)] = (
                _load_ckpt(e["path"], lambda n=nv, w=widths: build_d_mlp(n, w, "silu", 0.1)),
                stats,
            )
        return models

    return {
        "P": p_models,
        "D": _load_group("selected"),
        "Dctrl": _load_group("controlled"),
    }


# -- Inference --

def _infer_p(model, sample):
    anchor = anchor_sample(sample)
    z = torch.from_numpy(anchor.z.astype(np.float32)).unsqueeze(0)
    with torch.no_grad():
        raw = model(z)
    decoded = decode_model_output(
        raw,
        torch.tensor([anchor.location], dtype=torch.float32),
        torch.tensor([anchor.scale], dtype=torch.float32),
    )
    bf, ef, gf = float(decoded[0, 0]), float(decoded[0, 1]), float(decoded[0, 2])
    if bf <= 0 or ef <= 0 or not all(np.isfinite([bf, ef, gf])):
        return np.nan
    return quantile_true(bf, ef, gf, 0.95)


def _infer_d(model, stats, sample):
    anchor = anchor_sample(sample)
    z = torch.from_numpy(anchor.z.astype(np.float32)).unsqueeze(0)
    with torch.no_grad():
        raw = float(model(z).item())
    enc = unstandardize_d(np.array([raw]), stats)[0]
    return decode_d_target(enc, anchor)


def _infer_traditional(method_id, kwargs, sample):
    r = run_method(method_id, sample, **kwargs)
    bh, eh, gh = r["beta_hat"], r["eta_hat"], r["gamma_hat"]
    if bh is None or eh is None or gh is None:
        return np.nan
    return quantile_true(float(bh), float(eh), float(gh), 0.95)


# -- Main evaluation --

def run_b4(output_dir: str | None = None) -> dict:
    if output_dir is None:
        rid = f"B4-core-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        output_dir = str(_EXTERNAL_ROOT / rid)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    code_tip = _git_tip()

    print(f"=== B4 Core Test ===")
    print(f"Output: {out}")
    print(f"Code tip: {code_tip}")

    # 1. Load B3 manifest and models
    print("\n[1/5] Loading B3 manifest and models ...")
    b3 = json.loads(_B3_MANIFEST_PATH.read_text(encoding="utf-8"))
    b3_sha = hashlib.sha256(_B3_MANIFEST_PATH.read_bytes()).hexdigest()
    print(f"  B3 manifest SHA256: {b3_sha}")
    models = load_all_models(b3)
    print(f"  P: {len(models['P'])} models")
    print(f"  D: {len(models['D'])} models")
    print(f"  Dctrl: {len(models['Dctrl'])} models")

    # 2. Generate test data
    print(f"\n[2/5] Generating {_N_CLUSTERS*_N_REPLICATES*len(_N_VALUES)} test datasets ...")
    datasets = generate_test_data()

    # 3. Evaluate all routes
    print("\n[3/5] Evaluating routes ...")
    routes = {}

    # P route
    print("  P route ...")
    p_preds = {}
    count = 0
    total = len(datasets)
    for (ci, ri, n), td in datasets.items():
        seeds = [s for (ns, s) in models["P"] if ns == n]
        vals = [_infer_p(models["P"][(n, s)], td.sample) for s in seeds]
        p_preds[(ci, ri, n)] = np.array(vals)
        count += 1
        if count % 1000 == 0:
            print(f"    P: {count}/{total}")
    routes["P"] = p_preds

    # D route
    for label, key in [("D", "D"), ("Dctrl", "Dctrl")]:
        print(f"  {label} route ...")
        preds = {}
        count = 0
        for (ci, ri, n), td in datasets.items():
            seeds_data = [(s, m, st) for (ns, s), (m, st) in models[key].items() if ns == n]
            vals = [_infer_d(m, st, td.sample) for _, m, st in seeds_data]
            preds[(ci, ri, n)] = np.array(vals)
            count += 1
            if count % 1000 == 0:
                print(f"    {label}: {count}/{total}")
        routes[label] = preds

    # Traditional routes
    for method_id, kwargs, label in [("mdm", {"offset": 0.1}, "MDM"),
                                       ("mle", {}, "MLE"),
                                       ("lre", {}, "LRE")]:
        print(f"  {label} route ...")
        preds = {}
        count = 0
        for (ci, ri, n), td in datasets.items():
            preds[(ci, ri, n)] = np.array([_infer_traditional(method_id, kwargs, td.sample)])
            count += 1
            if count % 1000 == 0:
                print(f"    {label}: {count}/{total}")
        routes[label] = preds

    # 4. Compute metrics per route
    print("\n[4/5] Computing metrics ...")
    route_names = ["P", "D", "Dctrl", "MDM", "MLE", "LRE"]

    # Per-route relative errors
    per_route_errors: dict[str, dict[tuple, np.ndarray]] = {}
    for name in route_names:
        per_route_errors[name] = {}

    csv_rows = []
    for (ci, ri, n), td in datasets.items():
        row = {
            "cluster": ci, "replicate": ri, "n": n,
            "beta": td.beta, "eta": td.eta, "gamma": td.gamma,
            "true_x095": td.true_x095,
        }
        for name in route_names:
            vals = routes[name].get((ci, ri, n), np.array([np.nan]))
            mean_val = float(np.nanmean(vals))
            err = (mean_val - td.true_x095) / td.true_x095 if td.true_x095 != 0 else np.nan
            row[f"{name}_mean"] = mean_val
            row[f"{name}_rel_err"] = err
            per_route_errors[name].setdefault((ci, n), []).append(err)
        csv_rows.append(row)

    # Write CSV
    csv_path = out / "results.csv"
    fieldnames = ["cluster", "replicate", "n", "beta", "eta", "gamma", "true_x095"]
    for name in route_names:
        fieldnames.extend([f"{name}_mean", f"{name}_rel_err"])
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(csv_rows)
    csv_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    print(f"  CSV: {csv_path} ({len(csv_rows)} rows, SHA256: {csv_sha[:16]}...)")

    # Compute per-route summaries (pooled core)
    summaries = {}
    for name in route_names:
        all_errs = []
        n_fail = 0
        for (ci, n), errs in per_route_errors[name].items():
            finite = [e for e in errs if np.isfinite(e)]
            all_errs.extend(finite)
            n_fail += len(errs) - len(finite)
        summary = summarize_standard_errors(all_errs)
        summary["n_failure"] = n_fail
        summaries[name] = summary
        print(f"  {name}: n={summary.get('n',0)} rmse={summary.get('rmse',np.nan):.6f} "
              f"failures={n_fail}")

    # 5. Bootstrap D vs P improvement
    print(f"\n[5/5] Bootstrap ({_N_BOOTSTRAP} reps) ...")
    rng = np.random.default_rng(42)
    cluster_ids = list(range(_N_CLUSTERS))

    # Per-cluster, per-n RMSE
    cluster_d_rmse = np.zeros((_N_CLUSTERS, len(_N_VALUES)))
    cluster_p_rmse = np.zeros((_N_CLUSTERS, len(_N_VALUES)))
    cluster_dctrl_rmse = np.zeros((_N_CLUSTERS, len(_N_VALUES)))

    for ci in range(_N_CLUSTERS):
        for ni, n in enumerate(_N_VALUES):
            d_errs = [e for e in per_route_errors["D"].get((ci, n), []) if np.isfinite(e)]
            p_errs = [e for e in per_route_errors["P"].get((ci, n), []) if np.isfinite(e)]
            dc_errs = [e for e in per_route_errors["Dctrl"].get((ci, n), []) if np.isfinite(e)]
            # Relative errors → absolute RMSE = sqrt(mean(rel_err^2))
            # Pool: equal weight per n
            cluster_d_rmse[ci, ni] = np.sqrt(np.mean(np.array(d_errs) ** 2)) if d_errs else np.nan
            cluster_p_rmse[ci, ni] = np.sqrt(np.mean(np.array(p_errs) ** 2)) if p_errs else np.nan
            cluster_dctrl_rmse[ci, ni] = np.sqrt(np.mean(np.array(dc_errs) ** 2)) if dc_errs else np.nan

    # Bootstrap I = (RMSE_P - RMSE_D) / RMSE_P, equal 5-n weight
    def _pooled_rmse(cluster_rmse):
        valid = cluster_rmse[~np.isnan(cluster_rmse).any(axis=1)]
        return float(np.mean(valid))

    pooled_d = _pooled_rmse(cluster_d_rmse)
    pooled_p = _pooled_rmse(cluster_p_rmse)
    pooled_dctrl = _pooled_rmse(cluster_dctrl_rmse)
    point_i = (pooled_p - pooled_d) / pooled_p if pooled_p > 0 else 0.0

    boot_i = []
    for _ in range(_N_BOOTSTRAP):
        idx = rng.choice(cluster_ids, size=_N_CLUSTERS, replace=True)
        bd = _pooled_rmse(cluster_d_rmse[idx])
        bp = _pooled_rmse(cluster_p_rmse[idx])
        if bp > 0 and np.isfinite(bd) and np.isfinite(bp):
            boot_i.append((bp - bd) / bp)

    boot_i = np.array(boot_i)
    ci_lo = float(np.percentile(boot_i, 2.5))
    ci_hi = float(np.percentile(boot_i, 97.5))

    verdict = "no confirmed difference"
    if ci_lo > 0 and point_i >= 0.05:
        verdict = "supported and material"
    elif ci_lo > 0 and point_i < 0.05:
        verdict = "supported but small"
    elif ci_hi < 0:
        verdict = "parameter route better"

    print(f"\n  Pooled rel RMSE: P={pooled_p:.6f} D={pooled_d:.6f} Dctrl={pooled_dctrl:.6f}")
    print(f"  I = {point_i:.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Verdict: {verdict}")

    # 6. Manifest
    manifest = {
        "version": "1.0",
        "run_id": out.name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "complete",
        "code_tip": code_tip,
        "b3_manifest_sha256": b3_sha,
        "design": {
            "n_clusters": _N_CLUSTERS,
            "n_replicates": _N_REPLICATES,
            "n_values": _N_VALUES,
            "total_datasets": len(datasets),
            "seed_test_namespace": _SEED_TEST_NS,
            "bootstrap_replicates": _N_BOOTSTRAP,
        },
        "primary": {
            "improvement_I": point_i,
            "ci_95_lower": ci_lo,
            "ci_95_upper": ci_hi,
            "pooled_rmse_P": pooled_p,
            "pooled_rmse_D": pooled_d,
            "pooled_rmse_Dctrl": pooled_dctrl,
            "verdict": verdict,
        },
        "per_route": summaries,
        "outputs": {
            "results.csv": {
                "path": str(csv_path),
                "sha256": csv_sha,
                "rows": len(csv_rows),
            },
        },
    }

    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    mf_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    print(f"\n  Manifest: {manifest_path}")
    print(f"  Manifest SHA256: {mf_sha}")

    print(f"\n=== B4 complete ===")
    return manifest


if __name__ == "__main__":
    run_b4()
