"""Lazy, thread-safe loading of Blackmagic's official scripting module."""

import importlib
import os
import sys
import threading
from pathlib import Path
from typing import Any

from .errors import ConnectionError
from .utils import require

DEFAULT_MODULE_PATH = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Developer/Scripting/Modules"
)


def resolve_module_path(value: str | None = None) -> Path:
    """Accept Blackmagic's official Scripting root or the final Modules directory."""
    configured = Path(
        value
        or os.getenv("RESOLVE_SCRIPT_API")
        or DEFAULT_MODULE_PATH
    ).expanduser()
    return configured if configured.name == "Modules" else configured / "Modules"


class ResolveConnection:
    """Owns a lazy Resolve handle without importing Resolve at server startup."""

    def __init__(self, module_path: str | None = None) -> None:
        self.module_path = resolve_module_path(module_path)
        self._resolve: Any = None
        self._lock = threading.RLock()

    def connect(self, force: bool = False) -> Any:
        with self._lock:
            if self._resolve is not None and not force:
                return self._resolve
            if str(self.module_path) not in sys.path:
                sys.path.insert(0, str(self.module_path))
            try:
                module = importlib.import_module("DaVinciResolveScript")
                resolve = module.scriptapp("Resolve")
            except Exception as exc:
                raise ConnectionError(
                    "Could not load the official DaVinciResolveScript module. "
                    "Open Resolve Studio and enable External scripting in Preferences."
                ) from exc
            if resolve is None:
                raise ConnectionError(
                    "Resolve did not return a scripting handle. Ensure Resolve Studio is running "
                    "and Preferences > System > General > External scripting is enabled."
                )
            self._resolve = resolve
            return resolve

    def project_manager(self) -> Any:
        return require(self.connect().GetProjectManager(), "Project manager is unavailable")

    def project(self) -> Any:
        return require(
            self.project_manager().GetCurrentProject(),
            "No project is currently open",
        )

    def timeline(self) -> Any:
        return require(self.project().GetCurrentTimeline(), "No timeline is currently open")

    def status(self) -> dict[str, Any]:
        resolve = self.connect()
        product = getattr(resolve, "GetProductName", lambda: "DaVinci Resolve")()
        version = getattr(resolve, "GetVersionString", lambda: "unknown")()
        project = self.project_manager().GetCurrentProject()
        timeline = project.GetCurrentTimeline() if project else None
        return {
            "product": product,
            "version": version,
            "project": project.GetName() if project else None,
            "timeline": timeline.GetName() if timeline else None,
        }
