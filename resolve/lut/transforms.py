"""Pure deterministic color transforms used by LUT generation.

Encoded Rec.709/gamma-2.4 values are decoded with a display-referred power law.
All treatment then occurs in linear Rec.709 RGB. Temperature/tint is a restrained
creative RGB gain approximation, not camera white balance or chromatic adaptation.
"""

from __future__ import annotations

import colorsys
import math

from .model import GradeProfile

RGB = tuple[float, float, float]
LUMA = (0.2126, 0.7152, 0.0722)


def decode_gamma24(value: float) -> float:
    return max(0.0, value) ** 2.4


def encode_gamma24(value: float) -> float:
    return max(0.0, value) ** (1.0 / 2.4)


def exposure(rgb: RGB, stops: float) -> RGB:
    gain = 2.0**stops
    return tuple(value * gain for value in rgb)  # type: ignore[return-value]


def temperature_tint(rgb: RGB, temperature: float, tint: float) -> RGB:
    red_gain = 1.0 + temperature
    blue_gain = 1.0 - temperature
    green_gain = 1.0 + tint
    magenta_gain = 1.0 - tint * 0.5
    return (
        rgb[0] * red_gain * magenta_gain,
        rgb[1] * green_gain,
        rgb[2] * blue_gain * magenta_gain,
    )


def contrast_pivot(rgb: RGB, contrast: float, pivot: float) -> RGB:
    def curve(value: float) -> float:
        if value <= 0.0 or value >= 1.0:
            return value
        if value <= pivot:
            return pivot * (value / pivot) ** contrast
        return 1.0 - (1.0 - pivot) * ((1.0 - value) / (1.0 - pivot)) ** contrast

    return tuple(curve(value) for value in rgb)  # type: ignore[return-value]


def toe(value: float, strength: float) -> float:
    if strength == 0.0:
        return value
    sign = -1.0 if value < 0 else 1.0
    return sign * abs(value) ** (1.0 + strength)


def shoulder(value: float, strength: float) -> float:
    if strength == 0.0 or value <= 0.0:
        return value
    if value >= 1.0:
        return 1.0 + (value - 1.0) / (1.0 + strength * (value - 1.0))
    return 1.0 - (1.0 - value) ** (1.0 / (1.0 + strength))


def luma(rgb: RGB) -> float:
    return sum(weight * value for weight, value in zip(LUMA, rgb))


def saturation(rgb: RGB, amount: float) -> RGB:
    luminance = luma(rgb)
    return tuple(luminance + (value - luminance) * amount for value in rgb)  # type: ignore[return-value]


def tonal_saturation(rgb: RGB, shadow_amount: float, highlight_amount: float) -> RGB:
    luminance = min(1.0, max(0.0, luma(rgb)))
    shadow_weight = (1.0 - luminance) ** 2
    highlight_weight = luminance**2
    amount = (
        1.0
        + (shadow_amount - 1.0) * shadow_weight
        + (highlight_amount - 1.0) * highlight_weight
    )
    return saturation(rgb, amount)


def hue_weight(hue: float, center: float, width: float = 1.0 / 6.0) -> float:
    distance = abs(hue - center) % 1.0
    distance = min(distance, 1.0 - distance)
    if distance >= width:
        return 0.0
    phase = distance / width
    return 0.5 + 0.5 * math.cos(math.pi * phase)


def hue_sectors(
    rgb: RGB, teal_preservation: float, magenta_preservation: float, gold_warmth: float
) -> RGB:
    bounded = tuple(min(1.0, max(0.0, value)) for value in rgb)
    hue, sat, val = colorsys.rgb_to_hsv(*bounded)
    if sat < 1e-9:
        return rgb
    chroma_weight = min(1.0, sat / 0.25) ** 2
    teal = hue_weight(hue, 0.50) * teal_preservation * chroma_weight
    magenta = (
        hue_weight(hue, 5.0 / 6.0) * magenta_preservation * chroma_weight
    )
    gold = hue_weight(hue, 1.0 / 8.0) * gold_warmth * chroma_weight
    preserved_sat = sat * (1.0 + teal + magenta)
    adjusted = colorsys.hsv_to_rgb(hue, min(1.0, preserved_sat), val)
    return (
        adjusted[0] * (1.0 + gold),
        adjusted[1] * (1.0 + gold * 0.25),
        adjusted[2] * (1.0 - gold * 0.5),
    )


def gamut_compress(rgb: RGB, strength: float) -> RGB:
    if strength == 0.0:
        return rgb

    def compress(value: float) -> float:
        if value > 1.0:
            excursion = value - 1.0
            return 1.0 + excursion / (1.0 + strength * excursion * 4.0)
        if value < 0.0:
            return value / (1.0 + strength * abs(value) * 4.0)
        return value

    return tuple(compress(value) for value in rgb)  # type: ignore[return-value]


def apply_profile(encoded_rgb: RGB, profile: GradeProfile) -> RGB:
    rgb = tuple(decode_gamma24(value) for value in encoded_rgb)
    rgb = exposure(rgb, profile.exposure_stops)
    rgb = temperature_tint(rgb, profile.temperature, profile.tint)
    rgb = contrast_pivot(rgb, profile.contrast, profile.pivot)
    rgb = tuple(toe(value, profile.toe_strength) for value in rgb)
    rgb = tuple(shoulder(value, profile.shoulder_strength) for value in rgb)
    rgb = saturation(rgb, profile.saturation)
    rgb = tonal_saturation(
        rgb, profile.shadow_saturation, profile.highlight_saturation
    )
    rgb = hue_sectors(
        rgb,
        profile.teal_preservation,
        profile.magenta_preservation,
        profile.gold_warmth,
    )
    rgb = gamut_compress(rgb, profile.gamut_compression)
    span = profile.white_ceiling - profile.black_floor
    rgb = tuple(profile.black_floor + value * span for value in rgb)
    return tuple(
        min(1.0, max(0.0, encode_gamma24(value))) for value in rgb
    )  # type: ignore[return-value]
