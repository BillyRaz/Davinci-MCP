"""TOML-backed user configuration with environment-variable overrides."""

from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .platforms import PlatformPaths, detect_platform


@dataclass(frozen=True)
class AppConfig:
    config_file: Path
    script_api_path: Path | None
    script_library_path: Path | None
    output_directory: Path
    preset_directory: Path
    log_level: str
    connection_mode: str
    capture_format: str
    temporary_render_directory: Path
    connection_timeout_seconds: float
    render_timeout_seconds: float


def _path(value: Any, fallback: Path | None = None) -> Path | None:
    return Path(str(value)).expanduser() if value not in (None, "") else fallback


def load_config(
    paths: PlatformPaths | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    env = os.environ if environ is None else environ
    platform_paths = paths or detect_platform(environ=env)
    values: dict[str, Any] = {}
    if platform_paths.configuration_file.is_file():
        with platform_paths.configuration_file.open("rb") as stream:
            document = tomllib.load(stream)
        values = document.get("davinci_mcp", document)

    output = _path(
        env.get("DAVINCI_MCP_OUTPUT_DIR") or values.get("output_directory"),
        platform_paths.output_directory,
    )
    assert output is not None
    presets = _path(
        env.get("DAVINCI_MCP_PRESET_DIR") or values.get("preset_directory"),
        output / "presets",
    )
    temporary = _path(
        env.get("DAVINCI_MCP_TEMP_RENDER_DIR")
        or values.get("temporary_render_directory"),
        output / "cache" / "temporary-renders",
    )
    assert presets is not None and temporary is not None
    return AppConfig(
        platform_paths.configuration_file,
        _path(
            env.get("RESOLVE_SCRIPT_API") or values.get("script_api_path"),
            platform_paths.resolve.scripting_root,
        ),
        _path(
            env.get("RESOLVE_SCRIPT_LIB") or values.get("script_library_path"),
            platform_paths.resolve.native_library,
        ),
        output,
        presets,
        str(env.get("DAVINCI_MCP_LOG_LEVEL") or values.get("log_level") or "INFO"),
        str(
            env.get("DAVINCI_MCP_CONNECTION_MODE")
            or values.get("connection_mode")
            or "external"
        ),
        str(
            env.get("DAVINCI_MCP_CAPTURE_FORMAT")
            or values.get("capture_format")
            or "png"
        ),
        temporary,
        float(
            env.get("DAVINCI_MCP_CONNECTION_TIMEOUT")
            or values.get("connection_timeout_seconds")
            or 10
        ),
        float(
            env.get("DAVINCI_MCP_RENDER_TIMEOUT")
            or values.get("render_timeout_seconds")
            or 120
        ),
    )


def default_config_text(paths: PlatformPaths | None = None) -> str:
    config = load_config(paths=paths, environ={})

    def quote(value: object) -> str:
        return json.dumps(str(value), ensure_ascii=False)

    return (
        "[davinci_mcp]\n"
        f"script_api_path = {quote(config.script_api_path or '')}\n"
        f"script_library_path = {quote(config.script_library_path or '')}\n"
        f"output_directory = {quote(config.output_directory)}\n"
        f"preset_directory = {quote(config.preset_directory)}\n"
        'log_level = "INFO"\n'
        'connection_mode = "external"\n'
        'capture_format = "png"\n'
        f"temporary_render_directory = {quote(config.temporary_render_directory)}\n"
        "connection_timeout_seconds = 10\n"
        "render_timeout_seconds = 120\n"
    )


def create_default_config(
    paths: PlatformPaths | None = None, *, overwrite: bool = False
) -> Path:
    platform_paths = paths or detect_platform()
    destination = platform_paths.configuration_file
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or overwrite:
        destination.write_text(default_config_text(platform_paths), encoding="utf-8")
    return destination.resolve()
