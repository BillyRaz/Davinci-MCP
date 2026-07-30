"""Locked-TimelineItem application using disposable local versions only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from resolve.errors import OperationError, ValidationError
from resolve.setlut import require_owned_empty_node

from .registry import LutRegistry

OUTCOMES = {
    "APPLIED_AND_VALIDATED",
    "APPLIED_WITH_WARNINGS",
    "REJECTED_VISIBLE_NOOP",
    "REJECTED_TECHNICAL_SAFETY",
    "RESTORED_AFTER_FAILURE",
    "BLOCKED_TARGET_INVALID",
    "BLOCKED_BACKUP_FAILED",
    "BLOCKED_VERSION_CREATION_FAILED",
    "BLOCKED_LUT_DISCOVERY_FAILED",
}


def graph_snapshot(graph: Any) -> dict[str, Any]:
    nodes = [
        {
            "index": index,
            "label": graph.GetNodeLabel(index),
            "lut": graph.GetLUT(index),
            "tools": graph.GetToolsInNode(index) or [],
            "cache_mode": graph.GetNodeCacheMode(index),
        }
        for index in range(1, graph.GetNumNodes() + 1)
    ]
    document = {"count": len(nodes), "nodes": nodes}
    fingerprint = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {**document, "fingerprint": fingerprint}


@dataclass
class ApplicationTransaction:
    target_unique_id: str
    original_version_name: str
    original_version_type: int
    original_graph: dict[str, Any]
    temporary_version_name: str
    lut_identifier: str
    backup_drx_path: str


class LutApplicationService:
    """Stateful per-MCP-session application and restoration coordinator."""

    def __init__(self, services: Any, registry: LutRegistry) -> None:
        self.services = services
        self.registry = registry
        self.transaction: ApplicationTransaction | None = None

    def _item(self) -> tuple[Any, dict[str, Any]]:
        return self.services.targets.item()

    def prepare(
        self, profile_name: str, lut_identifier: str, backup_drx_path: str
    ) -> dict[str, Any]:
        if self.transaction is not None:
            raise OperationError("A LUT application transaction is already active")
        entry = self.registry.get(profile_name)
        if entry.approval_state == "deprecated":
            raise ValidationError("Deprecated LUT cannot be applied")
        if not Path(entry.file_path).is_file():
            raise ValidationError("Registered LUT file is missing")
        digest = hashlib.sha256(Path(entry.file_path).read_bytes()).hexdigest()
        if digest != entry.sha256:
            raise ValidationError("Registered LUT hash changed")
        backup = Path(backup_drx_path)
        if not backup.is_file() or not backup.read_bytes():
            raise OperationError("Verified grade backup is required before application")
        item, resolved = self._item()
        current = item.GetCurrentVersion()
        original_graph = graph_snapshot(item.GetNodeGraph())
        temp = f"MCP_LUT_{profile_name}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        if not item.AddVersion(temp, 0) or not item.LoadVersionByName(temp, 0):
            raise OperationError("Could not create and load disposable local version")
        try:
            temporary_graph = graph_snapshot(item.GetNodeGraph())
            require_owned_empty_node(temporary_graph["nodes"], 1)
        except Exception:
            item.LoadVersionByName(current["versionName"], current["versionType"])
            item.DeleteVersionByName(temp, 0)
            raise
        self.transaction = ApplicationTransaction(
            resolved["target"]["item_unique_id"],
            current["versionName"],
            current["versionType"],
            original_graph,
            temp,
            lut_identifier,
            str(backup.resolve()),
        )
        return {
            "status": "prepared",
            "target": resolved["target"],
            "resolved_item": resolved["resolved_item"],
            "temporary_version": temp,
            "original_graph": original_graph,
            "temporary_graph": temporary_graph,
        }

    def apply(self) -> dict[str, Any]:
        if self.transaction is None:
            raise OperationError("No prepared LUT application transaction")
        item, resolved = self._item()
        if resolved["target"]["item_unique_id"] != self.transaction.target_unique_id:
            return self.restore("BLOCKED_TARGET_INVALID")
        graph = item.GetNodeGraph()
        require_owned_empty_node(graph_snapshot(graph)["nodes"], 1)
        result = bool(graph.SetLUT(1, self.transaction.lut_identifier))
        readback = graph.GetLUT(1)
        if not result or readback != self.transaction.lut_identifier:
            restored = self.restore("RESTORED_AFTER_FAILURE")
            restored.update({"setlut_return": result, "getlut": readback})
            return restored
        return {
            "status": "APPLIED_AND_VALIDATED",
            "target": resolved["target"],
            "resolved_item": resolved["resolved_item"],
            "setlut_return": result,
            "getlut": readback,
            "temporary_version": self.transaction.temporary_version_name,
        }

    def restore(self, status: str = "RESTORED_AFTER_FAILURE") -> dict[str, Any]:
        if status not in OUTCOMES:
            raise ValidationError(f"Unknown LUT application outcome: {status}")
        if self.transaction is None:
            raise OperationError("No active LUT application transaction")
        item, resolved = self._item()
        transaction = self.transaction
        loaded = item.LoadVersionByName(
            transaction.original_version_name, transaction.original_version_type
        )
        deleted = item.DeleteVersionByName(transaction.temporary_version_name, 0)
        restored_graph = graph_snapshot(item.GetNodeGraph())
        self.transaction = None
        if not loaded or not deleted or restored_graph != transaction.original_graph:
            raise OperationError("Original version/graph restoration could not be verified")
        return {
            "status": status,
            "target": resolved["target"],
            "original_version_loaded": loaded,
            "temporary_version_deleted": deleted,
            "restored_graph": restored_graph,
        }
