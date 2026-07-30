"""Serializable models at the MCP boundary."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class Result(BaseModel):
    ok: bool = True
    message: str
    data: Any = None


class ClipRef(BaseModel):
    track_index: int = Field(ge=1)
    item_index: int = Field(ge=1)


class MarkerInput(BaseModel):
    frame: int = Field(ge=0)
    color: str = "Blue"
    name: str = ""
    note: str = ""
    duration: int = Field(default=1, ge=1)
    custom_data: str = ""


class RenderSettings(BaseModel):
    target_dir: str
    custom_name: str = ""
    format: str | None = None
    codec: str | None = None
    preset: str | None = None
    mode: Literal["single", "individual"] = "single"
    export_video: bool = True
    export_audio: bool = True


class GradeTemplate(BaseModel):
    name: str
    drx_path: str
    description: str = ""
    category: str = "custom"
    favorite: bool = False
    compatible_resolve_version: str | None = None
    sha256: str = ""
    expected_node_count: int | None = Field(default=None, ge=1)
    validation_status: Literal["unvalidated", "validated", "failed"] = "unvalidated"
    validated_at: str | None = None
