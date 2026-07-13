from __future__ import annotations

from dataclasses import replace
import json
import os
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
from study02a.formal_config import load_effective_formal_config
from study02a.formal_data import FormalFixedBatch, FormalSetBatch
from study02a.formal_runner import (
    FormalDatasetRowError,
    apply_training_scaler,
    build_dataset,
    build_training_spec,
    build_validation_spec,
    cache_dataset,
    fit_training_scaler,
    pilot_for_tests,
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
        pilot_for_tests=guard,
    )
    validation = build_validation_spec(
        route="V", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        frozen_config=frozen, effective_config=effective, pilot_for_tests=guard,
    )
    assert (training.row_count, training.design_namespace, training.sample_namespace) == (8, 220201, 320201)
    assert (validation.point_count, validation.repeat_count) == (4, 2)
    assert validation.row_count == 8
    production = build_validation_spec(
        route="S", distribution="core_continuous", n_mode="shared_n", fixed_n=None,
        frozen_config=frozen, effective_config=effective,
    )
    assert (production.point_count, production.repeat_count, production.row_count) == (256, 50, 64000)
    with pytest.raises(ValueError, match="pilot_for_tests"):
        build_dataset(production, frozen, sample_generator=lambda row, namespace: np.ones(int(row["n"])))
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
        pilot_for_tests=guard,
    )
    first = build_dataset(fixed_spec, frozen)
    second = build_dataset(fixed_spec, frozen)
    assert isinstance(first.batch, FormalFixedBatch)
    assert torch.equal(first.batch.features, second.batch.features)
    assert first.dataset_hash == second.dataset_hash
    assert [row["sample_id"] for row in first.metadata] == [row["sample_id"] for row in second.metadata]
    assert first.batch.features.shape == (10, 15)

    set_spec = build_training_spec(
        route="S", distribution="core_continuous", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot_for_tests=guard,
    )
    set_data = build_dataset(set_spec, frozen)
    assert isinstance(set_data.batch, FormalSetBatch)
    assert torch.equal(set_data.batch.mask.sum(1).to(set_data.batch.n.dtype), set_data.batch.n)
    assert set(set_data.batch.n.tolist()) == {5.0, 7.0, 10.0, 15.0, 20.0}

    historical_spec = build_training_spec(
        route="H1", distribution="legacy_grid", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot_for_tests=guard,
    )
    historical = build_dataset(historical_spec, frozen)
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
        pilot_for_tests=guard,
    )
    valid_spec = build_validation_spec(
        route="V", distribution="core_continuous", n_mode="fixed_n", fixed_n=7,
        frozen_config=frozen, effective_config=effective, pilot_for_tests=guard,
    )
    train = build_dataset(train_spec, frozen)
    valid = build_dataset(valid_spec, frozen)
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
        pilot_for_tests=pilot_for_tests(rows=2, points=2, repeats=1),
    )
    def broken(row, namespace):
        raise RuntimeError("boom")
    with pytest.raises(FormalDatasetRowError, match=r"training:.*sample_id.*boom"):
        build_dataset(spec, frozen, sample_generator=broken)


def test_training_only_scalers_and_raw_n_separation(configs) -> None:
    frozen, effective = configs
    guard = pilot_for_tests(rows=10, points=3, repeats=2)
    train_spec = build_training_spec(
        route="S", distribution="core_continuous", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot_for_tests=guard,
    )
    valid_spec = build_validation_spec(
        route="S", distribution="core_continuous", n_mode="shared_n", fixed_n=None,
        frozen_config=frozen, effective_config=effective, pilot_for_tests=guard,
    )
    training = build_dataset(train_spec, frozen)
    validation = build_dataset(valid_spec, frozen)
    scaler = fit_training_scaler(training)
    prepared_train = apply_training_scaler(training, scaler)
    prepared_valid = apply_training_scaler(validation, scaler)
    assert scaler.source_role == "training" and scaler.channel == "explicit_n"
    assert torch.equal(prepared_train.batch.n, training.batch.n)
    assert torch.equal(prepared_valid.batch.n, validation.batch.n)
    assert torch.allclose(prepared_train.batch.model_n.mean(), torch.tensor(0.0), atol=1e-7)
    assert not torch.equal(prepared_valid.batch.model_n, prepared_valid.batch.n)

    constant = replace(training, batch=replace(training.batch, n=torch.full_like(training.batch.n, 5.0), model_n=torch.full_like(training.batch.n, 5.0)))
    zero = fit_training_scaler(constant)
    assert zero.sd == (0.0,)
    assert torch.equal(apply_training_scaler(constant, zero).batch.model_n, torch.zeros_like(constant.batch.n))
    with pytest.raises(ValueError, match="training"):
        fit_training_scaler(validation)

    fixed_spec = build_training_spec(
        route="V", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot_for_tests=guard,
    )
    fixed = build_dataset(fixed_spec, frozen)
    fixed_scaler = fit_training_scaler(fixed)
    fixed_prepared = apply_training_scaler(fixed, fixed_scaler)
    assert fixed_scaler.columns == tuple(f"sorted_z_{index}" for index in range(5))
    assert torch.allclose(fixed_prepared.batch.features.mean(0), torch.zeros(5), atol=2e-6)

    other_spec = build_training_spec(
        route="H1", distribution="legacy_grid", n_mode="shared_n", fixed_n=None,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot_for_tests=guard,
    )
    other_scaler = fit_training_scaler(build_dataset(other_spec, frozen))
    six_wide_spec = build_training_spec(
        route="F0eq_hsm", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot_for_tests=guard,
    )
    with pytest.raises(ValueError, match="provenance"):
        apply_training_scaler(build_dataset(six_wide_spec, frozen), other_scaler)
    with pytest.raises(ValueError, match="distribution/hash"):
        apply_training_scaler(replace(fixed, dataset_hash="f" * 64), fixed_scaler)

    wide_spec = build_training_spec(
        route="F2", distribution="extended_wide", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot_for_tests=guard,
    )
    core_validation_spec = build_validation_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        frozen_config=frozen, effective_config=effective, pilot_for_tests=guard,
    )
    wide_scaler = fit_training_scaler(build_dataset(wide_spec, frozen))
    assert apply_training_scaler(build_dataset(core_validation_spec, frozen), wide_scaler).batch.features.shape[1] == 15
    with pytest.raises(ValueError, match="core_continuous"):
        build_validation_spec(
            route="F2", distribution="extended_wide", n_mode="fixed_n", fixed_n=5,
            frozen_config=frozen, effective_config=effective, pilot_for_tests=guard,
        )


