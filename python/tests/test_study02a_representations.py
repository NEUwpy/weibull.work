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
    build_features,
    decode_targets,
    encode_targets,
    SetFeatures,
)


@pytest.mark.parametrize("scale,shift", [(1e-3, -500.0), (1e3, 5e6)])
def test_main_representation_is_scale_translation_equivariant(scale, shift):
    x = np.array([120.0, 135.0, 180.0, 220.0, 410.0])
    params = (2.2, 140.0, 80.0)
    base_anchor = anchor_sample(x)
    base = decode_targets(encode_targets(*params, base_anchor), base_anchor)

    transformed_x = scale * x + shift
    transformed_params = (params[0], scale * params[1], scale * params[2] + shift)
    transformed_anchor = anchor_sample(transformed_x)
    transformed = decode_targets(
        encode_targets(*transformed_params, transformed_anchor),
        transformed_anchor,
    )

    assert transformed[0] == pytest.approx(base[0], rel=1e-6)
    assert transformed[1] == pytest.approx(scale * base[1], rel=1e-6)
    assert transformed[2] == pytest.approx(scale * base[2] + shift, rel=1e-6)


def test_anchor_uses_range_fallback_and_rejects_constant_sample():
    anchor = anchor_sample(np.array([1.0, 1.0, 1.0, 1.0, 2.0]))
    assert anchor.location == 1.0
    assert anchor.scale == 1.0
    with pytest.raises(DegenerateSampleError, match="constant sample"):
        anchor_sample(np.ones(5))


def test_decode_round_trip_is_legal():
    x = np.array([100.0, 110.0, 125.0, 160.0, 220.0])
    anchor = anchor_sample(x)
    decoded = decode_targets(encode_targets(1.8, 90.0, 70.0, anchor), anchor)
    assert decoded == pytest.approx((1.8, 90.0, 70.0))
    assert decoded[0] > 0 and decoded[1] > 0 and decoded[2] < x.min()


def test_frozen_feature_route_widths_and_mode_ids():
    x = np.array([100.0, 101.0, 102.0, 120.0, 180.0, 181.0, 230.0])
    expected_widths = {
        "H0_hsm": 7,
        "H0_kde_scott1024": 7,
        "H1": 6,
        "F0eq_hsm": 6,
        "F0eq_kde_scott1024": 6,
        "F1eq": 6,
        "F2": 15,
        "V": len(x),
    }
    features = {route: build_features(route, x, len(x)) for route in expected_widths}
    assert {route: len(value) for route, value in features.items()} == expected_widths
    assert features["H0_hsm"][4] != pytest.approx(features["H0_kde_scott1024"][4])
    set_features = build_features("S", x, len(x))
    assert isinstance(set_features, SetFeatures)
    assert set_features.values.shape == (len(x), 1)
    assert set_features.mask.tolist() == [True] * len(x)
    assert set_features.n == len(x)


def test_equivariant_feature_routes_ignore_units_and_shift():
    x = np.array([80.0, 95.0, 120.0, 180.0, 260.0, 400.0, 610.0])
    transformed = 1000.0 * x - 5e6
    for route in ("F0eq_hsm", "F0eq_kde_scott1024", "F1eq", "F2", "V"):
        np.testing.assert_allclose(
            build_features(route, x, len(x)),
            build_features(route, transformed, len(x)),
            rtol=1e-6,
            atol=1e-8,
        )
