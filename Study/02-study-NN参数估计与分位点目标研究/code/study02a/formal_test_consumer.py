"""One-shot test evaluation consumer for Study/02 formal runs.

Closes the production path between ``authorize_test_once`` (sealed -> unsealed_once)
and ``consume_test_once`` (unsealed_once -> consumed). After external oracle approval
binds the unseal, this module loads the selected winner's checkpoint, builds the
module test dataset (256 points x 200 repeats, per-module independent namespace),
runs inference, computes frozen evaluation metrics, and atomically transitions to
consumed with an immutable result or failure receipt.

Test data is accessed exactly once. Success and failure both produce terminal
receipts; no retry is possible after consumption.
"""

from __future__ import annotations

import hashlib
import json
import math
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import torch
from torch import nn

from . import design
from .config import FrozenConfig
from .evaluation import evaluate_rows
from .formal_config import EffectiveFormalConfig
from .formal_data import (
    FormalFixedBatch,
    FormalFixedExample,
    FormalSetBatch,
    FormalSetExample,
    collate_fixed_features,
    collate_set_features,
)
from .formal_runner import (
    FormalDataset,
    FormalDatasetSpec,
    ScalerManifest,
    _standardize,
    build_training_spec,
    cache_dataset,
    fit_training_scaler,
)
from .formal_state import consume_test_once
from .representations import SetFeatures, anchor_sample, build_features, encode_targets
from .training import load_checkpoint

