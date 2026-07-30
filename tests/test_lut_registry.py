import json
from pathlib import Path

import pytest

from resolve.errors import ValidationError
from resolve.lut.generator import generate_artifacts
from resolve.lut.model import GradeProfile
from resolve.lut.registry import LutRegistry


def artifacts(
    tmp_path: Path, name: str = "REGISTRY_V1", exposure: float = 0.0
) -> dict[str, object]:
    profile = GradeProfile(
        name=name, description="Registry", cube_size=17, exposure_stops=exposure
    )
    return generate_artifacts(profile, tmp_path / name)


def test_register_duplicate_state_and_deprecation(tmp_path: Path) -> None:
    result = artifacts(tmp_path)
    registry = LutRegistry(tmp_path / "registry.json")
    registered = registry.register(
        Path(result["cube_path"]), Path(result["metadata_path"])  # type: ignore[arg-type]
    )
    assert registered["status"] == "registered"
    duplicate = registry.register(
        Path(result["cube_path"]), Path(result["metadata_path"])  # type: ignore[arg-type]
    )
    assert duplicate["status"] == "already_registered"
    assert registry.set_state("REGISTRY_V1", "enabled")["approval_state"] == "enabled"
    assert (
        registry.set_state("REGISTRY_V1", "deprecated")["approval_state"]
        == "deprecated"
    )


def test_name_and_hash_conflicts(tmp_path: Path) -> None:
    result = artifacts(tmp_path)
    registry = LutRegistry(tmp_path / "registry.json")
    registry.register(
        Path(result["cube_path"]), Path(result["metadata_path"])  # type: ignore[arg-type]
    )
    changed = artifacts(tmp_path / "changed", exposure=0.1)
    metadata_path = Path(changed["metadata_path"])  # type: ignore[arg-type]
    metadata = json.loads(metadata_path.read_text())
    metadata["profile_name"] = "REGISTRY_V1"
    metadata["parameters"]["name"] = "REGISTRY_V1"
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValidationError, match="conflict"):
        registry.register(Path(changed["cube_path"]), metadata_path)  # type: ignore[arg-type]

    registry_rows = json.loads((tmp_path / "registry.json").read_text())
    registry_rows[0]["profile_name"] = "OTHER_V1"
    (tmp_path / "registry.json").write_text(json.dumps(registry_rows))
    with pytest.raises(ValidationError, match="Hash conflict"):
        registry.register(
            Path(result["cube_path"]), Path(result["metadata_path"])  # type: ignore[arg-type]
        )


def test_unsupported_metadata_schema(tmp_path: Path) -> None:
    result = artifacts(tmp_path)
    metadata_path = Path(result["metadata_path"])  # type: ignore[arg-type]
    metadata = json.loads(metadata_path.read_text())
    metadata["parameters"]["schema_version"] = 2
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValidationError):
        LutRegistry(tmp_path / "registry.json").register(
            Path(result["cube_path"]), metadata_path  # type: ignore[arg-type]
        )
