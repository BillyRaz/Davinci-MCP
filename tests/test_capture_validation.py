"""Capture/output/validation tests using Resolve API fakes only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resolve.capture import CaptureService
from resolve.connection import resolve_module_path
from resolve.errors import CapabilityError, OperationError
from resolve.output import OUTPUT_SUBDIRECTORIES, OutputPaths, safe_filename
from resolve.validation import ValidationService


class FakeTimeline:
    def GetName(self) -> str:
        return "Timeline A"

    def GetUniqueId(self) -> str:
        return "timeline-1"

    def GetCurrentTimecode(self) -> str:
        return "01:00:00:12"

    def GetStartTimecode(self) -> str:
        return "01:00:00:00"

    def GetStartFrame(self) -> int:
        return 0

    def GetEndFrame(self) -> int:
        return 100

    def GetSetting(self, *_: object) -> dict[str, str]:
        return {"timelineFrameRate": "24"}

    def GrabStill(self) -> None:
        return None


class FakeGallery:
    def GetCurrentStillAlbum(self) -> None:
        return None


class FakeProject:
    def __init__(self, target_bytes: bytes = b"real-resolve-export") -> None:
        self.target_bytes = target_bytes

    def GetName(self) -> str:
        return "Project A"

    def GetSetting(self, *_: object) -> str:
        return "24"

    def GetGallery(self) -> FakeGallery:
        return FakeGallery()

    def ExportCurrentFrameAsStill(self, path: str) -> bool:
        Path(path).write_bytes(self.target_bytes)
        return True


class FakeConnection:
    def __init__(self, project: object | None = None) -> None:
        self.project_value = project or FakeProject()
        self.timeline_value = FakeTimeline()

    def project(self) -> object:
        return self.project_value

    def timeline(self) -> FakeTimeline:
        return self.timeline_value


def test_output_directory_creation(tmp_path: Path) -> None:
    paths = OutputPaths(tmp_path / "custom")
    created = paths.ensure()
    assert Path(created["root"]).is_dir()
    assert all((paths.root / name).is_dir() for name in OUTPUT_SUBDIRECTORIES)


def test_safe_filename_generation() -> None:
    assert safe_filename("../../My unsafe/frame?.png") == "frame"
    assert "/" not in safe_filename("Client / Final: 01")
    assert safe_filename("...") == "capture"


def test_capture_metadata_generation(tmp_path: Path) -> None:
    capture = CaptureService(
        FakeConnection(),  # type: ignore[arg-type]
        OutputPaths(tmp_path),
    )
    result = capture.capture_current("reference", "png")
    assert Path(result["image_path"]).read_bytes() == b"real-resolve-export"
    metadata = json.loads(Path(result["metadata_path"]).read_text())
    assert metadata["project_name"] == "Project A"
    assert metadata["timeline_name"] == "Timeline A"
    assert metadata["capture_method"] == "Project.ExportCurrentFrameAsStill"
    assert Path(metadata["image_path"]).is_absolute()


def test_unsupported_capture_handling(tmp_path: Path) -> None:
    class UnsupportedProject:
        def GetName(self) -> str:
            return "Project A"

        def GetSetting(self, *_: object) -> str:
            return "24"

    capture = CaptureService(
        FakeConnection(UnsupportedProject()),  # type: ignore[arg-type]
        OutputPaths(tmp_path),
    )
    with pytest.raises(CapabilityError, match="neither direct current-frame export"):
        capture.capture_current()


def test_gallery_capture_fallback_and_cleanup(tmp_path: Path) -> None:
    class Album:
        deleted = False

        def ExportStills(
            self, stills: list[object], folder: str, prefix: str, fmt: str
        ) -> bool:
            Path(folder, f"{prefix}.{fmt}").write_bytes(b"gallery-export")
            return bool(stills)

        def DeleteStills(self, stills: list[object]) -> bool:
            self.deleted = bool(stills)
            return True

    album = Album()

    class Gallery:
        def GetCurrentStillAlbum(self) -> Album:
            return album

    class Timeline(FakeTimeline):
        def GrabStill(self) -> object:
            return object()

    class Project:
        def GetName(self) -> str:
            return "Project A"

        def GetSetting(self, *_: object) -> str:
            return "24"

        def GetGallery(self) -> Gallery:
            return Gallery()

    connection = FakeConnection(Project())
    connection.timeline_value = Timeline()
    capture = CaptureService(connection, OutputPaths(tmp_path))  # type: ignore[arg-type]
    result = capture.capture_current("gallery-fallback")
    assert Path(result["image_path"]).read_bytes() == b"gallery-export"
    assert result["capture_method"].startswith("Timeline.GrabStill")
    assert album.deleted is True


def test_temporary_render_cleanup() -> None:
    class Project:
        deleted: str | None = None

        def DeleteRenderJob(self, job_id: str) -> bool:
            self.deleted = job_id
            return True

    project = Project()
    assert CaptureService.cleanup_temporary_render(project, "job-1") is True
    assert project.deleted == "job-1"
    assert CaptureService.cleanup_temporary_render(project, None) is True


def test_validation_report_generation(tmp_path: Path) -> None:
    paths = OutputPaths(tmp_path)
    service = ValidationService(
        FakeConnection(),  # type: ignore[arg-type]
        paths,
    )
    report = service.run_full(live=False)
    assert Path(report["paths"]["latest_json"]).is_file()
    assert Path(report["paths"]["latest_markdown"]).is_file()
    assert report["mode"] == "offline"
    assert service.latest()["path"] == report["paths"]["latest_json"]


def test_environment_variable_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    root = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
    monkeypatch.setenv("RESOLVE_SCRIPT_API", root)
    assert resolve_module_path() == Path(root) / "Modules"
    assert resolve_module_path(f"{root}/Modules") == Path(root) / "Modules"


def test_launcher_path_quoting_and_missing_venv_message() -> None:
    project = Path(__file__).parents[1]
    run_script = (project / "run-davinci-mcp.command").read_text()
    setup_script = (project / "setup-davinci-mcp.command").read_text()
    assert 'PROJECT_DIR="${0:A:h}"' in run_script
    assert '"$PYTHON_PATH" "$PROJECT_DIR/server.py"' in run_script
    assert "missing $PYTHON_PATH" in run_script
    assert '"$PROJECT_DIR/.venv/bin/python" -m pip install -e \'.[dev]\'' in setup_script


def test_missing_resolve_connection_behavior(tmp_path: Path) -> None:
    class MissingConnection:
        def connect(self) -> None:
            raise OperationError("Resolve closed")

    service = ValidationService(
        MissingConnection(),  # type: ignore[arg-type]
        OutputPaths(tmp_path),
    )
    result = service.connection_check()
    assert result["status"] == "failed"
    assert "Resolve closed" in result["technical_detail"]


def test_unsupported_gallery_api_behavior(tmp_path: Path) -> None:
    capture = CaptureService(
        FakeConnection(),  # type: ignore[arg-type]
        OutputPaths(tmp_path),
    )
    support = capture.support()
    assert support["gallery_export_stills"] is False
    assert support["gallery_delete_stills"] is False
    assert support["direct_current_frame_export"] is True


def test_before_after_metadata_consistency(tmp_path: Path) -> None:
    paths = OutputPaths(tmp_path)
    capture = CaptureService(
        FakeConnection(),  # type: ignore[arg-type]
        paths,
    )
    before = paths.directory("captures") / "before.png"
    after = paths.directory("captures") / "after.png"
    before.write_bytes(b"before-export")
    after.write_bytes(b"after-export")
    report = capture.compare(
        str(before), str(after), "validated", create_side_by_side=False
    )
    persisted = json.loads(Path(report["validation_report_path"]).read_text())
    assert Path(persisted["before_image_path"]).read_bytes() == b"before-export"
    assert Path(persisted["after_image_path"]).read_bytes() == b"after-export"
    assert persisted["before_source"] == str(before)
    assert persisted["after_source"] == str(after)
