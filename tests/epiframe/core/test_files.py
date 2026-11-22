import os
import stat
from pathlib import Path

import pytest

from epiframe.core.files import last_modified, write_text_atomic


def test_last_modified(tmp_path: Path) -> None:
    file = tmp_path / "file.txt"
    file.write_text("x")
    os.utime(file, (1_000_000, 2_000_000))
    assert last_modified(file) == 2_000_000
    assert last_modified(str(file)) == 2_000_000


def test_last_modified_missing_file(tmp_path: Path) -> None:
    assert last_modified(tmp_path / "missing.txt") is None


def test_write_text_atomic_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "new.txt"

    write_text_atomic(target, "content")

    assert target.read_text() == "content"
    assert [path.name for path in tmp_path.iterdir()] == ["new.txt"]


def test_write_text_atomic_keeps_mode(tmp_path: Path) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("old")
    target.chmod(0o640)

    write_text_atomic(str(target), "new")

    assert target.read_text() == "new"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_write_text_atomic_failure_keeps_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("old")

    def broken_replace(source: str, destination: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken_replace)
    with pytest.raises(OSError, match="disk full"):
        write_text_atomic(target, "new")

    assert target.read_text() == "old"
    assert [path.name for path in tmp_path.iterdir()] == ["existing.txt"]
