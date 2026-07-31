"""Unit tests for D-route target encoding/decoding and equivariance."""

from pathlib import Path
import sys

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from study02a.representations import (
    DegenerateSampleError,
    anchor_sample,
    Anchor,
)
from study02b.representations import (
    encode_d_target,
    decode_d_target,
    encode_d_batch,
    decode_d_batch,
    compute_d_stats,
    standardize_d,
    unstandardize_d,
    DTrainingStats,
)


def test_encode_decode_roundtrip():
    """Basic roundtrip: encode then decode recovers original x_{0.95}."""
    x = np.array([100.0, 110.0, 125.0, 160.0, 220.0])
    anchor = anchor_sample(x)
    x095 = 50.0  # a value below sample min
    encoded = encode_d_target(x095, anchor)
    decoded = decode_d_target(encoded, anchor)
    assert decoded == pytest.approx(x095, rel=1e-12)


def test_encode_decode_below_min():
    """x_{0.95} can be below the sample minimum (lower tail quantile)."""
    x = np.array([200.0, 300.0, 400.0])
    anchor = anchor_sample(x)
    x095 = 150.0
    encoded = encode_d_target(x095, anchor)
    decoded = decode_d_target(encoded, anchor)
    assert decoded == pytest.approx(x095, rel=1e-12)


def test_encode_decode_above_max():
    """x_{0.95} can be above the sample maximum (when beta < 1)."""
    x = np.array([100.0, 200.0, 300.0])
    anchor = anchor_sample(x)
    x095 = 500.0
    encoded = encode_d_target(x095, anchor)
    decoded = decode_d_target(encoded, anchor)
    assert decoded == pytest.approx(x095, rel=1e-12)


@pytest.mark.parametrize("scale,shift", [
    (1e-3, -500.0),
    (1e3, 5e6),
    (0.1, 0.0),
    (10.0, 10000.0),
])
def test_d_target_is_scale_translation_equivariant(scale, shift):
    """Encoding must be invariant under joint scale+translation of sample and x_{0.95}."""
    x = np.array([120.0, 135.0, 180.0, 220.0, 410.0])
    anchor = anchor_sample(x)

    beta, eta, gamma = 2.2, 140.0, 80.0
    x095 = gamma + eta * (-np.log(0.95)) ** (1.0 / beta)

    encoded_base = encode_d_target(x095, anchor)

    # Transform sample and x_{0.95}
    transformed_x = scale * x + shift
    transformed_anchor = anchor_sample(transformed_x)
    transformed_x095 = scale * x095 + shift

    encoded_transformed = encode_d_target(transformed_x095, transformed_anchor)

    assert encoded_transformed == pytest.approx(encoded_base, rel=1e-10)


def test_standardize_roundtrip():
    """Standardize then unstandardize recovers original values."""
    targets = np.array([0.5, 1.0, 1.5, 2.0, 2.5])
    stats = compute_d_stats(targets)
    standardized = standardize_d(targets, stats)
    recovered = unstandardize_d(standardized, stats)
    np.testing.assert_allclose(recovered, targets, rtol=1e-12)


def test_standardize_zero_sd():
    """When training targets are constant, safe_sd returns 1.0."""
    targets = np.array([3.0, 3.0, 3.0])
    stats = compute_d_stats(targets)
    assert stats.sd == 0.0
    # standardize should not divide by zero
    standardized = standardize_d(targets, stats)
    np.testing.assert_allclose(standardized, np.zeros_like(targets), rtol=1e-12)
    # unstandardize with safe_sd=1.0 still recovers original
    recovered = unstandardize_d(standardized, stats)
    np.testing.assert_allclose(recovered, targets, rtol=1e-12)


def test_batch_encode_decode():
    """Batch encode/decode must be consistent with per-sample operations."""
    samples = [
        np.array([100.0, 120.0, 150.0, 200.0, 300.0]),
        np.array([50.0, 55.0, 60.0, 65.0, 70.0]),
        np.array([1000.0, 1100.0, 1200.0, 1300.0, 1400.0]),
    ]
    x095s = np.array([80.0, 45.0, 950.0])
    anchors = [anchor_sample(x) for x in samples]

    encoded = encode_d_batch(x095s, anchors)
    decoded = decode_d_batch(encoded, anchors)
    np.testing.assert_allclose(decoded, x095s, rtol=1e-12)

    # Check per-sample consistency
    for i, (x, x095) in enumerate(zip(samples, x095s)):
        single = encode_d_target(x095, anchors[i])
        assert encoded[i] == pytest.approx(single, rel=1e-12)


def test_mismatched_batch_lengths_raise():
    """Batch functions reject mismatched input lengths."""
    x = np.array([100.0, 110.0, 125.0, 160.0, 220.0])
    anchor = anchor_sample(x)

    with pytest.raises(ValueError):
        encode_d_batch(np.array([1.0, 2.0]), [anchor])

    with pytest.raises(ValueError):
        decode_d_batch(np.array([1.0, 2.0]), [anchor])


def test_compute_stats_empty_raises():
    """Computing stats on empty targets must raise."""
    with pytest.raises(ValueError):
        compute_d_stats(np.array([]))
