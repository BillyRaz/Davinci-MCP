"""Safe playhead-target locking tests with Resolve API fakes."""

from __future__ import annotations

from pathlib import Path

import pytest

from resolve.errors import NotFoundError, OperationError, ValidationError
from resolve.targeting import TimelineTargetService
from resolve.timeline import TimelineService
from tools.target_tools import (
    require_observable_change,
    wait_for_resolve_refresh,
)


class FakeMedia:
    def __init__(self, uid: str, path: str) -> None:
        self.uid = uid
        self.path = path

    def GetUniqueId(self) -> str:
        return self.uid

    def GetClipProperty(self) -> dict[str, str]:
        return {"File Path": self.path}


class FakeItem:
    def __init__(
        self,
        name: str,
        uid: str | None,
        start: int,
        end: int,
        media_id: str = "media-1",
    ) -> None:
        self.name = name
        self.uid = uid
        self.start = start
        self.end = end
        self.media = FakeMedia(media_id, f"/media/{name}")

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str | None:
        return self.uid

    def GetStart(self) -> int:
        return self.start

    def GetEnd(self) -> int:
        return self.end

    def GetDuration(self) -> int:
        return self.end - self.start

    def GetClipEnabled(self) -> bool:
        return True

    def GetMediaPoolItem(self) -> FakeMedia:
        return self.media


class FakeTimeline:
    def __init__(self, name: str = "Timeline", uid: str = "timeline-1") -> None:
        self.name = name
        self.uid = uid
        self.timecode = "01:00:00:00"
        self.tracks: dict[int, list[FakeItem]] = {
            1: [FakeItem("A.mov", "item-a", 100, 125)]
        }
        self.current = self.tracks[1][0]

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def GetCurrentTimecode(self) -> str:
        return self.timecode

    def GetCurrentVideoItem(self) -> FakeItem:
        return self.current

    def GetTrackCount(self, track_type: str) -> int:
        return max(self.tracks) if track_type == "video" else 0

    def GetItemListInTrack(self, track_type: str, index: int) -> list[FakeItem]:
        return list(self.tracks.get(index, [])) if track_type == "video" else []


class FakeProject:
    def __init__(self) -> None:
        self.name = "Project"
        self.uid = "project-1"
        self.timeline = FakeTimeline()

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def GetCurrentTimeline(self) -> FakeTimeline:
        return self.timeline


class FakeConnection:
    def __init__(self) -> None:
        self.value = FakeProject()
        self.generation = 1

    def project(self) -> FakeProject:
        return self.value

    def timeline(self) -> FakeTimeline:
        return self.value.timeline


def service() -> tuple[TimelineTargetService, FakeConnection]:
    connection = FakeConnection()
    timelines = TimelineService(connection)  # type: ignore[arg-type]
    return TimelineTargetService(connection, timelines), connection  # type: ignore[arg-type]


def test_playhead_and_media_pool_selection_are_truthfully_distinct() -> None:
    inspect_source = (Path(__file__).parents[1] / "tools/inspect.py").read_text()
    timeline_source = (Path(__file__).parents[1] / "tools/timeline_tools.py").read_text()
    assert "Media Pool selection only" in inspect_source
    assert "timeline-item selection is not API-exposed" in inspect_source
    assert "under the playhead; not timeline selection" in timeline_source


def test_stable_double_read_locks_same_item() -> None:
    targets, _ = service()
    result = targets.lock()
    assert result["status"] == "locked"
    assert result["target"]["item_unique_id"] == "item-a"


def test_mismatched_double_read_refuses_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    targets, _ = service()
    values = [
        {**targets.inspect_playhead(), "playhead_timecode": "01:00:00:00"},
        {**targets.inspect_playhead(), "playhead_timecode": "01:00:01:00"},
    ]
    monkeypatch.setattr(targets, "inspect_playhead", lambda: values.pop(0))
    with pytest.raises(ValidationError, match="unstable"):
        targets.lock()
    with pytest.raises(NotFoundError):
        targets.get()


def test_preconfirmed_identity_and_exact_unique_id_resolution() -> None:
    targets, _ = service()
    targets.lock({"unique_id": "item-a", "track": 1, "duration": 25})
    assert targets.resolve()["resolution_rule"] == "exact_unique_id"


def test_duplicate_filename_does_not_select_wrong_item() -> None:
    targets, connection = service()
    connection.timeline().tracks[1].append(FakeItem("A.mov", "item-b", 200, 225))
    targets.lock({"unique_id": "item-a"})
    assert targets.resolve()["resolved_item"]["unique_id"] == "item-a"


