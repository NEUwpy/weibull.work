from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import inspect
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest
import torch


ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
sys.path.insert(0, str(STUDY_ROOT / "code"))
sys.path.insert(0, str(ROOT / "python"))

from study02a.config import load_frozen_config
import study02a.formal_runner as formal_runner
from study02a.formal_config import load_effective_formal_config
from study02a.formal_data import FormalFixedBatch, FormalSetBatch
from study02a.formal_runner import (
    FormalDatasetRowError,
    apply_training_scaler,
    build_dataset as _public_build_dataset,
    build_training_spec as _public_build_training_spec,
    build_validation_spec as _public_build_validation_spec,
    cache_dataset as _public_cache_dataset,
    _build_dataset_for_tests,
    _build_training_spec_for_tests,
    _build_validation_spec_for_tests,
    _cache_dataset_for_tests,
    fit_training_scaler,
    _pilot_for_tests as pilot_for_tests,
)


def build_training_spec(**kwargs):
    pilot = kwargs.pop("_pilot_for_tests", None)
    return (
        _build_training_spec_for_tests(**kwargs, pilot=pilot)
        if pilot is not None else _public_build_training_spec(**kwargs)
    )


def build_validation_spec(**kwargs):
    pilot = kwargs.pop("_pilot_for_tests", None)
    return (
        _build_validation_spec_for_tests(**kwargs, pilot=pilot)
        if pilot is not None else _public_build_validation_spec(**kwargs)
    )


def build_dataset(spec, frozen, effective, **kwargs):
    return (
        _build_dataset_for_tests(spec, frozen, effective, **kwargs)
        if type(spec) is formal_runner._TestDatasetSpec
        else _public_build_dataset(spec, frozen, effective, **kwargs)
    )


def cache_dataset(spec, frozen, effective, cache_dir, **kwargs):
    if kwargs:
        raise TypeError("test cache does not accept custom generators")
    return (
        _cache_dataset_for_tests(spec, frozen, effective, cache_dir)
        if type(spec) is formal_runner._TestDatasetSpec
        else _public_cache_dataset(spec, frozen, effective, cache_dir)
    )


@pytest.fixture(scope="module")
def configs():
    return load_frozen_config(STUDY_ROOT), load_effective_formal_config(STUDY_ROOT)


def test_specs_reject_test_roles_namespaces_and_production_overrides(configs) -> None:
    frozen, effective = configs
    guard = pilot_for_tests(rows=8, points=4, repeats=2)
    training = build_training_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    validation = build_validation_spec(
        route="V", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        frozen_config=frozen, effective_config=effective, _pilot_for_tests=guard,
    )
    assert (training.row_count, training.design_namespace, training.sample_namespace) == (8, 220201, 320201)
    assert (validation.point_count, validation.repeat_count) == (4, 2)
    assert validation.row_count == 8
    production = build_validation_spec(
        route="S", distribution="core_continuous", n_mode="shared_n", fixed_n=None,
        frozen_config=frozen, effective_config=effective,
    )
    assert (production.point_count, production.repeat_count, production.row_count) == (256, 50, 64000)
    with pytest.raises(TypeError):
        _public_build_dataset(
            production, frozen, effective,
            sample_generator=lambda row, namespace: np.ones(int(row["n"])),
        )
    with pytest.raises(ValueError, match="frozen training size"):
        build_training_spec(
            route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
            training_rows=8, frozen_config=frozen, effective_config=effective,
        )
    with pytest.raises(ValueError, match="test"):
        replace(training, role="test")
    with pytest.raises(ValueError, match="namespace"):
        replace(training, design_namespace=220301)


