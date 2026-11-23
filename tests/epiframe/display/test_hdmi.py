import logging
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from epiframe.display import hdmi
from epiframe.display.base import Capability, DisplayError
from epiframe.display.hdmi import HdmiDisplay, HdmiPower


def executable(path: Path, script: str) -> str:
    path.write_text(f"#!/bin/sh\n{script}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_show_runs_viewer(tmp_path: Path, mocker: MockerFixture) -> None:
    run = mocker.patch.object(subprocess, "run")
    popen = mocker.patch.object(subprocess, "Popen")

    display = HdmiDisplay("/usr/bin/fbi", 2)
    display.show(tmp_path / "photo.bmp")

    assert display.capabilities == {Capability.FULL}
    assert run.call_args.args[0] == ["pkill", "-KILL", "-x", "fbi"]
    assert popen.call_args.args[0] == [
        "/usr/bin/fbi",
        "-vt",
        "2",
        "-noverbose",
        "-a",
        str(tmp_path / "photo.bmp"),
    ]
    assert popen.call_args.kwargs["start_new_session"] is True


def test_show_with_real_process(tmp_path: Path) -> None:
    shown = tmp_path / "shown"
    # unique name: pkill stops every process of that name
    viewer = executable(tmp_path / "epiframe-viewer", f'echo "$@" > {shown}')

    HdmiDisplay(viewer, 1).show(tmp_path / "photo.bmp")

    for _ in range(200):
        if shown.exists() and shown.read_text():
            break
        time.sleep(0.01)
    assert shown.read_text().split() == [
        "-vt",
        "1",
        "-noverbose",
        "-a",
        str(tmp_path / "photo.bmp"),
    ]


def test_show_missing_viewer(tmp_path: Path) -> None:
    with pytest.raises(DisplayError, match=r"Can't start .*missing"):
        HdmiDisplay(str(tmp_path / "missing"), 1).show(tmp_path / "photo.bmp")


def test_long_viewer_name_is_cut_for_pkill(mocker: MockerFixture) -> None:
    run = mocker.patch.object(subprocess, "run")
    mocker.patch.object(subprocess, "Popen")

    HdmiDisplay("/opt/a-very-long-viewer-name", 1).show("photo.bmp")

    assert run.call_args.args[0][-1] == "a-very-long-vie"


@pytest.fixture
def blank(tmp_path: Path) -> Path:
    return tmp_path / "blank"


@pytest.fixture
def vcgencmd(tmp_path: Path) -> tuple[str, Path]:
    """A fake vcgencmd: remembers the arguments, prints the stored state."""
    calls = tmp_path / "calls"
    state = tmp_path / "state"
    state.write_text("1")
    script = (
        f'echo "$@" >> {calls}\n'
        f'if [ -n "$2" ]; then echo "$2" > {state}; fi\n'
        f'echo "display_power=$(cat {state})"'
    )
    return executable(tmp_path / "vcgencmd", script), calls


def test_power_with_vcgencmd(vcgencmd: tuple[str, Path], blank: Path) -> None:
    command, calls = vcgencmd
    power = HdmiPower(command, blank)

    assert power.state() is True
    power.set(False)
    assert power.state() is False
    power.set(True)

    assert power.state() is True
    assert calls.read_text().splitlines() == [
        "display_power",
        "display_power 0",
        "display_power",
        "display_power 1",
        "display_power",
    ]
    assert blank.read_text() == hdmi.UNBLANK


def test_power_with_framebuffer_only(blank: Path, mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value=None)
    power = HdmiPower(blank=blank)

    assert power.state() is None
    power.set(False)

    assert blank.read_text() == hdmi.POWERDOWN
    assert power.state() is False


def test_power_vcgencmd_without_state_under_kms(tmp_path: Path, blank: Path) -> None:
    # under KMS vcgencmd answers, but doesn't know the state
    command = executable(tmp_path / "vcgencmd", 'echo "display_power=-1"')
    power = HdmiPower(command, blank)

    assert power.state() is None
    power.set(True)
    assert power.state() is True


def test_power_nothing_works(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="epiframe")
    power = HdmiPower(str(tmp_path / "missing"), tmp_path / "no" / "blank")

    power.set(False)

    assert power.state() is False
    assert "vcgencmd failed" in caplog.text
    assert "Framebuffer blanking not available" in caplog.text


def test_power_vcgencmd_timeout(blank: Path, mocker: MockerFixture) -> None:
    def timeout(*_args: Any, **_kwargs: Any) -> None:
        raise subprocess.TimeoutExpired("vcgencmd", hdmi.COMMAND_TIMEOUT)

    mocker.patch.object(subprocess, "run", timeout)

    assert HdmiPower("vcgencmd", blank).state() is None
