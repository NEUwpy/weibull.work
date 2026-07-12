from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path
import sys

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = next((ROOT / "Study").glob("02-study-*"))
sys.path.insert(0, str(STUDY_ROOT / "code"))

from study02a.formal_config import EffectiveFormalConfig
from study02a.formal_data import (
    FormalFixedExample,
    FormalSetExample,
    collate_fixed_features,
    collate_set_features,
)
from study02a.models import build_deepsets, build_mlp
from study02a.representations import SetFeatures
from study02a.training import fit_fixed_candidate, fit_set_candidate


def _example(n: int, *, offset: float = 0.0) -> FormalSetExample:
    values = np.arange(n, dtype=float).reshape(n, 1) + offset
    return FormalSetExample(
        features=SetFeatures(values=values, mask=np.ones(n, dtype=bool), n=n),
        target=np.array([0.1, -0.2, 0.3], dtype=float) + offset / 10.0,
        location=10.0 + offset,
        scale=2.0 + offset / 10.0,
    )


def _effective_config() -> EffectiveFormalConfig:
    return EffectiveFormalConfig(
        base_protocol_id="protocol",
        base_protocol_sha256="a" * 64,
        base_search_id="search",
        base_search_sha256="b" * 64,
        amendment_id="A-G3-pilot-amendment-v4",
        amendment_sha256="c" * 64,
        effective_config_sha256="d" * 64,
        max_epochs=100,
        min_epochs=50,
        patience=40,
        base_max_epochs=500,
        approved_override_paths=("search.training.max_epochs",),
    )


def _fixed_example(width: int, *, offset: float = 0.0) -> FormalFixedExample:
    return FormalFixedExample(
        features=np.arange(width, dtype=float) + offset,
        target=np.array([0.1, -0.2, 0.3], dtype=float) + offset / 10.0,
        location=10.0 + offset,
        scale=2.0 + offset / 10.0,
    )


def test_collate_fixed_features_carries_targets_and_anchors() -> None:
    batch = collate_fixed_features([_fixed_example(4), _fixed_example(4, offset=1.0)])

    assert batch.features.shape == (2, 4)
    assert batch.targets.shape == (2, 3)
    assert batch.location.shape == batch.scale.shape == (2,)
    assert all(tensor.dtype == torch.float32 for tensor in (
        batch.features, batch.targets, batch.location, batch.scale
    ))


def test_real_fixed_fit_is_deterministic_and_config_only() -> None:
    training = collate_fixed_features([_fixed_example(4, offset=float(i) / 5.0) for i in range(8)])
    validation = collate_fixed_features([_fixed_example(4, offset=2.0 + float(i) / 5.0) for i in range(3)])
    config = _effective_config()

    def factory():
        return build_mlp(input_dim=4, widths=(5,), activation="relu", dropout=0.0)

    result_a = fit_fixed_candidate(factory, training, validation, config, seed=92, batch_size=4)
    result_b = fit_fixed_candidate(factory, training, validation, config, seed=92, batch_size=4)

    assert torch.equal(result_a.predictions, result_b.predictions)
    assert result_a.checkpoint_sha256 == result_b.checkpoint_sha256
    assert result_a.best_epoch == result_b.best_epoch
    parameters = inspect.signature(fit_fixed_candidate).parameters
    assert not ({"max_epochs", "min_epochs", "patience"} & set(parameters))

    with pytest.raises(ValueError, match="100/50/40"):
        fit_fixed_candidate(
            factory,
            training,
            validation,
            replace(config, patience=39),
            seed=92,
            batch_size=4,
        )


def test_collate_mixed_n_pads_without_fake_n_element() -> None:
    batch = collate_set_features([_example(3), _example(5, offset=1.0)])

    assert batch.values.shape == (2, 5, 1)
    assert batch.mask.shape == (2, 5)
    assert batch.targets.shape == (2, 3)
    assert batch.location.shape == batch.scale.shape == batch.n.shape == (2,)
    assert batch.mask.dtype is torch.bool
    assert batch.n.dtype.is_floating_point
    assert torch.equal(batch.mask.sum(dim=1).to(batch.n.dtype), batch.n)
    assert torch.equal(batch.values[0, 3:, :], torch.zeros(2, 1))


@pytest.mark.parametrize("pool", ["sum", "mean"])
def test_padding_never_contributes_to_deepsets_pool(pool: str) -> None:
    torch.manual_seed(7)
    model = build_deepsets(encoder=(4,), pool=pool, head=(5,), activation="relu")
    batch = collate_set_features([_example(3)])
    padded_values = torch.cat([batch.values, torch.full((1, 4, 1), 999.0)], dim=1)
    padded_mask = torch.cat([batch.mask, torch.zeros((1, 4), dtype=torch.bool)], dim=1)

    assert torch.allclose(
        model(batch.values, batch.mask, batch.n),
        model(padded_values, padded_mask, batch.n),
        atol=1e-7,
    )


