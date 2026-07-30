"""Acquire TimelineItems from the playhead and operate on identity-only locks."""

import hashlib
import time
from datetime import UTC, datetime
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


def require_visible_change_or_restore(
    before_path: str,
    after_path: str,
    restore: Any,
) -> tuple[str, str]:
    """Reject a template no-op and prove the supplied backup restored the frame."""
    try:
        return require_observable_change(before_path, after_path)
    except OperationError as exc:
        restored_path = restore()
        before_hash = hashlib.sha256(Path(before_path).read_bytes()).hexdigest()
        restored_hash = hashlib.sha256(Path(restored_path).read_bytes()).hexdigest()
        if restored_hash != before_hash:
            raise OperationError(
                "Template was a visible no-op and backup restoration could not be "
                "verified against the original frame"
            ) from exc
        raise OperationError(
            "Template produced no visible change; backup DRX was restored successfully"
        ) from exc


def register(mcp: Any, services: Services) -> None:
    @mcp.tool()
    def inspect_playhead_item() -> dict[str, Any]:
        """Identify the timeline item under the playhead; this is not timeline selection."""
        return services.targets.inspect_playhead()

    @mcp.tool()
    def lock_timeline_target(
        expected_identity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Acquire once from the playhead and create an identity-only TimelineItem lock."""
        return services.targets.lock(expected_identity)

    @mcp.tool()
    def acquire_timeline_item(
        expected_identity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Double-read a playhead item for acquisition without creating a lock."""
        return services.targets.acquire(expected_identity)

    @mcp.tool()
    def lock_timeline_item(
        expected_identity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Acquire and lock a TimelineItem; later playhead state is ignored."""
        return services.targets.lock(expected_identity)

    @mcp.tool()
    def queue_timeline_item(
        expected_identity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Acquire the current TimelineItem and append an independent identity lock."""
        return services.targets.queue(expected_identity)

    @mcp.tool()
    def list_queued_timeline_items() -> list[dict[str, Any]]:
        """List session-local queued TimelineItem identities without resolving them."""
        return services.targets.get_queue()

    @mcp.tool()
    def validate_queued_timeline_items() -> list[dict[str, Any]]:
        """Resolve every queued TimelineItem by identity, never by playhead."""
        return services.targets.resolve_queue()

    @mcp.tool()
    def release_timeline_item_queue() -> dict[str, Any]:
        """Release all queued TimelineItem locks."""
        return services.targets.clear_queue()

    @mcp.tool()
    def get_locked_timeline_target() -> dict[str, Any]:
        """Return session-local locked identity without resolving or mutating Resolve."""
        return services.targets.get()

    @mcp.tool()
    def validate_locked_timeline_target() -> dict[str, Any]:
        """Strictly re-resolve the locked item without relying on the current playhead."""
        return services.targets.resolve()

    @mcp.tool()
    def resolve_locked_timeline_item() -> dict[str, Any]:
        """Resolve the TimelineItem lock by unique ID or strict composite fallback."""
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
    def release_timeline_item() -> dict[str, Any]:
        """Release the active TimelineItem lock."""
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
        if frame_strategy == "current":
            raise OperationError(
                "Locked TimelineItem capture cannot use the current playhead; "
                "use first, middle, last, or custom"
            )
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
        mutation_address = services.targets.resolve()["resolved_item"]
        operation = services.colors.apply_drx(
            mutation_address["track_index"],
            mutation_address["item_index"],
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
        mutation_address = services.targets.resolve()["resolved_item"]
        operation = services.colors.set_cdl(
            mutation_address["track_index"],
            mutation_address["item_index"],
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

    @mcp.tool()
    def apply_grade_template_to_locked_target(
        name: str,
        backup_drx_path: str,
        grade_mode: int = 0,
        frame_strategy: str = "middle",
    ) -> dict[str, Any]:
        """Apply a validated template to the lock and restore backup on visible no-op."""
        resolved_before = services.targets.resolve()
        target = resolved_before["target"]
        identifier = target["item_unique_id"] or target["clip_name"]
        template = services.grades.validate(
            name, services.connection.status()["version"]
        )
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        before = services.captures.capture_clip(
            identifier,
            frame_strategy,  # type: ignore[arg-type]
            None,
            f"{name}_BEFORE_{stamp}",
            "png",
            False,
            True,
        )
        mutation_address = services.targets.resolve()["resolved_item"]
        operation = services.grades.apply(
            name,
            mutation_address["track_index"],
            mutation_address["item_index"],
            grade_mode,
        )
        resolved_after = services.targets.resolve()
        wait_for_resolve_refresh()
        after = services.captures.capture_clip(
            identifier,
            frame_strategy,  # type: ignore[arg-type]
            None,
            f"{name}_AFTER_{stamp}",
            "png",
            False,
            True,
        )

        def restore() -> str:
            restore_resolution = services.targets.resolve()
            restore_address = restore_resolution["resolved_item"]
            services.colors.apply_drx(
                restore_address["track_index"],
                restore_address["item_index"],
                backup_drx_path,
                0,
            )
            services.targets.resolve()
            wait_for_resolve_refresh()
            restored = services.captures.capture_clip(
                identifier,
                frame_strategy,  # type: ignore[arg-type]
                None,
                f"{name}_RESTORED_{stamp}",
                "png",
                False,
                True,
            )
            services.grades.set_validation(name, "failed")
            return restored["image_path"]

        before_hash, after_hash = require_visible_change_or_restore(
            before["image_path"], after["image_path"], restore
        )
        inspection_address = services.targets.resolve()["resolved_item"]
        node_count = services.nodes.inspect(
            inspection_address["track_index"], inspection_address["item_index"]
        )["count"]
        if (
            template["expected_node_count"] is not None
            and node_count != template["expected_node_count"]
        ):
            restore()
            raise OperationError(
                "Template node-count validation failed; backup DRX was restored"
            )
        services.grades.set_validation(name, "validated")
        return {
            "template": template,
            "operation": operation,
            "target": resolved_after["target"],
            "node_count": node_count,
            "before": before,
            "after": after,
            "before_sha256": before_hash,
            "after_sha256": after_hash,
            "observable_change": True,
        }