_RESULT_RECEIPT_VERSION = "study02-test-result-v1"
_FAILURE_RECEIPT_VERSION = "study02-test-failure-v1"
_MODULE_TEST_ROLES = {"A-E1", "A-E2", "A-E3", "A-E4", "A-E5", "A-E6"}


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _publish_no_replace(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"receipt already exists (no-replace): {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


@dataclass(frozen=True)
class ModuleTestSpec:
    module_id: str
    route: str
    n_mode: str
    fixed_n: int | None
    point_count: int
    repeat_count: int
    design_namespace: int
    sample_namespace: int

    def __post_init__(self) -> None:
        if self.module_id not in _MODULE_TEST_ROLES:
            raise ValueError(f"unknown module test role: {self.module_id!r}")
        if self.point_count <= 0 or self.repeat_count <= 0:
            raise ValueError("test spec counts must be positive")
        if self.n_mode == "fixed_n" and self.fixed_n is None:
            raise ValueError("fixed_n mode requires fixed_n value")
        if self.n_mode == "shared_n" and self.fixed_n is not None:
            raise ValueError("shared_n mode cannot declare fixed_n")


def build_module_test_spec(
    *, module_id: str, route: str, n_mode: str, fixed_n: int | None,
    frozen_config: FrozenConfig,
    _point_count: int | None = None, _repeat_count: int | None = None,
) -> ModuleTestSpec:
    seeds = frozen_config.protocol["seeds"]
    if module_id not in seeds.get("module_test_design", {}):
        raise ValueError(f"module {module_id!r} has no frozen test design namespace")
    if module_id not in seeds.get("module_test_sample", {}):
        raise ValueError(f"module {module_id!r} has no frozen test sample namespace")
    formal_sizes = frozen_config.protocol["formal_sizes"]["module_test"]
    points = _point_count if _point_count is not None else int(formal_sizes["parameter_points"])
    repeats = _repeat_count if _repeat_count is not None else int(formal_sizes["repeats_per_point_n"])
    return ModuleTestSpec(
        module_id=module_id, route=route, n_mode=n_mode, fixed_n=fixed_n,
        point_count=points, repeat_count=repeats,
        design_namespace=int(seeds["module_test_design"][module_id]),
        sample_namespace=int(seeds["module_test_sample"][module_id]),
    )


def _build_test_rows(spec: ModuleTestSpec, frozen_config: FrozenConfig) -> list[dict[str, Any]]:
    points = design.generate_parameter_points(spec.module_id, "core", spec.point_count, frozen_config)
    if spec.n_mode == "shared_n":
        n_values = [int(v) for v in frozen_config.protocol["sample_sizes"]["core"]]
    else:
        n_values = [int(spec.fixed_n)]
    rows: list[dict[str, Any]] = []
    for point in points.to_dict(orient="records"):
        for n in n_values:
            for repeat_id in range(spec.repeat_count):
                rows.append({**point, "n": n, "repeat_id": repeat_id, "cell_id": f"{point['point_id']}:n{n}"})
    return rows


def _build_test_batch(
    spec: ModuleTestSpec, frozen_config: FrozenConfig,
) -> tuple[FormalFixedBatch | FormalSetBatch, tuple[dict[str, Any], ...]]:
    rows = _build_test_rows(spec, frozen_config)
    examples: list[FormalFixedExample | FormalSetExample] = []
    metadata: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        sample = design.generate_lifetime_sample(row, spec.sample_namespace)
        anchor = anchor_sample(sample)
        features = build_features(spec.route, sample, int(row["n"]))
        target = encode_targets(row["beta"], row["eta"], row["gamma"], anchor)
        point_id = str(row.get("point_id", f"row-{index:07d}"))
        identity = {
            "role": "module_test",
            "route": spec.route,
            "design_namespace": spec.design_namespace,
            "sample_namespace": spec.sample_namespace,
            "point_id": point_id,
            "sample_id": f"module_test:{point_id}:n{int(row['n'])}:r{int(row['repeat_id'])}:i{index:07d}",
            "repeat_id": int(row["repeat_id"]),
            "n": int(row["n"]),
            "beta": float(row["beta"]),
            "eta": float(row["eta"]),
            "rho": float(row["rho"]),
            "gamma": float(row["gamma"]),
        }
        if isinstance(features, SetFeatures):
            examples.append(FormalSetExample(features, target, anchor.location, anchor.scale))
        else:
            examples.append(FormalFixedExample(features, target, anchor.location, anchor.scale))
        metadata.append(identity)
    batch = collate_set_features(examples) if spec.route == "S" else collate_fixed_features(examples)
    return batch, tuple(metadata)


def _apply_scaler_to_test_batch(
    batch: FormalFixedBatch | FormalSetBatch, scaler: ScalerManifest,
) -> FormalFixedBatch | FormalSetBatch:
    from dataclasses import replace
    if isinstance(batch, FormalSetBatch):
        if scaler.channel != "explicit_n":
            raise ValueError("set test batch requires explicit_n scaler")
        return replace(batch, model_n=_standardize(batch.n.reshape(-1, 1), scaler).reshape(-1))
    if scaler.channel != "fixed_features":
        raise ValueError("fixed test batch requires fixed_features scaler")
    if len(scaler.mean) != batch.features.shape[1]:
        raise ValueError("scaler width does not match test feature width")
    return replace(batch, features=_standardize(batch.features, scaler))


def _decode_param_columns(raw: torch.Tensor, location: np.ndarray, scale: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = raw.detach().cpu().numpy().astype(float)
    beta = np.exp(values[:, 0])
    eta = scale * np.exp(values[:, 1])
    gamma = location - scale * np.exp(values[:, 2])
    return beta, eta, gamma


def _identify_winner_plan_row(run_dir: Path, winner_fit_id: str) -> dict[str, Any]:
    plan_path = run_dir / "plan.jsonl"
    if not plan_path.is_file():
        raise ValueError(f"plan.jsonl not found in {run_dir}")
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if str(row.get("fit_id")) == winner_fit_id:
            return row
    raise ValueError(f"winner fit {winner_fit_id!r} not found in plan.jsonl")


def _require_succeeded_checkpoint(run_dir: Path, winner_fit_id: str) -> bytes:
    checkpoint_path = run_dir / "outputs" / winner_fit_id / "checkpoint.pt"
    if not checkpoint_path.is_file():
        raise ValueError(f"winner checkpoint not found: {checkpoint_path}")
    return checkpoint_path.read_bytes()


def consume_test_evaluation(
    *,
    run_dir: Path,
    study_root: Path,
    cache_root: Path,
    module_id: str,
    winner_fit_id: str,
    timestamp: str,
    _point_count: int | None = None,
    _repeat_count: int | None = None,
) -> dict[str, Any]:
    """One-shot test evaluation: unsealed_once -> evaluate test -> consumed.

    Loads the selected winner's checkpoint, builds the module test dataset
    (per-module independent namespace), runs inference, computes frozen evaluation
    metrics, writes an immutable result or failure receipt, and transitions the
    state machine to consumed. Both success and exception produce terminal receipts;
    no retry is possible after consumption.
    """
    run_dir = Path(run_dir).resolve()
    state_path = run_dir / "formal_state.json"
    bundle_path = run_dir / "pre_unseal_bundle.json"
    approval_path = run_dir / "oracle_approval.json"
    ledger_path = run_dir / "transition_ledger.jsonl"

    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("state") != "unsealed_once":
        raise ValueError(f"test consumption requires state unsealed_once, got {state.get('state')!r}")
    if state.get("test_access_count") != 1:
        raise ValueError(f"test_access_count must be 1, got {state.get('test_access_count')}")

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle_sha = _sha256_bytes(bundle_path.read_bytes())
    if state.get("pre_unseal_bundle_sha256") != bundle_sha:
        raise ValueError("state pre_unseal_bundle_sha256 does not match bundle on disk")
    if bundle.get("test_state") != "sealed":
        raise ValueError("bundle test_state must be sealed at construction time")

    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval_sha = _sha256_bytes(approval_path.read_bytes())
    if state.get("approval_sha256") != approval_sha:
        raise ValueError("state approval_sha256 does not match approval on disk")

    code_commit = str(bundle.get("code_commit", ""))
    effective_config_sha256 = str(bundle.get("effective_config_sha256", ""))

    from .config import load_frozen_config
    from .formal_config import load_effective_formal_config
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)

    plan_row = _identify_winner_plan_row(run_dir, winner_fit_id)
    route = str(plan_row["route"])
    n_mode = "shared_n" if (plan_row.get("n_mode") == "shared_n" or plan_row.get("n") == "shared") else "fixed_n"
    fixed_n = int(plan_row["fixed_n"]) if n_mode == "fixed_n" and plan_row.get("fixed_n") is not None else (
        int(plan_row["n"]) if n_mode == "fixed_n" else None
    )

    ceiling_report_path = run_dir / "ceiling_hit_report.json"
    leakage_audit_path = run_dir / "leakage_audit.json"
    oracle_review_path = run_dir / "oracle_review.json"
    if not oracle_review_path.is_file():
        candidates = list(run_dir.glob("oracle_review*"))
        if candidates:
            oracle_review_path = candidates[0]

    try:
        checkpoint_bytes = _require_succeeded_checkpoint(run_dir, winner_fit_id)
        checkpoint_sha256 = _sha256_bytes(checkpoint_bytes)

        test_spec = build_module_test_spec(
            module_id=module_id, route=route, n_mode=n_mode, fixed_n=fixed_n,
            frozen_config=frozen, _point_count=_point_count, _repeat_count=_repeat_count,
        )
        test_batch, test_metadata = _build_test_batch(test_spec, frozen)

        training_spec = build_training_spec(
            route=route,
            distribution="core_continuous" if route not in {"H0_hsm", "H0_kde_scott1024", "H1"} else "legacy_grid",
            n_mode=n_mode, fixed_n=fixed_n,
            training_rows=int(plan_row.get("training_size", plan_row.get("training_rows", 7000))),
            frozen_config=frozen, effective_config=effective,
        )
        training_dataset = cache_dataset(training_spec, frozen, effective, cache_root)
        scaler = fit_training_scaler(training_dataset, frozen, effective)
        scaled_test_batch = _apply_scaler_to_test_batch(test_batch, scaler)

        from .formal_executor import resolve_model_factory
        is_set = route == "S"
        input_dim = None if is_set else int(scaled_test_batch.features.shape[1])
        model_factory = resolve_model_factory(str(plan_row["architecture"]), frozen, input_dim)

        state_dict = load_checkpoint(checkpoint_bytes)
        model = model_factory()
        model.load_state_dict(state_dict)
        model.eval()
        with torch.no_grad():
            if is_set:
                prediction = model(scaled_test_batch.values, scaled_test_batch.mask, scaled_test_batch.model_n)
            else:
                prediction = model(scaled_test_batch.features)

        location = scaled_test_batch.location.detach().cpu().numpy().astype(float)
        scale_arr = scaled_test_batch.scale.detach().cpu().numpy().astype(float)
        beta_hat, eta_hat, gamma_hat = _decode_param_columns(prediction, location, scale_arr)
        beta_true, eta_true, gamma_true = _decode_param_columns(scaled_test_batch.targets, location, scale_arr)

        eval_rows = [
            {
                "beta_hat": float(beta_hat[i]), "eta_hat": float(eta_hat[i]), "gamma_hat": float(gamma_hat[i]),
                "beta": float(beta_true[i]), "eta": float(eta_true[i]), "gamma": float(gamma_true[i]),
                "sample_min": float(location[i]),
            }
            for i in range(location.size)
        ]
        evaluation = evaluate_rows(eval_rows, failure_penalty=10.0)

        for key in ("unconditional_mean_l_param", "conditional_mean_l_param"):
            value = evaluation.get(key)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"test evaluation produced non-finite {key}: {value}")

        receipt = {
            "receipt_version": _RESULT_RECEIPT_VERSION,
            "module_id": module_id,
            "run_id": str(plan_row.get("run_id", "")),
            "code_commit": code_commit,
            "effective_config_sha256": effective_config_sha256,
            "pre_unseal_bundle_sha256": bundle_sha,
            "approval_sha256": approval_sha,
            "winner_fit_id": winner_fit_id,
            "winner_checkpoint_sha256": checkpoint_sha256,
            "test_design_namespace": test_spec.design_namespace,
            "test_sample_namespace": test_spec.sample_namespace,
            "test_point_count": test_spec.point_count,
            "test_repeat_count": test_spec.repeat_count,
            "test_total_rows": len(eval_rows),
            "evaluation": evaluation,
            "test_access_count": 1,
            "timestamp": timestamp,
        }
        receipt_bytes = _canonical(receipt)
        receipt_sha256 = _sha256_bytes(receipt_bytes)
        receipt_path = run_dir / "test_result_receipt.json"
        _publish_no_replace(receipt_path, receipt_bytes)

        after = consume_test_once(
            state_path=state_path, bundle_path=bundle_path, approval_path=approval_path,
            ledger_path=ledger_path, result_receipt_sha256=receipt_sha256,
            failure_receipt_sha256=None, timestamp=timestamp,
            ceiling_report_path=ceiling_report_path,
            leakage_audit_path=leakage_audit_path,
            oracle_review_path=oracle_review_path,
        )
        return {"outcome": "result", "receipt_sha256": receipt_sha256, "state": after, "evaluation": evaluation}

    except Exception as exc:
        failure_receipt = {
            "receipt_version": _FAILURE_RECEIPT_VERSION,
            "module_id": module_id,
            "run_id": str(plan_row.get("run_id", "")) if "plan_row" in dir() else "",
            "code_commit": code_commit,
            "effective_config_sha256": effective_config_sha256,
            "pre_unseal_bundle_sha256": bundle_sha,
            "approval_sha256": approval_sha,
            "winner_fit_id": winner_fit_id,
            "failure_code": type(exc).__name__[:64],
            "message": str(exc)[:500],
            "traceback_tail": traceback.format_exc()[-1000:],
            "test_access_count": 1,
            "timestamp": timestamp,
        }
        failure_bytes = _canonical(failure_receipt)
        failure_sha256 = _sha256_bytes(failure_bytes)
        failure_path = run_dir / "test_failure_receipt.json"
        _publish_no_replace(failure_path, failure_bytes)

        after = consume_test_once(
            state_path=state_path, bundle_path=bundle_path, approval_path=approval_path,
            ledger_path=ledger_path, result_receipt_sha256=None,
            failure_receipt_sha256=failure_sha256, timestamp=timestamp,
            ceiling_report_path=ceiling_report_path,
            leakage_audit_path=leakage_audit_path,
            oracle_review_path=oracle_review_path,
        )
        return {"outcome": "failure", "receipt_sha256": failure_sha256, "state": after, "error": str(exc)}


__all__ = ["ModuleTestSpec", "build_module_test_spec", "consume_test_evaluation"]
