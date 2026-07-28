"""Supported color operations and honest analysis boundaries."""

from pathlib import Path
from typing import Any

from .connection import ResolveConnection
from .errors import CapabilityError, OperationError, ValidationError
from .timeline import TimelineService


class ColorService:
    def __init__(self, connection: ResolveConnection) -> None:
        self.connection = connection
        self.timelines = TimelineService(connection)

    def apply_drx(
        self, track_index: int, item_index: int, path: str, grade_mode: int = 0
    ) -> dict[str, Any]:
        drx = Path(path).expanduser()
        if drx.suffix.lower() != ".drx" or not drx.is_file():
            raise ValidationError(f"DRX file does not exist: {drx}")
        if grade_mode not in (0, 1, 2):
            raise ValidationError("grade_mode must be 0, 1, or 2")
        graph = self.timelines.item(track_index, item_index).GetNodeGraph()
        if not graph.ApplyGradeFromDRX(str(drx), grade_mode):
            raise OperationError("Resolve could not apply the DRX grade")
        return {"path": str(drx), "grade_mode": grade_mode}

    def set_cdl(
        self,
        track_index: int,
        item_index: int,
        node_index: int,
        slope: str,
        offset: str,
        power: str,
        saturation: float,
    ) -> dict[str, Any]:
        item = self.timelines.item(track_index, item_index)
        values = {
            "NodeIndex": str(node_index),
            "Slope": slope,
            "Offset": offset,
            "Power": power,
            "Saturation": str(saturation),
        }
        if not item.SetCDL(values):
            raise OperationError("Resolve rejected the CDL values")
        return values

    @staticmethod
    def inspect_clip_limitation() -> None:
        raise CapabilityError(
            "Numerical exposure, clipping, histogram, noise, white-balance, and skin "
            "measurements are not exposed by the official Resolve scripting API. "
            "The server will not infer them via screenshots, OCR, or UI automation."
        )