def test_collated_set_is_permutation_invariant() -> None:
    model = build_deepsets(encoder=(4,), pool="mean", head=(5,), activation="relu")
    original = _example(5)
    order = np.array([3, 0, 4, 1, 2])
    permuted = replace(
        original,
        features=SetFeatures(
            values=original.features.values[order],
            mask=original.features.mask[order],
            n=original.features.n,
        ),
    )
    batch_a = collate_set_features([original])
    batch_b = collate_set_features([permuted])

    assert torch.allclose(
        model(batch_a.values, batch_a.mask, batch_a.n),
        model(batch_b.values, batch_b.mask, batch_b.n),
        atol=1e-7,
    )


@pytest.mark.parametrize(
    "features",
    [
        SetFeatures(values=np.ones((3, 2)), mask=np.ones(3, dtype=bool), n=3),
        SetFeatures(values=np.ones((3, 1)), mask=np.ones(2, dtype=bool), n=3),
        SetFeatures(values=np.ones((3, 1)), mask=np.array([True, False, True]), n=3),
        SetFeatures(values=np.ones((3, 1)), mask=np.ones(3, dtype=bool), n=0),
    ],
)
def test_collate_rejects_malformed_value_mask_or_n(features: SetFeatures) -> None:
    with pytest.raises(ValueError):
        collate_set_features([replace(_example(3), features=features)])


def test_collate_rejects_empty_and_nonfinite_or_nonpositive_fields() -> None:
    with pytest.raises(ValueError):
        collate_set_features([])
    for item in (
        replace(_example(3), target=np.array([1.0, 2.0])),
        replace(_example(3), target=np.array([1.0, np.nan, 3.0])),
        replace(_example(3), location=np.inf),
        replace(_example(3), scale=0.0),
        replace(
            _example(3),
            features=SetFeatures(
                values=np.array([[1.0], [np.inf], [3.0]]),
                mask=np.ones(3, dtype=bool),
                n=3,
            ),
        ),
    ):
        with pytest.raises(ValueError):
            collate_set_features([item])


def test_fixed_collate_rejects_float32_overflow_in_every_float_tensor() -> None:
    huge = float(np.finfo(np.float32).max) * 2.0
    for item in (
        replace(_fixed_example(3), features=np.array([1.0, huge, 3.0])),
        replace(_fixed_example(3), target=np.array([1.0, huge, 3.0])),
        replace(_fixed_example(3), location=huge),
        replace(_fixed_example(3), scale=huge),
    ):
        with pytest.raises(ValueError, match="float32"):
            collate_fixed_features([item])


def test_set_collate_rejects_float32_overflow_in_every_float_tensor() -> None:
    huge = float(np.finfo(np.float32).max) * 2.0
    base = _example(3)
    for item in (
        replace(
            base,
            features=SetFeatures(
                values=np.array([[1.0], [huge], [3.0]]),
                mask=np.ones(3, dtype=bool),
                n=3,
            ),
        ),
        replace(base, target=np.array([1.0, huge, 3.0])),
        replace(base, location=huge),
        replace(base, scale=huge),
    ):
        with pytest.raises(ValueError, match="float32"):
            collate_set_features([item])


def test_real_set_fit_is_deterministic_and_uses_only_effective_config() -> None:
    training = collate_set_features([_example(3, offset=float(i) / 5.0) for i in range(8)])
    validation = collate_set_features([_example(5, offset=2.0 + float(i) / 5.0) for i in range(3)])
    config = _effective_config()

    def factory():
        return build_deepsets(encoder=(4,), pool="mean", head=(5,), activation="relu")

    result_a = fit_set_candidate(factory, training, validation, config, seed=91, batch_size=4)
    result_b = fit_set_candidate(factory, training, validation, config, seed=91, batch_size=4)

    assert torch.equal(result_a.predictions, result_b.predictions)
    assert result_a.checkpoint_sha256 == result_b.checkpoint_sha256
    assert result_a.best_epoch == result_b.best_epoch
    assert "max_epochs" not in inspect.signature(fit_set_candidate).parameters

    with pytest.raises(ValueError, match="100/50/40"):
        fit_set_candidate(
            factory,
            training,
            validation,
            replace(config, max_epochs=99),
            seed=91,
            batch_size=4,
        )


def test_set_fit_exposes_no_test_role_or_path_argument() -> None:
    parameters = inspect.signature(fit_set_candidate).parameters
    assert not ({"test", "test_data", "test_path", "dataset_path"} & set(parameters))
