import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import ClassVar

import pytest

from epiframe.core.logs import CONSOLE_ONLY_ENV
from epiframe.service import refresh
from epiframe.service.refresh import Refresher, copy_output

SCRIPT = f"""
import os, sys
print("2026-11-25 12:00:00 : Getting next photo...")
print("console only:", os.environ.get("{CONSOLE_ONLY_ENV}"))
print("arguments:", sys.argv[1:])
print("Traceback (most recent call last):", file=sys.stderr)
sys.exit(int(os.environ.get("EXIT_CODE", "0")))
"""


MODULE = "fake_update"


@pytest.fixture(autouse=True)
def script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The module ``MODULE`` (importable by the child process)."""
    path = tmp_path / f"{MODULE}.py"
    path.write_text(SCRIPT)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    return path


@pytest.fixture(autouse=True)
def info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="epiframe")


class RecordedThread(threading.Thread):
    started: ClassVar[list[threading.Thread]] = []

    def start(self) -> None:
        RecordedThread.started.append(self)
        super().start()


@pytest.fixture(autouse=True)
def threads(monkeypatch: pytest.MonkeyPatch) -> list[threading.Thread]:
    RecordedThread.started = []
    monkeypatch.setattr(refresh, "Thread", RecordedThread)
    return RecordedThread.started


def wait_for_end(
    process: subprocess.Popen[str] | None, threads: list[threading.Thread]
) -> None:
    """Wait until the output thread has logged everything."""
    assert process is not None
    (thread,) = threads
    thread.join(timeout=30)
    assert not thread.is_alive()
    assert thread.daemon


def test_defaults() -> None:
    refresher = Refresher()

    assert refresher.module == refresh.MODULE == "epiframe"
    assert refresher.python == sys.executable


def test_command() -> None:
    refresher = Refresher("python3")

    # -P: the working directory is not on the import path
    assert refresher.command(("redisplay",)) == [
        "python3",
        "-P",
        "-m",
        "epiframe",
        "redisplay",
    ]


def test_output_goes_to_the_log(
    caplog: pytest.LogCaptureFixture, threads: list[threading.Thread]
) -> None:
    process = Refresher(module=MODULE).start(["redisplay"])
    wait_for_end(process, threads)

    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "2026-11-25 12:00:00 : Getting next photo...",
        "console only: 1",
        "arguments: ['redisplay']",
        "Traceback (most recent call last):",
    ]
    assert {record.name for record in caplog.records} == {"epiframe.service"}


def test_exit_code_is_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    threads: list[threading.Thread],
) -> None:
    monkeypatch.setenv("EXIT_CODE", "3")

    wait_for_end(Refresher(module=MODULE).start(), threads)

    assert caplog.records[-1].levelno == logging.WARNING
    assert caplog.records[-1].getMessage() == "ePiframe update ended with exit code 3"


def test_start_failure(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    process = Refresher(str(tmp_path / "no-python")).start()

    assert process is None
    assert "Can't start the ePiframe update: " in caplog.text


def test_copy_output_without_pipe(caplog: pytest.LogCaptureFixture) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL, text=True
    )

    copy_output(process)

    assert process.returncode == 0
    assert caplog.records == []
