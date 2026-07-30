import hashlib
from pathlib import Path

import pytest

from resolve.errors import OperationError, ValidationError
from resolve.lut.installer import LutInstaller, resolve_lut_root


def test_platform_paths() -> None:
    assert "DaVinci Resolve/LUT" in str(resolve_lut_root("Darwin", Path("/Users/a")))
    assert "ProgramData" in str(
        resolve_lut_root("Windows", Path("C:/Users/a"), Path("C:/ProgramData"))
    )


def test_atomic_install_identical_and_conflict(tmp_path: Path) -> None:
    source = tmp_path / "look.cube"
    source.write_bytes(b"cube")
    digest = hashlib.sha256(b"cube").hexdigest()
    installer = LutInstaller(tmp_path / "resolve-lut")
    dry = installer.install(source, digest, dry_run=True)
    assert dry["status"] == "dry_run"
    result = installer.install(source, digest)
    assert result["status"] == "installed"
    assert installer.install(source, digest)["status"] == "already_installed"
    Path(result["destination"]).write_bytes(b"user content")
    with pytest.raises(ValidationError, match="overwrite"):
        installer.install(source, digest)


def test_hash_and_refresh_failures(tmp_path: Path) -> None:
    source = tmp_path / "look.cube"
    source.write_bytes(b"cube")
    with pytest.raises(ValidationError, match="SHA-256"):
        LutInstaller(tmp_path / "lut").install(source, "bad")

    class Project:
        def RefreshLUTList(self) -> bool:
            return False

    with pytest.raises(OperationError, match="returned false"):
        LutInstaller.refresh(Project())
