"""Unit tests for API boundaries without a running Resolve process."""

import hashlib
from pathlib import Path

import pytest

from resolve.errors import CapabilityError, NotFoundError, ValidationError
from resolve.models import GradeTemplate, MarkerInput
from resolve.nodes import NodeService
from resolve.powergrade import PowerGradeCatalog
from resolve.project import ProjectService


class FakeTimeline:
    def __init__(self, name: str, uid: str) -> None:
        self.name = name
        self.uid = uid

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid


class FakeProject:
    def __init__(self) -> None:
        self.timelines = [FakeTimeline("A", "1"), FakeTimeline("B", "2")]
        self.current = self.timelines[0]

    def GetTimelineCount(self) -> int:
        return len(self.timelines)

    def GetTimelineByIndex(self, index: int) -> FakeTimeline:
        return self.timelines[index - 1]

    def GetCurrentTimeline(self) -> FakeTimeline:
        return self.current

    def SetCurrentTimeline(self, timeline: FakeTimeline) -> bool:
        self.current = timeline
        return True


class FakeConnection:
    def __init__(self) -> None:
        self.value = FakeProject()

    def project(self) -> FakeProject:
        return self.value


def test_switch_timeline() -> None:
    service = ProjectService(FakeConnection())  # type: ignore[arg-type]
    assert service.switch_timeline("B")["unique_id"] == "2"
    assert service.timelines()[1]["current"] is True
    with pytest.raises(NotFoundError):
        service.switch_timeline("missing")


def test_node_edit_gap_is_explicit() -> None:
    with pytest.raises(CapabilityError, match="official scripting API"):
        NodeService.unsupported_edit("add_serial_node")


class FakeColor:
    def apply_drx(self, *_: object) -> dict[str, object]:
        return {"ok": True}


def test_catalog_round_trip(tmp_path: Path) -> None:
    drx = tmp_path / "look.drx"
    drx.write_text("fixture")
    catalog = PowerGradeCatalog(FakeColor(), str(tmp_path / "catalog.json"))  # type: ignore[arg-type]
    catalog.register(GradeTemplate(name="cinematic", drx_path=str(drx), favorite=True))
    assert catalog.search("cinema")[0]["favorite"] is True
    assert catalog.search("cinema")[0]["sha256"] == hashlib.sha256(
        drx.read_bytes()
    ).hexdigest()
    assert catalog.validate("cinematic")["hash_valid"] is True
    assert catalog.apply("cinematic", 1, 1)["ok"] is True


def test_catalog_rejects_missing_drx(tmp_path: Path) -> None:
    catalog = PowerGradeCatalog(FakeColor(), str(tmp_path / "catalog.json"))  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        catalog.register(GradeTemplate(name="bad", drx_path=str(tmp_path / "no.drx")))


def test_catalog_rejects_tampered_registered_drx(tmp_path: Path) -> None:
    drx = tmp_path / "look.drx"
    drx.write_text("first")
    catalog = PowerGradeCatalog(FakeColor(), str(tmp_path / "catalog.json"))  # type: ignore[arg-type]
    catalog.register(
        GradeTemplate(
            name="locked-look",
            drx_path=str(drx),
            compatible_resolve_version="21.0",
            expected_node_count=5,
        )
    )
    drx.write_text("tampered")
    with pytest.raises(ValidationError, match="hash changed"):
        catalog.validate("locked-look", "21.0.2.4")


def test_marker_validation() -> None:
    with pytest.raises(ValueError):
        MarkerInput(frame=-1)
