"""Strongly typed LUT profile schema."""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ColorSpace = Literal["rec709_gamma24"]
WorkingSpace = Literal["linear_rec709"]


class GradeProfile(BaseModel):
    """Versioned controls for a display-referred Rec.709 global treatment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    input_color_space: ColorSpace = "rec709_gamma24"
    output_color_space: ColorSpace = "rec709_gamma24"
    working_space: WorkingSpace = "linear_rec709"
    cube_size: Literal[17, 33, 65] = 33
    exposure_stops: float = Field(default=0.0, ge=-2.0, le=2.0)
    temperature: float = Field(default=0.0, ge=-0.1, le=0.1)
    tint: float = Field(default=0.0, ge=-0.1, le=0.1)
    contrast: float = Field(default=1.0, ge=0.5, le=1.5)
    pivot: float = Field(default=0.5, gt=0.0, lt=1.0)
    toe_strength: float = Field(default=0.0, ge=0.0, le=0.5)
    shoulder_strength: float = Field(default=0.0, ge=0.0, le=0.5)
    saturation: float = Field(default=1.0, ge=0.0, le=2.0)
    shadow_saturation: float = Field(default=1.0, ge=0.0, le=2.0)
    highlight_saturation: float = Field(default=1.0, ge=0.0, le=2.0)
    teal_preservation: float = Field(default=0.0, ge=0.0, le=0.2)
    magenta_preservation: float = Field(default=0.0, ge=0.0, le=0.2)
    gold_warmth: float = Field(default=0.0, ge=0.0, le=0.2)
    gamut_compression: float = Field(default=0.0, ge=0.0, le=1.0)
    black_floor: float = Field(default=0.0, ge=0.0, le=0.1)
    white_ceiling: float = Field(default=1.0, ge=0.9, le=1.0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
            raise ValueError("name must be uppercase ASCII with underscores")
        return value

    @field_validator(
        "exposure_stops",
        "temperature",
        "tint",
        "contrast",
        "pivot",
        "toe_strength",
        "shoulder_strength",
        "saturation",
        "shadow_saturation",
        "highlight_saturation",
        "teal_preservation",
        "magenta_preservation",
        "gold_warmth",
        "gamut_compression",
        "black_floor",
        "white_ceiling",
    )
    @classmethod
    def finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("profile values must be finite")
        return value

    @model_validator(mode="after")
    def valid_bounds(self) -> GradeProfile:
        if self.black_floor >= self.white_ceiling:
            raise ValueError("black_floor must be below white_ceiling")
        return self

    @property
    def logical_version(self) -> int:
        match = re.search(r"_V(\d+)$", self.name)
        return int(match.group(1)) if match else 1

    @property
    def filename_stem(self) -> str:
        return f"{self.name}__v{self.logical_version}__{self.cube_size}"