def test_cache_reuses_exact_payload_and_fails_closed(configs, tmp_path: Path) -> None:
    frozen, effective = configs
    spec = build_training_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot_for_tests=pilot_for_tests(rows=5, points=2, repeats=1),
    )
    calls = 0
    def counted(row, namespace):
        nonlocal calls
        calls += 1
        from study02a.design import generate_lifetime_sample
        return generate_lifetime_sample(row, namespace)
    first = cache_dataset(spec, frozen, tmp_path, sample_generator=counted)
    assert calls == 5
    second = cache_dataset(spec, frozen, tmp_path, sample_generator=counted)
    assert calls == 5 and second.dataset_hash == first.dataset_hash
    entry = next(tmp_path.iterdir())
    manifest = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
    (entry / manifest["files"][0]["name"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="cache"):
        cache_dataset(spec, frozen, tmp_path)


def test_partial_and_alias_cache_fail_closed(configs, tmp_path: Path) -> None:
    frozen, effective = configs
    spec = build_training_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot_for_tests=pilot_for_tests(rows=3, points=2, repeats=1),
    )
    partial = tmp_path / spec.cache_key
    partial.mkdir()
    with pytest.raises(ValueError, match="partial"):
        cache_dataset(spec, frozen, tmp_path)
    partial.rmdir()
    cache_dataset(spec, frozen, tmp_path)
    manifest = json.loads((partial / "manifest.json").read_text(encoding="utf-8"))
    source = partial / manifest["files"][0]["name"]
    alias = partial / "alias.npy"
    try:
        alias.hardlink_to(source)
    except OSError:
        pytest.skip("hard links unavailable")
    with pytest.raises(ValueError, match="alias"):
        cache_dataset(spec, frozen, tmp_path)


def test_noncanonical_wrong_role_and_racing_cache_never_overwrite(configs, tmp_path: Path, monkeypatch) -> None:
    frozen, effective = configs
    guard = pilot_for_tests(rows=3, points=2, repeats=1)
    training_spec = build_training_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        training_rows=7000, frozen_config=frozen, effective_config=effective,
        pilot_for_tests=guard,
    )
    cache_dataset(training_spec, frozen, tmp_path)
    training_entry = tmp_path / training_spec.cache_key
    manifest_path = training_entry / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="noncanonical"):
        cache_dataset(training_spec, frozen, tmp_path)
    manifest_path.write_bytes(
        (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    )

    validation_spec = build_validation_spec(
        route="F2", distribution="core_continuous", n_mode="fixed_n", fixed_n=5,
        frozen_config=frozen, effective_config=effective, pilot_for_tests=guard,
    )
    wrong_role_root = tmp_path / "wrong-role"
    wrong_role_root.mkdir()
    shutil.copytree(training_entry, wrong_role_root / validation_spec.cache_key)
    with pytest.raises(ValueError, match="spec/role/hash"):
        cache_dataset(validation_spec, frozen, wrong_role_root)

    race_root = tmp_path / "race"
    real_rename = os.rename
    marker_payload = b"do-not-overwrite"
    def racing_rename(source, destination):
        destination = Path(destination)
        destination.mkdir()
        (destination / "marker").write_bytes(marker_payload)
        raise FileExistsError("simulated same-key publisher")
    monkeypatch.setattr(os, "rename", racing_rename)
    with pytest.raises(ValueError, match="partial"):
        cache_dataset(training_spec, frozen, race_root)
    monkeypatch.setattr(os, "rename", real_rename)
    assert (race_root / training_spec.cache_key / "marker").read_bytes() == marker_payload
