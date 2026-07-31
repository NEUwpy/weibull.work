"""D-route B2: frozen 12-fit validation search.

Executes exactly the compact search frozen in 02-B-实验协议.md §2:
  2 architectures × 2 losses × 3 screening seeds = 12 fits.
  n=10, core domain, 100k training rows.
  Separate training/validation seed namespaces.
  Select by decoded x0.95 relative RMSE; <1% diff → fewer params.

Each fit reuses fit_d_model from study02b.training.  Results, checkpoints,
and manifest are written to C:\\weibull-runs\\study02\\formal-b\\<run-id>.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from dataclasses import dataclass, field
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
from study02b.metrics import aggregate_direct_metrics


_EXTERNAL_ROOT = Path("C:/weibull-runs/study02/formal-b")

# Frozen search grid (2 × 2 = 4 candidates)
_ARCHITECTURES: list[tuple[Sequence[int], str]] = [
    ([64, 32], "a_64_32"),
    ([128, 64, 32], "a_m12"),
]
_LOSSES = ["huber", "mse"]
_SCREENING_SEEDS = [101, 202, 303]  # exactly 3

_TRAIN_SEED_NS = 2000
_VAL_SEED_NS = 3000
_N_SAMPLE = 10
_N_TRAIN = 100_000
_N_VAL = 20_000


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


@dataclass
class FitRecord:
    architecture_id: str
    widths: Sequence[int]
    loss: str
    seed: int
    best_validation_loss: float
    best_epoch: int
    actual_epochs: int
    early_stop_reason: str
    param_count: int
    checkpoint_sha256: str
    checkpoint_bytes: bytes
    decoded_rmse: float
    decoded_rel_rmse: float
    decoded_bias: float
    decoded_mae: float
    n_valid: int
    n_total: int

    def to_dict(self) -> dict:
        return {
            "architecture_id": self.architecture_id,
            "widths": list(self.widths),
            "loss": self.loss,
            "seed": self.seed,
            "best_validation_loss": self.best_validation_loss,
            "best_epoch": self.best_epoch,
            "actual_epochs": self.actual_epochs,
            "early_stop_reason": self.early_stop_reason,
            "param_count": self.param_count,
            "checkpoint_sha256": self.checkpoint_sha256,
            "decoded_rmse": self.decoded_rmse,
            "decoded_rel_rmse": self.decoded_rel_rmse,
            "decoded_bias": self.decoded_bias,
            "decoded_mae": self.decoded_mae,
            "n_valid": self.n_valid,
            "n_total": self.n_total,
        }


@dataclass
class CandidateMean:
    architecture_id: str
    widths: Sequence[int]
    loss: str
    param_count: int
    mean_rel_rmse: float
    rel_rmse_values: list[float]

    def to_dict(self) -> dict:
        return {
            "architecture_id": self.architecture_id,
            "widths": list(self.widths),
            "loss": self.loss,
            "param_count": self.param_count,
            "mean_rel_rmse": self.mean_rel_rmse,
            "rel_rmse_per_seed": self.rel_rmse_values,
        }


@dataclass
class SelectionResult:
    winner_id: str
    winner_widths: Sequence[int]
    winner_loss: str
    winner_param_count: int
    winner_mean_rel_rmse: float
    tie_break_applied: bool
    tie_break_reason: str
    all_candidates: list[CandidateMean]
    all_fits: list[FitRecord]

    def to_dict(self) -> dict:
        return {
            "winner_id": self.winner_id,
            "winner_widths": list(self.winner_widths),
            "winner_loss": self.winner_loss,
            "winner_param_count": self.winner_param_count,
            "winner_mean_rel_rmse": self.winner_mean_rel_rmse,
            "tie_break_applied": self.tie_break_applied,
            "tie_break_reason": self.tie_break_reason,
            "candidates": [c.to_dict() for c in self.all_candidates],
            "fits": [f.to_dict() for f in self.all_fits],
        }


def select_winner(records: list[FitRecord]) -> SelectionResult:
    """Apply the frozen B2 selection rule to 12 fit records.

    1. Compute mean decoded x0.95 relative RMSE per candidate (3 seeds).
    2. Rank ascending by mean_rel_rmse.
    3. If the best and second-best differ by < 1% (relative), select the
       candidate with fewer parameters. If still tied, prefer the one with
       lexicographically earlier architecture_id.
    """
    if len(records) != 12:
        raise ValueError(f"B2 search requires exactly 12 fits, got {len(records)}")

    # Group by (architecture_id, loss)
    groups: dict[tuple[str, str], list[FitRecord]] = {}
    for r in records:
        key = (r.architecture_id, r.loss)
        groups.setdefault(key, []).append(r)

    if len(groups) != 4:
        raise ValueError(f"Expected 4 candidate groups, got {len(groups)}")

    candidates: list[CandidateMean] = []
    for (arch_id, loss), fits in sorted(groups.items()):
        if len(fits) != 3:
            raise ValueError(
                f"Candidate {arch_id}/{loss} has {len(fits)} fits, expected 3"
            )
        values = [f.decoded_rel_rmse for f in fits]
        mean_val = float(np.mean(values))
        param_count = fits[0].param_count  # same for all seeds
        candidates.append(CandidateMean(
            architecture_id=arch_id,
            widths=fits[0].widths,
            loss=loss,
            param_count=param_count,
            mean_rel_rmse=mean_val,
            rel_rmse_values=values,
        ))

    # Sort ascending by mean_rel_rmse
    candidates.sort(key=lambda c: (c.mean_rel_rmse, c.architecture_id, c.loss))

    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None

    # Tie-break: if best and second differ by < 1% relative, pick fewer params
    tie_break_applied = False
    tie_break_reason = "best candidate selected by mean relative RMSE"
    winner = best

    if second is not None and best.mean_rel_rmse > 0:
        rel_diff = abs(best.mean_rel_rmse - second.mean_rel_rmse) / best.mean_rel_rmse
        if rel_diff < 0.01:
            tie_break_applied = True
            # Among the top candidates within 1%, pick fewest params
            close = [c for c in candidates
                     if abs(c.mean_rel_rmse - best.mean_rel_rmse) / best.mean_rel_rmse < 0.01]
            close.sort(key=lambda c: (c.param_count, c.architecture_id, c.loss))
            winner = close[0]
            if winner.architecture_id != best.architecture_id or winner.loss != best.loss:
                tie_break_reason = (
                    f"best {best.architecture_id}/{best.loss} and "
                    f"{second.architecture_id}/{second.loss} within 1% "
                    f"({rel_diff:.4f}); selected {winner.architecture_id}/{winner.loss} "
                    f"with fewer params ({winner.param_count} vs {best.param_count})"
                )
            else:
                tie_break_reason = (
                    f"tie within 1% ({rel_diff:.4f}) but best already has fewest params"
                )

    return SelectionResult(
        winner_id=f"{winner.architecture_id}:{winner.loss}",
        winner_widths=winner.widths,
        winner_loss=winner.loss,
        winner_param_count=winner.param_count,
        winner_mean_rel_rmse=winner.mean_rel_rmse,
        tie_break_applied=tie_break_applied,
        tie_break_reason=tie_break_reason,
        all_candidates=candidates,
        all_fits=records,
    )


def generate_search_data() -> dict:
    """Generate training (100k) and validation (20k) data with separate seed namespaces."""
    rng = np.random.default_rng(42)

    def _draw_params(rng, size):
        betas = rng.uniform(1.2, 4.0, size=size)
        etas = rng.uniform(100.0, 10000.0, size=size)
        rhos = rng.uniform(0.0, 1.0, size=size)
        gammas = rhos * etas
        return betas, etas, gammas

    print(f"Generating {_N_TRAIN} train + {_N_VAL} val rows (n={_N_SAMPLE}) ...")
    total = _N_TRAIN + _N_VAL
    betas, etas, gammas = _draw_params(rng, total)

    samples = []
    x095s = []
    for i in range(total):
        b, e, g = float(betas[i]), float(etas[i]), float(gammas[i])
        ns = _TRAIN_SEED_NS if i < _N_TRAIN else _VAL_SEED_NS
        rid = i if i < _N_TRAIN else i - _N_TRAIN
        sample = generate_sample(b, e, g, _N_SAMPLE, rid, seed=ns)
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
    train_anchors = anchors[:_N_TRAIN]
    val_anchors = anchors[_N_TRAIN:]

    stats = compute_d_stats(train_targets_raw)
    train_targets = standardize_d(train_targets_raw, stats).astype(np.float32)
    val_targets = standardize_d(val_targets_raw, stats).astype(np.float32)
    val_x095 = np.array(x095s[_N_TRAIN:], dtype=float)

    print(f"  Training: {train_features.shape[0]} rows")
    print(f"  Validation: {val_features.shape[0]} rows")
    return {
        "train_features": train_features,
        "train_targets": train_targets,
        "val_features": val_features,
        "val_targets": val_targets,
        "val_anchors": val_anchors,
        "val_x095": val_x095,
        "target_stats": stats,
    }


def run_search(output_dir: str | None = None) -> SelectionResult:
    """Run the complete 12-fit B2 search and return selection result."""
    if output_dir is None:
        run_id = f"B2-search-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        output_dir = str(_EXTERNAL_ROOT / run_id)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    code_tip = _git_tip()
    print(f"=== B2 D-route search ===")
    print(f"Output: {out}")
    print(f"Code tip: {code_tip}")

    # 1. Generate data
    print("\n[1/3] Generating training/validation data ...")
    data = generate_search_data()

    train_x = torch.from_numpy(data["train_features"]).to(torch.float32)
    train_y = torch.from_numpy(data["train_targets"]).to(torch.float32).reshape(-1, 1)
    val_x = torch.from_numpy(data["val_features"]).to(torch.float32)
    val_y = torch.from_numpy(data["val_targets"]).to(torch.float32).reshape(-1, 1)

    # 2. Run all 12 fits
    print("\n[2/3] Running 12 fits (2 arch × 2 loss × 3 seeds) ...")
    records: list[FitRecord] = []
    fit_num = 0
    total_fits = len(_ARCHITECTURES) * len(_LOSSES) * len(_SCREENING_SEEDS)

    for widths, arch_id in _ARCHITECTURES:
        for loss in _LOSSES:
            for seed in _SCREENING_SEEDS:
                fit_num += 1
                label = f"{arch_id}/{loss}/seed{seed}"
                print(f"\n  Fit {fit_num}/{total_fits}: {label}")

                model_factory = lambda w=widths: build_d_mlp(
                    input_dim=_N_SAMPLE, widths=list(w),
                    activation="silu", dropout=0.1,
                )
                # Check param count
                probe = model_factory()
                param_count = trainable_parameter_count(probe)
                del probe

                result = fit_d_model(
                    model_factory,
                    train_x, train_y, val_x, val_y,
                    seed=seed,
                    max_epochs=500,
                    min_epochs=50,
                    patience=40,
                    loss_id=loss,
                    lr=1e-3,
                    weight_decay=1e-4,
                    batch_size=512,
                )

                # Decode predictions
                with torch.no_grad():
                    probe2 = model_factory()
                    probe2.load_state_dict(load_checkpoint(result.checkpoint_bytes))
                    probe2.eval()
                    pred_std = probe2(val_x).detach().numpy().ravel()
                    del probe2

                pred_enc = unstandardize_d(pred_std, data["target_stats"])
                pred_x095 = np.array([
                    decode_d_target(float(enc), anch)
                    for enc, anch in zip(pred_enc, data["val_anchors"])
                ])

                metrics = aggregate_direct_metrics(pred_x095, data["val_x095"])

                # Save checkpoint
                ckpt_path = out / f"checkpoint_{arch_id}_{loss}_seed{seed}.pt"
                ckpt_path.write_bytes(result.checkpoint_bytes)

                record = FitRecord(
                    architecture_id=arch_id,
                    widths=widths,
                    loss=loss,
                    seed=seed,
                    best_validation_loss=result.best_validation_loss,
                    best_epoch=result.best_epoch,
                    actual_epochs=result.actual_epochs,
                    early_stop_reason=result.early_stop_reason,
                    param_count=param_count,
                    checkpoint_sha256=result.checkpoint_sha256,
                    checkpoint_bytes=result.checkpoint_bytes,
                    decoded_rmse=float(metrics.get("rmse", float("nan"))),
                    decoded_rel_rmse=float(metrics.get("rmse_rel", float("nan"))),
                    decoded_bias=float(metrics.get("bias", float("nan"))),
                    decoded_mae=float(metrics.get("mae", float("nan"))),
                    n_valid=int(metrics.get("n_valid", 0)),
                    n_total=int(metrics.get("n_total", 0)),
                )
                records.append(record)
                print(f"    val_loss={result.best_validation_loss:.6f} "
                      f"rel_rmse={record.decoded_rel_rmse:.6f} "
                      f"epoch={result.best_epoch}/{result.actual_epochs} "
                      f"valid={record.n_valid}/{record.n_total}")

    # 3. Select
    print("\n[3/3] Selection ...")
    selection = select_winner(records)

    print(f"\n  Candidates (mean rel RMSE):")
    for c in selection.all_candidates:
        flag = " ← WINNER" if (c.architecture_id == selection.winner_id.split(":")[0]
                                and c.loss == selection.winner_loss) else ""
        print(f"    {c.architecture_id:10s} {c.loss:5s}  "
              f"params={c.param_count:6d}  "
              f"mean_rel_rmse={c.mean_rel_rmse:.6f}  "
              f"seeds={[f'{v:.6f}' for v in c.rel_rmse_values]}{flag}")

    print(f"\n  Winner: {selection.winner_id}")
    print(f"  Tie-break: {selection.tie_break_applied} — {selection.tie_break_reason}")

    # 4. Save manifest
    config = {
        "n_sample": _N_SAMPLE,
        "n_train": _N_TRAIN,
        "n_val": _N_VAL,
        "architectures": [{"id": aid, "widths": list(w)} for w, aid in _ARCHITECTURES],
        "losses": _LOSSES,
        "screening_seeds": _SCREENING_SEEDS,
        "param_domain": "core (beta∈[1.2,4], eta∈[100,10000], ρ∈[0,1])",
        "train_seed_namespace": _TRAIN_SEED_NS,
        "val_seed_namespace": _VAL_SEED_NS,
        "total_fits": total_fits,
        "activation": "silu",
        "dropout": 0.1,
        "max_epochs": 500,
        "min_epochs": 50,
        "patience": 40,
        "lr": 1e-3,
        "weight_decay": 1e-4,
        "batch_size": 512,
    }

    manifest = {
        "version": "1.0",
        "run_id": out.name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "complete",
        "code_tip": code_tip,
        "config_sha256": hashlib.sha256(
            json.dumps(config, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "python_version": sys.version,
            "platform": sys.platform,
        },
        "config": config,
        "selection": selection.to_dict(),
    }

    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n  Manifest: {manifest_path}")

    # Write fit records CSV
    csv_path = out / "fits.csv"
    csv_lines = ["architecture_id,widths,loss,seed,val_loss,best_epoch,actual_epochs,"
                 "early_stop,param_count,decoded_rmse,decoded_rel_rmse,decoded_bias,"
                 "decoded_mae,n_valid,n_total,checkpoint_sha256"]
    for r in records:
        csv_lines.append(
            f"{r.architecture_id},\"{list(r.widths)}\",{r.loss},{r.seed},"
            f"{r.best_validation_loss:.8f},{r.best_epoch},{r.actual_epochs},"
            f"{r.early_stop_reason},{r.param_count},"
            f"{r.decoded_rmse:.6f},{r.decoded_rel_rmse:.6f},"
            f"{r.decoded_bias:.6f},{r.decoded_mae:.6f},"
            f"{r.n_valid},{r.n_total},{r.checkpoint_sha256}"
        )
    csv_path.write_text("\n".join(csv_lines) + "\n", encoding="utf-8")

    print(f"  Fits CSV: {csv_path}")
    print(f"\n=== B2 search complete ===")
    return selection


if __name__ == "__main__":
    run_search()
