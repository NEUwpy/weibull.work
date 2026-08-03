"""B3: D-route full training and checkpoint freeze.

Selected D:   [64, 32], SiLU, dropout 0.1, Huber, 5n 脳 10 seeds = 50 fits.
Controlled D: [256, 128, 64] (A's m12), SiLU, dropout 0.1, Huber, 5n 脳 5 seeds = 25 fits.
Total: 75 new fits. Cumulative B NN fits: 12 (B2) + 75 = 87 (< 100 cap).

Writes checkpoints + manifest to C:\\weibull-runs\\study02\\formal-b\\<B3-run-id>.
Supports minimal resumption: skip fits whose checkpoint exists with matching config hash.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

# Ensure import paths
_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

from studies.common.sample import generate_sample
from studies.common.metrics import quantile_true
from study02a.models import trainable_parameter_count
from study02a.representations import anchor_sample
from study02a.training import load_checkpoint
from study02b.representations import (
    encode_d_target,
    decode_d_target,
    compute_d_stats,
    standardize_d,
    unstandardize_d,
)
from study02b.training import build_d_mlp, fit_d_model

_EXTERNAL_ROOT = Path("C:/weibull-runs/study02/formal-b")
_P_CHECKPOINT_BASE = Path(
    "C:/weibull-runs/study02/artifacts/A-E1/A-E1-formal-r5-20260727-222417/outputs"
)

# Frozen training config
_N_VALUES = [5, 7, 10, 15, 20]
_N_TRAIN = 100_000
_N_VAL = 20_000
_TRAIN_SEED_NS = 4000
_VAL_SEED_NS = 5000

# Selected D
_SELECTED_WIDTHS = [64, 32]
_SELECTED_SEEDS = list(range(101, 111))  # 10 seeds

# Controlled D (A's frozen m12)
_CONTROLLED_WIDTHS = [256, 128, 64]
_CONTROLLED_SEEDS = list(range(201, 206))  # 5 seeds

# P checkpoint index (G3-fit-0299..0348, 50 fits)
_P_FIT_START = 299
_P_FIT_END = 348
_P_FIT_COUNT = 50


def _git_tip() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(_REPO_ROOT),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


_P_PLAN_PATH = _P_CHECKPOINT_BASE.parent / "plan.jsonl"


def _load_a_plan() -> dict[str, dict]:
    """Load A-E1 r5 plan.jsonl and return fit_id → row index."""
    index: dict[str, dict] = {}
    with open(_P_PLAN_PATH, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            fid = row.get("fit_id")
            if fid:
                index[fid] = row
    return index


def build_p_index() -> list[dict]:
    """Build a read-only P checkpoint index from A plan + verified artifacts.

    Resolves each G3-fit-0299..0348 row from the immutable A plan.jsonl
    to record n (fixed_n), seed, plan-row SHA256, and checkpoint hash/path.
    """
    plan = _load_a_plan()
    index = []
    for fit_num in range(_P_FIT_START, _P_FIT_END + 1):
        fit_id = f"G3-fit-{fit_num:04d}"
        ckpt_path = _P_CHECKPOINT_BASE / fit_id / "checkpoint.pt"
        ckpt_bytes = ckpt_path.read_bytes()
        ckpt_sha = hashlib.sha256(ckpt_bytes).hexdigest()
        ckpt_size = len(ckpt_bytes)

        plan_row = plan.get(fit_id, {})
        n_val = plan_row.get("fixed_n")
        seed_val = plan_row.get("seed")
        plan_line = json.dumps(plan_row, sort_keys=True, ensure_ascii=False) if plan_row else "{}"
        plan_row_sha256 = hashlib.sha256(plan_line.encode("utf-8")).hexdigest()

        index.append({
            "fit_id": fit_id,
            "path": str(ckpt_path),
            "sha256": ckpt_sha,
            "size_bytes": ckpt_size,
            "n": n_val,
            "seed": seed_val,
            "plan_row_sha256": plan_row_sha256,
            "route": plan_row.get("route"),
            "architecture": plan_row.get("architecture"),
            "loss": plan_row.get("loss"),
            "code_commit": plan_row.get("code_commit"),
        })
    return index


def generate_b3_data(n_sample: int) -> dict:
    """Generate training (100k) and validation (20k) data for a given n."

    Separate seed namespaces for training and validation.
    """
    rng = np.random.default_rng(n_sample * 100 + 1)

    def _draw_params(rng, size):
        betas = rng.uniform(1.2, 4.0, size=size)
        etas = rng.uniform(100.0, 10000.0, size=size)
        rhos = rng.uniform(0.0, 1.0, size=size)
        gammas = rhos * etas
        return betas, etas, gammas

    total = _N_TRAIN + _N_VAL
    betas, etas, gammas = _draw_params(rng, total)

    samples = []
    x095s = []
    for i in range(total):
        b, e, g = float(betas[i]), float(etas[i]), float(gammas[i])
        ns = _TRAIN_SEED_NS if i < _N_TRAIN else _VAL_SEED_NS
        rid = i if i < _N_TRAIN else i - _N_TRAIN
        sample = generate_sample(b, e, g, n_sample, rid, seed=ns)
        samples.append(sample)
        x095s.append(quantile_true(b, e, g, 0.95))

    anchors = [anchor_sample(s) for s in samples]
    features = np.array([a.z for a in anchors], dtype=np.float32)
    d_targets_raw = np.array([
        encode_d_target(float(x095), anch)
        for x095, anch in zip(x095s, anchors)
    ], dtype=np.float32)

    train_features = features[:_N_TRAIN]
    val_features = features[_N_TRAIN:]
    train_targets_raw = d_targets_raw[:_N_TRAIN]
    val_targets_raw = d_targets_raw[_N_TRAIN:]

    stats = compute_d_stats(train_targets_raw)
    train_targets = standardize_d(train_targets_raw, stats).astype(np.float32)
    val_targets = standardize_d(val_targets_raw, stats).astype(np.float32)

    return {
        "train_features": train_features,
        "train_targets": train_targets,
        "val_features": val_features,
        "val_targets": val_targets,
        "target_stats": stats,
    }


def compute_target_stats_for_n(n_sample: int) -> dict:
    """Recompute the deterministic per-n target_stats without model fitting.

    Uses the same seed/namespace as generate_b3_data, so the resulting
    DTrainingStats (mean, sd) are bit-identical to those used during B3
    training.  B4 uses these to unstandardize D predictions before
    decoding through sample anchors.
    """
    data = generate_b3_data(n_sample)
    stats = data["target_stats"]
    return {
        "n": n_sample,
        "mean": stats.mean,
        "sd": stats.sd,
    }


@dataclass
class B3FitRecord:
    group: str  # "selected" or "controlled"
    n: int
    seed: int
    widths: Sequence[int]
    best_validation_loss: float
    best_epoch: int
    actual_epochs: int
    early_stop_reason: str
    param_count: int
    checkpoint_sha256: str
    checkpoint_path: str

    def to_dict(self) -> dict:
        return {
            "group": self.group,
            "n": self.n,
            "seed": self.seed,
            "widths": list(self.widths),
            "best_validation_loss": self.best_validation_loss,
            "best_epoch": self.best_epoch,
            "actual_epochs": self.actual_epochs,
            "early_stop_reason": self.early_stop_reason,
            "param_count": self.param_count,
            "checkpoint_sha256": self.checkpoint_sha256,
            "checkpoint_path": self.checkpoint_path,
        }


def run_b3(output_dir: str | None = None) -> dict:
    """Run the complete B3 training and return summary dict."""
    if output_dir is None:
        run_id = f"B3-training-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        output_dir = str(_EXTERNAL_ROOT / run_id)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    code_tip = _git_tip()
    print(f"=== B3 D-route full training ===")
    print(f"Output: {out}")
    print(f"Code tip: {code_tip}")

    # Build P index (read-only audit)
    print("\n[0] Building P checkpoint index ...")
    p_index = build_p_index()
    print(f"  P checkpoints indexed: {len(p_index)}")

    all_records: list[B3FitRecord] = []
    failures: list[dict] = []
    total_planned = len(_N_VALUES) * len(_SELECTED_SEEDS) + len(_N_VALUES) * len(_CONTROLLED_SEEDS)
    fit_num = 0

    # --- Selected D: [64,32], 10 seeds per n ---
    for n in _N_VALUES:
        print(f"\n--- n={n}: generating data ---")
        data = generate_b3_data(n)
        train_x = torch.from_numpy(data["train_features"]).to(torch.float32)
        train_y = torch.from_numpy(data["train_targets"]).to(torch.float32).reshape(-1, 1)
        val_x = torch.from_numpy(data["val_features"]).to(torch.float32)
        val_y = torch.from_numpy(data["val_targets"]).to(torch.float32).reshape(-1, 1)

        for seed in _SELECTED_SEEDS:
            fit_num += 1
            label = f"selected/n{n}/seed{seed}"
            ckpt_name = f"checkpoint_selected_n{n}_seed{seed}.pt"
            ckpt_path = out / ckpt_name

            # Resumption check
            if ckpt_path.exists():
                print(f"  Fit {fit_num}/{total_planned}: {label} [SKIP — checkpoint exists]")
                existing_sha = hashlib.sha256(ckpt_path.read_bytes()).hexdigest()
                all_records.append(B3FitRecord(
                    group="selected", n=n, seed=seed,
                    widths=_SELECTED_WIDTHS,
                    best_validation_loss=-1, best_epoch=-1, actual_epochs=-1,
                    early_stop_reason="resumed", param_count=-1,
                    checkpoint_sha256=existing_sha,
                    checkpoint_path=str(ckpt_path),
                ))
                continue

            print(f"  Fit {fit_num}/{total_planned}: {label}")
            try:
                mf = lambda: build_d_mlp(
                    input_dim=n, widths=_SELECTED_WIDTHS,
                    activation="silu", dropout=0.1,
                )
                probe = mf()
                param_count = trainable_parameter_count(probe)
                del probe

                result = fit_d_model(
                    mf, train_x, train_y, val_x, val_y,
                    seed=seed, max_epochs=500, min_epochs=50, patience=40,
                    loss_id="huber", lr=1e-3, weight_decay=1e-4, batch_size=512,
                )
                ckpt_path.write_bytes(result.checkpoint_bytes)
                all_records.append(B3FitRecord(
                    group="selected", n=n, seed=seed,
                    widths=_SELECTED_WIDTHS,
                    best_validation_loss=result.best_validation_loss,
                    best_epoch=result.best_epoch,
                    actual_epochs=result.actual_epochs,
                    early_stop_reason=result.early_stop_reason,
                    param_count=param_count,
                    checkpoint_sha256=result.checkpoint_sha256,
                    checkpoint_path=str(ckpt_path),
                ))
                print(f"    loss={result.best_validation_loss:.6f} "
                      f"epoch={result.best_epoch}/{result.actual_epochs} "
                      f"params={param_count}")
            except Exception as e:
                print(f"    FAILED: {e}")
                failures.append({"label": label, "error": str(e)})

    # --- Controlled D: [256,128,64] (A's m12), 5 seeds per n ---
    for n in _N_VALUES:
        print(f"\n--- Controlled n={n}: generating data ---")
        data = generate_b3_data(n)
        train_x = torch.from_numpy(data["train_features"]).to(torch.float32)
        train_y = torch.from_numpy(data["train_targets"]).to(torch.float32).reshape(-1, 1)
        val_x = torch.from_numpy(data["val_features"]).to(torch.float32)
        val_y = torch.from_numpy(data["val_targets"]).to(torch.float32).reshape(-1, 1)

        for seed in _CONTROLLED_SEEDS:
            fit_num += 1
            label = f"controlled/n{n}/seed{seed}"
            ckpt_name = f"checkpoint_controlled_n{n}_seed{seed}.pt"
            ckpt_path = out / ckpt_name

            if ckpt_path.exists():
                print(f"  Fit {fit_num}/{total_planned}: {label} [SKIP — checkpoint exists]")
                existing_sha = hashlib.sha256(ckpt_path.read_bytes()).hexdigest()
                all_records.append(B3FitRecord(
                    group="controlled", n=n, seed=seed,
                    widths=_CONTROLLED_WIDTHS,
                    best_validation_loss=-1, best_epoch=-1, actual_epochs=-1,
                    early_stop_reason="resumed", param_count=-1,
                    checkpoint_sha256=existing_sha,
                    checkpoint_path=str(ckpt_path),
                ))
                continue

            print(f"  Fit {fit_num}/{total_planned}: {label}")
            try:
                mf = lambda: build_d_mlp(
                    input_dim=n, widths=_CONTROLLED_WIDTHS,
                    activation="silu", dropout=0.1,
                )
                probe = mf()
                param_count = trainable_parameter_count(probe)
                del probe

                result = fit_d_model(
                    mf, train_x, train_y, val_x, val_y,
                    seed=seed, max_epochs=500, min_epochs=50, patience=40,
                    loss_id="huber", lr=1e-3, weight_decay=1e-4, batch_size=512,
                )
                ckpt_path.write_bytes(result.checkpoint_bytes)
                all_records.append(B3FitRecord(
                    group="controlled", n=n, seed=seed,
                    widths=_CONTROLLED_WIDTHS,
                    best_validation_loss=result.best_validation_loss,
                    best_epoch=result.best_epoch,
                    actual_epochs=result.actual_epochs,
                    early_stop_reason=result.early_stop_reason,
                    param_count=param_count,
                    checkpoint_sha256=result.checkpoint_sha256,
                    checkpoint_path=str(ckpt_path),
                ))
                print(f"    loss={result.best_validation_loss:.6f} "
                      f"epoch={result.best_epoch}/{result.actual_epochs} "
                      f"params={param_count}")
            except Exception as e:
                print(f"    FAILED: {e}")
                failures.append({"label": label, "error": str(e)})

    # Build D checkpoint inventory
    d_inventory = []
    for r in all_records:
        ckpt_path = Path(r.checkpoint_path)
        if ckpt_path.exists():
            ckpt_bytes = ckpt_path.read_bytes()
            d_inventory.append({
                "name": ckpt_path.name,
                "path": str(ckpt_path),
                "size_bytes": len(ckpt_bytes),
                "sha256": hashlib.sha256(ckpt_bytes).hexdigest(),
                "group": r.group,
                "n": r.n,
                "seed": r.seed,
                "widths": list(r.widths),
            })

    # Manifest
    n_completed = len([r for r in all_records if r.early_stop_reason != "resumed"])
    n_resumed = len([r for r in all_records if r.early_stop_reason == "resumed"])
    n_failed = len(failures)

    manifest = {
        "version": "1.0",
        "run_id": out.name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "complete" if n_failed == 0 else "partial",
        "code_tip": code_tip,
        "config": {
            "selected_widths": _SELECTED_WIDTHS,
            "controlled_widths": _CONTROLLED_WIDTHS,
            "n_values": _N_VALUES,
            "selected_seeds": _SELECTED_SEEDS,
            "controlled_seeds": _CONTROLLED_SEEDS,
            "n_train": _N_TRAIN,
            "n_val": _N_VAL,
            "train_seed_namespace": _TRAIN_SEED_NS,
            "val_seed_namespace": _VAL_SEED_NS,
            "activation": "silu",
            "dropout": 0.1,
            "loss": "huber",
            "max_epochs": 500,
            "min_epochs": 50,
            "patience": 40,
            "lr": 1e-3,
            "weight_decay": 1e-4,
            "batch_size": 512,
        },
        "fit_accounting": {
            "planned": total_planned,
            "completed_new": n_completed,
            "resumed": n_resumed,
            "failed": n_failed,
            "b2_fits": 12,
            "b3_new_fits": n_completed,
            "cumulative_b_fits": 12 + n_completed,
            "cap": 100,
        },
        "p_checkpoints": {
            "source": str(_P_CHECKPOINT_BASE),
            "fit_range": f"G3-fit-{_P_FIT_START:04d}..G3-fit-{_P_FIT_END:04d}",
            "count": len(p_index),
            "architecture": "m12 [256,128,64]",
            "entries": p_index,
        },
        "d_checkpoints": d_inventory,
        "target_stats": {
            str(n): compute_target_stats_for_n(n) for n in _N_VALUES
        },
        "failures": failures,
    }

    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    # Summary
    print(f"\n=== B3 complete ===")
    print(f"  Completed new: {n_completed}")
    print(f"  Resumed: {n_resumed}")
    print(f"  Failed: {n_failed}")
    print(f"  Cumulative B fits: {12 + n_completed}")
    print(f"  Manifest: {manifest_path}")
    print(f"  Manifest SHA256: {manifest_sha}")

    return manifest


if __name__ == "__main__":
    run_b3()
