"""Reference-frame export using only documented Resolve and filesystem APIs."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .connection import ResolveConnection
from .errors import CapabilityError, NotFoundError, OperationError, ValidationError
from .output import OutputPaths, safe_filename, timestamp_slug
from .platforms import folder_open_command
from .timeline import TimelineService

ImageFormat = Literal["png", "jpg"]
FrameStrategy = Literal["current", "first", "middle", "last", "custom"]


def timecode_to_frame(timecode: str, fps: float) -> int:
    """Convert Resolve timecode to a nominal frame number, including drop-frame syntax."""
    if fps <= 0:
        raise ValidationError(f"Invalid timeline frame rate: {fps}")
    drop = ";" in timecode
    parts = timecode.replace(";", ":").split(":")
    if len(parts) != 4:
        raise ValidationError(f"Unsupported Resolve timecode: {timecode!r}")
    hours, minutes, seconds, frames = (int(part) for part in parts)
    nominal = round(fps)
    total = ((hours * 60 + minutes) * 60 + seconds) * nominal + frames
    if drop:
        dropped = 2 if nominal == 30 else 4 if nominal == 60 else 0
        if dropped:
            total -= dropped * ((hours * 60 + minutes) - (hours * 6))
    return total


def frame_to_timecode(frame: int, fps: float, drop: bool = False) -> str:
    if frame < 0 or fps <= 0:
        raise ValidationError("Frame and frame rate must be non-negative")
    nominal = round(fps)
    separator = ";" if drop else ":"
    if drop and nominal in (30, 60):
        drop_frames = 2 if nominal == 30 else 4
        frames_per_10_minutes = nominal * 600 - drop_frames * 9
        ten_minute_chunks, remainder = divmod(frame, frames_per_10_minutes)
        dropped = drop_frames * 9 * ten_minute_chunks
        if remainder >= drop_frames:
            dropped += drop_frames * ((remainder - drop_frames) // (nominal * 60 - drop_frames))
        frame += dropped
    frames = frame % nominal
    total_seconds = frame // nominal
    seconds = total_seconds % 60
    minutes = (total_seconds // 60) % 60
    hours = (total_seconds // 3600) % 24
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{frames:02d}"


class CaptureService:
    def __init__(
        self,
        connection: ResolveConnection,
        output: OutputPaths | None = None,
    ) -> None:
        self.connection = connection
        self.output = output or OutputPaths()
        self.timelines = TimelineService(connection)

    @staticmethod
    def _format(value: str) -> ImageFormat:
        normalized = value.lower()
        if normalized not in {"png", "jpg"}:
            raise ValidationError("output_format must be 'png' or 'jpg'")
        return normalized  # type: ignore[return-value]

    def support(self) -> dict[str, Any]:
        project = self.connection.project()
        timeline = self.connection.timeline()
        gallery = project.GetGallery()
        album = gallery.GetCurrentStillAlbum() if gallery else None
        return {
            "direct_current_frame_export": callable(
                getattr(project, "ExportCurrentFrameAsStill", None)
            ),
            "gallery_grab_still": callable(getattr(timeline, "GrabStill", None)),
            "gallery_export_stills": bool(
                album and callable(getattr(album, "ExportStills", None))
            ),
            "gallery_delete_stills": bool(
                album and callable(getattr(album, "DeleteStills", None))
            ),
            "temporary_one_frame_render": all(
                callable(getattr(project, name, None))
                for name in (
                    "SetRenderSettings",
                    "AddRenderJob",
                    "StartRendering",
                    "GetRenderJobStatus",
                    "DeleteRenderJob",
                )
            ),
            "preferred_method": "Project.ExportCurrentFrameAsStill",
        }

    def _context(self) -> dict[str, Any]:
        project = self.connection.project()
        timeline = self.connection.timeline()
        timecode = timeline.GetCurrentTimecode()
        settings = timeline.GetSetting() or {}
        fps_value = settings.get("timelineFrameRate") or project.GetSetting("timelineFrameRate")
        try:
            fps = float(fps_value)
        except (TypeError, ValueError):
            fps = 24.0
        return {
            "project_name": project.GetName(),
            "timeline_name": timeline.GetName(),
            "timecode": timecode,
            "frame": timecode_to_frame(timecode, fps),
            "timeline_frame_rate": fps,
            "timeline_unique_id": getattr(timeline, "GetUniqueId", lambda: None)(),
        }

    def _artifact_paths(
        self,
        output_name: str | None,
        output_format: ImageFormat,
        overwrite: bool,
    ) -> tuple[Path, Path]:
        stem = safe_filename(output_name, f"capture-{timestamp_slug()}")
        image = self.output.directory("captures") / f"{stem}.{output_format}"
        metadata = self.output.directory("captures") / f"{stem}.json"
        if not overwrite and (image.exists() or metadata.exists()):
            raise ValidationError(
                f"Capture already exists: {image}; pass overwrite=true or choose another name"
            )
        return image.resolve(), metadata.resolve()

    def capture_current(
        self,
        output_name: str | None = None,
        output_format: str = "png",
        include_metadata: bool = True,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        fmt = self._format(output_format)
        image_path, metadata_path = self._artifact_paths(output_name, fmt, overwrite)
        project = self.connection.project()
        exporter = getattr(project, "ExportCurrentFrameAsStill", None)
        context = self._context()
        captured_at = datetime.now(UTC).isoformat()
        capture_method = "Project.ExportCurrentFrameAsStill"
        if callable(exporter):
            if not exporter(str(image_path)):
                raise OperationError("Resolve rejected ExportCurrentFrameAsStill")
        else:
            capture_method = self._capture_with_gallery(image_path, fmt)
        if not image_path.is_file():
            raise OperationError(
                f"Resolve reported success but no image was created at {image_path}"
            )
        metadata = {
            "schema_version": 1,
            "capture_method": capture_method,
            "image_path": str(image_path),
            "metadata_path": str(metadata_path),
            "output_format": fmt,
            "date": captured_at,
            "project_name": context["project_name"],
            "timeline_name": context["timeline_name"],
            "timecode": context["timecode"],
            "frame": context["frame"],
            "extended_metadata_included": include_metadata,
        }
        if include_metadata:
            metadata.update(
                {
                    "timeline_frame_rate": context["timeline_frame_rate"],
                    "timeline_unique_id": context["timeline_unique_id"],
                }
            )
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
        return metadata

    def _capture_with_gallery(self, image_path: Path, fmt: ImageFormat) -> str:
        """Fallback to documented Timeline.GrabStill/Gallery ExportStills APIs."""
        project = self.connection.project()
        timeline = self.connection.timeline()
        get_gallery = getattr(project, "GetGallery", None)
        gallery = get_gallery() if callable(get_gallery) else None
        album = gallery.GetCurrentStillAlbum() if gallery else None
        grab = getattr(timeline, "GrabStill", None)
        export = getattr(album, "ExportStills", None)
        delete = getattr(album, "DeleteStills", None)
        if not (callable(grab) and callable(export)):
            raise CapabilityError(
                "The installed Resolve API exposes neither direct current-frame export nor "
                "a usable Gallery GrabStill/ExportStills workflow. A temporary render fallback "
                "is not started implicitly because it changes render configuration."
            )
        before = set(image_path.parent.iterdir())
        still = grab()
        if still is None:
            raise OperationError("Resolve could not grab a Gallery still from the current frame")
        try:
            if not export([still], str(image_path.parent), image_path.stem, fmt):
                raise OperationError("Resolve could not export the temporary Gallery still")
            created = [
                path
                for path in set(image_path.parent.iterdir()) - before
                if path.is_file() and path.suffix.lower() in {f".{fmt}", ".jpeg"}
            ]
            if image_path not in created:
                if len(created) != 1:
                    raise OperationError(
                        "Resolve exported the Gallery still but its output filename "
                        f"could not be identified in {image_path.parent}"
                    )
                created[0].replace(image_path)
        finally:
            if callable(delete) and not delete([still]):
                raise OperationError(
                    "Frame exported, but Resolve could not delete the temporary Gallery still"
                )
        return "Timeline.GrabStill + GalleryStillAlbum.ExportStills"

    def _find_clip(self, identifier: str) -> dict[str, Any]:
        matches = [
            clip
            for clip in self.timelines.clips()
            if clip["unique_id"] == identifier or clip["name"] == identifier
        ]
        if not matches:
            raise NotFoundError(f"Timeline clip was not found: {identifier!r}")
        if len(matches) > 1:
            raise ValidationError(
                f"Clip name {identifier!r} is ambiguous; use the Resolve unique_id"
            )
        return matches[0]

    def capture_clip(
        self,
        clip_identifier: str,
        frame_strategy: FrameStrategy = "middle",
        custom_frame: int | None = None,
        output_name: str | None = None,
        output_format: str = "png",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        clip = self._find_clip(clip_identifier)
        timeline = self.connection.timeline()
        original_timecode = timeline.GetCurrentTimecode()
        context = self._context()
        fps = context["timeline_frame_rate"]
        strategy_frames = {
            "first": int(clip["start"]),
            "middle": int((clip["start"] + clip["end"] - 1) // 2),
            "last": int(clip["end"] - 1),
        }
        if frame_strategy == "current":
            target_frame = context["frame"]
            if not (clip["start"] <= target_frame < clip["end"]):
                raise ValidationError("The current playhead is not within the requested clip")
        elif frame_strategy == "custom":
            if custom_frame is None:
                raise ValidationError("custom_frame is required for the custom strategy")
            target_frame = custom_frame
            if not (clip["start"] <= target_frame < clip["end"]):
                raise ValidationError(
                    f"custom_frame must be within [{clip['start']}, {clip['end'] - 1}]"
                )
        elif frame_strategy in strategy_frames:
            target_frame = strategy_frames[frame_strategy]
        else:
            raise ValidationError(f"Unsupported frame strategy: {frame_strategy}")
        start_tc_frames = timecode_to_frame(timeline.GetStartTimecode(), fps)
        timecode = frame_to_timecode(
            start_tc_frames + target_frame - int(timeline.GetStartFrame()),
            fps,
            ";" in timeline.GetStartTimecode(),
        )
        if timecode != original_timecode and not timeline.SetCurrentTimecode(timecode):
            raise OperationError(f"Resolve could not move the playhead to {timecode}")
        try:
            result = self.capture_current(
                output_name or f"{clip['name']}-{frame_strategy}-{timestamp_slug()}",
                output_format,
                True,
                overwrite,
            )
            result.update(
                {
                    "clip_identifier": clip_identifier,
                    "clip_name": clip["name"],
                    "clip_unique_id": clip["unique_id"],
                    "track_index": clip["track_index"],
                    "item_index": clip["item_index"],
                    "frame_strategy": frame_strategy,
                    "requested_frame": target_frame,
                }
            )
            Path(result["metadata_path"]).write_text(json.dumps(result, indent=2) + "\n")
            return result
        finally:
            if timecode != original_timecode:
                timeline.SetCurrentTimecode(original_timecode)

    def compare(
        self,
        before_reference: str,
        after_reference: str,
        output_name: str | None = None,
        create_side_by_side: bool = True,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Package two already-exported references; never invents a missing 'before'."""
        before_source = self.output.resolve_existing_artifact(before_reference)
        after_source = self.output.resolve_existing_artifact(after_reference)
        if before_source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise ValidationError("before_reference must be an exported PNG or JPG")
        if after_source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise ValidationError("after_reference must be an exported PNG or JPG")
        stem = safe_filename(output_name, f"comparison-{timestamp_slug()}")
        directory = self.output.directory("comparisons")
        before_path = (directory / f"{stem}-before{before_source.suffix.lower()}").resolve()
        after_path = (directory / f"{stem}-after{after_source.suffix.lower()}").resolve()
        comparison_path = (directory / f"{stem}-side-by-side.png").resolve()
        report_path = (self.output.directory("validation") / f"{stem}.json").resolve()
        targets = [before_path, after_path, report_path]
        if create_side_by_side:
            targets.append(comparison_path)
        if not overwrite and any(path.exists() for path in targets):
            raise ValidationError(f"Comparison output already exists for name {stem!r}")
        shutil.copy2(before_source, before_path)
        shutil.copy2(after_source, after_path)
        metrics: dict[str, Any] | None = None
        if create_side_by_side:
            try:
                from PIL import Image, ImageChops, ImageStat
            except ImportError as exc:
                raise CapabilityError(
                    "Pillow is required only for side-by-side comparison output"
                ) from exc
            with (
                Image.open(before_path).convert("RGB") as before_image,
                Image.open(after_path).convert("RGB") as after_image,
            ):
                height = max(before_image.height, after_image.height)
                canvas = Image.new(
                    "RGB", (before_image.width + after_image.width, height), "black"
                )
                canvas.paste(before_image, (0, 0))
                canvas.paste(after_image, (before_image.width, 0))
                canvas.save(comparison_path)
                comparable = after_image.resize(before_image.size)
                difference = ImageChops.difference(before_image, comparable)
                metrics = {
                    "mean_absolute_rgb_difference": ImageStat.Stat(difference).mean,
                    "label": (
                        "Technical image-change measurement; not an artistic-quality judgment"
                    ),
                }
        report = {
            "schema_version": 1,
            "status": "passed",
            "message": "Before and after references were supplied and preserved",
            "before_source": str(before_source),
            "after_source": str(after_source),
            "before_image_path": str(before_path),
            "after_image_path": str(after_path),
            "comparison_image_path": str(comparison_path) if create_side_by_side else None,
            "validation_report_path": str(report_path),
            "metrics": metrics,
            "date": datetime.now(UTC).isoformat(),
        }
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        return report

    def list_references(self) -> list[dict[str, Any]]:
        results = []
        for directory_name in ("captures", "comparisons"):
            for path in sorted(self.output.directory(directory_name).iterdir()):
                if path.is_file():
                    results.append(
                        {
                            "name": path.name,
                            "path": str(path.resolve()),
                            "kind": directory_name,
                            "size_bytes": path.stat().st_size,
                            "modified": datetime.fromtimestamp(
                                path.stat().st_mtime, UTC
                            ).isoformat(),
                        }
                    )
        return results

    def open_folder(self) -> dict[str, str]:
        folder = self.output.directory("captures").resolve()
        command = folder_open_command(folder)
        if command is None:
            raise OperationError(
                f"No supported folder opener was discovered for: {folder}"
            )
        completed = subprocess.run(command, check=False)
        if completed.returncode:
            raise OperationError(f"The operating system could not open: {folder}")
        return {"capture_folder": str(folder)}

    def delete_reference(self, reference: str) -> dict[str, Any]:
        path = self.output.resolve_existing_artifact(reference)
        deleted = [str(path)]
        if path.parent == self.output.directory("captures") and path.suffix.lower() in {
            ".png",
            ".jpg",
            ".jpeg",
        }:
            metadata = path.with_suffix(".json")
            if metadata.is_file():
                metadata.unlink()
                deleted.append(str(metadata))
        path.unlink()
        return {"deleted_paths": deleted, "recoverable": False}

    @staticmethod
    def cleanup_temporary_render(project: Any, job_id: str | None) -> bool:
        """Best-effort removal for a capture job created by a future render fallback."""
        if not job_id:
            return True
        delete = getattr(project, "DeleteRenderJob", None)
        return bool(callable(delete) and delete(job_id))
