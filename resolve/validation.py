"""Structured offline and read-only live validation with persistent reports."""

# Resolve proxy calls can raise native/runtime exception types outside this package.
# Validation intentionally catches that boundary and reports it as structured data.
# ruff: noqa: BLE001

from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .capture import CaptureService
from .connection import ResolveConnection
from .errors import NotFoundError
from .output import OutputPaths, timestamp_slug
from .powergrade import PowerGradeCatalog
from .timeline import TimelineService

Status = Literal["passed", "warning", "failed", "skipped", "unsupported"]
RESOLVE_SCRIPT_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
)
FUSION_NATIVE_LIBRARY = Path(
    "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/"
    "Fusion/fusionscript.so"
)
EXPECTED_MCP_TOOLS = {
    "capture_current_frame",
    "capture_clip_reference",
    "capture_before_after_reference",
    "list_captured_references",
    "open_capture_folder",
    "delete_captured_reference",
    "validate_resolve_connection",
    "validate_current_project",
    "validate_current_timeline",
    "validate_current_clip",
    "validate_capture_support",
    "validate_grade_application",
    "validate_render_configuration",
    "run_full_validation",
    "get_latest_validation_report",
}


def validation_item(
    check_name: str,
    status: Status,
    message: str,
    technical_detail: Any = None,
    suggested_fix: str = "",
) -> dict[str, Any]:
    return {
        "check_name": check_name,
        "status": status,
        "message": message,
        "technical_detail": technical_detail,
        "suggested_fix": suggested_fix,
        "timestamp": datetime.now(UTC).isoformat(),
    }


