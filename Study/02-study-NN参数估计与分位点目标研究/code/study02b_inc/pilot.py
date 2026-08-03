"""Bounded end-to-end pilot for the incremental B run.

Trains P/D/Dctrl at ONE missing n (n=6) with reduced seeds, runs a small
dense-core slice and a small parameter-grid slice through the real evaluation
path, verifies per-seed artifacts and reproduces B4 on one shared n row.

This is NOT evidence: it uses reduced seeds/draws and does not write into the
frozen matrix run namespace. It measures end-to-end throughput to confirm the
frozen matrix timing before the full run.

Usage:
    python -m study02b_inc.pilot --out <dir> [--workers 4]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))

from study02a.models import build_mlp
from study02a.training import fit_candidate, load_checkpoint
from study02b.representations import DTrainingStats
from study02b.training import build_d_mlp, fit_d_model

from study02b_inc import config as C
from study02b_inc import data as D
from study02b_inc import evaluate_inc as E


def train_small(run_dir: Path, workers: int) -> dict:
    """Train a few fits at n=6 to validate the training path."""
    n = 6
    results = []
    # P: 2 seeds
    pdata = D.generate_training_data("P", n)
    train_x = torch.from_numpy(pdata["features"][:C.N_TRAIN]).to(torch.float32)
    train_y = torch.from_numpy(pdata["targets"][:C.N_TRAIN]).to(torch.float32)
    val_x = torch.from_numpy(pdata["features"][C.N_TRAIN:]).to(torch.float32)
    val_y = torch.from_numpy(pdata["targets"][C.N_TRAIN:]).to(torch.float32)
    for seed in [420101, 420102]:
        t0 = time.perf_counter()
        r = fit_candidate(lambda: build_mlp(n, C.P_WIDTHS, C.ACTIVATION, C.DROPOUT),
                          (train_x, train_y), (val_x, val_y), seed=seed,
                          loss_id=C.LOSS_P, lr=C.LR, weight_decay=C.WEIGHT_DECAY,
                          batch_size=C.BATCH_SIZE, **C.P_EPOCHS)
        ckpt = run_dir / f"pilot_P_n{n}_seed{seed}.pt"
        ckpt.write_bytes(r.checkpoint_bytes)
        results.append({"route": "P", "n": n, "seed": seed,
                        "loss": r.best_validation_loss, "epochs": r.actual_epochs,
                        "seconds": time.perf_counter() - t0})

    # D: 2 seeds
    ddata = D.generate_training_data("D", n)
    dx = torch.from_numpy(ddata["features"][:C.N_TRAIN]).to(torch.float32)
    dy = torch.from_numpy(ddata["targets"][:C.N_TRAIN]).to(torch.float32)
    dvx = torch.from_numpy(ddata["features"][C.N_TRAIN:]).to(torch.float32)
    dvy = torch.from_numpy(ddata["targets"][C.N_TRAIN:]).to(torch.float32)
    for seed in [101, 102]:
        t0 = time.perf_counter()
        r = fit_d_model(lambda: build_d_mlp(n, C.D_SELECTED_WIDTHS, C.ACTIVATION, C.DROPOUT),
                        dx, dy, dvx, dvy, seed=seed, loss_id=C.LOSS_D, lr=C.LR,
                        weight_decay=C.WEIGHT_DECAY, batch_size=C.BATCH_SIZE, **C.D_EPOCHS)
        ckpt = run_dir / f"pilot_D_n{n}_seed{seed}.pt"
        ckpt.write_bytes(r.checkpoint_bytes)
        results.append({"route": "D", "n": n, "seed": seed,
                        "loss": r.best_validation_loss, "epochs": r.actual_epochs,
                        "seconds": time.perf_counter() - t0})
    # Dctrl: 1 seed
    t0 = time.perf_counter()
    r = fit_d_model(lambda: build_d_mlp(n, C.DCTRL_WIDTHS, C.ACTIVATION, C.DROPOUT),
                    dx, dy, dvx, dvy, seed=201, loss_id=C.LOSS_D, lr=C.LR,
                    weight_decay=C.WEIGHT_DECAY, batch_size=C.BATCH_SIZE, **C.D_EPOCHS)
    ckpt = run_dir / f"pilot_Dctrl_n{n}_seed201.pt"
    ckpt.write_bytes(r.checkpoint_bytes)
    results.append({"route": "Dctrl", "n": n, "seed": 201,
                    "loss": r.best_validation_loss, "epochs": r.actual_epochs,
                    "seconds": time.perf_counter() - t0})
    print(json.dumps({"pilot_training": results}, indent=2))
    return results


def _reg_as_inc_checkpoint(run_dir: Path, route: str, n: int, seed: int):
    """Register a pilot checkpoint into the run-dir layout the eval expects."""
    import hashlib
    src = run_dir / f"pilot_{route}_n{n}_seed{seed}.pt"
    if route == "P":
        name = f"checkpoint_P_n{n}_seed{seed}.pt"
    elif route == "D":
        name = f"checkpoint_D_n{n}_seed{seed}.pt"
    else:
        name = f"checkpoint_Dctrl_n{n}_seed{seed}.pt"
    dst = run_dir / "training" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    side = dst.with_suffix(".json")
    side.write_text(json.dumps({"config_hash": "pilot",
                                "route": route, "n": n, "seed": seed,
                                "checkpoint_sha256": hashlib.sha256(src.read_bytes()).hexdigest()}),
                    encoding="utf-8")


def run_pilot(out: Path, workers: int = 4) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"=== Pilot (bounded, not evidence) ===")
    t0 = time.perf_counter()
    results = {}

    results["training"] = train_small(out, workers)
    for r in results["training"]:
        _reg_as_inc_checkpoint(out, r["route"], r["n"], r["seed"])

    # A tiny core slice: 4 clusters x 5 reps x 3 n, through the real eval path.
    # Temporarily reduce constants so E._run_block runs a small core block.
    old_clusters = C.CORE_N_CLUSTERS
    old_reps = C.CORE_N_REPLICATES
    old_ns = C.N_VALUES
    C.CORE_N_CLUSTERS = 4
    C.CORE_N_REPLICATES = 5
    C.N_VALUES = [5, 6, 7]
    try:
        rows = D.generate_core_rows()
        print(f"pilot core rows: {len(rows)}")
        results["core"] = E._run_block(out, rows, "core", workers)
    finally:
        C.CORE_N_CLUSTERS = old_clusters
        C.CORE_N_REPLICATES = old_reps
        C.N_VALUES = old_ns

    # Tiny grid slice: subset of cells x subset of draws.
    old_draws = C.PG_DRAWS
    C.PG_DRAWS = 8
    try:
        cells = D.param_grid_cells()[:2]
        rows = D.generate_grid_rows(cells)
        print(f"pilot grid rows: {len(rows)}")
        results["grid"] = E._run_block(out, rows, "grid", workers)
    finally:
        C.PG_DRAWS = old_draws

    results["elapsed_seconds"] = time.perf_counter() - t0
    report = out / "pilot_report.json"
    report.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Pilot report: {report}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    run_pilot(Path(args.out), workers=args.workers)


if __name__ == "__main__":
    main()
