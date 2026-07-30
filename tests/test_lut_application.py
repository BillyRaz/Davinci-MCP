from pathlib import Path
from types import SimpleNamespace

import pytest

from resolve.errors import OperationError
from resolve.lut.application import LutApplicationService
from resolve.lut.generator import generate_artifacts
from resolve.lut.model import GradeProfile
from resolve.lut.registry import LutRegistry


class Graph:
    def __init__(self) -> None:
        self.lut = ""

    def GetNumNodes(self) -> int:
        return 1

    def GetNodeLabel(self, _index: int) -> str:
        return ""

    def GetLUT(self, _index: int) -> str:
        return self.lut

    def GetToolsInNode(self, _index: int) -> list[str]:
        return []

    def GetNodeCacheMode(self, _index: int) -> int:
        return -1

    def SetLUT(self, _index: int, value: str) -> bool:
        self.lut = value
        return True


class Item:
    def __init__(self) -> None:
        self.graphs = {"Version 1": Graph()}
        self.current = "Version 1"

    def GetCurrentVersion(self) -> dict[str, object]:
        return {"versionName": self.current, "versionType": 0}

    def GetNodeGraph(self) -> Graph:
        return self.graphs[self.current]

    def AddVersion(self, name: str, _kind: int) -> bool:
        self.graphs[name] = Graph()
        return True

    def LoadVersionByName(self, name: str, _kind: int) -> bool:
        if name not in self.graphs:
            return False
        self.current = name
        return True

    def DeleteVersionByName(self, name: str, _kind: int) -> bool:
        if name == self.current:
            return False
        del self.graphs[name]
        return True


class Targets:
    def __init__(self, item: Item) -> None:
        self.item_value = item
        self.uid = "target"

    def item(self):
        return self.item_value, {
            "target": {"item_unique_id": self.uid},
            "resolved_item": {"track_index": 1, "item_index": 2},
        }


def service(tmp_path: Path):
    generated = generate_artifacts(
        GradeProfile(name="APPLICATION_V1", description="Application", cube_size=17),
        tmp_path / "generated",
    )
    registry = LutRegistry(tmp_path / "registry.json")
    registry.register(
        Path(generated["cube_path"]), Path(generated["metadata_path"])
    )
    item = Item()
    targets = Targets(item)
    services = SimpleNamespace(targets=targets)
    return LutApplicationService(services, registry), item, targets


def test_lock_backup_owned_version_apply_and_restore(tmp_path: Path) -> None:
    application, item, _targets = service(tmp_path)
    backup = tmp_path / "backup.drx"
    backup.write_bytes(b"grade")
    prepared = application.prepare("APPLICATION_V1", "DavinciMCP/look.cube", str(backup))
    assert prepared["target"]["item_unique_id"] == "target"
    applied = application.apply()
    assert applied["status"] == "APPLIED_AND_VALIDATED"
    restored = application.restore()
    assert restored["status"] == "RESTORED_AFTER_FAILURE"
    assert item.current == "Version 1"
    assert list(item.graphs) == ["Version 1"]


def test_missing_lock_or_backup_and_project_drift_restore(tmp_path: Path) -> None:
    application, item, targets = service(tmp_path)
    with pytest.raises(OperationError, match="backup"):
        application.prepare("APPLICATION_V1", "look.cube", str(tmp_path / "missing"))
    backup = tmp_path / "backup.drx"
    backup.write_bytes(b"grade")
    application.prepare("APPLICATION_V1", "look.cube", str(backup))
    targets.uid = "different"
    restored = application.apply()
    assert restored["status"] == "BLOCKED_TARGET_INVALID"
    assert item.current == "Version 1"


def test_getlut_mismatch_restores(tmp_path: Path) -> None:
    application, item, _targets = service(tmp_path)
    backup = tmp_path / "backup.drx"
    backup.write_bytes(b"grade")
    application.prepare("APPLICATION_V1", "expected.cube", str(backup))
    graph = item.GetNodeGraph()
    graph.SetLUT = lambda _index, _value: True  # type: ignore[method-assign]
    result = application.apply()
    assert result["status"] == "RESTORED_AFTER_FAILURE"
    assert item.current == "Version 1"
