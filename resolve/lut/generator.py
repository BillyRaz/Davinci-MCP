"""Resolve-compatible .cube generation and metadata emission."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .model import GradeProfile
from .transforms import apply_profile

GENERATOR_VERSION = "1.0.0"


def generate_cube_bytes(profile: GradeProfile) -> bytes:
    size = profile.cube_size
    lines = [
        f'TITLE "{profile.name}"',
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN 0.000000000 0.000000000 0.000000000",
        "DOMAIN_MAX 1.000000000 1.000000000 1.000000000",
    ]
    scale = size - 1
    for blue in range(size):
        for green in range(size):
            for red in range(size):
                output = apply_profile((red / scale, green / scale, blue / scale), profile)
                lines.append(" ".join(f"{value:.9f}" for value in output))
    return ("\n".join(lines) + "\n").encode("ascii")


def build_metadata(
    profile: GradeProfile,
    cube_bytes: bytes,
    *,
    source_profile_path: str | None,
    created_at: str | None = None,
    approval_state: str = "unapproved",
) -> dict[str, Any]:
    return {
        "schema_version": profile.schema_version,
        "profile_name": profile.name,
        "description": profile.description,
        "input_color_space": profile.input_color_space,
        "output_color_space": profile.output_color_space,
        "working_space": profile.working_space,
        "cube_size": profile.cube_size,
        "parameters": profile.model_dump(mode="json"),
        "generator_version": GENERATOR_VERSION,
        "sha256": hashlib.sha256(cube_bytes).hexdigest(),
        "validation_status": "pending",
        "resolve_compatibility": "Resolve Graph.SetLUT; RGB .cube; red-fastest ordering",
        "production_approval_state": approval_state,
        "creation_timestamp": created_at or datetime.now(UTC).isoformat(),
        "source_profile_path": source_profile_path,
    }


def generate_artifacts(
    profile: GradeProfile,
    output_directory: Path,
    *,
    source_profile_path: str | None = None,
    overwrite_identical: bool = True,
) -> dict[str, Any]:
    output_directory.mkdir(parents=True, exist_ok=True)
    cube_bytes = generate_cube_bytes(profile)
    cube_path = output_directory / f"{profile.filename_stem}.cube"
    metadata_path = output_directory / f"{profile.filename_stem}.json"
    if cube_path.exists() and cube_path.read_bytes() != cube_bytes:
        raise FileExistsError(f"Refusing to overwrite different LUT: {cube_path}")
    if not cube_path.exists() or not overwrite_identical:
        cube_path.write_bytes(cube_bytes)
    metadata = build_metadata(
        profile, cube_bytes, source_profile_path=source_profile_path
    )
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "cube_path": str(cube_path.resolve()),
        "metadata_path": str(metadata_path.resolve()),
        "sha256": metadata["sha256"],
        "row_count": profile.cube_size**3,
    }
