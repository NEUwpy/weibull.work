"""Resumable training runner for the incremental B fits.

Trains P / D / Dctrl for the missing n values only (existing checkpoints are
reused read-only). Each fit is fully deterministic and independent, so fits
may be run in process-parallel workers without changing any result.

Resumption: a fit is skipped iff its checkpoint exists AND the recorded
config hash in the sidecar matches the frozen CONFIG_HASH.

Usage:
    python -m study02b_inc.train_inc --run-dir <dir> [--workers 8] [--only n]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import torch

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))

from study02a.models import build_mlp, trainable_parameter_count
from study02a.training import fit_candidate
from study02b.training import build_d_mlp, fit_d_model

from study02b_inc import config as C
from study02b_inc import data as D

# Process-local training-data cache inside worker processes.
_WORKER_DATA_CACHE: dict[tuple, dict] = {}


def _git_tip() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                       cwd=str(C.REPO_ROOT), timeout=5)
    return r.stdout.strip() or "unknown"


def _sidecar_matches(ckpt_path: Path) -> bool:
    side = ckpt_path.with_suffix(".json")
    if not side.exists():
        return False
    try:
        meta = json.loads(side.read_text(encoding="utf-8"))
    except Exception:
        return False
    return meta.get("config_hash") == C.CONFIG_HASH


def _ckpt_name(route: str, n: int, seed: int) -> str:
    if route == "P":
        return f"checkpoint_P_n{n}_seed{seed}.pt"
    if route == "D":
        return f"checkpoint_D_n{n}_seed{seed}.pt"
    return f"checkpoint_Dctrl_n{n}_seed{seed}.pt"


def _write_fit(train_dir: Path, route: str, n: int, seed: int, r: dict,
               completed: list, failed: list) -> None:
    """Atomically persist one completed fit; appends to completed/failed."""
    if r is None:
        failed.append({"route": route, "n": n, "seed": seed, "error": "worker returned None"})
        return
    ckpt_path = train_dir / _ckpt_name(route, n, seed)
    ckpt_path.write_bytes(r["checkpoint_bytes"])
    r["checkpoint_path"] = str(ckpt_path)
    side = ckpt_path.with_suffix(".json")
    side.write_text(json.dumps({
        "config_hash": C.CONFIG_HASH, "route": route, "n": n, "seed": seed,
        "checkpoint_sha256": r["checkpoint_sha256"],
    }), encoding="utf-8")
    completed.append(r)
    print(f"  [ok] {route}/n{n}/seed{seed} loss={r['best_validation_loss']:.6f} "
          f"epochs={r['actual_epochs']}", flush=True)


def _worker_fit(job: tuple) -> dict:
    """Module-level worker: (route, n, seed, widths) -> fit result dict.

    Training data is generated deterministically and cached per (route, n)
    inside each worker process. Runs as a Pool worker (spawn on Windows);
    module globals are re-initialized per worker, which is fine.
    """
    route, n, seed, widths = job
    # One thread per worker: 8 workers × 1 thread avoid oversubscribing the
    # 12-core CPU (default multi-threaded torch caused ~85% idle). Deterministic
    # given the same thread count; results reproducible within this setting.
    torch.set_num_threads(1)
    # Dctrl uses the same training data (and target stats) as D.
    data_route = "D" if route in ("D", "Dctrl") else route
    key = (data_route, n)
    if key not in _WORKER_DATA_CACHE:
        _WORKER_DATA_CACHE[key] = D.generate_training_data(data_route, n)
    data = _WORKER_DATA_CACHE[key]

    train_x = torch.from_numpy(data["features"][:C.N_TRAIN]).to(torch.float32)
    train_y = torch.from_numpy(data["targets"][:C.N_TRAIN]).to(torch.float32)
    val_x = torch.from_numpy(data["features"][C.N_TRAIN:]).to(torch.float32)
    val_y = torch.from_numpy(data["targets"][C.N_TRAIN:]).to(torch.float32)

    if route == "P":
        mf = lambda: build_mlp(int(n), C.P_WIDTHS, C.ACTIVATION, C.DROPOUT)
        probe = mf()
        param_count = trainable_parameter_count(probe)
        del probe
        result = fit_candidate(
            mf, (train_x, train_y), (val_x, val_y),
            seed=seed, loss_id=C.LOSS_P, lr=C.LR, weight_decay=C.WEIGHT_DECAY,
            batch_size=C.BATCH_SIZE, **C.P_EPOCHS,
        )
        return {
            "route": "P", "n": n, "seed": seed, "widths": list(C.P_WIDTHS),
            "group": None, "param_count": param_count,
            "best_validation_loss": result.best_validation_loss,
            "best_epoch": result.best_epoch, "actual_epochs": result.actual_epochs,
            "early_stop_reason": result.early_stop_reason,
            "checkpoint_sha256": result.checkpoint_sha256,
            "checkpoint_bytes": result.checkpoint_bytes,
        }

    group = "controlled" if route == "Dctrl" else "selected"
    mf = lambda: build_d_mlp(int(n), list(widths), C.ACTIVATION, C.DROPOUT)
    probe = mf()
    param_count = trainable_parameter_count(probe)
    del probe
    result = fit_d_model(
        mf, train_x, train_y, val_x, val_y,
        seed=seed, loss_id=C.LOSS_D, lr=C.LR, weight_decay=C.WEIGHT_DECAY,
        batch_size=C.BATCH_SIZE, **C.D_EPOCHS,
    )
    return {
        "route": route, "group": group, "n": n, "seed": seed, "widths": list(widths),
        "param_count": param_count,
        "best_validation_loss": result.best_validation_loss,
        "best_epoch": result.best_epoch, "actual_epochs": result.actual_epochs,
        "early_stop_reason": result.early_stop_reason,
        "checkpoint_sha256": result.checkpoint_sha256,
        "checkpoint_bytes": result.checkpoint_bytes,
    }


def train_inc(run_dir: Path, workers: int = 8, only_n: list[int] | None = None,
              max_fits: int | None = None) -> dict:
    run_dir = Path(run_dir)
    train_dir = run_dir / "training"
    train_dir.mkdir(parents=True, exist_ok=True)

    n_missing = [n for n in C.N_MISSING if (only_n is None or n in only_n)]
    if not n_missing:
        print("No missing n to train.")
        return _write_manifest(train_dir, [], {}, run_dir)

    jobs = []
    for n in n_missing:
        for seed in C.P_FIT_SEEDS:
            jobs.append(("P", n, seed, tuple(C.P_WIDTHS)))
        for seed in C.D_FIT_SEEDS:
            jobs.append(("D", n, seed, tuple(C.D_SELECTED_WIDTHS)))
        for seed in C.DCTRL_FIT_SEEDS:
            jobs.append(("Dctrl", n, seed, tuple(C.DCTRL_WIDTHS)))
    if max_fits:
        jobs = jobs[:max_fits]

    print(f"=== Incremental training: {len(jobs)} planned fits ===")
    print(f"run_dir: {run_dir}")
    print(f"config_hash: {C.CONFIG_HASH}")
    t0 = time.perf_counter()

    completed, failed, pending = [], [], []
    for route, n, seed, widths in jobs:
        ckpt_path = train_dir / _ckpt_name(route, n, seed)
        if ckpt_path.exists() and _sidecar_matches(ckpt_path):
            completed.append({
                "route": route, "n": n, "seed": seed, "widths": list(widths),
                "group": ("controlled" if route == "Dctrl" else "selected") if route != "P" else None,
                "early_stop_reason": "resumed",
                "checkpoint_sha256": hashlib.sha256(ckpt_path.read_bytes()).hexdigest(),
                "checkpoint_path": str(ckpt_path),
            })
            print(f"  [skip] {route}/n{n}/seed{seed}")
            continue
        pending.append((route, n, seed, widths))

    if pending:
        if workers > 1 and len(pending) >= 2 * workers:
            with Pool(processes=workers) as pool:
                for r in pool.imap_unordered(_worker_fit, pending, chunksize=1):
                    _write_fit(train_dir, r["route"], r["n"], r["seed"], r, completed, failed)
        else:
            for job in pending:
                r = _worker_fit(job)
                _write_fit(train_dir, r["route"], r["n"], r["seed"], r, completed, failed)

    elapsed = time.perf_counter() - t0
    print(f"=== training elapsed {elapsed:.1f}s, {len(completed)} complete, {len(failed)} failed ===")

    target_stats = {}
    for n in n_missing:
        ts = D.target_stats_for_n(n)
        target_stats[str(n)] = {"mean": ts["mean"], "sd": ts["sd"], "source": "inc"}

    return _write_manifest(train_dir, completed, target_stats, run_dir, elapsed, failed)


def _write_manifest(train_dir: Path, completed: list, target_stats: dict,
                    run_dir: Path, elapsed: float = 0.0, failed: list | None = None) -> dict:
    failed = failed or []
    inventory = []
    for r in completed:
        if r.get("checkpoint_path") and Path(r["checkpoint_path"]).exists():
            ckpt_bytes = Path(r["checkpoint_path"]).read_bytes()
            inventory.append({
                "route": r.get("route"), "group": r.get("group"),
                "n": r.get("n"), "seed": r.get("seed"), "widths": r.get("widths"),
                "checkpoint_path": r["checkpoint_path"],
                "checkpoint_sha256": r.get("checkpoint_sha256")
                    or hashlib.sha256(ckpt_bytes).hexdigest(),
                "best_validation_loss": r.get("best_validation_loss"),
                "best_epoch": r.get("best_epoch"),
                "actual_epochs": r.get("actual_epochs"),
                "early_stop_reason": r.get("early_stop_reason"),
                "param_count": r.get("param_count"),
            })

    import platform
    manifest = {
        "version": "1.0",
        "run_id": run_dir.name,
        "kind": "training",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "complete" if not failed else "partial",
        "code_tip": _git_tip(),
        "config_hash": C.CONFIG_HASH,
        "elapsed_seconds": elapsed,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "torch_threads_per_worker": 1,
        },
        "n_missing": C.N_MISSING,
        "checkpoints": inventory,
        "target_stats": target_stats,
        "failures": failed,
    }
    mf = train_dir / "manifest.json"
    mf.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Training manifest: {mf}")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", type=int, nargs="*", default=None)
    ap.add_argument("--max-fits", type=int, default=None)
    args = ap.parse_args()
    train_inc(Path(args.run_dir), workers=args.workers,
              only_n=args.only, max_fits=args.max_fits)


if __name__ == "__main__":
    main()
