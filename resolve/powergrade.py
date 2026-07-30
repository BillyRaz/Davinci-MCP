"""Persistent DRX template catalog used for supported high-level looks."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .color import ColorService
from .config import load_config
from .errors import NotFoundError, ValidationError
from .models import GradeTemplate


class PowerGradeCatalog:
    def __init__(self, color: ColorService, catalog_path: str | None = None) -> None:
        self.color = color
        self.path = (
            Path(catalog_path).expanduser()
            if catalog_path
            else load_config().preset_directory / "grades.json"
        )

    def _read(self) -> list[GradeTemplate]:
        if not self.path.exists():
            return []
        try:
            return [GradeTemplate.model_validate(item) for item in json.loads(self.path.read_text())]
        except (OSError, ValueError) as exc:
            raise ValidationError(f"Invalid PowerGrade catalog {self.path}: {exc}") from exc

    def _write(self, entries: list[GradeTemplate]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([entry.model_dump() for entry in entries], indent=2) + "\n"
        )

    def register(self, template: GradeTemplate) -> dict[str, Any]:
        path = Path(template.drx_path).expanduser().resolve()
        if not path.is_file():
            raise ValidationError(f"DRX file does not exist: {template.drx_path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if template.sha256 and template.sha256 != digest:
            raise ValidationError(
                f"DRX SHA-256 mismatch: expected {template.sha256}, found {digest}"
            )
        template = template.model_copy(
            update={"drx_path": str(path), "sha256": digest}
        )
        entries = [item for item in self._read() if item.name != template.name]
        entries.append(template)
        self._write(entries)
        return {**template.model_dump(), "catalog_path": str(self.path.resolve())}

    def get(self, name: str) -> GradeTemplate:
        template = next((item for item in self._read() if item.name == name), None)
        if template is None:
            raise NotFoundError(f"Grade template {name!r} was not registered")
        return template

    def validate(
        self, name: str, resolve_version: str | None = None
    ) -> dict[str, Any]:
        template = self.get(name)
        path = Path(template.drx_path)
        if not path.is_file():
            raise ValidationError(f"Registered DRX file is missing: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if not template.sha256 or digest != template.sha256:
            raise ValidationError(
                f"Registered DRX hash changed: expected {template.sha256}, found {digest}"
            )
        compatible = (
            not template.compatible_resolve_version
            or not resolve_version
            or resolve_version.startswith(template.compatible_resolve_version)
        )
        if not compatible:
            raise ValidationError(
                "DRX Resolve compatibility mismatch: "
                f"template={template.compatible_resolve_version}, live={resolve_version}"
            )
        return {
            **template.model_dump(),
            "file_exists": True,
            "hash_valid": True,
            "resolve_version_compatible": compatible,
        }

    def set_validation(self, name: str, status: str) -> dict[str, Any]:
        if status not in {"unvalidated", "validated", "failed"}:
            raise ValidationError(f"Unsupported validation status: {status}")
        entries = self._read()
        template = next((item for item in entries if item.name == name), None)
        if template is None:
            raise NotFoundError(f"Grade template {name!r} was not registered")
        updated = template.model_copy(
            update={
                "validation_status": status,
                "validated_at": (
                    datetime.now(UTC).isoformat()
                    if status in {"validated", "failed"}
                    else None
                ),
            }
        )
        self._write([updated if item.name == name else item for item in entries])
        return updated.model_dump()

    def search(self, query: str = "", category: str | None = None) -> list[dict[str, Any]]:
        needle = query.casefold()
        return [
            item.model_dump()
            for item in self._read()
            if (not needle or needle in f"{item.name} {item.description}".casefold())
            and (category is None or item.category == category)
        ]

    def apply(
        self, name: str, track_index: int, item_index: int, grade_mode: int = 0
    ) -> dict[str, Any]:
        template = self.get(name)
        self.validate(name)
        return self.color.apply_drx(
            track_index, item_index, template.drx_path, grade_mode
        )
