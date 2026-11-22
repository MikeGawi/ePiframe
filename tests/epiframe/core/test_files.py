import os
from pathlib import Path

from epiframe.core.files import last_modified


def test_last_modified(tmp_path: Path) -> None:
    file = tmp_path / "file.txt"
    file.write_text("x")
    os.utime(file, (1_000_000, 2_000_000))
    assert last_modified(file) == 2_000_000
    assert last_modified(str(file)) == 2_000_000


def test_last_modified_missing_file(tmp_path: Path) -> None:
    assert last_modified(tmp_path / "missing.txt") is None
