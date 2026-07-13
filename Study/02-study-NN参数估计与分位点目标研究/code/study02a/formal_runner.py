"""Sealed-test-safe construction and local caching for Study/02 formal data."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Callable, Mapping

import numpy as np

from . import design
from .config import FrozenConfig
from .formal_config import EffectiveFormalConfig
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


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_hash(value: str, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{label} must be a lowercase SHA-256")


@dataclass(frozen=True)
class PilotForTests:
    """Explicit, cache-keyed size reduction that never resembles a formal spec."""

    rows: int
    points: int
    repeats: int
    marker: str = "pilot_for_tests_only"

    def __post_init__(self) -> None:
        if self.marker != "pilot_for_tests_only" or min(self.rows, self.points, self.repeats) <= 0:
            raise ValueError("pilot_for_tests requires positive test-only sizes")


def pilot_for_tests(*, rows: int, points: int, repeats: int) -> PilotForTests:
    return PilotForTests(rows=rows, points=points, repeats=repeats)


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
    pilot_for_tests: bool = False

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
        if min(self.row_count, self.point_count, self.repeat_count) <= 0:
            raise ValueError("dataset counts must be positive")
        if not self.pilot_for_tests:
            if self.role == "training" and (
                self.row_count not in {7000, 25000, 100000, 400000}
                or self.point_count != self.row_count or self.repeat_count != 1
            ):
                raise ValueError("production training specs must enforce frozen row counts")
            validation_n_count = 5 if self.n_mode == "shared_n" else 1
            if self.role == "validation" and (
                self.point_count != 256 or self.repeat_count != 50
                or self.row_count != 256 * 50 * validation_n_count
            ):
                raise ValueError("production validation specs must enforce exactly 256 points x 50 repeats per n")
        elif self.role == "training" and self.row_count in {7000, 25000, 100000, 400000}:
            raise ValueError("pilot_for_tests cannot label a production training count")
        elif self.role == "validation" and self.point_count == 256 and self.repeat_count == 50:
            raise ValueError("pilot_for_tests cannot label production validation counts")
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
        return _sha256_bytes(_canonical_bytes(asdict(self)))


def _spec_common(
    *, route: str, distribution: str, n_mode: str, fixed_n: int | None,
    frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
) -> dict[str, Any]:
    if not isinstance(frozen_config, FrozenConfig) or not isinstance(effective_config, EffectiveFormalConfig):
        raise ValueError("frozen_config and effective_config are required")
    if (
        effective_config.base_protocol_sha256 != frozen_config.protocol_sha256
        or effective_config.base_search_sha256 != frozen_config.search_sha256
    ):
        raise ValueError("effective config is not bound to the supplied frozen config")
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


def build_training_spec(
    *, route: str, distribution: str, n_mode: str, fixed_n: int | None,
    training_rows: int, frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
    pilot_for_tests: PilotForTests | None = None,
) -> FormalDatasetSpec:
    sizes = tuple(int(value) for value in frozen_config.protocol["training_sizes"])
    if training_rows not in sizes:
        raise ValueError(f"training_rows must be a frozen training size {sizes}")
    rows = pilot_for_tests.rows if isinstance(pilot_for_tests, PilotForTests) else training_rows
    return FormalDatasetSpec(
        role="training", row_count=rows, point_count=rows, repeat_count=1,
        design_namespace=220201, sample_namespace=320201,
        pilot_for_tests=pilot_for_tests is not None,
        **_spec_common(
            route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
            frozen_config=frozen_config, effective_config=effective_config,
        ),
    )


def build_validation_spec(
    *, route: str, distribution: str, n_mode: str, fixed_n: int | None,
    frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
    pilot_for_tests: PilotForTests | None = None,
) -> FormalDatasetSpec:
    if distribution != "core_continuous":
        raise ValueError("formal validation distribution must be core_continuous Sobol")
    formal = frozen_config.protocol["formal_sizes"]["validation"]
    points = int(formal["parameter_points"])
    repeats = int(formal["repeats_per_point_n"])
    is_pilot = isinstance(pilot_for_tests, PilotForTests)
    if is_pilot:
        points, repeats = pilot_for_tests.points, pilot_for_tests.repeats
    n_count = len(frozen_config.protocol["sample_sizes"]["core"]) if n_mode == "shared_n" else 1
    return FormalDatasetSpec(
        role="validation", row_count=points * repeats * n_count,
        point_count=points, repeat_count=repeats,
        design_namespace=220202, sample_namespace=320202, pilot_for_tests=is_pilot,
        **_spec_common(
            route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
            frozen_config=frozen_config, effective_config=effective_config,
        ),
    )


@dataclass(frozen=True)
class FormalDataset:
    spec: FormalDatasetSpec
    batch: FormalFixedBatch | FormalSetBatch
    metadata: tuple[dict[str, Any], ...]
    dataset_hash: str


class FormalDatasetRowError(ValueError):
    """A feature/target/sample failure with the complete row identity attached."""


def _design_rows(spec: FormalDatasetSpec, frozen: FrozenConfig) -> list[dict[str, Any]]:
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
    digest = hashlib.sha256(_canonical_bytes(asdict(spec)))
    tensors = {field.name: getattr(batch, field.name) for field in fields(batch)}
    for name in sorted(tensors):
        _array_hash(name, tensors[name].detach().cpu().numpy(), digest)
    digest.update(_canonical_bytes(metadata))
    return digest.hexdigest()


def build_dataset(
    spec: FormalDatasetSpec,
    frozen_config: FrozenConfig,
    *,
    sample_generator: Callable[[Mapping[str, Any], int], np.ndarray] | None = None,
) -> FormalDataset:
    if not isinstance(spec, FormalDatasetSpec):
        raise ValueError("spec must be a FormalDatasetSpec")
    if sample_generator is not None and not spec.pilot_for_tests:
        raise ValueError("custom sample_generator is permitted only for pilot_for_tests specs")
    if spec.base_protocol_sha256 != frozen_config.protocol_sha256 or spec.base_search_sha256 != frozen_config.search_sha256:
        raise ValueError("dataset spec does not match frozen config hashes")
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
    return FormalDataset(spec, batch, metadata_tuple, _dataset_hash(spec, batch, metadata_tuple))


@dataclass(frozen=True)
class ScalerManifest:
    source_role: str
    source_route: str
    source_distribution: str
    source_n_mode: str
    source_fixed_n: int | None
    channel: str
    columns: tuple[str, ...]
    mean: tuple[float, ...]
    sd: tuple[float, ...]
    zero_sd_handling: str
    source_dataset_hash: str
    effective_config_sha256: str


def fit_training_scaler(dataset: FormalDataset) -> ScalerManifest:
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
    return ScalerManifest(
        source_role="training", source_route=dataset.spec.route,
        source_distribution=dataset.spec.distribution, source_n_mode=dataset.spec.n_mode,
        source_fixed_n=dataset.spec.fixed_n, channel=channel, columns=columns,
        mean=tuple(float(value) for value in mean), sd=tuple(float(value) for value in sd),
        zero_sd_handling="map_to_zero", source_dataset_hash=dataset.dataset_hash,
        effective_config_sha256=dataset.spec.effective_config_sha256,
    )


def _standardize(values: Any, scaler: ScalerManifest) -> Any:
    mean = values.new_tensor(scaler.mean)
    sd = values.new_tensor(scaler.sd)
    safe = sd.where(sd != 0, values.new_ones(sd.shape))
    standardized = (values - mean) / safe
    return standardized.where(sd != 0, values.new_zeros(standardized.shape))


def apply_training_scaler(dataset: FormalDataset, scaler: ScalerManifest) -> FormalDataset:
    if scaler.source_role != "training" or scaler.effective_config_sha256 != dataset.spec.effective_config_sha256:
        raise ValueError("scaler is not owned by the matching training config")
    expected_provenance = (dataset.spec.route, dataset.spec.n_mode, dataset.spec.fixed_n)
    actual_provenance = (scaler.source_route, scaler.source_n_mode, scaler.source_fixed_n)
    if actual_provenance != expected_provenance:
        raise ValueError("scaler route/n provenance does not match the dataset")
    _require_hash(scaler.source_dataset_hash, "scaler source dataset hash")
    if dataset.spec.role == "training" and (
        scaler.source_distribution != dataset.spec.distribution
        or scaler.source_dataset_hash != dataset.dataset_hash
    ):
        raise ValueError("scaler source distribution/hash does not match this training dataset")
    if isinstance(dataset.batch, FormalSetBatch):
        if scaler.channel != "explicit_n" or scaler.columns != ("n",) or len(scaler.mean) != 1:
            raise ValueError("set data requires an explicit_n scaler")
        batch = replace(dataset.batch, model_n=_standardize(dataset.batch.n.reshape(-1, 1), scaler).reshape(-1))
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
    return replace(dataset, batch=batch)


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


def _write_cache_entry(entry: Path, dataset: FormalDataset) -> None:
    entry.mkdir()
    files: list[dict[str, Any]] = []
    for name, array in sorted(_batch_arrays(dataset.batch).items()):
        path = entry / f"{name}.npy"
        with path.open("xb") as handle:
            np.save(handle, array, allow_pickle=False)
        payload = path.read_bytes()
        files.append({"name": path.name, "sha256": _sha256_bytes(payload), "size": len(payload)})
    metadata_path = entry / "metadata.json"
    metadata_payload = _canonical_bytes(dataset.metadata)
    metadata_path.write_bytes(metadata_payload)
    files.append({"name": metadata_path.name, "sha256": _sha256_bytes(metadata_payload), "size": len(metadata_payload)})
    files.sort(key=lambda item: item["name"])
    manifest = {
        "cache_version": DATASET_SCHEMA_VERSION,
        "cache_key": dataset.spec.cache_key,
        "spec": asdict(dataset.spec),
        "dataset_hash": dataset.dataset_hash,
        "batch_kind": "set" if isinstance(dataset.batch, FormalSetBatch) else "fixed",
        "payload_sha256": _payload_digest(files),
        "files": files,
    }
    (entry / "manifest.json").write_bytes(_canonical_bytes(manifest))


def _reject_alias(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"cache alias/symlink is forbidden: {path}")
    try:
        if path.stat().st_nlink != 1:
            raise ValueError(f"cache alias/hardlink is forbidden: {path}")
    except OSError as exc:
        raise ValueError(f"cache identity cannot be verified: {path}") from exc


def _load_cache_entry(entry: Path, spec: FormalDatasetSpec) -> FormalDataset:
    if not entry.is_dir() or not (entry / "manifest.json").is_file():
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
    if manifest.get("cache_key") != spec.cache_key or manifest.get("spec") != asdict(spec):
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
        elif path.name == "metadata.json":
            parsed = json.loads(payload.decode("utf-8"))
            if payload != _canonical_bytes(parsed) or not isinstance(parsed, list):
                raise ValueError("cache metadata is noncanonical")
            metadata = tuple(parsed)
        else:
            raise ValueError(f"unexpected cache payload: {path.name}")
    if manifest.get("payload_sha256") != _payload_digest(files) or metadata is None:
        raise ValueError("cache payload manifest mismatch")
    import torch
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
    return dataset


def cache_dataset(
    spec: FormalDatasetSpec,
    frozen_config: FrozenConfig,
    cache_dir: Path,
    *,
    sample_generator: Callable[[Mapping[str, Any], int], np.ndarray] | None = None,
) -> FormalDataset:
    if sample_generator is not None and not spec.pilot_for_tests:
        raise ValueError("custom sample_generator is permitted only for pilot_for_tests specs")
    root = Path(cache_dir)
    if root.exists() and root.is_symlink():
        raise ValueError("cache directory alias/symlink is forbidden")
    root.mkdir(parents=True, exist_ok=True)
    entry = root / spec.cache_key
    if entry.exists():
        return _load_cache_entry(entry, spec)
    lock = root / f"{spec.cache_key}.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError(f"cache key is locked: {spec.cache_key}") from exc
    os.close(descriptor)
    temporary = root / f".{spec.cache_key}.{os.getpid()}.tmp"
    try:
        if entry.exists():
            return _load_cache_entry(entry, spec)
        if temporary.exists():
            raise ValueError(f"partial cache temporary exists: {temporary}")
        dataset = build_dataset(spec, frozen_config, sample_generator=sample_generator)
        _write_cache_entry(temporary, dataset)
        try:
            os.rename(temporary, entry)
        except FileExistsError:
            return _load_cache_entry(entry, spec)
        return _load_cache_entry(entry, spec)
    finally:
        lock.unlink(missing_ok=True)
        if temporary.exists():
            shutil.rmtree(temporary)


__all__ = [
    "DATASET_SCHEMA_VERSION", "FormalDataset", "FormalDatasetRowError", "FormalDatasetSpec",
    "PilotForTests", "ScalerManifest", "apply_training_scaler", "build_dataset",
    "build_training_spec", "build_validation_spec", "cache_dataset", "fit_training_scaler",
    "pilot_for_tests",
]
