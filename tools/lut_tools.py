"""Focused MCP surface for profile-driven LUT workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from resolve.lut.analysis import analyze_lut as analyze_lut_file
from resolve.lut.analysis import compare_captures
from resolve.lut.generator import generate_artifacts
from resolve.lut.model import GradeProfile
from resolve.lut.validator import validate_lut as validate_lut_file

from .context import Services


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def create_lut_profile(profile: dict[str, Any], output_path: str) -> dict[str, Any]:
        """Validate and save one strict versioned global-treatment profile."""
        validated = GradeProfile.model_validate(profile)
        path = Path(output_path).expanduser().resolve()
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite profile: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(validated.model_dump(mode="json"), indent=2) + "\n"
        )
        return {"profile_path": str(path), "profile": validated.model_dump(mode="json")}

    @mcp.tool()
    def generate_lut(
        profile_path: str, output_directory: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """Generate deterministic cube/metadata artifacts without touching Resolve."""
        path = Path(profile_path).expanduser().resolve()
        profile = GradeProfile.model_validate_json(path.read_text())
        if dry_run:
            return {
                "dry_run": True,
                "filename": f"{profile.filename_stem}.cube",
                "row_count": profile.cube_size**3,
            }
        return generate_artifacts(
            profile,
            Path(output_directory).expanduser().resolve(),
            source_profile_path=str(path),
        )

    @mcp.tool()
    def validate_lut(
        cube_path: str, metadata_path: str | None = None
    ) -> dict[str, Any]:
        """Validate cube structure, metadata, hash, and neutral-axis safety."""
        return validate_lut_file(
            Path(cube_path).expanduser().resolve(),
            Path(metadata_path).expanduser().resolve() if metadata_path else None,
        ).to_dict()

    @mcp.tool()
    def register_lut(cube_path: str, metadata_path: str) -> dict[str, Any]:
        """Register one validated LUT without allowing name or hash conflicts."""
        return services.lut_registry.register(
            Path(cube_path).expanduser().resolve(),
            Path(metadata_path).expanduser().resolve(),
        )

    @mcp.tool()
    def analyze_lut(cube_path: str) -> dict[str, Any]:
        """Run technical ramp/sample analysis; this is not an artistic score."""
        return analyze_lut_file(Path(cube_path).expanduser().resolve())

    @mcp.tool()
    def compare_grade_captures(
        before_path: str, after_path: str
    ) -> dict[str, Any]:
        """Measure bounded technical differences between two exported captures."""
        return compare_captures(
            Path(before_path).expanduser().resolve(),
            Path(after_path).expanduser().resolve(),
        )

    @mcp.tool()
    def validate_applied_lut(
        before_path: str, after_path: str
    ) -> dict[str, Any]:
        """Reject a visible no-op and report warnings for an applied LUT."""
        return compare_captures(
            Path(before_path).expanduser().resolve(),
            Path(after_path).expanduser().resolve(),
        )

    @mcp.tool()
    def list_luts() -> list[dict[str, Any]]:
        """List registered LUT profiles and approval/install state."""
        return services.lut_registry.list()

    @mcp.tool()
    def set_lut_registry_state(
        profile_name: str, state: str
    ) -> dict[str, Any]:
        """Enable, disable, or deprecate a registered LUT."""
        if state not in {"enabled", "disabled", "deprecated"}:
            raise ValueError("state must be enabled, disabled, or deprecated")
        return services.lut_registry.set_state(profile_name, state)  # type: ignore[arg-type]

    @mcp.tool()
    def install_lut(profile_name: str, dry_run: bool = False) -> dict[str, Any]:
        """Atomically install a registered LUT under DavinciMCP/Generated."""
        entry = services.lut_registry.get(profile_name)
        result = services.lut_installer.install(
            Path(entry.file_path), entry.sha256, dry_run=dry_run
        )
        if not dry_run:
            result.update(services.lut_installer.refresh(services.connection.project()))
            services.lut_registry.set_installed_path(
                profile_name, result["resolve_path"]
            )
        return result

    @mcp.tool()
    def prepare_lut_for_locked_timeline_item(
        profile_name: str,
        lut_identifier: str,
        backup_drx_path: str,
        bootstrap_empty_node_drx_path: str | None = None,
    ) -> dict[str, Any]:
        """Create a disposable owned local version after lock/hash/backup validation."""
        return services.lut_applications.prepare(
            profile_name,
            lut_identifier,
            backup_drx_path,
            bootstrap_empty_node_drx_path,
        )

    @mcp.tool()
    def apply_lut_to_locked_timeline_item() -> dict[str, Any]:
        """Apply the prepared LUT to the identity-locked disposable version."""
        return services.lut_applications.apply()

    @mcp.tool()
    def restore_locked_timeline_item_grade() -> dict[str, Any]:
        """Load the original version and delete the disposable LUT version."""
        return services.lut_applications.restore()
