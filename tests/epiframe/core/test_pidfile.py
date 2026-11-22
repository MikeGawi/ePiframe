import os
import sys
from pathlib import Path

import pytest

from epiframe.core.pidfile import PidFile, process_command


@pytest.fixture
def pid_file(tmp_path: Path) -> PidFile:
    return PidFile(tmp_path / "pid")


def test_init_does_not_create_file(pid_file: PidFile) -> None:
    assert pid_file.pid == os.getpid()
    assert not pid_file.path.exists()


def test_read_missing(pid_file: PidFile) -> None:
    assert pid_file.read() is None


def test_write_and_read(pid_file: PidFile) -> None:
    pid_file.write()

    assert pid_file.path.read_text() == str(os.getpid())
    assert PidFile(pid_file.path).read() == os.getpid()


def test_read_with_newline(pid_file: PidFile) -> None:
    pid_file.path.write_text("1234\n")

    assert pid_file.read() == 1234


def test_corrupted_file_is_removed(pid_file: PidFile) -> None:
    pid_file.path.write_text("not a pid")

    assert pid_file.read() is None
    assert not pid_file.path.exists()


def test_remove(pid_file: PidFile) -> None:
    pid_file.write()
    pid_file.remove()
    pid_file.remove()  # missing file is fine

    assert not pid_file.path.exists()


def test_process_command(tmp_path: Path) -> None:
    (tmp_path / "42").mkdir()
    (tmp_path / "42" / "cmdline").write_bytes(b"python3\0./ePiframe.py\0--test\0")

    assert process_command(42, tmp_path) == "python3 ./ePiframe.py --test"
    assert process_command(43, tmp_path) is None


@pytest.mark.skipif(not Path("/proc/self").exists(), reason="needs /proc")
def test_process_command_of_this_process() -> None:
    command = process_command(os.getpid())

    assert command is not None
    # the interpreter may be started with a relative path, compare the binary name
    assert Path(command.split()[0]).name == Path(sys.executable).name
