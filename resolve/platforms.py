"""Centralized, typed cross-platform discovery for Resolve MCP."""

from __future__ import annotations

import os
import platform
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PlatformName = Literal["Windows", "Darwin", "Linux", "Unknown"]


@dataclass(frozen=True)
class PlatformInfo:
    system: PlatformName
    architecture: str
    python_executable: Path
    home_directory: Path
    temporary_directory: Path
    launcher_type: str


@dataclass(frozen=True)
class ResolveInstallation:
    home: Path | None
    executable: Path | None
    scripting_root: Path | None
    modules_directory: Path | None
    native_library: Path | None
    edition: str
    discovery_source: str


@dataclass(frozen=True)
class PlatformPaths:
    info: PlatformInfo
    resolve: ResolveInstallation
    configuration_directory: Path
    configuration_file: Path
    output_directory: Path
    virtual_environment_python: Path
    legacy_output_directory: Path | None = None


def _first_existing(
    candidates: list[Path], exists: Callable[[Path], bool]
) -> Path | None:
    return next((candidate for candidate in candidates if exists(candidate)), None)


def _script_paths(value: str | Path | None) -> tuple[Path | None, Path | None]:
    if not value:
        return None, None
    configured = Path(value).expanduser()
    if configured.name.casefold() == "modules":
        return configured.parent, configured
    return configured, configured / "Modules"


def _windows_program_files(env: Mapping[str, str], home: Path) -> list[Path]:
    values = [
        env.get("ProgramFiles"),
        env.get("PROGRAMFILES"),
        env.get("ProgramW6432"),
        env.get("ProgramFiles(x86)"),
    ]
    roots = [Path(value) for value in values if value]
    if not roots:
        drive = home.drive or Path(env.get("USERPROFILE", str(home))).drive
        if drive:
            roots.append(Path(f"{drive}/Program Files"))
    return list(dict.fromkeys(roots))


def _discover_windows(
    env: Mapping[str, str],
    home: Path,
    exists: Callable[[Path], bool],
) -> ResolveInstallation:
    explicit_home = env.get("DAVINCI_RESOLVE_HOME")
    roots = _windows_program_files(env, home)
    homes = [
        root / "Blackmagic Design" / product
        for root in roots
        for product in ("DaVinci Resolve Studio", "DaVinci Resolve")
    ]
    home_path = Path(explicit_home).expanduser() if explicit_home else _first_existing(
        homes, exists
    )
    if home_path is None and homes:
        home_path = homes[-1]

    program_data = env.get("ProgramData") or env.get("PROGRAMDATA")
    known_script_root = (
        Path(program_data)
        / "Blackmagic Design"
        / "DaVinci Resolve"
        / "Support"
        / "Developer"
        / "Scripting"
        if program_data
        else None
    )
    script_override = env.get("RESOLVE_SCRIPT_API")
    script_root, modules = _script_paths(script_override or known_script_root)

    library_override = env.get("RESOLVE_SCRIPT_LIB")
    library_candidates = (
        [
            home_path / "fusionscript.dll",
            home_path / "Fusion" / "fusionscript.dll",
        ]
        if home_path
        else []
    )
    native_library = (
        Path(library_override).expanduser()
        if library_override
        else _first_existing(library_candidates, exists)
    )
    if native_library is None and library_candidates:
        native_library = library_candidates[0]

    executable = home_path / "Resolve.exe" if home_path else None
    edition = (
        "Studio"
        if home_path and "studio" in str(home_path).casefold()
        else "Unknown"
    )
    source = (
        "environment override"
        if explicit_home or script_override or library_override
        else "discovered installation"
        if any(
            path is not None and exists(path)
            for path in (home_path, script_root, native_library)
        )
        else "known platform default"
    )
    return ResolveInstallation(
        home_path,
        executable,
        script_root,
        modules,
        native_library,
        edition,
        source,
    )


def _discover_macos(
    env: Mapping[str, str], exists: Callable[[Path], bool]
) -> ResolveInstallation:
    explicit_home = env.get("DAVINCI_RESOLVE_HOME")
    homes = [
        Path("/Applications/DaVinci Resolve/DaVinci Resolve.app"),
        Path("/Applications/DaVinci Resolve Studio/DaVinci Resolve.app"),
    ]
    home = Path(explicit_home).expanduser() if explicit_home else _first_existing(
        homes, exists
    )
    if home is None:
        home = homes[0]
    default_script = Path(
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
        "Developer/Scripting"
    )
    script_override = env.get("RESOLVE_SCRIPT_API")
    script_root, modules = _script_paths(script_override or default_script)
    library = (
        Path(env["RESOLVE_SCRIPT_LIB"]).expanduser()
        if env.get("RESOLVE_SCRIPT_LIB")
        else home / "Contents/Libraries/Fusion/fusionscript.so"
    )
    return ResolveInstallation(
        home,
        home / "Contents/MacOS/Resolve",
        script_root,
        modules,
        library,
        "Unknown",
        "environment override"
        if explicit_home or script_override or env.get("RESOLVE_SCRIPT_LIB")
        else "discovered installation"
        if exists(home)
        else "known platform default",
    )


