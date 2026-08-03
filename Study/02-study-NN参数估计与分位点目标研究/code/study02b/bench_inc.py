"""Incremental B throughput benchmark (throwaway, not part of frozen evidence).

Measures, on the real training/evaluation path:
  - D-route training data generation (uniform beta/eta, B3 recipe) for a given n
  - P-route training data generation (log-uniform beta/eta, A-E1 recipe)
  - one D selected  [64,32] fit
  - one D controlled [256,128,64] fit
  - one P joint m12 [256,128,64] fit (100/50/40 epoch contract)
  - per-dataset inference cost (P 10 seeds + D 10 seeds + Dctrl 5 seeds + trad)

Run:  python code/study02b/bench_inc.py [--n-small 10 --n-large 30]
Output: JSON timing table. Used only to calibrate the frozen matrix.
"""

from __future__ import annotations

import json
import sys
import time
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

from studies.common.sample import generate_sample
from studies.common.metrics import quantile_true
from studies.common.runner import run_method
from study02a.models import build_mlp, trainable_parameter_count
from study02a.representations import anchor_sample, encode_targets
from study02a.training import fit_candidate, load_checkpoint
from study02b.representations import (
    encode_d_target, compute_d_stats, standardize_d,
)
from study02b.training import build_d_mlp, fit_d_model

_N_TRAIN = 100_000
_N_VAL = 20_000
_D_EPOCHS = dict(max_epochs=500, min_epochs=50, patience=40)
_P_EPOCHS = dict(max_epochs=100, min_epochs=50, patience=40)


def timeit(fn):
    t0 = time.perf_counter()
    result = fn()
    return time.perf_counter() - t0, result


def generate_d_data(n: int):
    """B3 uniform recipe."""
    rng = np.random.default_rng(n * 100 + 1)
    total = _N_TRAIN + _N_VAL
    betas = rng.uniform(1.2, 4.0, size=total)
    etas = rng.uniform(100.0, 10000.0, size=total)
    rhos = rng.uniform(0.0, 1.0, size=total)
    gammas = rhos * etas
    samples, x095s = [], []
    for i in range(total):
        b, e, g = float(betas[i]), float(etas[i]), float(gammas[i])
        ns = 4000 if i < _N_TRAIN else 5000
        rid = i if i < _N_TRAIN else i - _N_TRAIN
        samples.append(generate_sample(b, e, g, n, rid, seed=ns))
        x095s.append(quantile_true(b, e, g, 0.95))
    anchors = [anchor_sample(s) for s in samples]
    features = np.array([a.z for a in anchors], dtype=np.float32)
    raw = np.array([
        encode_d_target(float(x), a) for x, a in zip(x095s, anchors)
    ], dtype=np.float32)
    stats = compute_d_stats(raw[:_N_TRAIN])
    targets = standardize_d(raw, stats).astype(np.float32)
    return {
        "features": features,
        "targets": targets.reshape(-1, 1),
        "stats": stats,
    }


def generate_p_data(n: int):
    """A-E1 core_continuous recipe: log-uniform beta/eta, uniform rho.

    New deterministic seed namespace (documented in the incremental manifest),
    NOT the A-E1 Sobol seed — distribution matched, draw seed new.
    """
    rng = np.random.default_rng(7000 + n)  # dedicated P-inc train namespace
    total = _N_TRAIN + _N_VAL
    betas = np.exp(rng.uniform(np.log(1.2), np.log(4.0), size=total))
    etas = np.exp(rng.uniform(np.log(100.0), np.log(10000.0), size=total))
    rhos = rng.uniform(0.0, 1.0, size=total)
    gammas = rhos * etas
    samples = []
    for i in range(total):
        b, e, g = float(betas[i]), float(etas[i]), float(gammas[i])
        ns = 8000 if i < _N_TRAIN else 9000
        rid = i if i < _N_TRAIN else i - _N_TRAIN
        samples.append(generate_sample(b, e, g, n, rid, seed=ns))
    anchors = [anchor_sample(s) for s in samples]
    features = np.array([a.z for a in anchors], dtype=np.float32)
    targets = np.array([
        encode_targets(float(betas[i]), float(etas[i]), float(gammas[i]), anchors[i])
        for i in range(total)
    ], dtype=np.float32)
    return {
        "features": features,
        "targets": targets,
        "val_features": features[_N_TRAIN:],
        "val_targets": targets[_N_TRAIN:],
        "train_features": features[:_N_TRAIN],
        "train_targets": targets[:_N_TRAIN],
    }


def to_torch(data, n):
    x = torch.from_numpy(data["features"]).to(torch.float32)
    y = torch.from_numpy(data["targets"]).to(torch.float32)
    return (x[:_N_TRAIN], y[:_N_TRAIN]), (x[_N_TRAIN:], y[_N_TRAIN:])


