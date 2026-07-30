"""Technical LUT sampling and bounded before/after image analysis."""

from __future__ import annotations

import colorsys
import hashlib
import math
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from resolve.errors import OperationError

from .validator import parse_cube_bytes

RGB = tuple[float, float, float]
SAMPLES: dict[str, RGB] = {
    "cyan": (0.0, 1.0, 1.0),
    "magenta": (1.0, 0.0, 1.0),
    "yellow_gold": (1.0, 0.75, 0.05),
    "teal": (0.05, 0.65, 0.65),
    "warm_skin_like": (0.72, 0.42, 0.28),
    "cool_skin_like": (0.58, 0.38, 0.34),
    "near_black_red": (0.08, 0.01, 0.01),
    "near_white_blue": (0.92, 0.94, 1.0),
}


def _sample(rows: list[RGB], size: int, rgb: RGB) -> RGB:
    positions = [min(size - 1, max(0.0, value * (size - 1))) for value in rgb]
    lower = [math.floor(value) for value in positions]
    upper = [min(size - 1, value + 1) for value in lower]
    fractions = [positions[index] - lower[index] for index in range(3)]

    def row(red: int, green: int, blue: int) -> RGB:
        return rows[blue * size * size + green * size + red]

    output = [0.0, 0.0, 0.0]
    for blue_bit in (0, 1):
        for green_bit in (0, 1):
            for red_bit in (0, 1):
                indices = (
                    upper[0] if red_bit else lower[0],
                    upper[1] if green_bit else lower[1],
                    upper[2] if blue_bit else lower[2],
                )
                weight = (
                    (fractions[0] if red_bit else 1 - fractions[0])
                    * (fractions[1] if green_bit else 1 - fractions[1])
                    * (fractions[2] if blue_bit else 1 - fractions[2])
                )
                value = row(*indices)
                for channel in range(3):
                    output[channel] += value[channel] * weight
    return tuple(output)  # type: ignore[return-value]


def _hue_delta(first: RGB, second: RGB) -> float:
    first_hsv = colorsys.rgb_to_hsv(*first)
    second_hsv = colorsys.rgb_to_hsv(*second)
    if min(first_hsv[1], second_hsv[1], first_hsv[2], second_hsv[2]) < 0.02:
        return 0.0
    first_hue = first_hsv[0] * 360
    second_hue = second_hsv[0] * 360
    distance = abs(first_hue - second_hue)
    return min(distance, 360 - distance)


def analyze_lut(cube_path: Path) -> dict[str, Any]:
    parsed = parse_cube_bytes(cube_path.read_bytes())
    rows = parsed["rows"]
    size = parsed["size"]
    samples = {
        **SAMPLES,
        **{f"red_{index}": (index / 32, 0.0, 0.0) for index in range(33)},
        **{f"green_{index}": (0.0, index / 32, 0.0) for index in range(33)},
        **{f"blue_{index}": (0.0, 0.0, index / 32) for index in range(33)},
    }
    deltas = []
    hue_deltas = []
    saturation_deltas = []
    outputs = {}
    for name, source in samples.items():
        output = _sample(rows, size, source)
        outputs[name] = output
        deltas.append(sum(abs(output[i] - source[i]) for i in range(3)) / 3)
        hue_deltas.append(_hue_delta(source, output))
        saturation_deltas.append(
            colorsys.rgb_to_hsv(*output)[1] - colorsys.rgb_to_hsv(*source)[1]
        )
    neutral = [_sample(rows, size, (index / 128,) * 3) for index in range(129)]
    cast = max(max(value) - min(value) for value in neutral)
    monotonic = all(
        all(left[channel] <= right[channel] + 1e-9 for channel in range(3))
        for left, right in pairwise(neutral)
    )
    clipped = 0
    interior = 0
    for blue in range(1, size - 1):
        for green in range(1, size - 1):
            for red in range(1, size - 1):
                interior += 1
                row = rows[blue * size * size + green * size + red]
                clipped += all(value <= 1e-9 for value in row) or all(
                    value >= 1 - 1e-9 for value in row
                )
    return {
        "cube_path": str(cube_path.resolve()),
        "cube_size": size,
        "neutral_axis_cast": cast,
        "neutral_monotonic": monotonic,
        "clipping_percentage": 100 * clipped / interior,
        "channel_minima": [min(row[channel] for row in rows) for channel in range(3)],
        "channel_maxima": [max(row[channel] for row in rows) for channel in range(3)],
        "average_sample_delta": sum(deltas) / len(deltas),
        "maximum_sample_delta": max(deltas),
        "average_saturation_change": sum(saturation_deltas) / len(saturation_deltas),
        "maximum_hue_angle_change": max(hue_deltas),
        "identity_distance": sum(
            sum(
                abs(
                    rows[blue * size * size + green * size + red][channel]
                    - (red, green, blue)[channel] / (size - 1)
                )
                for channel in range(3)
            )
            for blue in range(size)
            for green in range(size)
            for red in range(size)
        )
        / (len(rows) * 3),
        "standard_samples": {
            name: list(outputs[name]) for name in SAMPLES
        },
        "label": "Technical transform analysis; not an artistic-quality score",
    }


