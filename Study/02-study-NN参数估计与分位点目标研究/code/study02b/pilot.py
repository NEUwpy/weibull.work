"""Micro end-to-end pilot for the D-route foundation.

Proves the full chain: generate data → encode targets → train model →
save checkpoint → load checkpoint → inference → summary.

Runs in ~30 seconds on CPU. Does NOT access any formal test namespace.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import torch

# Ensure study code path
_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))

# Ensure python/ path for common modules
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PYTHON))

from studies.common.sample import generate_sample
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


def true_x095(beta: float, eta: float, gamma: float) -> float:
    """Ground-truth x_{0.95} from Weibull parameters."""
    return gamma + eta * (-math.log(0.95)) ** (1.0 / beta)


def generate_d_training_data(
    n_train: int = 5000,
    n_val: int = 1000,
    n_sample: int = 10,
    seed: int = 42,
) -> dict:
    """Generate core-domain training and validation data for the D-route.

    Parameters drawn uniformly from the core domain:
      beta ∈ [1.2, 4], eta ∈ [100, 10000], ρ = γ/η ∈ [0, 1].

    Returns a dict with numpy arrays and per-sample anchors.
    """
    rng = np.random.default_rng(seed)
    total = n_train + n_val

    def _draw_params(rng, size):
        betas = rng.uniform(1.2, 4.0, size=size)
        etas = rng.uniform(100.0, 10000.0, size=size)
        rhos = rng.uniform(0.0, 1.0, size=size)
        gammas = rhos * etas
        return betas, etas, gammas

    betas, etas, gammas = _draw_params(rng, total)

    samples = []
    x095s = []
    for i in range(total):
        sample = generate_sample(
            float(betas[i]), float(etas[i]), float(gammas[i]),
            n_sample, i, seed=seed + 1000,
        )
        samples.append(sample)
        x095s.append(true_x095(float(betas[i]), float(etas[i]), float(gammas[i])))

    # Build features (anchored sorted z-scores) and D-targets
    anchors = [anchor_sample(s) for s in samples]
    features = np.array([a.z for a in anchors], dtype=np.float32)
    d_targets_raw = np.array([
        encode_d_target(float(x095), anch)
        for x095, anch in zip(x095s, anchors)
    ], dtype=np.float32)

    # Split train/val
    train_features = features[:n_train]
    val_features = features[n_train:]
    train_targets_raw = d_targets_raw[:n_train]
    val_targets_raw = d_targets_raw[n_train:]
    train_anchors = anchors[:n_train]
    val_anchors = anchors[n_train:]

    # Compute standardization stats from training targets
    stats = compute_d_stats(train_targets_raw)
    train_targets = standardize_d(train_targets_raw, stats)
    val_targets = standardize_d(val_targets_raw, stats)

    return {
        "train_features": train_features,
        "train_targets": train_targets.astype(np.float32),
        "val_features": val_features,
        "val_targets": val_targets.astype(np.float32),
        "train_anchors": train_anchors,
        "val_anchors": val_anchors,
        "train_x095": np.array(x095s[:n_train], dtype=float),
        "val_x095": np.array(x095s[n_train:], dtype=float),
        "target_stats": stats,
        "n_sample": n_sample,
    }


def run_pilot(output_dir: str | None = None) -> dict:
    """Run the D-route micro pilot and return a summary dict.

    If output_dir is provided, saves checkpoint.pt and summary.json there.
    """
    if output_dir is None:
        output_dir = str(Path(__file__).resolve().parent / "pilot_output")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("=== D-route micro pilot ===")
    print(f"Output: {out}")

    # 1. Generate data
    print("\n[1/5] Generating training/validation data ...")
    data = generate_d_training_data(n_train=5000, n_val=1000, n_sample=10, seed=42)
    n_sample = data["n_sample"]
    print(f"  Training: {len(data['train_features'])} rows, n={n_sample}")
    print(f"  Validation: {len(data['val_features'])} rows, n={n_sample}")

    # 2. Build model
    print("\n[2/5] Building D-route MLP ([64, 32], SiLU, dropout=0.1) ...")
    model_factory = lambda: build_d_mlp(
        input_dim=n_sample, widths=[64, 32], activation="silu", dropout=0.1,
    )
    model = model_factory()
    n_params = trainable_parameter_count(model)
    print(f"  Trainable parameters: {n_params}")

    # 3. Train
    print("\n[3/5] Training ...")
    train_x = torch.from_numpy(data["train_features"]).to(torch.float32)
    train_y = torch.from_numpy(data["train_targets"]).to(torch.float32).reshape(-1, 1)
    val_x = torch.from_numpy(data["val_features"]).to(torch.float32)
    val_y = torch.from_numpy(data["val_targets"]).to(torch.float32).reshape(-1, 1)

    result = fit_d_model(
        model_factory,
        train_x, train_y, val_x, val_y,
        seed=42,
        max_epochs=500,
        min_epochs=50,
        patience=40,
        loss_id="huber",
        lr=1e-3,
        weight_decay=1e-4,
        batch_size=512,
    )
    print(f"  Best validation loss: {result.best_validation_loss:.6f}")
    print(f"  Best epoch: {result.best_epoch}")
    print(f"  Actual epochs: {result.actual_epochs}")
    print(f"  Early stop reason: {result.early_stop_reason}")
    print(f"  Checkpoint SHA256: {result.checkpoint_sha256[:16]}...")

    # 4. Save checkpoint
    print("\n[4/5] Saving checkpoint ...")
    ckpt_path = out / "checkpoint.pt"
    ckpt_path.write_bytes(result.checkpoint_bytes)
    print(f"  Saved: {ckpt_path} ({len(result.checkpoint_bytes)} bytes)")

    # Verify checkpoint loads
    state = load_checkpoint(result.checkpoint_bytes)
    model.load_state_dict(state)
    model.eval()
    print("  Checkpoint load+verify: OK")

    # 5. Inference and summary
    print("\n[5/5] Inference and summary ...")
    with torch.no_grad():
        pred_standardized = model(val_x).detach().numpy().ravel()

    # Un-standardize then decode through anchors
    pred_encoded = unstandardize_d(pred_standardized, data["target_stats"])
    pred_x095 = np.array([
        decode_d_target(float(enc), anch)
        for enc, anch in zip(pred_encoded, data["val_anchors"])
    ])

    # Compute metrics
    metrics = aggregate_direct_metrics(pred_x095, data["val_x095"])
    print(f"  n_valid: {metrics['n_valid']}/{metrics['n_total']}")
    print(f"  RMSE: {metrics.get('rmse', 'N/A'):.4f}" if metrics.get('rmse') else "  RMSE: N/A")
    print(f"  Rel RMSE: {metrics.get('rmse_rel', 'N/A'):.6f}" if metrics.get('rmse_rel') else "  Rel RMSE: N/A")
    print(f"  Bias: {metrics.get('bias', 'N/A'):.4f}" if metrics.get('bias') else "  Bias: N/A")
    print(f"  MAE: {metrics.get('mae', 'N/A'):.4f}" if metrics.get('mae') else "  MAE: N/A")

    # Save summary
    summary = {
        "pilot": "study02b-d-route-micro",
        "code_version": "B1-minimal",
        "n_sample": n_sample,
        "n_train": len(data["train_features"]),
        "n_val": len(data["val_features"]),
        "trainable_params": n_params,
        "checkpoint_sha256": result.checkpoint_sha256,
        "best_validation_loss": result.best_validation_loss,
        "best_epoch": result.best_epoch,
        "actual_epochs": result.actual_epochs,
        "early_stop_reason": result.early_stop_reason,
        "metrics": {k: (
            float(v) if isinstance(v, (np.floating, float, int))
            else str(v) if v is not None else None
        ) for k, v in metrics.items() if not isinstance(v, dict)},
    }
    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Summary saved: {summary_path}")

    print("\n=== Pilot complete ===")
    return summary


if __name__ == "__main__":
    run_pilot()
