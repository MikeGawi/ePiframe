import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from epiframe.core.logs import CONSOLE_ONLY_ENV
from epiframe.service import refresh
from epiframe.service.refresh import Refresher, copy_output, stop

SCRIPT = f"""
import os, sys, time
print("2026-11-25 12:00:00 : Getting next photo...")
print("console only:", os.environ.get("{CONSOLE_ONLY_ENV}"))
print("arguments:", sys.argv[1:])
print("Traceback (most recent call last):", file=sys.stderr)
try:
    time.sleep(float(os.environ.get("SLEEP", "0")))
except KeyboardInterrupt:
    print("cleaned up")
    sys.exit(130)
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


def messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records]


def test_defaults() -> None:
    refresher = Refresher()

    assert refresher.module == refresh.MODULE == "epiframe"
    assert refresher.python == sys.executable


def test_command() -> None:
    refresher = Refresher("python3")

    # -P: the working directory is not on the import path
    assert refresher.command(("prepare",)) == [
        "python3",
        "-P",
        "-m",
        "epiframe",
        "prepare",
    ]


def test_output_goes_to_the_log(caplog: pytest.LogCaptureFixture) -> None:
    code = Refresher(module=MODULE).run(["prepare"])

    assert code == 0
    # all lines are logged before run returns
    assert messages(caplog) == [
        "2026-11-25 12:00:00 : Getting next photo...",
        "console only: 1",
        "arguments: ['prepare']",
        "Traceback (most recent call last):",
    ]
    assert {record.name for record in caplog.records} == {"epiframe.service"}


def test_exit_code_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("EXIT_CODE", "3")

    assert Refresher(module=MODULE).run() == 3

    assert caplog.records[-1].levelno == logging.WARNING
    assert caplog.records[-1].getMessage() == "ePiframe update ended with exit code 3"


def test_hanging_update_is_stopped(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("SLEEP", "60")

    code = Refresher(module=MODULE).run(timeout=2)

    assert code == 130  # SIGINT: it could clean up
    assert "ePiframe update still running after 2 seconds: stopping it" in messages(
        caplog
    )
    assert "cleaned up" in messages(caplog)


def test_stop_kills_after_the_grace_period() -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal, time; signal.signal(signal.SIGINT, signal.SIG_IGN); "
            "print('ready', flush=True); time.sleep(60)",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stdout.readline() == "ready\n"

    assert stop(process, grace=0.2) == -9
    process.stdout.close()


def test_stop_from_another_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLEEP", "60")
    refresher = Refresher(module=MODULE)
    codes: list[int | None] = []
    runner = threading.Thread(target=lambda: codes.append(refresher.run()))
    runner.start()
    deadline = time.monotonic() + 30
    while refresher._process is None:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    time.sleep(0.5)  # the child installs its SIGINT handler

    refresher.stop()
    runner.join(30)

    assert codes == [130]
    assert refresher._process is None


def test_stop_without_update() -> None:
    Refresher().stop()  # nothing to stop


def test_start_failure(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    code = Refresher(str(tmp_path / "no-python")).run()

    assert code is None
    assert "Can't start the ePiframe update: " in caplog.text


def test_copy_output_without_pipe(caplog: pytest.LogCaptureFixture) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL, text=True
    )

    copy_output(process)

    assert process.wait() == 0
    assert caplog.records == []
