import hashlib
import json
from pathlib import Path

import pytest

from resolve.lut.generator import generate_artifacts, generate_cube_bytes
from resolve.lut.model import GradeProfile


def profile(size: int = 17, **overrides: object) -> GradeProfile:
    values = {
        "name": "GENERATOR_TEST_V1",
        "description": "Generator test",
        "cube_size": size,
    }
    values.update(overrides)
    return GradeProfile.model_validate(values)


@pytest.mark.parametrize("size", [17, 33])
def test_cube_sizes_row_count_and_determinism(size: int) -> None:
    value = generate_cube_bytes(profile(size))
    assert value == generate_cube_bytes(profile(size))
    assert b"\r" not in value
    assert len(value.splitlines()) == size**3 + 4
    assert hashlib.sha256(value).hexdigest() == hashlib.sha256(value).hexdigest()


def test_parameter_change_changes_hash() -> None:
    first = generate_cube_bytes(profile(exposure_stops=0))
    second = generate_cube_bytes(profile(exposure_stops=0.1))
    assert hashlib.sha256(first).digest() != hashlib.sha256(second).digest()


def test_artifact_metadata_and_conflict(tmp_path: Path) -> None:
    result = generate_artifacts(profile(), tmp_path, source_profile_path="profile.json")
    metadata = json.loads(Path(result["metadata_path"]).read_text())
    assert metadata["sha256"] == result["sha256"]
    assert metadata["parameters"]["name"] == "GENERATOR_TEST_V1"
    Path(result["cube_path"]).write_text("different")
    with pytest.raises(FileExistsError):
        generate_artifacts(profile(), tmp_path)
