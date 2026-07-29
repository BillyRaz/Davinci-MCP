"""Filesystem layout and safe artifact naming for generated MCP output."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from .config import load_config
from .errors import NotFoundError, ValidationError

OUTPUT_SUBDIRECTORIES = (
    "captures",
    "comparisons",
    "validation",
    "logs",
    "reports",
    "presets",
    "cache",
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def timestamp_slug(moment: datetime | None = None) -> str:
    return (moment or utc_now()).strftime("%Y%m%dT%H%M%S.%fZ")


def safe_filename(value: str | None, fallback: str = "capture") -> str:
    """Return a portable basename without allowing path traversal."""
    candidate = (value or fallback).strip()
    candidate = Path(candidate).stem
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate)
    candidate = re.sub(r"[-_.]{2,}", "-", candidate).strip("-._")
    if not candidate:
        candidate = fallback
    return candidate[:120]


class OutputPaths:
    def __init__(self, root: str | Path | None = None) -> None:
        configured = root or load_config().output_directory
        self.root = Path(configured).expanduser().resolve()

    def ensure(self) -> dict[str, str]:
        self.root.mkdir(parents=True, exist_ok=True)
        result = {"root": str(self.root)}
        for name in OUTPUT_SUBDIRECTORIES:
            path = self.root / name
            path.mkdir(parents=True, exist_ok=True)
            result[name] = str(path)
        return result

    def directory(self, name: str) -> Path:
        if name not in OUTPUT_SUBDIRECTORIES:
            raise ValidationError(f"Unknown output directory: {name}")
        self.ensure()
        return self.root / name

    def resolve_existing_artifact(self, reference: str) -> Path:
        requested = Path(reference).expanduser()
        candidates = [requested] if requested.is_absolute() else [
            self.directory("captures") / requested,
            self.directory("comparisons") / requested,
            self.directory("validation") / requested,
            self.directory("reports") / requested,
        ]
        for candidate in candidates:
            resolved = candidate.resolve()
            try:
                resolved.relative_to(self.root)
            except ValueError:
                continue
            if resolved.is_file():
                return resolved
        raise NotFoundError(f"Generated artifact was not found under {self.root}: {reference}")