def main():
    n_small = 10
    n_large = 30
    if "--n-small" in sys.argv:
        n_small = int(sys.argv[sys.argv.index("--n-small") + 1])
    if "--n-large" in sys.argv:
        n_large = int(sys.argv[sys.argv.index("--n-large") + 1])

    results = {}

    # --- data generation ---
    dt, ddata = timeit(lambda: generate_d_data(n_small))
    results["d_data_n10"] = dt
    dt, pdata = timeit(lambda: generate_p_data(n_small))
    results["p_data_n10"] = dt

    # --- D selected fit n=10 ---
    (tr_x, tr_y), (va_x, va_y) = to_torch(ddata, n_small)
    def fit_d(n, widths):
        mf = lambda: build_d_mlp(n, widths, "silu", 0.1)
        r = fit_d_model(mf, tr_x, tr_y, va_x, va_y, seed=101,
                        loss_id="huber", lr=1e-3, weight_decay=1e-4,
                        batch_size=512, **_D_EPOCHS)
        return r
    dt, r = timeit(lambda: fit_d(n_small, [64, 32]))
    results["d_selected_fit_n10"] = {"seconds": dt, "epochs": r.actual_epochs}
    dt, r = timeit(lambda: fit_d(n_small, [256, 128, 64]))
    results["dctrl_fit_n10"] = {"seconds": dt, "epochs": r.actual_epochs}

    # --- D selected fit n=30 (n-dependence) ---
    dt, ddata30 = timeit(lambda: generate_d_data(n_large))
    results["d_data_n30"] = dt
    (tr_x30, tr_y30), (va_x30, va_y30) = to_torch(ddata30, n_large)
    def fit_d30():
        mf = lambda: build_d_mlp(n_large, [64, 32], "silu", 0.1)
        return fit_d_model(mf, tr_x30, tr_y30, va_x30, va_y30, seed=101,
                           loss_id="huber", lr=1e-3, weight_decay=1e-4,
                           batch_size=512, **_D_EPOCHS)
    dt, r = timeit(fit_d30)
    results["d_selected_fit_n30"] = {"seconds": dt, "epochs": r.actual_epochs}

    # --- P m12 fit n=10 and n=30 ---
    (ptr_x, ptr_y), (pva_x, pva_y) = to_torch(pdata, n_small)
    def fit_p(n, x_tr, y_tr, x_va, y_va):
        mf = lambda: build_mlp(n, [256, 128, 64], "silu", 0.1)
        return fit_candidate(mf, (x_tr, y_tr), (x_va, y_va), seed=420101,
                             loss_id="transformed_train_z_huber", lr=1e-3,
                             weight_decay=1e-4, batch_size=512, **_P_EPOCHS)
    dt, r = timeit(lambda: fit_p(n_small, ptr_x, ptr_y, pva_x, pva_y))
    results["p_fit_n10"] = {"seconds": dt, "epochs": r.actual_epochs}

    dt, pdata30 = timeit(lambda: generate_p_data(n_large))
    results["p_data_n30"] = dt
    (ptr_x30, ptr_y30), (pva_x30, pva_y30) = to_torch(pdata30, n_large)
    dt, r = timeit(lambda: fit_p(n_large, ptr_x30, ptr_y30, pva_x30, pva_y30))
    results["p_fit_n30"] = {"seconds": dt, "epochs": r.actual_epochs}

    # --- inference throughput: 2000 datasets x P/D (n=5 checkpoints) ---
    from study02b.training import build_d_mlp as _bd
    p_m = build_mlp(5, [256, 128, 64], "silu", 0.1)
    d_m = _bd(5, [64, 32], "silu", 0.1)
    p_state = load_checkpoint(Path(
        "C:/weibull-runs/study02/artifacts/A-E1/A-E1-formal-r5-20260727-222417"
        "/outputs/G3-fit-0299/checkpoint.pt").read_bytes())
    p_m.load_state_dict(p_state); p_m.eval()
    d_state = load_checkpoint(Path(
        "C:/weibull-runs/study02/formal-b/B3-training-20260731-121958"
        "/checkpoint_selected_n5_seed101.pt").read_bytes())
    d_m.load_state_dict(d_state); d_m.eval()

    rng = np.random.default_rng(42)
    n_datasets = 2000
    t0 = time.perf_counter()
    for k in range(n_datasets):
        b, e, g = float(rng.uniform(1.2, 4.0)), 1000.0, float(rng.uniform(0, 1) * 1000.0)
        s = generate_sample(b, e, g, 5, k, seed=6000)
        a = anchor_sample(s)
        z = torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0)
        with torch.no_grad():
            raw = p_m(z)
            _ = decode_quick(raw, a)
            raw_d = d_m(z)
            _ = float(a.location + a.scale * float(raw_d.item()))
    elapsed = time.perf_counter() - t0
    results["inference_per_dataset_p10_d10"] = elapsed / n_datasets

    # traditional single fit
    t0 = time.perf_counter()
    n_trad = 200
    for k in range(n_trad):
        b, e, g = float(rng.uniform(1.2, 4.0)), 1000.0, float(rng.uniform(0, 1) * 1000.0)
        s = generate_sample(b, e, g, n_small, k, seed=6000)
        run_method("mle", s)
    results["trad_mle_per_dataset"] = (time.perf_counter() - t0) / n_trad

    print(json.dumps(results, indent=2))


def decode_quick(raw, anchor):
    from study02a.models import decode_model_output
    dec = decode_model_output(raw, torch.tensor([anchor.location]),
                              torch.tensor([anchor.scale]))
    bf, ef, gf = float(dec[0, 0]), float(dec[0, 1]), float(dec[0, 2])
    return quantile_true(bf, ef, gf, 0.95) if (bf > 0 and ef > 0) else np.nan


if __name__ == "__main__":
    main()
