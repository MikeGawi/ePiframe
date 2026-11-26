import os
import signal
from pathlib import Path

import pytest

from epiframe.update.lock import is_update, stop_previous, update_lock

OTHER_PID = 4242


@pytest.mark.parametrize(
    "command",
    [
        "python3 ./ePiframe.py",
        "/usr/bin/python3 /home/pi/ePiframe/ePiframe.py test",
        "/opt/epiframe/venv/bin/python /opt/epiframe/venv/bin/epiframe",
        "/usr/bin/python3 -P -m epiframe redisplay",
    ],
)
def test_is_update(command: str) -> None:
    assert is_update(command)


@pytest.mark.parametrize(
    "command",
    [
        "python3 ./ePiframe_service.py",
        "/venv/bin/python /venv/bin/epiframe service",
        "vim /home/pi/ePiframe/config.cfg",
        "",
    ],
)
def test_is_not_update(command: str) -> None:
    assert not is_update(command)


def write_command(proc_dir: Path, pid: int, *arguments: str) -> None:
    (proc_dir / str(pid)).mkdir(parents=True)
    (proc_dir / str(pid) / "cmdline").write_bytes(
        b"\0".join(argument.encode() for argument in arguments) + b"\0"
    )


@pytest.fixture
def kills(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, number: killed.append((pid, number)))
    return killed


def test_previous_update_is_stopped(
    tmp_path: Path, kills: list[tuple[int, int]], caplog: pytest.LogCaptureFixture
) -> None:
    write_command(tmp_path, OTHER_PID, "python3", "./ePiframe.py")

    stop_previous(OTHER_PID, tmp_path)

    assert kills == [(OTHER_PID, signal.SIGKILL)]
    assert f"Stopping previous ePiframe run (PID {OTHER_PID})" in caplog.text


@pytest.mark.parametrize("pid", [OTHER_PID, os.getpid()])
def test_other_processes_are_not_stopped(
    tmp_path: Path, kills: list[tuple[int, int]], pid: int
) -> None:
    write_command(tmp_path, OTHER_PID, "vim", "notes.txt")
    write_command(tmp_path, os.getpid(), "python3", "-m", "epiframe")

    stop_previous(pid, tmp_path)

    assert kills == []


def test_finished_process_is_not_stopped(
    tmp_path: Path, kills: list[tuple[int, int]]
) -> None:
    stop_previous(OTHER_PID, tmp_path)

    assert kills == []


def test_process_ended_meanwhile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_command(tmp_path, OTHER_PID, "epiframe")

    def gone(pid: int, number: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr(os, "kill", gone)

    stop_previous(OTHER_PID, tmp_path)  # no error


def test_lock_holds_the_pid_file(tmp_path: Path, kills: list[tuple[int, int]]) -> None:
    pid_file = tmp_path / "pid"

    with update_lock(pid_file, tmp_path):
        assert pid_file.read_text() == str(os.getpid())

    assert not pid_file.exists()
    assert kills == []


def test_lock_stops_the_previous_update(
    tmp_path: Path, kills: list[tuple[int, int]]
) -> None:
    pid_file = tmp_path / "pid"
    pid_file.write_text(str(OTHER_PID))
    write_command(tmp_path, OTHER_PID, "epiframe")

    with update_lock(pid_file, tmp_path):
        assert pid_file.read_text() == str(os.getpid())

    assert kills == [(OTHER_PID, signal.SIGKILL)]


def test_lock_is_released_on_error(tmp_path: Path) -> None:
    pid_file = tmp_path / "pid"

    with pytest.raises(RuntimeError), update_lock(pid_file, tmp_path):
        raise RuntimeError

    assert not pid_file.exists()


def test_newer_update_keeps_its_pid_file(tmp_path: Path) -> None:
    pid_file = tmp_path / "pid"

    with update_lock(pid_file, tmp_path):
        pid_file.write_text(str(OTHER_PID))  # a newer update stopped this one

    assert pid_file.read_text() == str(OTHER_PID)
