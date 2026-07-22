"""Sealed-test-safe construction and local caching for Study/02 formal data."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
import ctypes
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
from typing import Any, Callable, Mapping

import numpy as np
import torch

from . import design
from .config import FrozenConfig
from .formal_config import EffectiveFormalConfig
from .formal_contracts import (
    APPROVED_BASE_PROTOCOL_ID,
    APPROVED_BASE_PROTOCOL_SHA256,
    APPROVED_BASE_SEARCH_ID,
    APPROVED_BASE_SEARCH_SHA256,
    APPROVED_EFFECTIVE_CONFIG_SHA256,
    _validate_effective_config,
)
from .formal_data import (
    FormalFixedBatch,
    FormalFixedExample,
    FormalSetBatch,
    FormalSetExample,
    collate_fixed_features,
    collate_set_features,
)
from .representations import SetFeatures, anchor_sample, build_features, encode_targets


DATASET_SCHEMA_VERSION = "study02-formal-dataset-v1"
_ROUTES = {
    "H0_hsm", "H0_kde_scott1024", "H1", "F0eq_hsm",
    "F0eq_kde_scott1024", "F1eq", "F2", "V", "S",
}
_HISTORICAL_ROUTES = {"H0_hsm", "H0_kde_scott1024", "H1"}
_FEATURE_COLUMNS = {
    "H0_hsm": ("raw_min", "raw_max", "raw_median", "raw_mean", "raw_half_sample_mode", "raw_cv", "n"),
    "H0_kde_scott1024": ("raw_min", "raw_max", "raw_median", "raw_mean", "raw_kde_mode", "raw_cv", "n"),
    "H1": ("raw_mean", "raw_sd", "raw_median", "raw_skewness", "raw_excess_kurtosis", "n"),
    "F0eq_hsm": ("z_max", "z_median", "z_mean", "z_half_sample_mode", "z_cv", "n"),
    "F0eq_kde_scott1024": ("z_max", "z_median", "z_mean", "z_kde_mode", "z_cv", "n"),
    "F1eq": ("z_mean", "z_sd", "z_median", "z_skewness", "z_excess_kurtosis", "n"),
    "F2": ("n", "z_max", "z_mean", "z_median", "z_sd", "z_cv", "z_skewness",
           "z_excess_kurtosis", "z_q10", "z_q25", "z_q75", "z_q90", "z_iqr", "z_mad",
           "z_half_sample_mode"),
}
_ROLE_NAMESPACES = {
    "training": (220201, 320201),
    "validation": (220202, 320202),
}
_APPROVED_PROTOCOL_CONTENT_SHA256 = "58084f3fcaa106d9258b1c7878b5dec14856cba967610fbe57abd814fb96bdf7"
_APPROVED_SEARCH_CONTENT_SHA256 = "8b5d9002c59db03a624793c516dce3f0fb60dd99251bb80a92cb6352847f4252"


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_hash(value: str, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{label} must be a lowercase SHA-256")


@dataclass(frozen=True)
class _TestSizes:
    """Explicit, cache-keyed size reduction that never resembles a formal spec."""

    rows: int
    points: int
    repeats: int
    def __post_init__(self) -> None:
        if min(self.rows, self.points, self.repeats) <= 0:
            raise ValueError("pilot_for_tests requires positive test-only sizes")


def _pilot_for_tests(*, rows: int, points: int, repeats: int) -> _TestSizes:
    """Private size declaration used only by the separate test-support builders."""

    return _TestSizes(rows=rows, points=points, repeats=repeats)


@dataclass(frozen=True)
class FormalDatasetSpec:
    role: str
    route: str
    distribution: str
    n_mode: str
    fixed_n: int | None
    row_count: int
    point_count: int
    repeat_count: int
    design_namespace: int
    sample_namespace: int
    target_form: str
    base_protocol_sha256: str
    base_search_sha256: str
    amendment_sha256: str
    effective_config_sha256: str
    schema_version: str = DATASET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.role not in _ROLE_NAMESPACES:
            raise ValueError("formal dataset role must be training or validation; test/calibration/module-test are forbidden")
        if self.route not in _ROUTES:
            raise ValueError(f"unknown formal route: {self.route!r}")
        if self.n_mode not in {"fixed_n", "shared_n"}:
            raise ValueError("n_mode must be fixed_n or shared_n")
        if self.n_mode == "fixed_n" and self.fixed_n not in {5, 7, 10, 15, 20}:
            raise ValueError("fixed_n must be a frozen core n")
        if self.n_mode == "shared_n" and self.fixed_n is not None:
            raise ValueError("shared_n cannot declare fixed_n")
        if self.route == "V" and self.n_mode != "fixed_n":
            raise ValueError("V requires fixed_n")
        if self.route == "S" and self.n_mode != "shared_n":
            raise ValueError("S requires shared_n")
        if self.route not in (_HISTORICAL_ROUTES | {"S"}) and self.n_mode != "fixed_n":
            raise ValueError("formal fixed feature routes require fixed_n")
        if min(self.row_count, self.point_count, self.repeat_count) <= 0:
            raise ValueError("dataset counts must be positive")
        expected_namespaces = _ROLE_NAMESPACES[self.role]
        if (self.design_namespace, self.sample_namespace) != expected_namespaces:
            raise ValueError(f"{self.role} dataset namespace must be exactly {expected_namespaces}")
        expected_target = "historical_raw" if self.route in _HISTORICAL_ROUTES else "equivariant_transformed"
        if self.target_form != expected_target:
            raise ValueError(f"target form for {self.route} must be {expected_target}")
        if self.schema_version != DATASET_SCHEMA_VERSION:
            raise ValueError("dataset schema version mismatch")
        for label, value in (
            ("base protocol hash", self.base_protocol_sha256),
            ("base search hash", self.base_search_sha256),
            ("amendment hash", self.amendment_sha256),
            ("effective config hash", self.effective_config_sha256),
        ):
            _require_hash(value, label)

    @property
    def cache_key(self) -> str:
        return _sha256_bytes(_canonical_bytes(_spec_payload(self)))


@dataclass(frozen=True)
class _TestDatasetSpec(FormalDatasetSpec):
    """Structurally separate spec that public production entry points reject."""


def _spec_payload(spec: FormalDatasetSpec) -> dict[str, Any]:
    payload = {
        field.name: getattr(spec, field.name)
        for field in fields(spec)
        if not field.name.startswith("_")
    }
    payload["test_only_override"] = type(spec) is _TestDatasetSpec
    return payload


def _content_hash(value: Any) -> str:
    return _sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _validate_authorities(frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig) -> None:
    try:
        _validate_effective_config(effective_config)
    except ValueError as exc:
        raise ValueError(f"approved effective config validation failed: {exc}") from exc
    _validate_frozen_config(frozen_config)
    if effective_config.effective_config_sha256 != APPROVED_EFFECTIVE_CONFIG_SHA256:
        raise ValueError("approved effective config hash mismatch")


def _validate_frozen_config(frozen_config: FrozenConfig) -> None:
    if not isinstance(frozen_config, FrozenConfig) or (
        frozen_config.protocol_sha256 != APPROVED_BASE_PROTOCOL_SHA256
        or frozen_config.search_sha256 != APPROVED_BASE_SEARCH_SHA256
        or frozen_config.protocol.get("protocol_id") != APPROVED_BASE_PROTOCOL_ID
        or frozen_config.search.get("search_id") != APPROVED_BASE_SEARCH_ID
        or _content_hash(frozen_config.protocol) != _APPROVED_PROTOCOL_CONTENT_SHA256
        or _content_hash(frozen_config.search) != _APPROVED_SEARCH_CONTENT_SHA256
    ):
        raise ValueError("frozen config content does not match the approved authority")


def _validate_spec_entry(spec: FormalDatasetSpec) -> None:
    if type(spec) not in {FormalDatasetSpec, _TestDatasetSpec}:
        raise ValueError("dataset spec type is not supported")
    spec.__post_init__()
    if type(spec) is _TestDatasetSpec:
        return
    if spec.route in _HISTORICAL_ROUTES:
        expected = (7000, 80, 18) if spec.role == "training" else (2000, 20, 20)
        if (spec.row_count, spec.point_count, spec.repeat_count) != expected:
            raise ValueError("historical production spec does not match frozen 80/20 allocation")
        return
    if spec.role == "training":
        if spec.row_count not in {7000, 25000, 100000, 400000}:
            raise ValueError("production training specs must enforce frozen row counts")
        if spec.distribution == "legacy_grid":
            cells = 500 if spec.n_mode == "shared_n" else 100
            expected_allocation = (100, (spec.row_count + cells - 1) // cells)
        elif spec.distribution in {"core_continuous", "extended_wide"}:
            expected_allocation = (spec.row_count, 1)
        else:
            raise ValueError("production training distribution is not frozen")
        if (spec.point_count, spec.repeat_count) != expected_allocation:
            raise ValueError("production training point/repeat allocation is not frozen")
    else:
        n_count = 5 if spec.n_mode == "shared_n" else 1
        if (spec.point_count, spec.repeat_count, spec.row_count) != (256, 50, 256 * 50 * n_count):
            raise ValueError("production validation specs must enforce exactly 256 points x 50 repeats per n")


def _spec_common(
    *, route: str, distribution: str, n_mode: str, fixed_n: int | None,
    frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
) -> dict[str, Any]:
    if not isinstance(frozen_config, FrozenConfig) or not isinstance(effective_config, EffectiveFormalConfig):
        raise ValueError("frozen_config and effective_config are required")
    _validate_authorities(frozen_config, effective_config)
    return {
        "route": route,
        "distribution": distribution,
        "n_mode": n_mode,
        "fixed_n": fixed_n,
        "target_form": "historical_raw" if route in _HISTORICAL_ROUTES else "equivariant_transformed",
        "base_protocol_sha256": frozen_config.protocol_sha256,
        "base_search_sha256": frozen_config.search_sha256,
        "amendment_sha256": effective_config.amendment_sha256,
        "effective_config_sha256": effective_config.effective_config_sha256,
    }


def _build_training_spec_impl(
    *, route: str, distribution: str, n_mode: str, fixed_n: int | None,
    training_rows: int, frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
    _pilot_for_tests: _TestSizes | None = None,
) -> FormalDatasetSpec:
    """Build an approved training spec; H routes follow A-E1's frozen 80-cell split."""
    sizes = tuple(int(value) for value in frozen_config.protocol["training_sizes"])
    if training_rows not in sizes:
        raise ValueError(f"training_rows must be a frozen training size {sizes}")
    if route in _HISTORICAL_ROUTES and (
        distribution != "legacy_grid" or n_mode != "shared_n" or fixed_n is not None or training_rows != 7000
    ):
        raise ValueError("historical training requires legacy_grid/shared_n/7000")
    pilot = _pilot_for_tests if isinstance(_pilot_for_tests, _TestSizes) else None
    if _pilot_for_tests is not None and pilot is None:
        raise ValueError("invalid private test override")
    rows = pilot.rows if pilot is not None else training_rows
    if route in _HISTORICAL_ROUTES:
        points = min(80, (rows + 4) // 5)
        repeats = max(1, (rows + 399) // 400)
    elif distribution == "legacy_grid":
        points = min(100, (rows + (4 if n_mode == "shared_n" else 0)) // (5 if n_mode == "shared_n" else 1))
        cells = 500 if n_mode == "shared_n" else 100
        repeats = max(1, (rows + cells - 1) // cells)
    else:
        points, repeats = rows, 1
    spec_class = _TestDatasetSpec if pilot is not None else FormalDatasetSpec
    spec = spec_class(
        role="training", row_count=rows, point_count=points, repeat_count=repeats,
        design_namespace=220201, sample_namespace=320201,
        **_spec_common(
            route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
            frozen_config=frozen_config, effective_config=effective_config,
        ),
    )
    _validate_spec_entry(spec)
    return spec


def build_training_spec(
    *, route: str, distribution: str, n_mode: str, fixed_n: int | None,
    training_rows: int, frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
) -> FormalDatasetSpec:
    return _build_training_spec_impl(
        route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
        training_rows=training_rows, frozen_config=frozen_config, effective_config=effective_config,
    )


def _build_training_spec_for_tests(
    *, route: str, distribution: str, n_mode: str, fixed_n: int | None,
    training_rows: int, frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
    pilot: _TestSizes,
) -> FormalDatasetSpec:
    return _build_training_spec_impl(
        route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
        training_rows=training_rows, frozen_config=frozen_config, effective_config=effective_config,
        _pilot_for_tests=pilot,
    )


def _build_validation_spec_impl(
    *, route: str, distribution: str, n_mode: str, fixed_n: int | None,
    frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
    _pilot_for_tests: _TestSizes | None = None,
) -> FormalDatasetSpec:
    """Build validation data; H routes use A-E1's 20 held-out legacy cells."""
    historical = route in _HISTORICAL_ROUTES
    if historical:
        if distribution != "legacy_grid" or n_mode != "shared_n" or fixed_n is not None:
            raise ValueError("historical validation requires frozen legacy_grid/shared_n split")
    elif distribution != "core_continuous":
        raise ValueError("formal validation distribution must be core_continuous Sobol")
    formal = frozen_config.protocol["formal_sizes"]["validation"]
    points = int(formal["parameter_points"])
    repeats = int(formal["repeats_per_point_n"])
    pilot = _pilot_for_tests if isinstance(_pilot_for_tests, _TestSizes) else None
    if _pilot_for_tests is not None and pilot is None:
        raise ValueError("invalid private test override")
    if historical:
        points, repeats = 20, 20
        rows = pilot.rows if pilot is not None else 2000
        if pilot is not None:
            points = min(20, (rows + 4) // 5)
            repeats = max(1, (rows + 99) // 100)
    else:
        if pilot is not None:
            points, repeats = pilot.points, pilot.repeats
        n_count = len(frozen_config.protocol["sample_sizes"]["core"]) if n_mode == "shared_n" else 1
        rows = points * repeats * n_count
    spec_class = _TestDatasetSpec if pilot is not None else FormalDatasetSpec
    spec = spec_class(
        role="validation", row_count=rows,
        point_count=points, repeat_count=repeats,
        design_namespace=220202, sample_namespace=320202,
        **_spec_common(
            route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
            frozen_config=frozen_config, effective_config=effective_config,
        ),
    )
    _validate_spec_entry(spec)
    return spec


def build_validation_spec(
    *, route: str, distribution: str, n_mode: str, fixed_n: int | None,
    frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
) -> FormalDatasetSpec:
    return _build_validation_spec_impl(
        route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
        frozen_config=frozen_config, effective_config=effective_config,
    )


def _build_validation_spec_for_tests(
    *, route: str, distribution: str, n_mode: str, fixed_n: int | None,
    frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
    pilot: _TestSizes,
) -> FormalDatasetSpec:
    return _build_validation_spec_impl(
        route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
        frozen_config=frozen_config, effective_config=effective_config,
        _pilot_for_tests=pilot,
    )


def _validate_spec_against_authorities(
    spec: FormalDatasetSpec,
    frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig,
) -> None:
    _validate_authorities(frozen_config, effective_config)
    expected_hashes = (
        frozen_config.protocol_sha256,
        frozen_config.search_sha256,
        effective_config.amendment_sha256,
        effective_config.effective_config_sha256,
    )
    actual_hashes = (
        spec.base_protocol_sha256,
        spec.base_search_sha256,
        spec.amendment_sha256,
        spec.effective_config_sha256,
    )
    if actual_hashes != expected_hashes:
        raise ValueError("dataset spec authority hashes do not match approved configs")
    if type(spec) is _TestDatasetSpec:
        return
    expected = (
        build_training_spec(
            route=spec.route, distribution=spec.distribution, n_mode=spec.n_mode,
            fixed_n=spec.fixed_n, training_rows=spec.row_count,
            frozen_config=frozen_config, effective_config=effective_config,
        )
        if spec.role == "training" else
        build_validation_spec(
            route=spec.route, distribution=spec.distribution, n_mode=spec.n_mode,
            fixed_n=spec.fixed_n, frozen_config=frozen_config, effective_config=effective_config,
        )
    )
    if spec != expected:
        raise ValueError("production dataset spec is not the canonical frozen reconstruction")


@dataclass(frozen=True)
class FormalDataset:
    spec: FormalDatasetSpec
    batch: FormalFixedBatch | FormalSetBatch
    metadata: tuple[dict[str, Any], ...]
    dataset_hash: str
    preprocessing_hash: str | None = None


class FormalDatasetRowError(ValueError):
    """A feature/target/sample failure with the complete row identity attached."""


def _design_rows(spec: FormalDatasetSpec, frozen: FrozenConfig) -> list[dict[str, Any]]:
    if spec.route in _HISTORICAL_ROUTES:
        return design.allocate_historical_rows(spec.role, spec.row_count, frozen).to_dict(orient="records")
    if spec.role == "training":
        frame = design.allocate_training_rows(
            spec.distribution, spec.n_mode, spec.row_count, frozen, fixed_n=spec.fixed_n,
        )
        return frame.to_dict(orient="records")
    if spec.distribution == "legacy_grid":
        raise ValueError("validation requires a role-isolated Sobol distribution, not legacy_grid")
    layer = "core" if spec.distribution == "core_continuous" else spec.distribution
    points = design.generate_parameter_points("validation", layer, spec.point_count, frozen)
    n_values = [int(spec.fixed_n)] if spec.n_mode == "fixed_n" else [
        int(value) for value in frozen.protocol["sample_sizes"]["core"]
    ]
    rows: list[dict[str, Any]] = []
    for point in points.to_dict(orient="records"):
        for n in n_values:
            for repeat_id in range(spec.repeat_count):
                rows.append({**point, "n": n, "repeat_id": repeat_id, "cell_id": f"{point['point_id']}:n{n}"})
    return rows


def _metadata_row(spec: FormalDatasetSpec, row: Mapping[str, Any], index: int) -> dict[str, Any]:
    point_id = str(row.get("point_id", row.get("parameter_cell_id", f"row-{index:07d}")))
    repeat_id = int(row["repeat_id"])
    n = int(row["n"])
    return {
        "role": spec.role,
        "route": spec.route,
        "design_namespace": spec.design_namespace,
        "sample_namespace": spec.sample_namespace,
        "point_id": point_id,
        "sample_id": f"{spec.role}:{point_id}:n{n}:r{repeat_id}:i{index:07d}",
        "repeat_id": repeat_id,
        "n": n,
        "beta": float(row["beta"]),
        "eta": float(row["eta"]),
        "rho": float(row["rho"]),
        "gamma": float(row["gamma"]),
    }


def _array_hash(name: str, value: np.ndarray, digest: Any) -> None:
    contiguous = np.ascontiguousarray(value)
    digest.update(name.encode("utf-8") + b"\0")
    digest.update(str(contiguous.dtype).encode("ascii") + b"\0")
    digest.update(_canonical_bytes(list(contiguous.shape)))
    digest.update(contiguous.tobytes(order="C"))


def _dataset_hash(spec: FormalDatasetSpec, batch: FormalFixedBatch | FormalSetBatch, metadata: tuple[dict[str, Any], ...]) -> str:
    digest = hashlib.sha256(_canonical_bytes(_spec_payload(spec)))
    tensors = {field.name: getattr(batch, field.name) for field in fields(batch)}
    for name in sorted(tensors):
        _array_hash(name, tensors[name].detach().cpu().numpy(), digest)
    digest.update(_canonical_bytes(metadata))
    return digest.hexdigest()


def _validate_float32_array(value: Any, shape: tuple[int, ...], label: str) -> None:
    array = np.asarray(value)
    if array.shape != shape or not np.isfinite(array).all():
        raise ValueError(f"{label} has invalid shape or non-finite values")
    with np.errstate(over="ignore", invalid="ignore"):
        converted = array.astype(np.float32)
    if not np.isfinite(converted).all():
        raise ValueError(f"{label} must remain finite after float32 conversion")


def _validate_example_before_collate(
    features: np.ndarray | SetFeatures,
    target: np.ndarray,
    location: float,
    scale: float,
    n: int,
) -> None:
    _validate_float32_array(target, (3,), "target")
    _validate_float32_array(np.asarray([location]), (1,), "location")
    _validate_float32_array(np.asarray([scale]), (1,), "scale")
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("scale must be positive")
    if isinstance(features, SetFeatures):
        _validate_float32_array(features.values, (n, 1), "set values")
        if features.mask.shape != (n,) or features.mask.dtype.kind != "b" or int(features.mask.sum()) != n:
            raise ValueError("set mask/n shape mismatch")
    else:
        values = np.asarray(features)
        if values.ndim != 1 or values.size == 0:
            raise ValueError("fixed features must be a non-empty vector")
        _validate_float32_array(values, (values.size,), "fixed features")


_METADATA_FIELDS = {
    "role", "route", "design_namespace", "sample_namespace", "point_id", "sample_id",
    "repeat_id", "n", "beta", "eta", "rho", "gamma",
}


def _validate_dataset_semantics(
    dataset: FormalDataset,
    *,
    require_raw: bool,
    frozen_config: FrozenConfig | None = None,
) -> None:
    if not isinstance(dataset, FormalDataset):
        raise ValueError("dataset must be a FormalDataset")
    _validate_spec_entry(dataset.spec)
    batch = dataset.batch
    count = len(batch)
    if count != dataset.spec.row_count or len(dataset.metadata) != count:
        raise ValueError("dataset row count does not match its spec")
    float_tensors = {
        "targets": batch.targets, "location": batch.location, "scale": batch.scale,
    }
    if batch.targets.dtype != torch.float32 or batch.targets.shape != (count, 3):
        raise ValueError("dataset targets must be float32 [rows,3]")
    if batch.location.shape != (count,) or batch.scale.shape != (count,):
        raise ValueError("dataset anchors must be row vectors")
    if isinstance(batch, FormalSetBatch):
        if dataset.spec.route != "S":
            raise ValueError("set batch route mismatch")
        if batch.values.dtype != torch.float32 or batch.values.ndim != 3 or batch.values.shape[0] != count or batch.values.shape[2] != 1:
            raise ValueError("set values dtype/shape mismatch")
        if batch.mask.dtype != torch.bool or batch.mask.shape != batch.values.shape[:2]:
            raise ValueError("set mask dtype/shape mismatch")
        if batch.n.dtype != torch.float32 or batch.model_n.dtype != torch.float32:
            raise ValueError("set n channels must be float32")
        if batch.n.shape != (count,) or batch.model_n.shape != (count,):
            raise ValueError("set n channels must be row vectors")
        if not torch.equal(batch.mask.sum(1).to(batch.n.dtype), batch.n):
            raise ValueError("set raw n does not equal mask count")
        if require_raw and not torch.equal(batch.model_n, batch.n):
            raise ValueError("raw set cache requires model_n == n")
        if bool((batch.values.masked_select(~batch.mask.unsqueeze(-1)) != 0).any()):
            raise ValueError("set cache padding must be canonical zero")
        float_tensors.update(values=batch.values, n=batch.n, model_n=batch.model_n)
    else:
        if dataset.spec.route == "S":
            raise ValueError("S route requires a set batch")
        widths = {**{route: len(columns) for route, columns in _FEATURE_COLUMNS.items()}, "V": int(dataset.spec.fixed_n or 0)}
        expected_width = widths[dataset.spec.route]
        if batch.features.dtype != torch.float32 or batch.features.shape != (count, expected_width):
            raise ValueError("fixed feature dtype/route width mismatch")
        float_tensors["features"] = batch.features
    for name, tensor in float_tensors.items():
        if tensor.dtype != torch.float32 or not bool(torch.isfinite(tensor).all()):
            raise ValueError(f"dataset {name} must be finite float32")
    if not bool((batch.scale > 0).all()):
        raise ValueError("dataset scales must be positive")
    sample_ids: set[str] = set()
    point_ids: set[str] = set()
    for index, row in enumerate(dataset.metadata):
        if not isinstance(row, dict) or set(row) != _METADATA_FIELDS:
            raise ValueError("dataset metadata schema mismatch")
        expected_n = int(batch.n[index].item()) if isinstance(batch, FormalSetBatch) else dataset.spec.fixed_n
        if (
            row["role"] != dataset.spec.role or row["route"] != dataset.spec.route
            or row["design_namespace"] != dataset.spec.design_namespace
            or row["sample_namespace"] != dataset.spec.sample_namespace
            or (expected_n is not None and row["n"] != expected_n)
            or row["n"] not in {5, 7, 10, 15, 20}
        ):
            raise ValueError("dataset metadata role/namespace/n mismatch")
        if not isinstance(row["sample_id"], str) or not isinstance(row["point_id"], str):
            raise ValueError("dataset metadata IDs must be strings")
        expected_sample_id = (
            f"{dataset.spec.role}:{row['point_id']}:n{row['n']}:r{row['repeat_id']}:i{index:07d}"
        )
        if row["sample_id"] != expected_sample_id:
            raise ValueError("dataset sample ID is noncanonical")
        if row["sample_id"] in sample_ids:
            raise ValueError("dataset sample IDs must be unique")
        sample_ids.add(row["sample_id"])
        point_ids.add(row["point_id"])
        numeric = np.asarray([row["beta"], row["eta"], row["rho"], row["gamma"]], dtype=float)
        if not np.isfinite(numeric).all() or row["beta"] <= 0 or row["eta"] <= 0:
            raise ValueError("dataset metadata parameters are invalid")
        if not np.isclose(row["gamma"], row["rho"] * row["eta"], rtol=1e-12, atol=1e-12):
            raise ValueError("dataset metadata rho/gamma mismatch")
        if not isinstance(row["repeat_id"], int) or not 0 <= row["repeat_id"] < dataset.spec.repeat_count:
            raise ValueError("dataset repeat identity is invalid")
        if dataset.spec.target_form == "historical_raw":
            expected_target = np.asarray([row["beta"], row["eta"], row["gamma"]], dtype=np.float32)
        else:
            location = float(batch.location[index].item())
            scale = float(batch.scale[index].item())
            gap = location - float(row["gamma"])
            if gap <= 0:
                raise ValueError("dataset transformed target support is invalid")
            expected_target = np.asarray([
                np.log(row["beta"]), np.log(row["eta"] / scale), np.log(gap / scale),
            ], dtype=np.float32)
        if not np.allclose(batch.targets[index].cpu().numpy(), expected_target, rtol=1e-4, atol=1e-4):
            raise ValueError("dataset target does not match metadata/anchors")
    if len(point_ids) != dataset.spec.point_count:
        raise ValueError("dataset parameter point count mismatch")
    if frozen_config is not None:
        _validate_frozen_config(frozen_config)
        expected_rows = _design_rows(dataset.spec, frozen_config)
        expected_metadata = tuple(
            _metadata_row(dataset.spec, row, index) for index, row in enumerate(expected_rows)
        )
        if dataset.metadata != expected_metadata:
            raise ValueError("cache metadata does not match the frozen design rows")
    if require_raw:
        if dataset.preprocessing_hash is not None:
            raise ValueError("dataset is already preprocessed")
        if dataset.dataset_hash != _dataset_hash(dataset.spec, batch, dataset.metadata):
            raise ValueError("raw dataset hash mismatch")


def _build_dataset_impl(
    spec: FormalDatasetSpec,
    frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig,
    *,
    sample_generator: Callable[[Mapping[str, Any], int], np.ndarray] | None = None,
) -> FormalDataset:
    _validate_spec_entry(spec)
    _validate_spec_against_authorities(spec, frozen_config, effective_config)
    if sample_generator is not None and type(spec) is not _TestDatasetSpec:
        raise ValueError("custom sample_generator is permitted only for pilot_for_tests specs")
    generator = sample_generator or design.generate_lifetime_sample
    rows = _design_rows(spec, frozen_config)
    if len(rows) != spec.row_count:
        raise RuntimeError(f"dataset allocation returned {len(rows)} rows, expected {spec.row_count}")
    examples: list[FormalFixedExample | FormalSetExample] = []
    metadata: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        identity = _metadata_row(spec, row, index)
        try:
            sample = generator(row, spec.sample_namespace)
            anchor = anchor_sample(sample)
            features = build_features(spec.route, sample, int(row["n"]))
            target = (
                np.array([row["beta"], row["eta"], row["gamma"]], dtype=float)
                if spec.target_form == "historical_raw"
                else encode_targets(row["beta"], row["eta"], row["gamma"], anchor)
            )
            _validate_example_before_collate(features, target, anchor.location, anchor.scale, int(row["n"]))
            if isinstance(features, SetFeatures):
                examples.append(FormalSetExample(features, target, anchor.location, anchor.scale))
            else:
                examples.append(FormalFixedExample(features, target, anchor.location, anchor.scale))
        except Exception as exc:
            raise FormalDatasetRowError(
                f"{spec.role}:{spec.route} sample_id={identity['sample_id']} point_id={identity['point_id']} failed: {exc}"
            ) from exc
        metadata.append(identity)
    batch = collate_set_features(examples) if spec.route == "S" else collate_fixed_features(examples)
    metadata_tuple = tuple(metadata)
    dataset = FormalDataset(spec, batch, metadata_tuple, _dataset_hash(spec, batch, metadata_tuple))
    _validate_dataset_semantics(dataset, require_raw=True, frozen_config=frozen_config)
    return dataset


def build_dataset(
    spec: FormalDatasetSpec,
    frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig,
) -> FormalDataset:
    if type(spec) is not FormalDatasetSpec:
        raise ValueError("public production builder rejects test-only specs")
    return _build_dataset_impl(spec, frozen_config, effective_config)


def _build_dataset_for_tests(
    spec: FormalDatasetSpec,
    frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig,
    *,
    sample_generator: Callable[[Mapping[str, Any], int], np.ndarray] | None = None,
) -> FormalDataset:
    if type(spec) is not _TestDatasetSpec:
        raise ValueError("private test dataset builder requires a test-only spec")
    return _build_dataset_impl(
        spec, frozen_config, effective_config, sample_generator=sample_generator,
    )


@dataclass(frozen=True)
class ScalerManifest:
    source_role: str
    source_route: str
    source_distribution: str
    source_n_mode: str
    source_fixed_n: int | None
    source_spec_cache_key: str
    source_test_only: bool
    source_row_count: int
    channel: str
    columns: tuple[str, ...]
    mean: tuple[float, ...]
    sd: tuple[float, ...]
    zero_sd_handling: str
    source_dataset_hash: str
    effective_config_sha256: str
    payload_sha256: str = ""


def _scaler_payload(scaler: ScalerManifest) -> dict[str, Any]:
    return {
        field.name: getattr(scaler, field.name)
        for field in fields(scaler)
        if field.name != "payload_sha256"
    }


def _validate_scaler(scaler: ScalerManifest) -> None:
    if not isinstance(scaler, ScalerManifest):
        raise ValueError("scaler must be a ScalerManifest")
    expected_hash = _sha256_bytes(_canonical_bytes(_scaler_payload(scaler)))
    if scaler.payload_sha256 != expected_hash:
        raise ValueError("scaler payload hash mismatch")
    _require_hash(scaler.source_spec_cache_key, "scaler source spec cache key")
    if scaler.zero_sd_handling != "map_to_zero" or not scaler.columns:
        raise ValueError("scaler zero policy/columns are invalid")
    if not isinstance(scaler.source_row_count, int) or scaler.source_row_count <= 0:
        raise ValueError("scaler source row count is invalid")
    if len(scaler.mean) != len(scaler.sd) or len(scaler.mean) != len(scaler.columns):
        raise ValueError("scaler statistics shape mismatch")
    mean = np.asarray(scaler.mean, dtype=np.float64)
    sd = np.asarray(scaler.sd, dtype=np.float64)
    if not np.isfinite(mean).all() or not np.isfinite(sd).all() or np.any(sd < 0):
        raise ValueError("scaler statistics must be finite with nonnegative sd")


def fit_training_scaler(
    dataset: FormalDataset,
    frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig,
) -> ScalerManifest:
    _validate_spec_against_authorities(dataset.spec, frozen_config, effective_config)
    _validate_dataset_semantics(dataset, require_raw=True, frozen_config=frozen_config)
    if dataset.spec.role != "training":
        raise ValueError("scaler may be fit from training data only")
    if isinstance(dataset.batch, FormalSetBatch):
        values = dataset.batch.n.detach().cpu().numpy().reshape(-1, 1).astype(np.float64)
        channel = "explicit_n"
        columns = ("n",)
    else:
        values = dataset.batch.features.detach().cpu().numpy().astype(np.float64)
        channel = "fixed_features"
        columns = _FEATURE_COLUMNS.get(
            dataset.spec.route,
            tuple(f"sorted_z_{index}" for index in range(values.shape[1])),
        )
        if len(columns) != values.shape[1]:
            raise RuntimeError("frozen route columns do not match constructed feature width")
    mean = np.mean(values, axis=0)
    sd = np.std(values, axis=0, ddof=0)
    scaler = ScalerManifest(
        source_role="training", source_route=dataset.spec.route,
        source_distribution=dataset.spec.distribution, source_n_mode=dataset.spec.n_mode,
        source_fixed_n=dataset.spec.fixed_n, source_spec_cache_key=dataset.spec.cache_key,
        source_test_only=type(dataset.spec) is _TestDatasetSpec,
        source_row_count=dataset.spec.row_count,
        channel=channel, columns=columns,
        mean=tuple(float(value) for value in mean), sd=tuple(float(value) for value in sd),
        zero_sd_handling="map_to_zero", source_dataset_hash=dataset.dataset_hash,
        effective_config_sha256=dataset.spec.effective_config_sha256,
    )
    object.__setattr__(scaler, "payload_sha256", _sha256_bytes(_canonical_bytes(_scaler_payload(scaler))))
    _validate_scaler(scaler)
    return scaler


def _standardize(values: Any, scaler: ScalerManifest) -> Any:
    mean = values.new_tensor(scaler.mean)
    sd = values.new_tensor(scaler.sd)
    safe = sd.where(sd != 0, values.new_ones(sd.shape))
    standardized = (values - mean) / safe
    return standardized.where(sd != 0, values.new_zeros(standardized.shape))


def apply_training_scaler(
    dataset: FormalDataset,
    scaler: ScalerManifest,
    source_training_dataset: FormalDataset,
    frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig,
) -> FormalDataset:
    if dataset.preprocessing_hash is not None:
        raise ValueError("dataset is already preprocessed")
    _validate_spec_against_authorities(dataset.spec, frozen_config, effective_config)
    _validate_dataset_semantics(dataset, require_raw=True, frozen_config=frozen_config)
    _validate_scaler(scaler)
    _validate_spec_against_authorities(
        source_training_dataset.spec, frozen_config, effective_config,
    )
    _validate_dataset_semantics(
        source_training_dataset, require_raw=True, frozen_config=frozen_config,
    )
    if source_training_dataset.spec.role != "training":
        raise ValueError("scaler source dataset must be training")
    expected_scaler = fit_training_scaler(
        source_training_dataset, frozen_config, effective_config,
    )
    if scaler != expected_scaler:
        raise ValueError("scaler payload does not match the supplied training dataset")
    source_binding = (
        source_training_dataset.spec.cache_key,
        source_training_dataset.spec.distribution,
        source_training_dataset.dataset_hash,
        source_training_dataset.spec.row_count,
        type(source_training_dataset.spec) is _TestDatasetSpec,
    )
    manifest_binding = (
        scaler.source_spec_cache_key,
        scaler.source_distribution,
        scaler.source_dataset_hash,
        scaler.source_row_count,
        scaler.source_test_only,
    )
    if manifest_binding != source_binding:
        raise ValueError("scaler manifest source binding is not exact")
    if scaler.source_role != "training" or scaler.effective_config_sha256 != dataset.spec.effective_config_sha256:
        raise ValueError("scaler is not owned by the matching training config")
    if scaler.source_test_only is not (type(dataset.spec) is _TestDatasetSpec):
        raise ValueError("pilot/formal scaler state does not match the dataset")
    if not scaler.source_test_only and scaler.source_row_count not in {7000, 25000, 100000, 400000}:
        raise ValueError("formal scaler source row count is not approved")
    expected_provenance = (dataset.spec.route, dataset.spec.n_mode, dataset.spec.fixed_n)
    actual_provenance = (scaler.source_route, scaler.source_n_mode, scaler.source_fixed_n)
    if actual_provenance != expected_provenance:
        raise ValueError("scaler route/n provenance does not match the dataset")
    _require_hash(scaler.source_dataset_hash, "scaler source dataset hash")
    if dataset.spec.role == "training" and (
        scaler.source_distribution != dataset.spec.distribution
        or scaler.source_spec_cache_key != dataset.spec.cache_key
        or scaler.source_dataset_hash != dataset.dataset_hash
    ):
        raise ValueError("scaler source distribution/hash does not match this training dataset")
    if isinstance(dataset.batch, FormalSetBatch):
        if scaler.channel != "explicit_n" or scaler.columns != ("n",) or len(scaler.mean) != 1:
            raise ValueError("set data requires an explicit_n scaler")
        batch = replace(dataset.batch, model_n=_standardize(dataset.batch.n.reshape(-1, 1), scaler).reshape(-1))
        if not torch.equal(batch.n, dataset.batch.n) or not torch.equal(batch.mask, dataset.batch.mask):
            raise RuntimeError("set preprocessing modified the raw batch contract")
        prepared_values = batch.model_n
    else:
        expected_columns = _FEATURE_COLUMNS.get(
            dataset.spec.route,
            tuple(f"sorted_z_{index}" for index in range(dataset.batch.features.shape[1])),
        )
        if (
            scaler.channel != "fixed_features" or scaler.columns != expected_columns
            or len(scaler.mean) != dataset.batch.features.shape[1]
        ):
            raise ValueError("fixed data requires a same-width fixed feature scaler")
        batch = replace(dataset.batch, features=_standardize(dataset.batch.features, scaler))
        prepared_values = batch.features
    if not bool(torch.isfinite(prepared_values).all()):
        raise ValueError("scaler preprocessing produced non-finite values")
    preprocessing_hash = _sha256_bytes(_canonical_bytes({
        "source_dataset_hash": dataset.dataset_hash,
        "scaler_payload_sha256": scaler.payload_sha256,
        "operation": "training_only_standardization_v1",
    }))
    return replace(dataset, batch=batch, preprocessing_hash=preprocessing_hash)


def _batch_arrays(batch: FormalFixedBatch | FormalSetBatch) -> dict[str, np.ndarray]:
    return {
        field.name: getattr(batch, field.name).detach().cpu().numpy()
        for field in fields(batch)
    }


def _payload_digest(files: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for item in files:
        digest.update(item["name"].encode("utf-8") + b"\0" + item["sha256"].encode("ascii") + b"\n")
    return digest.hexdigest()


def _canonical_npy_bytes(array: np.ndarray) -> bytes:
    stream = io.BytesIO()
    np.save(stream, np.ascontiguousarray(array), allow_pickle=False)
    return stream.getvalue()


def _write_cache_entry(entry: Path, dataset: FormalDataset, frozen_config: FrozenConfig) -> None:
    _validate_dataset_semantics(dataset, require_raw=True, frozen_config=frozen_config)
    entry.mkdir()
    files: list[dict[str, Any]] = []
    for name, array in sorted(_batch_arrays(dataset.batch).items()):
        path = entry / f"{name}.npy"
        payload = _canonical_npy_bytes(array)
        with path.open("xb") as handle:
            handle.write(payload)
        files.append({"name": path.name, "sha256": _sha256_bytes(payload), "size": len(payload)})
    metadata_path = entry / "metadata.json"
    metadata_payload = _canonical_bytes(dataset.metadata)
    metadata_path.write_bytes(metadata_payload)
    files.append({"name": metadata_path.name, "sha256": _sha256_bytes(metadata_payload), "size": len(metadata_payload)})
    files.sort(key=lambda item: item["name"])
    manifest = {
        "cache_version": DATASET_SCHEMA_VERSION,
        "cache_key": dataset.spec.cache_key,
        "spec": _spec_payload(dataset.spec),
        "dataset_hash": dataset.dataset_hash,
        "batch_kind": "set" if isinstance(dataset.batch, FormalSetBatch) else "fixed",
        "payload_sha256": _payload_digest(files),
        "files": files,
    }
    (entry / "manifest.json").write_bytes(_canonical_bytes(manifest))


def _is_alias_path(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def _reject_alias(path: Path) -> None:
    if _is_alias_path(path):
        raise ValueError(f"cache alias/symlink is forbidden: {path}")
    try:
        if path.is_file() and path.stat().st_nlink != 1:
            raise ValueError(f"cache alias/hardlink is forbidden: {path}")
    except OSError as exc:
        raise ValueError(f"cache identity cannot be verified: {path}") from exc


def _load_cache_entry(entry: Path, spec: FormalDatasetSpec, frozen_config: FrozenConfig) -> FormalDataset:
    _validate_spec_entry(spec)
    if not os.path.lexists(entry) or not entry.is_dir() or not (entry / "manifest.json").is_file():
        raise ValueError(f"partial cache entry: {entry}")
    _reject_alias(entry)
    manifest_path = entry / "manifest.json"
    _reject_alias(manifest_path)
    try:
        raw_manifest = manifest_path.read_bytes()
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid cache manifest: {exc}") from exc
    if raw_manifest != _canonical_bytes(manifest):
        raise ValueError("cache manifest is noncanonical")
    required_manifest_fields = {
        "cache_version", "cache_key", "spec", "dataset_hash",
        "batch_kind", "payload_sha256", "files",
    }
    if set(manifest) != required_manifest_fields or manifest.get("cache_version") != DATASET_SCHEMA_VERSION:
        raise ValueError("cache manifest schema mismatch")
    if manifest.get("cache_key") != spec.cache_key or manifest.get("spec") != _spec_payload(spec):
        raise ValueError("cache spec/role/hash mismatch")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("partial cache file manifest")
    if any(
        not isinstance(item, dict) or set(item) != {"name", "sha256", "size"}
        or not isinstance(item["name"], str) or not item["name"]
        or not isinstance(item["size"], int) or item["size"] < 0
        for item in files
    ):
        raise ValueError("cache file manifest schema mismatch")
    if files != sorted(files, key=lambda item: item["name"]) or len({item["name"] for item in files}) != len(files):
        raise ValueError("cache file manifest is noncanonical")
    expected_names = {"manifest.json", *(item.get("name") for item in files)}
    actual_names = {path.name for path in entry.iterdir()}
    if actual_names != expected_names:
        raise ValueError("cache alias, partial, or unexpected payload files")
    arrays: dict[str, np.ndarray] = {}
    metadata: tuple[dict[str, Any], ...] | None = None
    for item in files:
        path = entry / item["name"]
        _reject_alias(path)
        payload = path.read_bytes()
        if len(payload) != item.get("size") or _sha256_bytes(payload) != item.get("sha256"):
            raise ValueError(f"cache payload hash mismatch: {path.name}")
        if path.suffix == ".npy":
            try:
                arrays[path.stem] = np.load(path, allow_pickle=False)
            except Exception as exc:
                raise ValueError(f"invalid cache numeric payload: {path.name}") from exc
            if payload != _canonical_npy_bytes(arrays[path.stem]):
                raise ValueError(f"cache numeric payload is noncanonical: {path.name}")
        elif path.name == "metadata.json":
            parsed = json.loads(payload.decode("utf-8"))
            if payload != _canonical_bytes(parsed) or not isinstance(parsed, list):
                raise ValueError("cache metadata is noncanonical")
            metadata = tuple(parsed)
        else:
            raise ValueError(f"unexpected cache payload: {path.name}")
    if manifest.get("payload_sha256") != _payload_digest(files) or metadata is None:
        raise ValueError("cache payload manifest mismatch")
    if manifest.get("batch_kind") == "fixed":
        required = {"features", "targets", "location", "scale"}
        if set(arrays) != required:
            raise ValueError("partial fixed cache arrays")
        batch: FormalFixedBatch | FormalSetBatch = FormalFixedBatch(**{name: torch.from_numpy(arrays[name]) for name in required})
    elif manifest.get("batch_kind") == "set":
        required = {"values", "mask", "n", "model_n", "targets", "location", "scale"}
        if set(arrays) != required:
            raise ValueError("partial set cache arrays")
        batch = FormalSetBatch(**{name: torch.from_numpy(arrays[name]) for name in required})
        if not torch.equal(batch.mask.sum(1).to(batch.n.dtype), batch.n):
            raise ValueError("cache raw n no longer matches mask count")
    else:
        raise ValueError("cache batch kind mismatch")
    dataset = FormalDataset(spec, batch, metadata, _dataset_hash(spec, batch, metadata))
    if dataset.dataset_hash != manifest.get("dataset_hash"):
        raise ValueError("cache dataset hash mismatch")
    _validate_dataset_semantics(dataset, require_raw=True, frozen_config=frozen_config)
    return dataset


def _rename_no_replace(source: Path, destination: Path) -> None:
    """Publish a completed cache directory without replacement on Windows/Linux."""

    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file = kernel32.MoveFileW
        move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        move_file.restype = ctypes.c_int
        if not move_file(str(source), str(destination)):
            error = ctypes.get_last_error()
            if error in {80, 183}:  # ERROR_FILE_EXISTS / ERROR_ALREADY_EXISTS
                raise FileExistsError(error, "cache destination already exists", str(destination))
            raise OSError(error, "MoveFileW failed", str(destination))
        return
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError(error, "cache destination already exists", str(destination))
        raise OSError(error, os.strerror(error), str(destination))


def _cache_dataset_impl(
    spec: FormalDatasetSpec,
    frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig,
    cache_dir: Path,
) -> FormalDataset:
    _validate_spec_entry(spec)
    _validate_spec_against_authorities(spec, frozen_config, effective_config)
    root = Path(cache_dir)
    if os.path.lexists(root) and (_is_alias_path(root) or not root.is_dir()):
        raise ValueError("cache directory alias/symlink is forbidden")
    root.mkdir(parents=True, exist_ok=True)
    entry = root / spec.cache_key
    if os.path.lexists(entry):
        return _load_cache_entry(entry, spec, frozen_config)
    lock = root / f"{spec.cache_key}.lock"
    if os.path.lexists(lock):
        raise ValueError(f"cache key is locked or aliased: {spec.cache_key}")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError(f"cache key is locked: {spec.cache_key}") from exc
    os.close(descriptor)
    temporary = root / f".{spec.cache_key}.{os.getpid()}.tmp"
    try:
        if os.path.lexists(entry):
            return _load_cache_entry(entry, spec, frozen_config)
        if os.path.lexists(temporary):
            raise ValueError(f"partial cache temporary exists: {temporary}")
        dataset = _build_dataset_impl(spec, frozen_config, effective_config)
        _write_cache_entry(temporary, dataset, frozen_config)
        try:
            _rename_no_replace(temporary, entry)
        except FileExistsError:
            return _load_cache_entry(entry, spec, frozen_config)
        return _load_cache_entry(entry, spec, frozen_config)
    finally:
        lock.unlink(missing_ok=True)
        if os.path.lexists(temporary):
            if _is_alias_path(temporary):
                temporary.unlink()
            else:
                shutil.rmtree(temporary)


def cache_dataset(
    spec: FormalDatasetSpec,
    frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig,
    cache_dir: Path,
) -> FormalDataset:
    if type(spec) is not FormalDatasetSpec:
        raise ValueError("public production cache rejects test-only specs")
    return _cache_dataset_impl(spec, frozen_config, effective_config, cache_dir)


def _cache_dataset_for_tests(
    spec: FormalDatasetSpec,
    frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig,
    cache_dir: Path,
) -> FormalDataset:
    if type(spec) is not _TestDatasetSpec:
        raise ValueError("private test cache requires a test-only spec")
    return _cache_dataset_impl(spec, frozen_config, effective_config, cache_dir)


__all__ = [
    "DATASET_SCHEMA_VERSION", "FormalDataset", "FormalDatasetRowError", "FormalDatasetSpec",
    "ScalerManifest", "apply_training_scaler", "build_dataset",
    "build_training_spec", "build_validation_spec", "cache_dataset", "fit_training_scaler",
]
