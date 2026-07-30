import json
from pathlib import Path

import pytest

from resolve.errors import ValidationError
from resolve.lut.generator import generate_artifacts, generate_cube_bytes
from resolve.lut.model import GradeProfile
from resolve.lut.validator import parse_cube_bytes, validate_lut


def profile(**overrides: object) -> GradeProfile:
    values = {
        "name": "VALIDATOR_TEST_V1",
        "description": "Validator test",
        "cube_size": 17,
    }
    values.update(overrides)
    return GradeProfile.model_validate(values)


def test_valid_cube_and_metadata(tmp_path: Path) -> None:
    result = generate_artifacts(profile(exposure_stops=0.1), tmp_path)
    validation = validate_lut(
        Path(result["cube_path"]), Path(result["metadata_path"]), require_metadata=True
    )
    assert validation.valid
    assert validation.details["row_count"] == 17**3


@pytest.mark.parametrize(
    "mutate",
    [
        lambda text: text.replace("TITLE", "NO_TITLE", 1),
        lambda text: text.replace("LUT_3D_SIZE 17", "LUT_3D_SIZE 18", 1),
        lambda text: "\n".join(text.splitlines()[:-1]) + "\n",
        lambda text: text.replace("0.000000000", "nan", 1),
        lambda text: text.replace("0.000000000", "inf", 1),
        lambda text: text.replace("0.000000000", "2.000000000", 1),
        lambda text: text.replace("0.000000000 0.000000000 0.000000000", "bad", 1),
    ],
)
def test_corrupt_cube_rejected(mutate) -> None:
    text = generate_cube_bytes(profile()).decode()
    with pytest.raises((ValidationError, ValueError)):
        parse_cube_bytes(mutate(text).encode())


def test_metadata_hash_and_profile_mismatch(tmp_path: Path) -> None:
    result = generate_artifacts(profile(), tmp_path)
    metadata_path = Path(result["metadata_path"])
    metadata = json.loads(metadata_path.read_text())
    metadata["sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata))
    validation = validate_lut(Path(result["cube_path"]), metadata_path)
    assert not validation.valid
    assert "SHA-256" in validation.errors[0]


def test_identity_warning_and_nonmonotonic_neutral_rejection(tmp_path: Path) -> None:
    result = generate_artifacts(profile(), tmp_path)
    validation = validate_lut(Path(result["cube_path"]))
    assert "Identity LUT" in validation.warnings
    lines = Path(result["cube_path"]).read_text().splitlines()
    size = 17
    offset = 4 + 8 * size * size + 8 * size + 8
    lines[offset] = "0.900000000 0.900000000 0.900000000"
    next_offset = 4 + 9 * size * size + 9 * size + 9
    lines[next_offset] = "0.100000000 0.100000000 0.100000000"
    Path(result["cube_path"]).write_text("\n".join(lines) + "\n")
    assert not validate_lut(Path(result["cube_path"])).valid
