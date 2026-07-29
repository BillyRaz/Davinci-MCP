"""Cross-platform discovery and launcher tests; no Resolve installation required."""

from __future__ import annotations

from pathlib import Path

from resolve.config import load_config
from resolve.platforms import detect_platform, discover_python_312, folder_open_command


def test_windows_program_files_and_appdata_discovery(tmp_path: Path) -> None:
    program_files = tmp_path / "Alternate Drive/Program Files"
    resolve_home = program_files / "Blackmagic Design/DaVinci Resolve Studio"
    program_data = tmp_path / "ProgramData"
    existing = {
        resolve_home,
        resolve_home / "fusionscript.dll",
    }
    paths = detect_platform(
        system_name="Windows",
        architecture="AMD64",
        environ={
            "ProgramFiles": str(program_files),
            "ProgramData": str(program_data),
            "APPDATA": str(tmp_path / "Roaming"),
            "LOCALAPPDATA": str(tmp_path / "Local"),
            "USERPROFILE": str(tmp_path / "User"),
        },
        home=tmp_path / "User",
        project_root=tmp_path / "Davinci MCP",
        exists=lambda path: path in existing,
    )
    assert paths.resolve.home == resolve_home
    assert paths.resolve.edition == "Studio"
    assert paths.resolve.modules_directory == (
        program_data
        / "Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules"
    )
    assert paths.configuration_file == tmp_path / "Roaming/DavinciMCP/config.toml"
    assert paths.output_directory == tmp_path / "Local/DavinciMCP"
    assert "Davinci MCP" in str(paths.virtual_environment_python)


def test_windows_missing_program_files_is_clear(tmp_path: Path) -> None:
    paths = detect_platform(
        system_name="Windows",
        environ={"USERPROFILE": str(tmp_path)},
        home=tmp_path,
        project_root=tmp_path,
        exists=lambda _: False,
    )
    assert paths.resolve.home is None
    assert paths.resolve.executable is None
    assert paths.resolve.discovery_source == "known platform default"


def test_windows_environment_overrides_and_direct_modules(tmp_path: Path) -> None:
    modules = tmp_path / "Resolve API/MoDuLeS"
    library = tmp_path / "Resolve Home/fusionscript.dll"
    paths = detect_platform(
        system_name="Windows",
        environ={
            "USERPROFILE": str(tmp_path),
            "RESOLVE_SCRIPT_API": str(modules),
            "RESOLVE_SCRIPT_LIB": str(library),
            "DAVINCI_RESOLVE_HOME": str(tmp_path / "Resolve Studio"),
            "DAVINCI_MCP_OUTPUT_DIR": str(tmp_path / "Custom Output"),
        },
        home=tmp_path,
        project_root=tmp_path,
        exists=lambda _: False,
    )
    assert paths.resolve.scripting_root == modules.parent
    assert paths.resolve.modules_directory == modules
    assert paths.resolve.native_library == library
    assert paths.output_directory == tmp_path / "Custom Output"
    assert paths.resolve.discovery_source == "environment override"


def test_config_file_values_and_environment_priority(tmp_path: Path) -> None:
    paths = detect_platform(
        system_name="Linux",
        environ={"XDG_CONFIG_HOME": str(tmp_path / "config")},
        home=tmp_path,
        project_root=tmp_path,
        exists=lambda _: False,
    )
    paths.configuration_file.parent.mkdir(parents=True)
    paths.configuration_file.write_text(
        '[davinci_mcp]\noutput_directory = "/from/config"\n'
        'capture_format = "jpg"\n'
    )
    config = load_config(
        paths,
        {"DAVINCI_MCP_OUTPUT_DIR": str(tmp_path / "from env")},
    )
    assert config.output_directory == tmp_path / "from env"
    assert config.capture_format == "jpg"


def test_macos_and_linux_defaults(tmp_path: Path) -> None:
    mac = detect_platform(
        system_name="Darwin",
        environ={},
        home=tmp_path,
        project_root=tmp_path,
        exists=lambda _: False,
    )
    linux = detect_platform(
        system_name="Linux",
        environ={},
        home=tmp_path,
        project_root=tmp_path,
        exists=lambda _: False,
    )
    assert mac.output_directory == tmp_path / "Library/Application Support/DavinciMCP"
    assert mac.resolve.modules_directory.name == "Modules"
    assert linux.resolve.home == Path("/opt/resolve")
    assert linux.output_directory == tmp_path / ".local/share/DavinciMCP"


def test_python_launcher_discovery() -> None:
    found = {"py": "C:/Windows/py.exe", "python": "C:/Python/python.exe"}
    which = found.get
    assert discover_python_312(system_name="Windows", which=which) == (
        "C:/Windows/py.exe",
        "-3.12",
    )
    assert discover_python_312(system_name="Linux", which=which) == (
        "C:/Python/python.exe",
    )
    assert discover_python_312(system_name="Windows", which=lambda _: None) is None


def test_folder_open_commands_are_platform_specific(tmp_path: Path) -> None:
    assert folder_open_command(
        tmp_path, system_name="Windows", which=lambda _: None
    ) == ["explorer.exe", str(tmp_path)]
    assert folder_open_command(
        tmp_path, system_name="Darwin", which=lambda _: None
    ) == ["/usr/bin/open", str(tmp_path)]
    assert (
        folder_open_command(tmp_path, system_name="Linux", which=lambda _: None)
        is None
    )


def test_windows_launchers_quote_paths_and_forward_safely() -> None:
    root = Path(__file__).parents[1]
    run = (root / "run-davinci-mcp.ps1").read_text()
    setup = (root / "setup-davinci-mcp.ps1").read_text()
    wrapper = (root / "run-davinci-mcp.cmd").read_text()
    assert "$PSScriptRoot" in run
    assert "Join-Path $ProjectDir" in run
    assert "Missing $VenvPython" in run
    assert '& $Python @PythonPrefix -m venv' in setup
    assert 'pip install -e ".[dev]"' in setup
    assert '-File "%~dp0run-davinci-mcp.ps1" %*' in wrapper
    assert "execution policy" not in run.casefold()
