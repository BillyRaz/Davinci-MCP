import math

import pytest
from pydantic import ValidationError

from resolve.lut.model import GradeProfile


def profile(**overrides: object) -> GradeProfile:
    values = {
        "name": "TEST_PROFILE_V1",
        "description": "Test profile",
    }
    values.update(overrides)
    return GradeProfile.model_validate(values)


def test_valid_profile_and_filename() -> None:
    value = profile()
    assert value.schema_version == 1
    assert value.filename_stem == "TEST_PROFILE_V1__v1__33"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", 2),
        ("cube_size", 18),
        ("input_color_space", "logc"),
        ("contrast", 3.0),
        ("unknown", 1),
    ],
)
def test_invalid_and_unknown_profile_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        profile(**{field: value})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_rejected(value: float) -> None:
    with pytest.raises(ValidationError):
        profile(exposure_stops=value)


def test_schema_migration_is_explicitly_not_silent() -> None:
    with pytest.raises(ValidationError):
        profile(schema_version=0)