def _discover_linux(
    env: Mapping[str, str], exists: Callable[[Path], bool]
) -> ResolveInstallation:
    explicit_home = env.get("DAVINCI_RESOLVE_HOME")
    candidates = [Path("/opt/resolve"), Path("/opt/resolve-studio")]
    home = Path(explicit_home).expanduser() if explicit_home else _first_existing(
        candidates, exists
    )
    if home is None:
        home = candidates[0]
    script_override = env.get("RESOLVE_SCRIPT_API")
    script_root, modules = _script_paths(
        script_override or home / "Developer/Scripting"
    )
    library_candidates = [
        home / "libs/Fusion/fusionscript.so",
        home / "libs/fusionscript.so",
    ]
    library = (
        Path(env["RESOLVE_SCRIPT_LIB"]).expanduser()
        if env.get("RESOLVE_SCRIPT_LIB")
        else _first_existing(library_candidates, exists) or library_candidates[0]
    )
    return ResolveInstallation(
        home,
        home / "bin/resolve",
        script_root,
        modules,
        library,
        "Unknown",
        "environment override"
        if explicit_home or script_override or env.get("RESOLVE_SCRIPT_LIB")
        else "discovered installation"
        if exists(home)
        else "known platform default",
    )


def detect_platform(
    *,
    system_name: str | None = None,
    architecture: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    project_root: Path | None = None,
    exists: Callable[[Path], bool] | None = None,
) -> PlatformPaths:
    """Discover runtime paths without importing the Resolve scripting module."""
    env = os.environ if environ is None else environ
    detected = system_name or platform.system()
    system: PlatformName = (
        detected if detected in {"Windows", "Darwin", "Linux"} else "Unknown"
    )
    home_path = Path(home or env.get("USERPROFILE") or Path.home()).expanduser()
    path_exists = exists or Path.exists
    root = project_root or Path(__file__).resolve().parents[1]

    if system == "Windows":
        installation = _discover_windows(env, home_path, path_exists)
        appdata = Path(env.get("APPDATA") or home_path / "AppData/Roaming")
        local = Path(env.get("LOCALAPPDATA") or home_path / "AppData/Local")
        config_dir = appdata / "DavinciMCP"
        output_dir = local / "DavinciMCP"
        venv_python = root / ".venv/Scripts/python.exe"
        launcher = "PowerShell"
        legacy = None
    elif system == "Darwin":
        installation = _discover_macos(env, path_exists)
        config_dir = home_path / "Library/Application Support/DavinciMCP"
        output_dir = config_dir
        venv_python = root / ".venv/bin/python"
        launcher = "macOS command"
        legacy = Path("/Applications/DaVinci Resolve/davinci-mcp/output")
    else:
        installation = _discover_linux(env, path_exists)
        config_dir = Path(
            env.get("XDG_CONFIG_HOME") or home_path / ".config"
        ) / "davinci-mcp"
        output_dir = Path(
            env.get("XDG_DATA_HOME") or home_path / ".local/share"
        ) / "DavinciMCP"
        venv_python = root / ".venv/bin/python"
        launcher = "POSIX shell"
        legacy = None

    output_override = env.get("DAVINCI_MCP_OUTPUT_DIR")
    if output_override:
        output_dir = Path(output_override).expanduser()
    return PlatformPaths(
        PlatformInfo(
            system,
            architecture or platform.machine(),
            Path(sys.executable),
            home_path,
            Path(tempfile.gettempdir()),
            launcher,
        ),
        installation,
        config_dir,
        config_dir / "config.toml",
        output_dir,
        venv_python,
        legacy,
    )


def discover_python_312(
    *,
    system_name: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[str, ...] | None:
    """Return the preferred Python 3.12 launcher command for setup scripts."""
    system = system_name or platform.system()
    if system == "Windows" and which("py"):
        return (str(which("py")), "-3.12")
    for candidate in ("python3.12", "python"):
        found = which(candidate)
        if found:
            return (str(found),)
    return None


def folder_open_command(
    folder: Path,
    *,
    system_name: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> list[str] | None:
    """Return the platform-native folder opener without executing it."""
    system = system_name or platform.system()
    if system == "Windows":
        executable = which("explorer") or "explorer.exe"
    elif system == "Darwin":
        executable = which("open") or "/usr/bin/open"
    else:
        executable = which("xdg-open")
        if not executable:
            return None
    return [str(executable), str(folder)]
