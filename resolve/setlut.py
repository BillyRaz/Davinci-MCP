"""Safety and evidence helpers for a narrowly scoped Graph.SetLUT proof."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from .errors import OperationError, ValidationError

PROBE_TITLE = "MCP_SETLUT_VISIBLE_PROBE_V1"
PROBE_SIZE = 33
PROBE_NODE_LABEL = "MCP_SETLUT_PROBE"


def _probe_transform(red: float, green: float, blue: float) -> tuple[float, float, float]:
    # Contrast about middle gray, warm channel gains, and a modest saturation boost.
    values = (red * 1.18, green * 1.03, blue * 0.72)
    luma = 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]
    saturated = tuple(luma + (value - luma) * 1.14 for value in values)
    contrasted = tuple((value - 0.5) * 1.18 + 0.5 for value in saturated)
    return tuple(min(1.0, max(0.0, value)) for value in contrasted)  # type: ignore[return-value]


def generate_diagnostic_cube(size: int = PROBE_SIZE) -> str:
    if size != PROBE_SIZE:
        raise ValidationError("The diagnostic proof requires a 33x33x33 LUT")
    lines = [
        f'TITLE "{PROBE_TITLE}"',
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    denominator = size - 1
    for blue in range(size):
        for green in range(size):
            for red in range(size):
                output = _probe_transform(
                    red / denominator, green / denominator, blue / denominator
                )
                lines.append(" ".join(f"{value:.9f}" for value in output))
    return "\n".join(lines) + "\n"


def validate_cube(text: str, expected_size: int = PROBE_SIZE) -> dict[str, Any]:
    title = None
    size = None
    domain_min = None
    domain_max = None
    rows: list[tuple[float, float, float]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if fields[0] == "TITLE":
            title = line.removeprefix("TITLE").strip().strip('"')
        elif fields[0] == "LUT_3D_SIZE" and len(fields) == 2:
            size = int(fields[1])
        elif fields[0] in {"DOMAIN_MIN", "DOMAIN_MAX"} and len(fields) == 4:
            values = tuple(float(value) for value in fields[1:])
            if not all(math.isfinite(value) for value in values):
                raise ValidationError("Cube domain contains a non-finite value")
            if fields[0] == "DOMAIN_MIN":
                domain_min = values
            else:
                domain_max = values
        elif len(fields) == 3:
            try:
                values = tuple(float(value) for value in fields)
            except ValueError as exc:
                raise ValidationError(f"Malformed cube row: {line}") from exc
            if not all(math.isfinite(value) for value in values):
                raise ValidationError("Cube data contains a non-finite value")
            if not all(0.0 <= value <= 1.0 for value in values):
                raise ValidationError("Cube data is outside the approved 0–1 range")
            rows.append(values)  # type: ignore[arg-type]
        else:
            raise ValidationError(f"Malformed cube row: {line}")
    if not title or size != expected_size:
        raise ValidationError("Cube TITLE or LUT_3D_SIZE is invalid")
    if domain_min != (0.0, 0.0, 0.0) or domain_max != (1.0, 1.0, 1.0):
        raise ValidationError("Cube domain must be exactly 0–1")
    if len(rows) != expected_size**3:
        raise ValidationError(
            f"Cube has {len(rows)} rows; expected {expected_size**3}"
        )
    return {
        "title": title,
        "size": size,
        "row_count": len(rows),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "minimum": min(min(row) for row in rows),
        "maximum": max(max(row) for row in rows),
    }


def write_diagnostic_cube(path: Path) -> dict[str, Any]:
    if path.exists():
        raise OperationError(f"Refusing to overwrite existing LUT: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = generate_diagnostic_cube()
    path.write_text(text, encoding="utf-8", newline="\n")
    return {**validate_cube(text), "path": str(path)}


def require_owned_empty_node(nodes: Iterable[dict[str, Any]], node_index: int) -> None:
    matches = [node for node in nodes if node.get("index") == node_index]
    if len(matches) != 1:
        raise OperationError("Dedicated LUT node index is missing or ambiguous")
    node = matches[0]
    if node.get("lut"):
        raise OperationError("Refusing to overwrite an existing LUT")
    if node.get("label") not in {"", PROBE_NODE_LABEL} or node.get("tools"):
        raise OperationError("Node is not a validated empty temporary-version node")


def require_setlut_readback(
    set_result: bool, requested: str, readback: str | None
) -> None:
    if not set_result:
        raise OperationError("Graph.SetLUT returned false")
    if readback is not None and readback != requested:
        raise OperationError(
            f"Graph.GetLUT mismatch: requested {requested!r}, got {readback!r}"
        )


@dataclass(frozen=True)
class ImageDifference:
    before_sha256: str
    after_sha256: str
    dimensions: tuple[int, int]
    mean_absolute_rgb_difference: tuple[float, float, float]
    per_channel_mean_difference: tuple[float, float, float]
    luma_difference: float
    saturation_difference: float
    changed_pixel_percentage: float


def compare_images(before_path: Path, after_path: Path) -> ImageDifference:
    before_hash = hashlib.sha256(before_path.read_bytes()).hexdigest()
    after_hash = hashlib.sha256(after_path.read_bytes()).hexdigest()
    with (
        Image.open(before_path).convert("RGB") as before,
        Image.open(after_path).convert("RGB") as after,
    ):
        if before.size != after.size:
            raise OperationError("Before/after image dimensions do not match")
        difference = ImageChops.difference(before, after)
        absolute = tuple(ImageStat.Stat(difference).mean)
        before_mean = ImageStat.Stat(before).mean
        after_mean = ImageStat.Stat(after).mean
        channel_delta = tuple(after_mean[i] - before_mean[i] for i in range(3))
        before_luma = sum(weight * value for weight, value in zip((.2126, .7152, .0722), before_mean))
        after_luma = sum(weight * value for weight, value in zip((.2126, .7152, .0722), after_mean))
        before_sat = ImageStat.Stat(before.convert("HSV").getchannel("S")).mean[0]
        after_sat = ImageStat.Stat(after.convert("HSV").getchannel("S")).mean[0]
        changed = sum(1 for pixel in difference.getdata() if pixel != (0, 0, 0))
        percentage = 100.0 * changed / (before.width * before.height)
        return ImageDifference(
            before_hash,
            after_hash,
            before.size,
            absolute,
            channel_delta,
            after_luma - before_luma,
            after_sat - before_sat,
            percentage,
        )


def require_visible_difference(
    difference: ImageDifference,
    minimum_mean_rgb: float = 1.0,
    minimum_changed_pixels: float = 5.0,
) -> None:
    if difference.before_sha256 == difference.after_sha256:
        raise OperationError("SetLUT produced identical before/after image hashes")
    if (
        sum(difference.mean_absolute_rgb_difference) / 3 < minimum_mean_rgb
        or difference.changed_pixel_percentage < minimum_changed_pixels
    ):
        raise OperationError("SetLUT produced no trustworthy visible image difference")


def mutate_with_restoration(
    mutate: Callable[[], Any], restore: Callable[[], Any]
) -> Any:
    try:
        return mutate()
    finally:
        restore()
