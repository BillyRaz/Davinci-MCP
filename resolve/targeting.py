"""Session-local, identity-locked timeline targeting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from .connection import ResolveConnection
from .errors import NotFoundError, OperationError, ValidationError
from .timeline import TimelineService


@dataclass(frozen=True, slots=True)
class TimelineTarget:
    project_name: str
    project_unique_id: str | None
    timeline_name: str
    timeline_unique_id: str | None
    clip_name: str
    item_unique_id: str | None
    track_type: str
    track_index: int
    item_index: int
    start_frame: int
    end_frame: int
    duration: int
    playhead_timecode: str
    media_pool_id: str | None
    source_media_path: str | None
    locked_at: str
    connection_generation: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TimelineTargetService:
    """Lock one timeline item by identity and re-resolve it before every use."""

    def __init__(
        self, connection: ResolveConnection, timelines: TimelineService | None = None
    ) -> None:
        self.connection = connection
        self.timelines = timelines or TimelineService(connection)
        self._locked: TimelineTarget | None = None

    def clear(self) -> dict[str, Any]:
        had_target = self._locked is not None
        self._locked = None
        return {"cleared": had_target}

    def _generation(self) -> int:
        return int(getattr(self.connection, "generation", 0))

    def _context(self) -> dict[str, Any]:
        project = self.connection.project()
        timeline = self.connection.timeline()
        return {
            "project_name": project.GetName(),
            "project_unique_id": getattr(project, "GetUniqueId", lambda: None)(),
            "timeline_name": timeline.GetName(),
            "timeline_unique_id": getattr(timeline, "GetUniqueId", lambda: None)(),
            "playhead_timecode": timeline.GetCurrentTimecode(),
        }

    def inspect_playhead(self) -> dict[str, Any]:
        context = self._context()
        current = self.timelines.current_item()
        unique_id = current.GetUniqueId()
        matches = [
            clip
            for clip in self.timelines.clips()
            if unique_id and clip["unique_id"] == unique_id
        ]
        if not matches:
            matches = [
                clip
                for clip in self.timelines.clips()
                if clip["name"] == current.GetName()
                and clip["start"] == current.GetStart()
                and clip["end"] == current.GetEnd()
                and clip["duration"] == current.GetDuration()
            ]
        if len(matches) != 1:
            raise ValidationError(
                "The timeline item under the playhead could not be mapped to exactly "
                f"one timeline address; found {len(matches)} matches"
            )
        clip = matches[0]
        media = current.GetMediaPoolItem()
        media_properties = media.GetClipProperty() if media else {}
        return {
            **context,
            "clip_name": clip["name"],
            "item_unique_id": clip["unique_id"] or None,
            "track_type": "video",
            "track_index": clip["track_index"],
            "item_index": clip["item_index"],
            "start_frame": clip["start"],
            "end_frame": clip["end"],
            "duration": clip["duration"],
            "media_pool_id": clip.get("media_pool_id"),
            "source_media_path": media_properties.get("File Path") or None,
        }

    @staticmethod
    def _stable(first: dict[str, Any], second: dict[str, Any]) -> bool:
        return first == second

    @staticmethod
    def _validate_expected(actual: dict[str, Any], expected: dict[str, Any]) -> None:
        aliases = {
            "project": "project_name",
            "timeline": "timeline_name",
            "unique_id": "item_unique_id",
            "name": "clip_name",
            "clip": "clip_name",
            "start": "start_frame",
            "end": "end_frame",
            "track": "track_index",
            "item": "item_index",
            "playhead": "playhead_timecode",
        }
        conflicts = {}
        for supplied_key, supplied_value in expected.items():
            key = aliases.get(supplied_key, supplied_key)
            if key not in actual:
                raise ValidationError(f"Unknown target identity field: {supplied_key}")
            if supplied_value is not None and actual[key] != supplied_value:
                conflicts[supplied_key] = {
                    "expected": supplied_value,
                    "actual": actual[key],
                }
        if conflicts:
            raise ValidationError(f"Preconfirmed target identity conflicts: {conflicts}")

    def lock(self, expected: dict[str, Any] | None = None) -> dict[str, Any]:
        first = self.inspect_playhead()
        second = self.inspect_playhead()
        if not self._stable(first, second):
            self._locked = None
            raise ValidationError(
                "Playhead target was unstable across two independent reads; lock refused"
            )
        if expected:
            self._validate_expected(second, expected)
        target = TimelineTarget(
            **second,
            locked_at=datetime.now(UTC).isoformat(),
            connection_generation=self._generation(),
        )
        self._locked = target
        return {"status": "locked", "target": target.to_dict()}

    def get(self) -> dict[str, Any]:
        if self._locked is None:
            raise NotFoundError("No timeline target is locked in this MCP session")
        return self._locked.to_dict()

    def _assert_context(self, target: TimelineTarget) -> None:
        context = self._context()
        if self._generation() != target.connection_generation:
            self._locked = None
            raise ValidationError("Resolve connection changed; locked target was invalidated")
        if (
            context["project_name"] != target.project_name
            or (
                target.project_unique_id
                and context["project_unique_id"] != target.project_unique_id
            )
        ):
            self._locked = None
            raise ValidationError("Active project changed; locked target was invalidated")
        if (
            context["timeline_name"] != target.timeline_name
            or (
                target.timeline_unique_id
                and context["timeline_unique_id"] != target.timeline_unique_id
            )
        ):
            self._locked = None
            raise ValidationError("Active timeline changed; locked target was invalidated")

    @staticmethod
    def _unique(candidates: list[dict[str, Any]], rule: str) -> dict[str, Any] | None:
        if len(candidates) > 1:
            raise ValidationError(
                f"Locked target is ambiguous under {rule}; found {len(candidates)} matches"
            )
        return candidates[0] if candidates else None

    def resolve(self) -> dict[str, Any]:
        if self._locked is None:
            raise NotFoundError("No timeline target is locked in this MCP session")
        target = self._locked
        try:
            self._assert_context(target)
            clips = self.timelines.clips()
            match = None
            resolution_rule = ""
            if target.item_unique_id:
                match = self._unique(
                    [
                        clip
                        for clip in clips
                        if clip["unique_id"] == target.item_unique_id
                    ],
                    "exact unique ID",
                )
                resolution_rule = "exact_unique_id"
            if match is None:
                match = self._unique(
                    [
                        clip
                        for clip in clips
                        if clip["track_index"] == target.track_index
                        and clip["start"] == target.start_frame
                        and clip["end"] == target.end_frame
                        and clip["name"] == target.clip_name
                    ],
                    "track/start/end/name composite",
                )
                resolution_rule = "track_start_end_name"
            if match is None:
                match = self._unique(
                    [
                        clip
                        for clip in clips
                        if clip["track_index"] == target.track_index
                        and clip["item_index"] == target.item_index
                        and clip["duration"] == target.duration
                        and clip["name"] == target.clip_name
                    ],
                    "track/item/duration/name composite",
                )
                resolution_rule = "track_item_duration_name"
            if match is None:
                raise NotFoundError("Locked timeline target is stale or no longer exists")
            strict_fields = {
                "clip_name": match["name"],
                "track_index": match["track_index"],
                "item_index": match["item_index"],
                "start_frame": match["start"],
                "end_frame": match["end"],
                "duration": match["duration"],
            }
            expected_fields = {
                "clip_name": target.clip_name,
                "track_index": target.track_index,
                "item_index": target.item_index,
                "start_frame": target.start_frame,
                "end_frame": target.end_frame,
                "duration": target.duration,
            }
            if strict_fields != expected_fields:
                raise ValidationError(
                    "Locked target identity changed after editing or track movement; "
                    f"expected {expected_fields}, resolved {strict_fields}"
                )
            return {
                "status": "valid",
                "resolution_rule": resolution_rule,
                "target": target.to_dict(),
                "resolved_item": match,
            }
        except Exception:
            self._locked = None
            raise

    def item(self) -> tuple[Any, dict[str, Any]]:
        resolved = self.resolve()
        match = resolved["resolved_item"]
        item = self.timelines.item(match["track_index"], match["item_index"])
        if item.GetUniqueId() != match["unique_id"]:
            self._locked = None
            raise OperationError("Timeline changed during locked-target resolution")
        return item, resolved
