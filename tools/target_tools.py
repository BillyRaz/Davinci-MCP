"""Safe playhead inspection and session-local timeline target locking."""

import hashlib
import time
from pathlib import Path
from typing import Any

from resolve.errors import OperationError

from .context import Services


def require_observable_change(before_path: str, after_path: str) -> tuple[str, str]:
    """Return content hashes or fail when a reported grade made no visible change."""
    before_hash = hashlib.sha256(Path(before_path).read_bytes()).hexdigest()
    after_hash = hashlib.sha256(Path(after_path).read_bytes()).hexdigest()
    if before_hash == after_hash:
        raise OperationError(
            "Resolve reported grade success, but before/after frame bytes are identical"
        )
    return before_hash, after_hash


def wait_for_resolve_refresh(seconds: float = 1.0) -> None:
    """Allow Resolve to refresh its viewer/export cache after a color mutation."""
    if not 0.1 <= seconds <= 5.0:
        raise ValueError("Resolve refresh wait must be between 0.1 and 5 seconds")
    time.sleep(seconds)


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def inspect_playhead_item() -> dict[str, Any]:
        """Identify the timeline item under the playhead; this is not timeline selection."""
        return services.targets.inspect_playhead()

    @mcp.tool()
    def lock_timeline_target(
        expected_identity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Double-read and lock the playhead item, optionally validating preconfirmed identity."""
        return services.targets.lock(expected_identity)

    @mcp.tool()
    def get_locked_timeline_target() -> dict[str, Any]:
        """Return session-local locked identity without resolving or mutating Resolve."""
        return services.targets.get()

    @mcp.tool()
    def validate_locked_timeline_target() -> dict[str, Any]:
        """Strictly re-resolve the locked item without relying on the current playhead."""
        return services.targets.resolve()

    @mcp.tool()
    def inspect_locked_target_grade_context() -> dict[str, Any]:
        """Read official version, graph, group, cache, Fusion, and media context."""
        return services.targets.grade_context()

    @mcp.tool()
    def clear_locked_timeline_target() -> dict[str, Any]:
        """Explicitly clear the session-local timeline target lock."""
        return services.targets.clear()

    @mcp.tool()
    def capture_locked_target_frame(
        frame_strategy: str = "middle",
        custom_frame: int | None = None,
        output_name: str | None = None,
        output_format: str = "png",
        overwrite: bool = False,
        force_gallery: bool = False,
    ) -> dict[str, Any]:
        """Capture the locked item, then prove its identity remained valid."""
        resolved_before = services.targets.resolve()
        target = resolved_before["target"]
        identifier = target["item_unique_id"] or target["clip_name"]
        result = services.captures.capture_clip(
            identifier,
            frame_strategy,  # type: ignore[arg-type]
            custom_frame,
            output_name,
            output_format,
            overwrite,
            force_gallery,
        )
        resolved_after = services.targets.resolve()
        if result["clip_unique_id"] != resolved_after["target"]["item_unique_id"]:
            services.targets.clear()
            raise OperationError("Capture returned a different item than the locked target")
        return {
            **result,
            "locked_target_validated_before": True,
            "locked_target_validated_after": True,
        }

    @mcp.tool()
    def apply_grade_to_locked_target(
        drx_path: str,
        grade_mode: int = 0,
        frame_strategy: str = "middle",
        before_output_name: str | None = None,
        after_output_name: str | None = None,
    ) -> dict[str, Any]:
        """Apply DRX only to the locked item and reject an observable image no-op."""
        resolved_before = services.targets.resolve()
        target = resolved_before["target"]
        identifier = target["item_unique_id"] or target["clip_name"]
        before = services.captures.capture_clip(
            identifier,
            frame_strategy,  # type: ignore[arg-type]
            None,
            before_output_name,
            "png",
            False,
            True,
        )
        operation = services.colors.apply_drx(
            target["track_index"],
            target["item_index"],
            drx_path,
            grade_mode,
        )
        resolved_after = services.targets.resolve()
        wait_for_resolve_refresh()
        after = services.captures.capture_clip(
            identifier,
            frame_strategy,  # type: ignore[arg-type]
            None,
            after_output_name,
            "png",
            False,
            True,
        )
        before_hash, after_hash = require_observable_change(
            before["image_path"], after["image_path"]
        )
        return {
            "operation": operation,
            "target": resolved_after["target"],
            "before": before,
            "after": after,
            "observable_change": True,
            "before_sha256": before_hash,
            "after_sha256": after_hash,
        }

    @mcp.tool()
    def set_cdl_on_locked_target(
        node_index: int,
        slope: str = "1 1 1",
        offset: str = "0 0 0",
        power: str = "1 1 1",
        saturation: float = 1.0,
        frame_strategy: str = "middle",
        before_output_name: str | None = None,
        after_output_name: str | None = None,
    ) -> dict[str, Any]:
        """Set CDL on one existing node of the locked item and reject a visible no-op."""
        resolved_before = services.targets.resolve()
        target = resolved_before["target"]
        identifier = target["item_unique_id"] or target["clip_name"]
        before = services.captures.capture_clip(
            identifier,
            frame_strategy,  # type: ignore[arg-type]
            None,
            before_output_name,
            "png",
            False,
            True,
        )
        operation = services.colors.set_cdl(
            target["track_index"],
            target["item_index"],
            node_index,
            slope,
            offset,
            power,
            saturation,
        )
        resolved_after = services.targets.resolve()
        wait_for_resolve_refresh()
        after = services.captures.capture_clip(
            identifier,
            frame_strategy,  # type: ignore[arg-type]
            None,
            after_output_name,
            "png",
            False,
            True,
        )
        before_hash, after_hash = require_observable_change(
            before["image_path"], after["image_path"]
        )
        return {
            "operation": operation,
            "target": resolved_after["target"],
            "before": before,
            "after": after,
            "observable_change": True,
            "before_sha256": before_hash,
            "after_sha256": after_hash,
        }
