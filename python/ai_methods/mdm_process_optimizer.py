"""AI-assisted selection of the MDM offset process variable.

The selector predicts a 26-point loss curve for the current complete-failure
sample and chooses the discrete offset with the lowest predicted loss.  It does
not calculate an observable loss for the current sample and it does not replace
the production MDM implementation.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np


MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "mdm_process_optimization"
MANIFEST_PATH = MODEL_DIR / "manifest.json"
SUPPORTED_SAMPLE_SIZES = (7, 10, 15, 20)
DEFAULT_OFFSET = 0.10


class MDMProcessOptimizationError(ValueError):
    """Raised when a sample or packaged selector violates the product contract."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise MDMProcessOptimizationError("MDM AI 过程量优化模型清单缺失")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("supported_sample_sizes") != list(SUPPORTED_SAMPLE_SIZES):
        raise MDMProcessOptimizationError("MDM AI 过程量优化模型清单与支持样本量不一致")
    return manifest


@lru_cache(maxsize=len(SUPPORTED_SAMPLE_SIZES))
def load_model(n: int) -> dict[str, Any]:
    if n not in SUPPORTED_SAMPLE_SIZES:
        supported = ", ".join(str(value) for value in SUPPORTED_SAMPLE_SIZES)
        raise MDMProcessOptimizationError(f"AI 优化偏移量当前仅支持样本量 n={supported}")

    manifest = load_manifest()
    model_entry = manifest["models"][str(n)]
    model_path = MODEL_DIR / model_entry["file"]
    if not model_path.exists():
        raise MDMProcessOptimizationError(f"样本量 n={n} 的 MDM AI 模型缺失")
    actual_hash = _sha256(model_path)
    if actual_hash != model_entry["sha256"]:
        raise MDMProcessOptimizationError(f"样本量 n={n} 的 MDM AI 模型校验失败")

    model = json.loads(model_path.read_text(encoding="utf-8"))
    if model.get("n") != n:
        raise MDMProcessOptimizationError(f"样本量 n={n} 的模型身份不一致")
    if not str(model.get("normalization", "")).startswith("Z_n = sorted(x)/mean(x)"):
        raise MDMProcessOptimizationError(f"样本量 n={n} 的模型归一化合同不一致")
    if model.get("delta_grid") != manifest["delta_grid"]:
        raise MDMProcessOptimizationError(f"样本量 n={n} 的候选偏移量网格不一致")
    return model


def validate_sample(data: Iterable[float]) -> np.ndarray:
    values = np.asarray(list(data), dtype=float).reshape(-1)
    n = int(values.size)
    if n not in SUPPORTED_SAMPLE_SIZES:
        supported = ", ".join(str(value) for value in SUPPORTED_SAMPLE_SIZES)
        raise MDMProcessOptimizationError(f"AI 优化偏移量当前仅支持样本量 n={supported}")
    if not np.all(np.isfinite(values)):
        raise MDMProcessOptimizationError("样本必须全部为有限数值")
    if np.any(values <= 0.0):
        raise MDMProcessOptimizationError("样本必须全部大于 0")
    if float(np.mean(values)) <= 0.0:
        raise MDMProcessOptimizationError("样本均值必须大于 0")
    return np.sort(values)


def predict_loss_curve(data: Iterable[float], model: dict[str, Any]) -> np.ndarray:
    values = validate_sample(data)
    if values.size != int(model["n"]):
        raise MDMProcessOptimizationError("样本量与已加载模型不一致")

    normalized = values / float(np.mean(values))
    x = (
        (normalized - np.asarray(model["input_scaler_mean"], dtype=float))
        / np.asarray(model["input_scaler_std"], dtype=float)
    ).reshape(1, -1)

    weights = model["mlp_weights"]
    coefficients = [np.asarray(value, dtype=float) for value in weights["coefs_"]]
    intercepts = [np.asarray(value, dtype=float) for value in weights["intercepts_"]]
    for layer_index, (coefficient, intercept) in enumerate(zip(coefficients, intercepts)):
        x = x @ coefficient + intercept
        if layer_index < len(coefficients) - 1:
            x = np.maximum(x, 0.0)

    curve = (
        x[0] * np.asarray(model["target_scaler_std"], dtype=float)
        + np.asarray(model["target_scaler_mean"], dtype=float)
    )
    curve = np.maximum(curve, 0.0)
    if curve.shape != (26,) or not np.all(np.isfinite(curve)):
        raise MDMProcessOptimizationError("MDM AI 模型未返回有效的 26 点预测损失曲线")
    return curve


def select_mdm_offset(data: Iterable[float]) -> dict[str, Any]:
    values = validate_sample(data)
    n = int(values.size)
    model = load_model(n)
    curve = predict_loss_curve(values, model)
    delta_grid = np.asarray(model["delta_grid"], dtype=float)
    selected_index = int(np.argmin(curve))
    default_index = int(np.argmin(np.abs(delta_grid - DEFAULT_OFFSET)))
    manifest = load_manifest()
    model_entry = manifest["models"][str(n)]

    return {
        "model_n": n,
        "delta_grid": [float(value) for value in delta_grid],
        "predicted_loss_curve": [float(value) for value in curve],
        "selected_index": selected_index,
        "selected_delta": float(delta_grid[selected_index]),
        "selected_predicted_loss": float(curve[selected_index]),
        "default_delta": DEFAULT_OFFSET,
        "default_index": default_index,
        "default_predicted_loss": float(curve[default_index]),
        "model_source_commit": manifest["model_source_commit"],
        "model_sha256": model_entry["sha256"],
        "representation": manifest["representation"],
    }
