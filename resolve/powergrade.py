"""Persistent DRX template catalog used for supported high-level looks."""

import json
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
        if not Path(template.drx_path).expanduser().is_file():
            raise ValidationError(f"DRX file does not exist: {template.drx_path}")
        entries = [item for item in self._read() if item.name != template.name]
        entries.append(template)
        self._write(entries)
        return {**template.model_dump(), "catalog_path": str(self.path.resolve())}

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
        template = next((item for item in self._read() if item.name == name), None)
        if template is None:
            raise NotFoundError(f"Grade template {name!r} was not registered")
        return self.color.apply_drx(
            track_index, item_index, template.drx_path, grade_mode
        )
