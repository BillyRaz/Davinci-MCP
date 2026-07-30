from itertools import pairwise

import pytest

from resolve.lut.model import GradeProfile
from resolve.lut.transforms import (
    apply_profile,
    contrast_pivot,
    decode_gamma24,
    encode_gamma24,
    exposure,
    gamut_compress,
    hue_sectors,
    saturation,
    shoulder,
    temperature_tint,
    toe,
    tonal_saturation,
)


def identity_profile(**overrides: object) -> GradeProfile:
    values = {"name": "IDENTITY_V1", "description": "Identity"}
    values.update(overrides)
    return GradeProfile.model_validate(values)


@pytest.mark.parametrize("value", [0.0, 1e-6, 0.18, 0.5, 0.99, 1.0])
def test_gamma24_round_trip(value: float) -> None:
    assert encode_gamma24(decode_gamma24(value)) == pytest.approx(value, abs=1e-12)


def test_exposure_behavior() -> None:
    rgb = (0.1, 0.2, 0.3)
    assert exposure(rgb, 0) == rgb
    assert exposure(rgb, 1) == pytest.approx((0.2, 0.4, 0.6))
    assert exposure(rgb, -1) == pytest.approx((0.05, 0.1, 0.15))


def test_temperature_and_tint_directions_and_black() -> None:
    assert temperature_tint((0, 0, 0), 0.1, 0.1) == (0, 0, 0)
    warm = temperature_tint((0.5, 0.5, 0.5), 0.05, 0)
    assert warm[0] > warm[2]
    green = temperature_tint((0.5, 0.5, 0.5), 0, 0.05)
    assert green[1] > green[0]


def test_contrast_pivot_and_monotonic_toe_shoulder() -> None:
    assert contrast_pivot((0.2, 0.5, 0.8), 1, 0.4) == pytest.approx(
        (0.2, 0.5, 0.8)
    )
    ramp = [index / 1000 for index in range(1001)]
    for transform in (toe, shoulder):
        output = [transform(value, 0.2) for value in ramp]
        assert all(left <= right for left, right in pairwise(output))
        assert output[0] == 0
        assert output[-1] == 1
        assert [transform(value, 0) for value in ramp] == ramp


def test_saturation_and_tonal_weighting() -> None:
    rgb = (0.8, 0.2, 0.1)
    assert saturation(rgb, 1) == pytest.approx(rgb)
    gray = saturation(rgb, 0)
    assert gray[0] == pytest.approx(gray[1])
    assert gray[1] == pytest.approx(gray[2])
    assert saturation((0.4, 0.4, 0.4), 1.8) == pytest.approx((0.4, 0.4, 0.4))
    assert tonal_saturation(rgb, 1, 1) == pytest.approx(rgb)


def test_hue_sectors_are_smooth_and_neutral_safe() -> None:
    assert hue_sectors((0.5, 0.5, 0.5), 0.1, 0.1, 0.1) == (0.5, 0.5, 0.5)
    teal = hue_sectors((0.1, 0.7, 0.7), 0.1, 0, 0)
    gold = hue_sectors((0.8, 0.55, 0.1), 0, 0, 0.1)
    assert max(teal) - min(teal) >= 0.6
    assert gold[0] > 0.8 and gold[2] < 0.1


def test_gamut_compression_and_deterministic_pipeline() -> None:
    rgb = (1.3, 0.5, -0.1)
    assert gamut_compress(rgb, 0) == rgb
    compressed = gamut_compress(rgb, 0.5)
    assert max(compressed) - min(compressed) < max(rgb) - min(rgb)
    profile = identity_profile()
    sample = (0.2, 0.4, 0.8)
    assert apply_profile(sample, profile) == pytest.approx(sample, abs=1e-9)
    assert apply_profile(sample, profile) == apply_profile(sample, profile)