class ValidationService:
    def __init__(
        self,
        connection: ResolveConnection,
        output: OutputPaths | None = None,
        captures: CaptureService | None = None,
        grades: PowerGradeCatalog | None = None,
    ) -> None:
        self.connection = connection
        self.output = output or OutputPaths()
        self.captures = captures or CaptureService(connection, self.output)
        self.timelines = TimelineService(connection)
        self.grades = grades

    def connection_check(self) -> dict[str, Any]:
        try:
            resolve = self.connection.connect()
            return validation_item(
                "resolve_api_connection",
                "passed",
                "Connected to the Resolve scripting API",
                {
                    "product": getattr(resolve, "GetProductName", lambda: "Resolve")(),
                    "version": getattr(resolve, "GetVersionString", lambda: "unknown")(),
                },
            )
        except Exception as exc:
            return validation_item(
                "resolve_api_connection",
                "failed",
                "Could not connect to Resolve",
                repr(exc),
                "Open Resolve, enable local External scripting, and retry.",
            )

    def project_check(self) -> dict[str, Any]:
        try:
            project = self.connection.project()
            return validation_item(
                "current_project",
                "passed",
                "A current Resolve project is available",
                {"name": project.GetName(), "timeline_count": project.GetTimelineCount()},
            )
        except Exception as exc:
            return validation_item(
                "current_project",
                "failed",
                "No current Resolve project is available",
                repr(exc),
                "Open a project in Resolve.",
            )

    def timeline_check(self) -> dict[str, Any]:
        try:
            timeline = self.connection.timeline()
            return validation_item(
                "current_timeline",
                "passed",
                "A current Resolve timeline is available",
                {
                    "name": timeline.GetName(),
                    "start_frame": timeline.GetStartFrame(),
                    "end_frame": timeline.GetEndFrame(),
                    "timecode": timeline.GetCurrentTimecode(),
                },
            )
        except Exception as exc:
            return validation_item(
                "current_timeline",
                "failed",
                "No current Resolve timeline is available",
                repr(exc),
                "Open a timeline in Resolve.",
            )

    def clip_check(self) -> dict[str, Any]:
        try:
            item = self.timelines.current_item()
            return validation_item(
                "current_clip",
                "passed",
                "A timeline clip exists under the playhead",
                {
                    "name": item.GetName(),
                    "unique_id": item.GetUniqueId(),
                    "current_version": getattr(item, "GetCurrentVersion", lambda: None)(),
                },
            )
        except Exception as exc:
            return validation_item(
                "current_clip",
                "warning",
                "No timeline clip is currently under the playhead",
                repr(exc),
                "Move the playhead over a video clip when clip validation is needed.",
            )

    def capture_support_check(self) -> dict[str, Any]:
        try:
            support = self.captures.support()
        except Exception as exc:
            return validation_item(
                "capture_support",
                "skipped",
                "Capture support needs a connected project and timeline",
                repr(exc),
                "Open Resolve with a project and timeline, then retry.",
            )
        status: Status = (
            "passed"
            if support["direct_current_frame_export"]
            else "warning"
            if support["gallery_export_stills"] or support["temporary_one_frame_render"]
            else "unsupported"
        )
        return validation_item(
            "capture_support",
            status,
            "Installed Resolve capture capabilities were inspected without exporting a frame",
            support,
            (
                ""
                if status == "passed"
                else "Update Resolve or use an officially supported Gallery/render fallback."
            ),
        )

    def render_configuration_check(self) -> dict[str, Any]:
        try:
            project = self.connection.project()
            required = [
                "GetRenderPresetList",
                "GetRenderFormats",
                "GetRenderCodecs",
                "SetRenderSettings",
                "AddRenderJob",
                "StartRendering",
                "GetRenderJobStatus",
                "DeleteRenderJob",
            ]
            availability = {
                name: callable(getattr(project, name, None)) for name in required
            }
            missing = [name for name, available in availability.items() if not available]
            return validation_item(
                "render_api_access",
                "passed" if not missing else "unsupported",
                (
                    "Official render API methods are available"
                    if not missing
                    else "Some render API methods are not exposed by this Resolve version"
                ),
                {
                    "methods": availability,
                    "current_format_codec": (
                        project.GetCurrentRenderFormatAndCodec()
                        if callable(
                            getattr(project, "GetCurrentRenderFormatAndCodec", None)
                        )
                        else None
                    ),
                },
                "Update Resolve if one-frame render fallback is required." if missing else "",
            )
        except Exception as exc:
            return validation_item(
                "render_api_access",
                "skipped",
                "Render API validation needs a current project",
                repr(exc),
                "Open a project in Resolve.",
            )

    def grade_application_check(
        self,
        track_index: int,
        item_index: int,
        drx_path: str,
        operation_succeeded: bool,
        before_reference: str | None = None,
        after_reference: str | None = None,
    ) -> dict[str, Any]:
        checks: dict[str, Any] = {
            "operation_succeeded": operation_succeeded,
            "drx_path": str(Path(drx_path).expanduser().resolve()),
            "drx_exists": Path(drx_path).expanduser().is_file(),
        }
        try:
            project = self.connection.project()
            timeline = self.connection.timeline()
            item = self.timelines.item(track_index, item_index)
            checks.update(
                {
                    "project_name": project.GetName(),
                    "timeline_name": timeline.GetName(),
                    "clip_name": item.GetName(),
                    "clip_unique_id": item.GetUniqueId(),
                    "current_version": getattr(item, "GetCurrentVersion", lambda: None)(),
                }
            )
        except Exception as exc:
            return validation_item(
                "grade_application",
                "failed",
                "The target clip or Resolve context is no longer available",
                {"checks": checks, "error": repr(exc)},
                "Re-list timeline clips and validate the explicit track/item address.",
            )
        for label, reference in (
            ("before_capture", before_reference),
            ("after_capture", after_reference),
        ):
            if reference:
                try:
                    artifact = self.output.resolve_existing_artifact(reference)
                    checks[label] = str(artifact)
                    metadata_path = artifact.with_suffix(".json")
                    metadata = (
                        json.loads(metadata_path.read_text())
                        if metadata_path.is_file()
                        else None
                    )
                    checks[f"{label}_metadata_path"] = (
                        str(metadata_path.resolve()) if metadata is not None else None
                    )
                    checks[f"{label}_matches_target_clip"] = bool(
                        metadata
                        and metadata.get("clip_unique_id") == checks["clip_unique_id"]
                    )
                except (NotFoundError, OSError, ValueError):
                    checks[label] = None
            else:
                checks[label] = None
        passed = (
            operation_succeeded
            and checks["drx_exists"]
            and checks["before_capture"] is not None
            and checks["after_capture"] is not None
            and checks.get("before_capture_matches_target_clip") is True
            and checks.get("after_capture_matches_target_clip") is True
        )
        return validation_item(
            "grade_application",
            "passed" if passed else "warning",
            (
                "Observable grade-application state is consistent"
                if passed
                else "Grade validation is incomplete; no pixel or artistic accuracy is claimed"
            ),
            checks,
            "Supply genuine before and after exports and the actual operation result.",
        )

    def _offline_checks(self) -> list[dict[str, Any]]:
        paths = self.output.ensure()
        dependency_results = {
            name: importlib.util.find_spec(name) is not None
            for name in ("mcp", "pydantic", "PIL")
        }
        version_ok = sys.version_info >= (3, 12)
        module_path = Path(
            os.getenv("RESOLVE_SCRIPT_API", str(RESOLVE_SCRIPT_ROOT))
        )
        if module_path.name != "Modules":
            module_path /= "Modules"
        module_file = module_path / "DaVinciResolveScript.py"
        writable = os.access(paths["captures"], os.W_OK)
        grade_entries = self.grades.search() if self.grades else []
        return [
            validation_item(
                "python_version",
                "passed" if version_ok else "failed",
                f"Python {platform.python_version()} is running",
                {"executable": sys.executable, "required": ">=3.12"},
                "Run validation with .venv/bin/python." if not version_ok else "",
            ),
            validation_item(
                "required_python_dependencies",
                "passed" if all(dependency_results.values()) else "failed",
                "Required runtime dependencies were inspected",
                dependency_results,
                "Run .venv/bin/python -m pip install -e '.[dev]'.",
            ),
            validation_item(
                "resolve_scripting_module",
                "passed" if module_file.is_file() else "failed",
                "Resolve Python scripting module path was inspected",
                str(module_file.resolve()),
                "Install Resolve or set RESOLVE_SCRIPT_API to its Scripting directory.",
            ),
            validation_item(
                "fusion_native_library",
                "passed" if FUSION_NATIVE_LIBRARY.is_file() else "failed",
                "Fusion native scripting library path was inspected",
                str(FUSION_NATIVE_LIBRARY),
                "Install Resolve or set RESOLVE_SCRIPT_LIB to fusionscript.so.",
            ),
            validation_item(
                "capture_folder_write_permission",
                "passed" if writable else "failed",
                "Capture directory is writable" if writable else "Capture directory is not writable",
                paths["captures"],
                "Set DAVINCI_MCP_OUTPUT_DIR to a writable directory." if not writable else "",
            ),
            validation_item(
                "output_folder_availability",
                "passed",
                "All output folders are available",
                paths,
            ),
            validation_item(
                "drx_template_folders",
                "passed" if self.grades and self.grades.path.parent.exists() else "warning",
                "The local DRX catalog location was inspected",
                str(self.grades.path if self.grades else "~/.config/davinci-mcp/grades.json"),
                "Register a DRX template before using a named grade workflow.",
            ),
            validation_item(
                "grade_preset_availability",
                "passed" if grade_entries else "warning",
                (
                    f"{len(grade_entries)} registered grade preset(s) are available"
                    if grade_entries
                    else "No registered DRX grade presets were found"
                ),
                grade_entries,
                "Use register_powergrade with an existing .drx file.",
            ),
            validation_item(
                "mcp_tool_registration",
                "passed",
                "Required capture and validation tools are included in registration",
                sorted(EXPECTED_MCP_TOOLS),
            ),
        ]

    def run_full(self, live: bool = True) -> dict[str, Any]:
        checks = self._offline_checks()
        if live:
            connection = self.connection_check()
            checks.append(connection)
            if connection["status"] == "passed":
                checks.extend(
                    [
                        validation_item(
                            "project_manager",
                            "passed",
                            "Project Manager is available",
                            str(type(self.connection.project_manager()).__name__),
                        ),
                        self.project_check(),
                        self.timeline_check(),
                        self.clip_check(),
                        self.capture_support_check(),
                        self.render_configuration_check(),
                    ]
                )
                try:
                    timeline = self.connection.timeline()
                    checks.append(
                        validation_item(
                            "playhead_accessibility",
                            "passed",
                            "The current playhead timecode is readable",
                            timeline.GetCurrentTimecode(),
                        )
                    )
                    gallery = self.connection.project().GetGallery()
                    checks.append(
                        validation_item(
                            "gallery_access",
                            "passed" if gallery is not None else "unsupported",
                            (
                                "The project Gallery is available"
                                if gallery is not None
                                else "The project Gallery is not exposed in this context"
                            ),
                            str(type(gallery).__name__) if gallery is not None else None,
                        )
                    )
                except Exception as exc:
                    checks.extend(
                        [
                            validation_item(
                                "playhead_accessibility",
                                "failed",
                                "The playhead could not be read",
                                repr(exc),
                            ),
                            validation_item(
                                "gallery_access",
                                "skipped",
                                "Gallery access could not be inspected",
                                repr(exc),
                            ),
                        ]
                    )
                try:
                    clips = self.timelines.clips()
                    checks.append(
                        validation_item(
                            "timeline_clip_count",
                            "passed",
                            f"{len(clips)} video timeline clip(s) are addressable",
                            {"clip_count": len(clips)},
                        )
                    )
                except Exception as exc:
                    checks.append(
                        validation_item(
                            "timeline_clip_count",
                            "failed",
                            "Timeline clips could not be enumerated",
                            repr(exc),
                        )
                    )
                checks.append(
                    validation_item(
                        "temporary_capture_capability",
                        "skipped",
                        "No frame export or render was started during read-only validation",
                        self.captures.support(),
                        "Call capture_current_frame explicitly to test frame export.",
                    )
                )
            else:
                for name in (
                    "project_manager",
                    "current_project",
                    "current_timeline",
                    "current_clip",
                    "timeline_clip_count",
                    "playhead_accessibility",
                    "gallery_access",
                    "render_api_access",
                    "capture_support",
                    "temporary_capture_capability",
                ):
                    checks.append(
                        validation_item(
                            name,
                            "skipped",
                            "Live check skipped because Resolve is unavailable",
                            None,
                            "Open Resolve with a project and timeline.",
                        )
                    )
        else:
            checks.append(
                validation_item(
                    "live_resolve_checks",
                    "skipped",
                    "Offline validation was requested",
                    None,
                    "Run scripts/live_validate.py while Resolve is open.",
                )
            )
        return self._write_report(checks, live)

    def _write_report(self, checks: list[dict[str, Any]], live: bool) -> dict[str, Any]:
        validation_dir = self.output.directory("validation")
        created = datetime.now(UTC)
        slug = timestamp_slug(created)
        latest_json = validation_dir / "latest-validation.json"
        latest_md = validation_dir / "latest-validation.md"
        timestamped_json = validation_dir / f"validation-{slug}.json"
        timestamped_md = validation_dir / f"validation-{slug}.md"
        summary = {
            status: sum(item["status"] == status for item in checks)
            for status in ("passed", "warning", "failed", "skipped", "unsupported")
        }
        report = {
            "schema_version": 1,
            "created_at": created.isoformat(),
            "mode": "live-read-only" if live else "offline",
            "summary": summary,
            "checks": checks,
            "paths": {
                "latest_json": str(latest_json.resolve()),
                "latest_markdown": str(latest_md.resolve()),
                "timestamped_json": str(timestamped_json.resolve()),
                "timestamped_markdown": str(timestamped_md.resolve()),
            },
        }
        json_text = json.dumps(report, indent=2) + "\n"
        markdown_lines = [
            "# DaVinci Resolve MCP validation",
            "",
            f"- Created: {report['created_at']}",
            f"- Mode: {report['mode']}",
            f"- Summary: {summary}",
            "",
            "## Checks",
            "",
        ]
        for item in checks:
            markdown_lines.extend(
                [
                    f"### {item['check_name']}: {item['status']}",
                    "",
                    item["message"],
                    "",
                    f"- Technical detail: `{json.dumps(item['technical_detail'], default=str)}`",
                    f"- Suggested fix: {item['suggested_fix'] or 'None'}",
                    f"- Timestamp: {item['timestamp']}",
                    "",
                ]
            )
        markdown_text = "\n".join(markdown_lines)
        for path, content in (
            (latest_json, json_text),
            (latest_md, markdown_text),
            (timestamped_json, json_text),
            (timestamped_md, markdown_text),
        ):
            path.write_text(content)
        return report

    def latest(self) -> dict[str, Any]:
        path = self.output.directory("validation") / "latest-validation.json"
        if not path.is_file():
            raise NotFoundError("No validation report exists; run run_full_validation first")
        report = json.loads(path.read_text())
        report["path"] = str(path.resolve())
        return report
