from pathlib import Path

import pytest

from resolve.errors import OperationError, ValidationError
from resolve.setlut import (
    PROBE_SIZE,
    ImageDifference,
    generate_diagnostic_cube,
    mutate_with_restoration,
    require_owned_empty_node,
    require_setlut_readback,
    require_visible_difference,
    validate_cube,
)


def test_diagnostic_cube_is_deterministic_and_valid() -> None:
    first = generate_diagnostic_cube()
    second = generate_diagnostic_cube()
    assert first == second
    result = validate_cube(first)
    assert result["row_count"] == PROBE_SIZE**3
    assert result["minimum"] >= 0.0
    assert result["maximum"] <= 1.0


def test_invalid_cube_row_count_is_rejected() -> None:
    with pytest.raises(ValidationError, match="rows"):
        validate_cube(generate_diagnostic_cube().rsplit("\n", 2)[0] + "\n")


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_non_finite_cube_value_is_rejected(value: str) -> None:
    cube = generate_diagnostic_cube().replace("0.000000000", value, 1)
    with pytest.raises(ValidationError, match="non-finite"):
        validate_cube(cube)


def test_safe_node_ownership_and_existing_lut_protection() -> None:
    require_owned_empty_node(
        [{"index": 1, "label": "", "lut": "", "tools": []}], 1
    )
    with pytest.raises(OperationError, match="existing LUT"):
        require_owned_empty_node(
            [{"index": 1, "label": "", "lut": "user.cube", "tools": []}], 1
        )
    with pytest.raises(OperationError, match="not a validated empty"):
        require_owned_empty_node(
            [{"index": 1, "label": "User", "lut": "", "tools": []}], 1
        )


def test_setlut_false_positive_and_getlut_mismatch_are_rejected() -> None:
    with pytest.raises(OperationError, match="returned false"):
        require_setlut_readback(False, "probe.cube", "")
    with pytest.raises(OperationError, match="mismatch"):
        require_setlut_readback(True, "probe.cube", "other.cube")


def test_setlut_visible_false_positive_is_rejected() -> None:
    no_op = ImageDifference(
        "same", "same", (1920, 1080), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.0, 0.0, 0.0
    )
    with pytest.raises(OperationError, match="identical"):
        require_visible_difference(no_op)


@pytest.mark.parametrize("fail", [False, True])
def test_restoration_runs_after_success_or_error(fail: bool) -> None:
    events = []

    def mutate() -> str:
        events.append("mutate")
        if fail:
            raise RuntimeError("no-op or error")
        return "visible"

    def restore() -> None:
        events.append("restore")

    if fail:
        with pytest.raises(RuntimeError):
            mutate_with_restoration(mutate, restore)
    else:
        assert mutate_with_restoration(mutate, restore) == "visible"
    assert events == ["mutate", "restore"]


def test_fixture_path_is_not_required_for_generation(tmp_path: Path) -> None:
    path = tmp_path / "probe.cube"
    path.write_text(generate_diagnostic_cube())
    assert validate_cube(path.read_text())["row_count"] == 35937
