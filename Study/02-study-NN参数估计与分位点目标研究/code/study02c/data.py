"""Data loading and P-parameter inference for C2 (reuses frozen B artifacts).

Everything here consumes already-APPROVED B data:
- B4 core ``results.csv`` (6,400 paired rows)
- B4 ``per_seed_predictions.npz`` (per-seed x0.95 predictions)
- B3 manifest + frozen P checkpoints (only *inference*, no refit)

P parameter predictions were not persisted in B; we re-run deterministic
inference on the exact B4 test data to obtain per-seed (beta, eta, gamma).
No new training and no new test-data generation.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from scipy.stats import qmc

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in __import__("sys").path:
    import sys
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in __import__("sys").path:
    import sys
    sys.path.insert(0, str(_PYTHON))

from studies.common.sample import generate_sample
from studies.common.metrics import quantile_true
from study02a.models import build_mlp, decode_model_output
from study02a.representations import anchor_sample
from study02a.training import load_checkpoint

B_FORMAL = Path("C:/weibull-runs/study02/formal-b")
B3_MANIFEST = B_FORMAL / "B3-training-20260731-121958" / "manifest.json"
B4_RESULTS = B_FORMAL / "B4-core-20260801-051119" / "results.csv"
B4_NPZ = B_FORMAL / "B4-core-20260801-051119" / "per_seed_predictions.npz"
B5_V6_MANIFEST = B_FORMAL / "B5-v6-20260801-073535" / "manifest.json"

N_CLUSTERS, N_REPLICATES = 64, 20
N_VALUES = [5, 7, 10, 15, 20]
SEED_TEST_NS = 6000
P_SEEDS_PER_N = 10
D_SEEDS = 10
DCTRL_SEEDS = 5


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_b3_manifest() -> dict:
    return json.loads(B3_MANIFEST.read_text(encoding="utf-8"))


def load_b4_results() -> list[dict]:
    rows = []
    with open(B4_RESULTS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "cluster": int(r["cluster"]),
                "replicate": int(r["replicate"]),
                "n": int(r["n"]),
                "beta": float(r["beta"]),
                "eta": float(r["eta"]),
                "gamma": float(r["gamma"]),
                "true_x095": float(r["true_x095"]),
                "P_mean": float(r["P_mean"]),
                "P_rel_err": float(r["P_rel_err"]),
                "D_mean": float(r["D_mean"]),
                "D_rel_err": float(r["D_rel_err"]),
                "Dctrl_mean": float(r["Dctrl_mean"]),
                "Dctrl_rel_err": float(r["Dctrl_rel_err"]),
                "MDM_mean": float(r["MDM_mean"]) if r["MDM_mean"] else float("nan"),
                "MLE_mean": float(r["MLE_mean"]) if r["MLE_mean"] else float("nan"),
                "LRE_mean": float(r["LRE_mean"]) if r["LRE_mean"] else float("nan"),
            })
    return rows


def load_b4_npz() -> dict:
    d = np.load(B4_NPZ, allow_pickle=True)
    return {"keys": d["keys"], "p_seeds": d["p_seeds"], "d_seeds": d["d_seeds"],
            "dctrl_seeds": d["dctrl_seeds"]}


def row_key(row: dict) -> str:
    return f"{row['cluster']}_{row['replicate']}_{row['n']}"


def generate_test_data() -> dict[tuple[int, int, int], dict]:
    """Reproduce B4 test data exactly (Sobol 64 clusters x 20 reps x 5 n)."""
    sampler = qmc.Sobol(d=3, scramble=True, seed=42)
    pts = sampler.random_base2(m=6)
    betas = 1.2 + pts[:, 0] * (4.0 - 1.2)
    etas = 100.0 + pts[:, 1] * (10000.0 - 100.0)
    gammas = pts[:, 2] * etas
    datasets = {}
    for ci, (b, e, g) in enumerate(zip(betas, etas, gammas)):
        for ri in range(N_REPLICATES):
            for n in N_VALUES:
                sample = generate_sample(float(b), float(e), float(g), n, ri, seed=SEED_TEST_NS + ci)
                datasets[(ci, ri, n)] = {
                    "sample": sample, "beta": float(b), "eta": float(e),
                    "gamma": float(g), "true_x095": quantile_true(float(b), float(e), float(g), 0.95),
                }
    return datasets


def load_p_models(b3: dict) -> dict[tuple[int, int], torch.nn.Module]:
    """Load frozen P checkpoints: {(n, seed) -> model}."""
    models = {}
    for e in b3["p_checkpoints"]["entries"]:
        n, seed = int(e["n"]), int(e["seed"])
        state = load_checkpoint(Path(e["path"]).read_bytes())
        model = build_mlp(n, [256, 128, 64], "silu", 0.1)
        model.load_state_dict(state)
        model.eval()
        models[(n, seed)] = model
    return models


def infer_p_params(models: dict[tuple[int, int], torch.nn.Module],
                   datasets: dict[tuple[int, int, int], dict]) -> dict[tuple[int, int, int], np.ndarray]:
    """Per-seed P parameter predictions (beta, eta, gamma) for every core row.

    Returns {(ci, ri, n): (n_seeds, 3) float64 array}; invalid seeds are NaN.
    Deterministic: same frozen checkpoints + same B4 test data.
    """
    out = {}
    keys = sorted(datasets)
    for k in keys:
        ci, ri, n = k
        td = datasets[k]
        a = anchor_sample(td["sample"])
        z = torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0)
        loc = torch.tensor([a.location], dtype=torch.float32)
        sc = torch.tensor([a.scale], dtype=torch.float32)
        seeds = [s for (ns, s) in models if ns == n]
        vals = []
        for s in seeds:
            with torch.no_grad():
                raw = models[(n, s)](z)
            dec = decode_model_output(raw, loc, sc)
            bf, ef, gf = float(dec[0, 0]), float(dec[0, 1]), float(dec[0, 2])
            if bf > 0 and ef > 0 and np.isfinite([bf, ef, gf]).all():
                vals.append((bf, ef, gf))
            else:
                vals.append((np.nan, np.nan, np.nan))
        out[k] = np.array(vals, dtype=np.float64)
    return out


def verify_p_inference(p_params: dict[tuple[int, int, int], np.ndarray],
                       npz: dict) -> dict:
    """Cross-check re-inferred P x0.95 vs B4 per-seed NPZ (max abs rel diff)."""
    keys_npz = list(npz["keys"])
    row_to_idx = {k: i for i, k in enumerate(keys_npz)}
    max_diff = 0.0
    checked = 0
    for k, arr in p_params.items():
        idx = row_to_idx[f"{k[0]}_{k[1]}_{k[2]}"]
        stored = npz["p_seeds"][idx]
        for s in range(arr.shape[0]):
            bf, ef, gf = arr[s]
            if np.isfinite([bf, ef, gf]).all():
                pred = quantile_true(bf, ef, gf, 0.95)
                diff = abs(pred - float(stored[s])) / max(1.0, abs(float(stored[s])))
                max_diff = max(max_diff, diff)
                checked += 1
    return {"rows": len(p_params), "per_seed_checked": checked, "max_abs_rel_diff": max_diff}
