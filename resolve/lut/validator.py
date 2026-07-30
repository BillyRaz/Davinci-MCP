"""Structural and technical validation for generated/imported cube LUTs."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from resolve.errors import ValidationError

from .model import GradeProfile

SUPPORTED_SIZES = {17, 33, 65}


@dataclass
class LutValidation:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details,
        }


def parse_cube_bytes(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValidationError("Cube must be ASCII text") from exc
    if "\r" in text:
        raise ValidationError("Cube must use LF line endings")
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
        key = fields[0]
        if key == "TITLE" and len(fields) >= 2:
            title = line[len("TITLE") :].strip().strip('"')
        elif key == "LUT_3D_SIZE" and len(fields) == 2:
            size = int(fields[1])
        elif key in {"DOMAIN_MIN", "DOMAIN_MAX"} and len(fields) == 4:
            values = tuple(float(value) for value in fields[1:])
            if key == "DOMAIN_MIN":
                domain_min = values
            else:
                domain_max = values
        elif len(fields) == 3:
            try:
                values = tuple(float(value) for value in fields)
            except ValueError as exc:
                raise ValidationError(f"Malformed cube row: {line}") from exc
            if not all(math.isfinite(value) for value in values):
                raise ValidationError("Cube contains NaN or infinity")
            rows.append(values)  # type: ignore[arg-type]
        else:
            raise ValidationError(f"Invalid cube header or row: {line}")
    if not title or size not in SUPPORTED_SIZES:
        raise ValidationError("Missing title or unsupported LUT_3D_SIZE")
    if domain_min != (0.0, 0.0, 0.0) or domain_max != (1.0, 1.0, 1.0):
        raise ValidationError("DOMAIN_MIN/MAX must be exactly 0–1")
    if len(rows) != size**3:
        raise ValidationError(f"Cube has {len(rows)} rows; expected {size**3}")
    if any(value < 0.0 or value > 1.0 for row in rows for value in row):
        raise ValidationError("Cube sample outside approved 0–1 range")
    return {"title": title, "size": size, "rows": rows}


def validate_lut(
    cube_path: Path, metadata_path: Path | None = None, *, require_metadata: bool = False
) -> LutValidation:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    if not cube_path.is_file():
        return LutValidation(False, [f"Cube does not exist: {cube_path}"])
    data = cube_path.read_bytes()
    try:
        parsed = parse_cube_bytes(data)
    except (ValidationError, ValueError) as exc:
        return LutValidation(False, [str(exc)])
    digest = hashlib.sha256(data).hexdigest()
    rows = parsed["rows"]
    identity_delta = 0.0
    size = parsed["size"]
    scale = size - 1
    neutral_cast = 0.0
    monotonic = True
    previous = (-1.0, -1.0, -1.0)
    for index in range(size):
        offset = index * size * size + index * size + index
        output = rows[offset]
        neutral_cast = max(neutral_cast, max(output) - min(output))
        monotonic = monotonic and all(output[c] >= previous[c] for c in range(3))
        previous = output
    for blue in range(size):
        for green in range(size):
            for red in range(size):
                row = rows[blue * size * size + green * size + red]
                source = (red / scale, green / scale, blue / scale)
                identity_delta += sum(abs(row[i] - source[i]) for i in range(3))
    identity_distance = identity_delta / (len(rows) * 3)
    if identity_distance < 1e-9:
        warnings.append("Identity LUT")
    elif identity_distance < 0.001:
        warnings.append("Near-identity LUT")
    if neutral_cast > 0.03:
        warnings.append("Neutral-axis cast exceeds 0.03")
    if not monotonic:
        errors.append("Neutral ramp is non-monotonic")
    metadata = None
    if metadata_path and metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text())
            profile = GradeProfile.model_validate(metadata["parameters"])
            if metadata.get("sha256") != digest:
                errors.append("Metadata SHA-256 mismatch")
            if metadata.get("cube_size") != size or profile.cube_size != size:
                errors.append("Metadata/profile cube size mismatch")
            if metadata.get("profile_name") != parsed["title"]:
                errors.append("Metadata/profile title mismatch")
        except (KeyError, ValueError) as exc:
            errors.append(f"Invalid metadata: {exc}")
    elif require_metadata:
        errors.append("Required sidecar metadata is missing")
    details.update(
        {
            "title": parsed["title"],
            "cube_size": size,
            "row_count": len(rows),
            "sha256": digest,
            "identity_distance": identity_distance,
            "neutral_axis_cast": neutral_cast,
            "neutral_monotonic": monotonic,
            "metadata_loaded": metadata is not None,
        }
    )
    return LutValidation(not errors, errors, warnings, details)