def test_builds_deterministic_fixed_set_and_historical_targets(configs) -> None:
    frozen, effective = configs
    guard = pilot_for_tests(rows=10, points=3, repeats=2)
    fixed_spec = build_training_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    first = build_dataset(fixed_spec, frozen, effective)
    second = build_dataset(fixed_spec, frozen, effective)
    assert isinstance(first.batch, FormalFixedBatch)
    assert torch.equal(first.batch.features, second.batch.features)
    assert first.dataset_hash == second.dataset_hash
    assert [row["sample_id"] for row in first.metadata] == [row["sample_id"] for row in second.metadata]
    assert first.batch.features.shape == (10, 15)

    set_spec = build_training_spec(
        route="S", distribution="core_continuous", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    set_data = build_dataset(set_spec, frozen, effective)
    assert isinstance(set_data.batch, FormalSetBatch)
    assert torch.equal(set_data.batch.mask.sum(1).to(set_data.batch.n.dtype), set_data.batch.n)
    assert set(set_data.batch.n.tolist()) == {5.0, 7.0, 10.0, 15.0, 20.0}

    historical_spec = build_training_spec(
        route="H1", distribution="legacy_grid", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    historical = build_dataset(historical_spec, frozen, effective)
    first_meta = historical.metadata[0]
    np.testing.assert_allclose(
        historical.batch.targets[0].numpy(),
        [first_meta["beta"], first_meta["eta"], first_meta["gamma"]], rtol=1e-6,
    )


def test_validation_is_exact_and_role_disjoint(configs) -> None:
    frozen, effective = configs
    guard = pilot_for_tests(rows=8, points=4, repeats=3)
    train_spec = build_training_spec(
        route="V", distribution="core_continuous", n_mode="fixed_n", fixed_n=7,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    valid_spec = build_validation_spec(
        route="V", distribution="core_continuous", n_mode="fixed_n", fixed_n=7,
        frozen_config=frozen, effective_config=effective, _pilot_for_tests=guard,
    )
    train = build_dataset(train_spec, frozen, effective)
    valid = build_dataset(valid_spec, frozen, effective)
    assert len(valid.metadata) == 12
    assert len({row["point_id"] for row in valid.metadata}) == 4
    assert {row["repeat_id"] for row in valid.metadata} == {0, 1, 2}
    train_points = {(row["beta"], row["eta"], row["rho"]) for row in train.metadata}
    valid_points = {(row["beta"], row["eta"], row["rho"]) for row in valid.metadata}
    assert train_points.isdisjoint(valid_points)


def test_generator_failures_include_row_identity(configs) -> None:
    frozen, effective = configs
    spec = build_training_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=pilot_for_tests(rows=2, points=2, repeats=1),
    )
    def broken(row, namespace):
        raise RuntimeError("boom")
    with pytest.raises(FormalDatasetRowError, match=r"training:.*sample_id.*boom"):
        build_dataset(spec, frozen, effective, sample_generator=broken)


def test_training_only_scalers_and_raw_n_separation(configs) -> None:
    frozen, effective = configs
    guard = pilot_for_tests(rows=10, points=3, repeats=2)
    train_spec = build_training_spec(
        route="S", distribution="core_continuous", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    valid_spec = build_validation_spec(
        route="S", distribution="core_continuous", n_mode="shared_n", fixed_n=None,
        frozen_config=frozen, effective_config=effective, _pilot_for_tests=guard,
    )
    training = build_dataset(train_spec, frozen, effective)
    validation = build_dataset(valid_spec, frozen, effective)
    scaler = fit_training_scaler(training)
    prepared_train = apply_training_scaler(training, scaler, training)
    prepared_valid = apply_training_scaler(validation, scaler, training)
    assert scaler.source_role == "training" and scaler.channel == "explicit_n"
    assert torch.equal(prepared_train.batch.n, training.batch.n)
    assert torch.equal(prepared_valid.batch.n, validation.batch.n)
    assert torch.allclose(prepared_train.batch.model_n.mean(), torch.tensor(0.0), atol=1e-7)
    assert not torch.equal(prepared_valid.batch.model_n, prepared_valid.batch.n)

    with pytest.raises(ValueError, match="training"):
        fit_training_scaler(validation)

    fixed_spec = build_training_spec(
        route="V", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    fixed = build_dataset(fixed_spec, frozen, effective)
    fixed_scaler = fit_training_scaler(fixed)
    fixed_prepared = apply_training_scaler(fixed, fixed_scaler, fixed)
    assert fixed_scaler.columns == tuple(f"sorted_z_{index}" for index in range(5))
    assert fixed_scaler.sd[0] == 0.0
    assert torch.equal(fixed_prepared.batch.features[:, 0], torch.zeros(len(fixed.batch)))
    assert torch.allclose(fixed_prepared.batch.features.mean(0), torch.zeros(5), atol=2e-6)

    other_spec = build_training_spec(
        route="H1", distribution="legacy_grid", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    other_data = build_dataset(other_spec, frozen, effective)
    other_scaler = fit_training_scaler(other_data)
    six_wide_spec = build_training_spec(
        route="F0eq_hsm", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    with pytest.raises(ValueError, match="provenance"):
        apply_training_scaler(build_dataset(six_wide_spec, frozen, effective), other_scaler, other_data)
    with pytest.raises(ValueError, match="dataset hash"):
        apply_training_scaler(replace(fixed, dataset_hash="f" * 64), fixed_scaler, fixed)

    wide_spec = build_training_spec(
        route="F2", distribution="extended_wide", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    core_validation_spec = build_validation_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        frozen_config=frozen, effective_config=effective, _pilot_for_tests=guard,
    )
    wide_data = build_dataset(wide_spec, frozen, effective)
    wide_scaler = fit_training_scaler(wide_data)
    assert apply_training_scaler(build_dataset(core_validation_spec, frozen, effective), wide_scaler, wide_data).batch.features.shape[1] == 15
    with pytest.raises(ValueError, match="core_continuous"):
        build_validation_spec(
            route="F2", distribution="extended_wide", n_mode="fixed_n", fixed_n=5,
            frozen_config=frozen, effective_config=effective, _pilot_for_tests=guard,
        )


def test_cache_reuses_exact_payload_and_fails_closed(configs, tmp_path: Path, monkeypatch) -> None:
    frozen, effective = configs
    spec = build_training_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=pilot_for_tests(rows=5, points=2, repeats=1),
    )
    calls = 0
    original_generator = formal_runner.design.generate_lifetime_sample
    def counted(row, namespace):
        nonlocal calls
        calls += 1
        return original_generator(row, namespace)
    monkeypatch.setattr(formal_runner.design, "generate_lifetime_sample", counted)
    first = cache_dataset(spec, frozen, effective, tmp_path)
    assert calls == 5
    second = cache_dataset(spec, frozen, effective, tmp_path)
    assert calls == 5 and second.dataset_hash == first.dataset_hash
    entry = next(tmp_path.iterdir())
    manifest = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
    (entry / manifest["files"][0]["name"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="cache"):
        cache_dataset(spec, frozen, effective, tmp_path)


def test_partial_and_alias_cache_fail_closed(configs, tmp_path: Path) -> None:
    frozen, effective = configs
    spec = build_training_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=pilot_for_tests(rows=3, points=2, repeats=1),
    )
    partial = tmp_path / spec.cache_key
    partial.mkdir()
    with pytest.raises(ValueError, match="partial"):
        cache_dataset(spec, frozen, effective, tmp_path)
    partial.rmdir()
    cache_dataset(spec, frozen, effective, tmp_path)
    manifest = json.loads((partial / "manifest.json").read_text(encoding="utf-8"))
    source = partial / manifest["files"][0]["name"]
    alias = partial / "alias.npy"
    try:
        alias.hardlink_to(source)
    except OSError:
        pytest.skip("hard links unavailable")
    with pytest.raises(ValueError, match="alias"):
        cache_dataset(spec, frozen, effective, tmp_path)


def test_noncanonical_wrong_role_and_racing_cache_never_overwrite(configs, tmp_path: Path, monkeypatch) -> None:
    frozen, effective = configs
    guard = pilot_for_tests(rows=3, points=2, repeats=1)
    training_spec = build_training_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    cache_dataset(training_spec, frozen, effective, tmp_path)
    training_entry = tmp_path / training_spec.cache_key
    manifest_path = training_entry / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="noncanonical"):
        cache_dataset(training_spec, frozen, effective, tmp_path)
    manifest_path.write_bytes(
        (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    )

    validation_spec = build_validation_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        frozen_config=frozen, effective_config=effective, _pilot_for_tests=guard,
    )
    wrong_role_root = tmp_path / "wrong-role"
    wrong_role_root.mkdir()
    shutil.copytree(training_entry, wrong_role_root / validation_spec.cache_key)
    with pytest.raises(ValueError, match="spec/role/hash"):
        cache_dataset(validation_spec, frozen, effective, wrong_role_root)

    race_root = tmp_path / "race"
    marker_payload = b"do-not-overwrite"
    def racing_rename(source, destination):
        destination = Path(destination)
        destination.mkdir()
        (destination / "marker").write_bytes(marker_payload)
        raise FileExistsError("simulated same-key publisher")
    monkeypatch.setattr(formal_runner, "_rename_no_replace", racing_rename)
    with pytest.raises(ValueError, match="partial"):
        cache_dataset(training_spec, frozen, effective, race_root)
    assert (race_root / training_spec.cache_key / "marker").read_bytes() == marker_payload


def test_public_spec_cannot_forge_test_override_or_inject_generator(configs) -> None:
    frozen, effective = configs
    assert "pilot" not in inspect.signature(_public_build_training_spec).parameters
    assert "sample_generator" not in inspect.signature(_public_build_dataset).parameters
    test_spec = _build_training_spec_for_tests(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot=pilot_for_tests(rows=3, points=2, repeats=1),
    )
    with pytest.raises(ValueError, match="rejects test-only"):
        _public_build_dataset(test_spec, frozen, effective)


def test_entry_rejects_mutated_frozen_content_and_unapproved_effective_config(configs, tmp_path: Path) -> None:
    frozen, effective = configs
    approved_spec = build_training_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
    )
    mutated = replace(frozen, protocol=deepcopy(frozen.protocol))
    mutated.protocol["sample_sizes"]["core"] = [5, 7, 10, 15, 99]
    with pytest.raises(ValueError, match="frozen config content"):
        build_training_spec(
            route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
            training_rows=7000, frozen_config=mutated, effective_config=effective,
        )
    with pytest.raises(ValueError, match="frozen config content"):
        build_dataset(approved_spec, mutated, effective)
    forged_effective = replace(effective, base_protocol_id="forged")
    with pytest.raises(ValueError, match="approved effective config"):
        build_training_spec(
            route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
            training_rows=7000, frozen_config=frozen,
            effective_config=forged_effective,
        )
    with pytest.raises(ValueError, match="approved effective config"):
        build_dataset(approved_spec, frozen, forged_effective)
    with pytest.raises(ValueError, match="approved effective config"):
        cache_dataset(approved_spec, frozen, forged_effective, tmp_path)
    with pytest.raises(ValueError, match="production training"):
        build_dataset(replace(approved_spec, row_count=3, point_count=3), frozen, effective)
    with pytest.raises(ValueError, match="authority hashes"):
        _public_build_dataset(
            replace(approved_spec, amendment_sha256="f" * 64), frozen, effective,
        )
    with pytest.raises(ValueError, match="point/repeat"):
        _public_build_dataset(replace(approved_spec, repeat_count=2), frozen, effective)
    with pytest.raises(ValueError, match="authority hashes"):
        _public_cache_dataset(
            replace(approved_spec, amendment_sha256="f" * 64), frozen, effective, tmp_path,
        )


def test_historical_specs_use_frozen_80_20_split(configs) -> None:
    frozen, effective = configs
    train_spec = build_training_spec(
        route="H1", distribution="legacy_grid", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
    )
    validation_spec = build_validation_spec(
        route="H1", distribution="legacy_grid", n_mode="shared_n", fixed_n=None,
        frozen_config=frozen, effective_config=effective,
    )
    assert (train_spec.row_count, validation_spec.row_count) == (7000, 2000)
    assert (train_spec.point_count, validation_spec.point_count) == (80, 20)
    pilot = pilot_for_tests(rows=400, points=20, repeats=1)
    pilot_train_spec = build_training_spec(
        route="H1", distribution="legacy_grid", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=pilot,
    )
    pilot_validation_spec = build_validation_spec(
        route="H1", distribution="legacy_grid", n_mode="shared_n", fixed_n=None,
        frozen_config=frozen, effective_config=effective, _pilot_for_tests=pilot,
    )
    training = build_dataset(pilot_train_spec, frozen, effective)
    validation = build_dataset(pilot_validation_spec, frozen, effective)
    assert {row["point_id"] for row in training.metadata}.isdisjoint(
        {row["point_id"] for row in validation.metadata}
    )


def test_scaler_payload_validation_and_repeat_application(configs) -> None:
    frozen, effective = configs
    guard = pilot_for_tests(rows=8, points=2, repeats=1)
    spec = build_training_spec(
        route="V", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=guard,
    )
    dataset = build_dataset(spec, frozen, effective)
    scaler = fit_training_scaler(dataset)
    for forged in (
        replace(scaler, mean=(float("nan"),) * 5),
        replace(scaler, sd=(-1.0,) * 5),
        replace(scaler, zero_sd_handling="divide_anyway"),
    ):
        with pytest.raises(ValueError, match="scaler"):
            apply_training_scaler(dataset, forged, dataset)
    prepared = apply_training_scaler(dataset, scaler, dataset)
    assert prepared.preprocessing_hash
    with pytest.raises(ValueError, match="already preprocessed"):
        apply_training_scaler(prepared, scaler, dataset)


def test_collation_float32_failure_keeps_row_identity(configs) -> None:
    frozen, effective = configs
    spec = build_training_spec(
        route="H0_hsm", distribution="legacy_grid", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=pilot_for_tests(rows=2, points=2, repeats=1),
    )
    huge = float(np.finfo(np.float32).max) * 2.0
    with pytest.raises(FormalDatasetRowError, match=r"sample_id=.*float32"):
        build_dataset(
            spec, frozen, effective,
            sample_generator=lambda row, namespace: float(row["gamma"]) + np.array([1.0, 2.0, 3.0, 4.0, huge]),
        )


def test_cache_rejects_self_consistent_wrong_dtype_payload(configs, tmp_path: Path) -> None:
    frozen, effective = configs
    spec = build_training_spec(
        route="V", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        _pilot_for_tests=pilot_for_tests(rows=3, points=2, repeats=1),
    )
    cache_dataset(spec, frozen, effective, tmp_path)
    entry = tmp_path / spec.cache_key
    manifest_path = entry / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    features_path = entry / "features.npy"
    forged_features = np.load(features_path, allow_pickle=False).astype(np.float64)
    features_payload = formal_runner._canonical_npy_bytes(forged_features)
    features_path.write_bytes(features_payload)
    for item in manifest["files"]:
        if item["name"] == "features.npy":
            item["size"] = len(features_payload)
            item["sha256"] = formal_runner._sha256_bytes(features_payload)
    manifest["payload_sha256"] = formal_runner._payload_digest(manifest["files"])
    arrays = {
        name: np.load(entry / f"{name}.npy", allow_pickle=False)
        for name in ("features", "targets", "location", "scale")
    }
    metadata = tuple(json.loads((entry / "metadata.json").read_text(encoding="utf-8")))
    forged_batch = FormalFixedBatch(**{name: torch.from_numpy(value) for name, value in arrays.items()})
    manifest["dataset_hash"] = formal_runner._dataset_hash(spec, forged_batch, metadata)
    manifest_path.write_bytes(
        (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    )
    with pytest.raises(ValueError, match="dtype"):
        cache_dataset(spec, frozen, effective, tmp_path)

    design_root = tmp_path / "design"
    cache_dataset(spec, frozen, effective, design_root)
    design_entry = design_root / spec.cache_key
    design_manifest_path = design_entry / "manifest.json"
    design_manifest = json.loads(design_manifest_path.read_text(encoding="utf-8"))
    forged_metadata = json.loads((design_entry / "metadata.json").read_text(encoding="utf-8"))
    forged_metadata[0]["point_id"] = "training:core_continuous:forged"
    forged_metadata[0]["sample_id"] = (
        f"training:{forged_metadata[0]['point_id']}:n5:r0:i0000000"
    )
    metadata_payload = (
        json.dumps(forged_metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    (design_entry / "metadata.json").write_bytes(metadata_payload)
    for item in design_manifest["files"]:
        if item["name"] == "metadata.json":
            item["size"] = len(metadata_payload)
            item["sha256"] = formal_runner._sha256_bytes(metadata_payload)
    design_manifest["payload_sha256"] = formal_runner._payload_digest(design_manifest["files"])
    design_arrays = {
        name: np.load(design_entry / f"{name}.npy", allow_pickle=False)
        for name in ("features", "targets", "location", "scale")
    }
    design_batch = FormalFixedBatch(**{
        name: torch.from_numpy(value) for name, value in design_arrays.items()
    })
    design_manifest["dataset_hash"] = formal_runner._dataset_hash(
        spec, design_batch, tuple(forged_metadata),
    )
    design_manifest_path.write_bytes(
        (json.dumps(design_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    )
    with pytest.raises(ValueError, match="frozen design rows"):
        cache_dataset(spec, frozen, effective, design_root)