def test_project_change_invalidates_lock() -> None:
    targets, connection = service()
    targets.lock()
    connection.project().uid = "project-2"
    with pytest.raises(ValidationError, match="project changed"):
        targets.resolve()
    with pytest.raises(NotFoundError):
        targets.get()


def test_timeline_change_invalidates_lock() -> None:
    targets, connection = service()
    targets.lock()
    connection.timeline().uid = "timeline-2"
    with pytest.raises(ValidationError, match="timeline changed"):
        targets.resolve()


def test_track_movement_invalidates_stale_identity() -> None:
    targets, connection = service()
    targets.lock()
    item = connection.timeline().tracks[1].pop()
    connection.timeline().tracks[2] = [item]
    with pytest.raises(ValidationError, match="identity changed"):
        targets.resolve()


def test_missing_unique_id_uses_strict_composite() -> None:
    targets, connection = service()
    connection.timeline().current.uid = None
    targets.lock()
    assert targets.resolve()["resolution_rule"] == "track_start_end_name"


def test_ambiguous_composite_match_fails_safely() -> None:
    targets, connection = service()
    item = connection.timeline().current
    item.uid = None
    targets.lock()
    connection.timeline().tracks[1].append(FakeItem("A.mov", None, 100, 125))
    with pytest.raises(ValidationError, match="ambiguous"):
        targets.resolve()


def test_lock_remains_valid_when_playhead_moves_elsewhere() -> None:
    targets, connection = service()
    locked = connection.timeline().current
    other = FakeItem("B.mov", "item-b", 200, 225)
    connection.timeline().tracks[1].append(other)
    targets.lock()
    connection.timeline().current = other
    assert targets.resolve()["resolved_item"]["unique_id"] == locked.uid


def test_locked_capture_exposes_explicit_custom_frame_without_selection() -> None:
    source = (Path(__file__).parents[1] / "tools/target_tools.py").read_text()
    capture_tool = source.split("def capture_locked_target_frame(", 1)[1].split(
        "@mcp.tool()", 1
    )[0]
    assert "custom_frame: int | None" in capture_tool
    assert "force_gallery: bool" in capture_tool
    assert "selected_clips" not in capture_tool


def test_grade_address_comes_from_lock_not_new_playhead() -> None:
    targets, connection = service()
    other = FakeItem("B.mov", "item-b", 200, 225)
    connection.timeline().tracks[1].append(other)
    targets.lock()
    connection.timeline().current = other
    item, resolved = targets.item()
    assert item.GetUniqueId() == "item-a"
    assert resolved["resolved_item"]["item_index"] == 1


def test_locked_grade_tool_does_not_use_current_clip_address() -> None:
    source = (Path(__file__).parents[1] / "tools/target_tools.py").read_text()
    locked_tool = source.split("def set_cdl_on_locked_target(", 1)[1]
    assert 'target["track_index"]' in locked_tool
    assert 'target["item_index"]' in locked_tool
    assert "current_clip" not in locked_tool


def test_connection_generation_change_invalidates_lock() -> None:
    targets, connection = service()
    targets.lock()
    connection.generation += 1
    with pytest.raises(ValidationError, match="connection changed"):
        targets.resolve()


def test_noop_grade_is_reported(tmp_path: Path) -> None:
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    before.write_bytes(b"same")
    after.write_bytes(b"same")
    with pytest.raises(OperationError, match="identical"):
        require_observable_change(str(before), str(after))


def test_observable_grade_change_returns_distinct_hashes(tmp_path: Path) -> None:
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    before.write_bytes(b"before")
    after.write_bytes(b"after")
    assert require_observable_change(str(before), str(after))[0] != (
        require_observable_change(str(before), str(after))[1]
    )


def test_grade_capture_waits_for_resolve_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waited = []
    monkeypatch.setattr("tools.target_tools.time.sleep", waited.append)
    wait_for_resolve_refresh()
    assert waited == [1.0]
    with pytest.raises(ValueError):
        wait_for_resolve_refresh(0)


def test_explicit_clear_and_server_restart_state() -> None:
    targets, connection = service()
    targets.lock()
    assert targets.clear() == {"cleared": True}
    with pytest.raises(NotFoundError):
        targets.get()
    restarted = TimelineTargetService(connection, targets.timelines)
    with pytest.raises(NotFoundError):
        restarted.get()