@dataclass(frozen=True)
class CaptureThresholds:
    minimum_changed_pixels: float = 1.0
    maximum_highlight_clipping_increase: float = 0.5
    maximum_shadow_crush_increase: float = 1.0
    maximum_absolute_luma_change: float = 35.0
    maximum_saturation_increase: float = 40.0
    maximum_channel_imbalance: float = 30.0
    reject_visible_noop: bool = True
    reject_clipping: bool = False


def compare_captures(
    before_path: Path,
    after_path: Path,
    thresholds: CaptureThresholds | None = None,
) -> dict[str, Any]:
    limits = thresholds or CaptureThresholds()
    before_hash = hashlib.sha256(before_path.read_bytes()).hexdigest()
    after_hash = hashlib.sha256(after_path.read_bytes()).hexdigest()
    with (
        Image.open(before_path).convert("RGB") as before,
        Image.open(after_path).convert("RGB") as after,
    ):
        if before.size != after.size:
            raise OperationError("Capture dimensions differ")
        difference = ImageChops.difference(before, after)
        absolute = ImageStat.Stat(difference).mean
        before_mean = ImageStat.Stat(before).mean
        after_mean = ImageStat.Stat(after).mean
        channel_change = [after_mean[i] - before_mean[i] for i in range(3)]
        luma_weights = (0.2126, 0.7152, 0.0722)
        luma_change = sum(
            luma_weights[i] * channel_change[i] for i in range(3)
        )
        saturation_change = (
            ImageStat.Stat(after.convert("HSV").getchannel("S")).mean[0]
            - ImageStat.Stat(before.convert("HSV").getchannel("S")).mean[0]
        )
        before_pixels = list(before.get_flattened_data())
        after_pixels = list(after.get_flattened_data())
        count = len(before_pixels)
        changed = sum(left != right for left, right in zip(before_pixels, after_pixels))

        def percentage(pixels: list[RGB], predicate: Any) -> float:
            return 100 * sum(predicate(pixel) for pixel in pixels) / count

        before_black = percentage(before_pixels, lambda pixel: max(pixel) <= 5)
        after_black = percentage(after_pixels, lambda pixel: max(pixel) <= 5)
        before_white = percentage(before_pixels, lambda pixel: min(pixel) >= 250)
        after_white = percentage(after_pixels, lambda pixel: min(pixel) >= 250)
    metrics = {
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "hashes_equal": before_hash == after_hash,
        "dimensions": list(before.size),
        "mean_absolute_rgb_difference": absolute,
        "per_channel_mean_change": channel_change,
        "luma_change": luma_change,
        "mean_saturation_change": saturation_change,
        "changed_pixel_percentage": 100 * changed / count,
        "near_black_percentage_before": before_black,
        "near_black_percentage_after": after_black,
        "near_white_percentage_before": before_white,
        "near_white_percentage_after": after_white,
        "shadow_crush_increase": after_black - before_black,
        "highlight_clipping_increase": after_white - before_white,
    }
    warnings = []
    if metrics["changed_pixel_percentage"] < limits.minimum_changed_pixels:
        warnings.append("Changed pixels below configured no-op threshold")
    if metrics["highlight_clipping_increase"] > limits.maximum_highlight_clipping_increase:
        warnings.append("Highlight clipping increase exceeds warning threshold")
    if metrics["shadow_crush_increase"] > limits.maximum_shadow_crush_increase:
        warnings.append("Shadow crush increase exceeds warning threshold")
    if abs(luma_change) > limits.maximum_absolute_luma_change:
        warnings.append("Mean luma change exceeds warning threshold")
    if saturation_change > limits.maximum_saturation_increase:
        warnings.append("Mean saturation increase exceeds warning threshold")
    if max(channel_change) - min(channel_change) > limits.maximum_channel_imbalance:
        warnings.append("Global channel imbalance exceeds warning threshold")
    hard_rejections = []
    if limits.reject_visible_noop and metrics["changed_pixel_percentage"] < limits.minimum_changed_pixels:
        hard_rejections.append("REJECTED_VISIBLE_NOOP")
    if (
        limits.reject_clipping
        and metrics["highlight_clipping_increase"]
        > limits.maximum_highlight_clipping_increase
    ):
        hard_rejections.append("REJECTED_TECHNICAL_SAFETY")
    return {
        "metrics": metrics,
        "warnings": warnings,
        "hard_rejections": hard_rejections,
        "thresholds": asdict(limits),
        "label": "Bounded technical comparison; human visual approval is still required",
    }
