"""JSON-backed production LUT registry with conflict protection."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from resolve.errors import NotFoundError, ValidationError

from .validator import validate_lut

ApprovalState = Literal["disabled", "enabled", "deprecated"]


class LutRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_name: str
    schema_version: int
    file_path: str
    metadata_path: str
    sha256: str
    cube_size: int
    input_color_space: str
    output_color_space: str
    generator_version: str
    validation_result: dict[str, Any]
    approval_state: ApprovalState = "disabled"
    installed_resolve_path: str | None = None
    creation_timestamp: str
    update_timestamp: str


class LutRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> list[LutRegistryEntry]:
        if not self.path.exists():
            return []
        return [
            LutRegistryEntry.model_validate(row)
            for row in json.loads(self.path.read_text())
        ]

    def _save(self, entries: list[LutRegistryEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([entry.model_dump() for entry in entries], indent=2) + "\n"
        )
        temporary.replace(self.path)

    def register(self, cube_path: Path, metadata_path: Path) -> dict[str, Any]:
        validation = validate_lut(cube_path, metadata_path, require_metadata=True)
        if not validation.valid:
            raise ValidationError("; ".join(validation.errors))
        metadata = json.loads(metadata_path.read_text())
        entries = self._load()
        name = metadata["profile_name"]
        digest = validation.details["sha256"]
        for entry in entries:
            if entry.profile_name == name and entry.sha256 == digest:
                return {"status": "already_registered", "entry": entry.model_dump()}
            if entry.profile_name == name:
                raise ValidationError(
                    f"Profile name/version conflict for {name}; use a new versioned name"
                )
            if entry.sha256 == digest:
                raise ValidationError(
                    f"Hash conflict: identical bytes already registered as {entry.profile_name}"
                )
        now = datetime.now(UTC).isoformat()
        entry = LutRegistryEntry(
            profile_name=name,
            schema_version=metadata["schema_version"],
            file_path=str(cube_path.resolve()),
            metadata_path=str(metadata_path.resolve()),
            sha256=digest,
            cube_size=metadata["cube_size"],
            input_color_space=metadata["input_color_space"],
            output_color_space=metadata["output_color_space"],
            generator_version=metadata["generator_version"],
            validation_result=validation.to_dict(),
            creation_timestamp=metadata["creation_timestamp"],
            update_timestamp=now,
        )
        entries.append(entry)
        self._save(entries)
        return {"status": "registered", "entry": entry.model_dump()}

    def list(self) -> list[dict[str, Any]]:
        return [entry.model_dump() for entry in self._load()]

    def get(self, name: str) -> LutRegistryEntry:
        matches = [entry for entry in self._load() if entry.profile_name == name]
        if len(matches) != 1:
            raise NotFoundError(f"Registered LUT not found: {name}")
        return matches[0]

    def set_state(self, name: str, state: ApprovalState) -> dict[str, Any]:
        entries = self._load()
        found = False
        for entry in entries:
            if entry.profile_name == name:
                entry.approval_state = state
                entry.update_timestamp = datetime.now(UTC).isoformat()
                found = True
        if not found:
            raise NotFoundError(f"Registered LUT not found: {name}")
        self._save(entries)
        return self.get(name).model_dump()

    def set_installed_path(self, name: str, path: str) -> dict[str, Any]:
        entries = self._load()
        for entry in entries:
            if entry.profile_name == name:
                entry.installed_resolve_path = path
                entry.update_timestamp = datetime.now(UTC).isoformat()
                self._save(entries)
                return entry.model_dump()
        raise NotFoundError(f"Registered LUT not found: {name}")
