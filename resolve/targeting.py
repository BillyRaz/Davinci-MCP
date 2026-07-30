"""Session-local, identity-locked timeline targeting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from .connection import ResolveConnection
from .errors import NotFoundError, OperationError, ValidationError
from .timeline import TimelineService


@dataclass(frozen=True, slots=True)
class TimelineItemLock:
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
    media_pool_id: str | None
    source_media_path: str | None
    locked_at: str
    connection_generation: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TimelineItemService:
    """Acquire once from the playhead, then operate only on TimelineItem identity."""

    def __init__(
        self, connection: ResolveConnection, timelines: TimelineService | None = None
    ) -> None:
        self.connection = connection
        self.timelines = timelines or TimelineService(connection)
        self._locked: TimelineItemLock | None = None
        self._queue: list[TimelineItemLock] = []

    def clear(self) -> dict[str, Any]:
        had_target = self._locked is not None
        self._locked = None
        return {"cleared": had_target}

    def clear_queue(self) -> dict[str, Any]:
        count = len(self._queue)
        self._queue.clear()
        return {"cleared": count}

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

    def acquire(self, expected: dict[str, Any] | None = None) -> dict[str, Any]:
        first = self.inspect_playhead()
        second = self.inspect_playhead()
        if not self._stable(first, second):
            raise ValidationError(
                "TimelineItem acquisition was unstable across two independent reads"
            )
        if expected:
            self._validate_expected(second, expected)
        return {"status": "acquired", "item": second}

    def _make_lock(self, acquired: dict[str, Any]) -> TimelineItemLock:
        identity = {key: value for key, value in acquired.items() if key != "playhead_timecode"}
        return TimelineItemLock(
            **identity,
            locked_at=datetime.now(UTC).isoformat(),
            connection_generation=self._generation(),
        )

    def lock(self, expected: dict[str, Any] | None = None) -> dict[str, Any]:
        acquired = self.acquire(expected)["item"]
        target = self._make_lock(acquired)
        self._locked = target
        return {"status": "locked", "target": target.to_dict()}

    def queue(self, expected: dict[str, Any] | None = None) -> dict[str, Any]:
        acquired = self.acquire(expected)["item"]
        target = self._make_lock(acquired)
        if any(
            item.project_unique_id == target.project_unique_id
            and item.timeline_unique_id == target.timeline_unique_id
            and item.item_unique_id == target.item_unique_id
            for item in self._queue
        ):
            raise ValidationError("TimelineItem is already queued")
        self._queue.append(target)
        return {"status": "queued", "position": len(self._queue), "target": target.to_dict()}

    def get_queue(self) -> list[dict[str, Any]]:
        return [target.to_dict() for target in self._queue]

    def get(self) -> dict[str, Any]:
        if self._locked is None:
            raise NotFoundError("No timeline target is locked in this MCP session")
        return self._locked.to_dict()

    def _assert_context(self, target: TimelineItemLock) -> None:
        context = self._context()
        if self._generation() != target.connection_generation:
            raise ValidationError("Resolve connection changed; locked target was invalidated")
        if (
            context["project_name"] != target.project_name
            or (
                target.project_unique_id
                and context["project_unique_id"] != target.project_unique_id
            )
        ):
            raise ValidationError("Active project changed; locked target was invalidated")
        if (
            context["timeline_name"] != target.timeline_name
            or (
                target.timeline_unique_id
                and context["timeline_unique_id"] != target.timeline_unique_id
            )
        ):
            raise ValidationError("Active timeline changed; locked target was invalidated")

    @staticmethod
    def _unique(candidates: list[dict[str, Any]], rule: str) -> dict[str, Any] | None:
        if len(candidates) > 1:
            raise ValidationError(
                f"Locked target is ambiguous under {rule}; found {len(candidates)} matches"
            )
        return candidates[0] if candidates else None

    def _resolve_lock(self, target: TimelineItemLock) -> dict[str, Any]:
        self._assert_context(target)
        clips = self.timelines.clips()
        match = None
        resolution_rule = ""
        if target.item_unique_id:
            match = self._unique(
                [clip for clip in clips if clip["unique_id"] == target.item_unique_id],
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
            raise NotFoundError("Locked TimelineItem is stale or no longer exists")
        if not target.item_unique_id:
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
                    "Locked TimelineItem composite identity changed; "
                    f"expected {expected_fields}, resolved {strict_fields}"
                )
        return {
            "status": "valid",
            "resolution_rule": resolution_rule,
            "target": target.to_dict(),
            "resolved_item": match,
        }

    def resolve(self) -> dict[str, Any]:
        if self._locked is None:
            raise NotFoundError("No timeline target is locked in this MCP session")
        target = self._locked
        try:
            return self._resolve_lock(target)
        except Exception:
            self._locked = None
            raise

    def resolve_queue(self) -> list[dict[str, Any]]:
        return [self._resolve_lock(target) for target in self._queue]

    def item(self) -> tuple[Any, dict[str, Any]]:
        resolved = self.resolve()
        match = resolved["resolved_item"]
        item = self.timelines.item(match["track_index"], match["item_index"])
        if item.GetUniqueId() != match["unique_id"]:
            self._locked = None
            raise OperationError("Timeline changed during locked-target resolution")
        return item, resolved

    @staticmethod
    def _graph_context(graph: Any) -> dict[str, Any] | None:
        if graph is None:
            return None
        count = graph.GetNumNodes()
        return {
            "count": count,
            "nodes": [
                {
                    "index": index,
                    "label": graph.GetNodeLabel(index),
                    "lut": graph.GetLUT(index),
                    "tools": graph.GetToolsInNode(index) or [],
                    "cache_mode": graph.GetNodeCacheMode(index),
                    "enabled": {
                        "supported": False,
                        "reason": "The official Graph API has SetNodeEnabled but no getter.",
                    },
                    "cdl": {
                        "supported": False,
                        "reason": "The official TimelineItem API has SetCDL but no getter.",
                    },
                }
                for index in range(1, count + 1)
            ],
        }

    def grade_context(self) -> dict[str, Any]:
        """Inspect official grade/version/cache/group context without mutation."""
        item, resolved = self.item()
        resolve = self.connection.connect()
        group = item.GetColorGroup()
        media = item.GetMediaPoolItem()
        media_properties = media.GetClipProperty() if media else {}
        track = getattr(item, "GetTrackTypeAndIndex", lambda: None)()
        current_version = item.GetCurrentVersion()
        return {
            "target": resolved["target"],
            "resolved_item": resolved["resolved_item"],
            "current_page": resolve.GetCurrentPage(),
            "current_version": current_version,
            "grade_mode": (
                "local"
                if current_version and current_version.get("versionType") == 0
                else "remote"
                if current_version and current_version.get("versionType") == 1
                else "unknown"
            ),
            "local_versions": item.GetVersionNameList(0) or [],
            "remote_versions": item.GetVersionNameList(1) or [],
            "clip_color_bypass": {
                "supported": False,
                "reason": "No clip color-bypass getter is exposed by the official API.",
            },
            "timeline_color_bypass": {
                "supported": False,
                "reason": "No timeline color-bypass getter is exposed by the official API.",
            },
            "clip_graph": self._graph_context(item.GetNodeGraph()),
            "color_group": (
                {
                    "name": group.GetName(),
                    "pre_clip_graph": self._graph_context(group.GetPreClipNodeGraph()),
                    "post_clip_graph": self._graph_context(group.GetPostClipNodeGraph()),
                }
                if group
                else None
            ),
            "clip_enabled": item.GetClipEnabled(),
            "track_type_and_index": track,
            "color_output_cache": item.GetIsColorOutputCacheEnabled(),
            "fusion_output_cache": item.GetIsFusionOutputCacheEnabled(),
            "fusion_composition_count": item.GetFusionCompCount(),
            "fusion_composition_names": item.GetFusionCompNameList() or [],
            "media_pool_item_available": media is not None,
            "source_media_path": media_properties.get("File Path") or None,
            "media_type": media_properties.get("Type") or None,
            "compound_or_adjustment_context": {
                "supported": False,
                "reason": (
                    "The official API exposes media properties and Fusion composition count "
                    "but no authoritative adjustment-clip/compound-clip classification getter."
                ),
            },
        }


# Backward-compatible names for integrations built before TimelineItem terminology.
TimelineTarget = TimelineItemLock
TimelineTargetService = TimelineItemService
