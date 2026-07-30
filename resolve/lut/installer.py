"""Platform-aware, conflict-safe installation under DavinciMCP/Generated."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

from resolve.errors import OperationError, ValidationError


def resolve_lut_root(system: str, home: Path, program_data: Path | None = None) -> Path:
    if system == "Darwin":
        return Path(
            "/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT"
        )
    if system == "Windows":
        root = program_data or Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        return root / "Blackmagic Design/DaVinci Resolve/Support/LUT"
    return home / ".local/share/DaVinciResolve/LUT"


class LutInstaller:
    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def generated_directory(self) -> Path:
        return self.root / "DavinciMCP" / "Generated"

    def install(self, source: Path, expected_sha256: str, *, dry_run: bool = False) -> dict[str, Any]:
        if not source.is_file():
            raise ValidationError(f"LUT source does not exist: {source}")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != expected_sha256:
            raise ValidationError("Source LUT SHA-256 does not match registry")
        destination = self.generated_directory / source.name
        resolve_path = f"DavinciMCP/Generated/{source.name}"
        if destination.exists():
            existing = hashlib.sha256(destination.read_bytes()).hexdigest()
            if existing != digest:
                raise ValidationError(
                    f"Refusing to overwrite different installed LUT: {destination}"
                )
            return {
                "status": "already_installed",
                "destination": str(destination),
                "resolve_path": resolve_path,
                "sha256": digest,
            }
        if dry_run:
            return {
                "status": "dry_run",
                "destination": str(destination),
                "resolve_path": resolve_path,
                "sha256": digest,
            }
        self.generated_directory.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        shutil.copy2(source, temporary)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
            temporary.unlink(missing_ok=True)
            raise OperationError("Atomic install copy failed SHA-256 verification")
        temporary.replace(destination)
        return {
            "status": "installed",
            "destination": str(destination),
            "resolve_path": resolve_path,
            "sha256": digest,
        }

    @staticmethod
    def refresh(project: Any) -> dict[str, Any]:
        result = bool(project.RefreshLUTList())
        if not result:
            raise OperationError("Project.RefreshLUTList returned false")
        return {"refresh_lut_list": True, "restart_required": False}
