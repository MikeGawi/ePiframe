"""Smoke test of the real service (``ePiframe_service.py``) in an isolated frame."""

import json
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import requests
from PIL import Image

from tests.smoke.conftest import REPOSITORY, Frame, needs_imagemagick
from tests.smoke.test_display import WAIT, fake_viewer
from tests.smoke.test_display import wait_for as wait_for_file
from tests.smoke.test_webui import free_port, wait_for

NEVER = ",".join(["-"] * 7)  # no working hours: only triggers change the photo


@needs_imagemagick
def test_service_changes_the_photo_on_request_and_stops(frame: Frame) -> None:
    shown = fake_viewer(frame)
    frame.add_photo("a.jpg", "red", 1_600_000_000)
    port = free_port()
    frame.configure(
        use_web="1",
        web_host="127.0.0.1",
        web_port=str(port),
        start_times=NEVER,
        stop_times=NEVER,
        allow_triggers="1",
        control_display_power="0",  # not the machine's screen
    )
    service = subprocess.Popen(
        [sys.executable, str(REPOSITORY / "ePiframe_service.py")],
        cwd=frame.directory,
        env=frame.environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for(f"http://127.0.0.1:{port}/")
        action = requests.get(f"http://127.0.0.1:{port}/api/action=next", timeout=5)
        wait_for_file(shown)
    finally:
        service.send_signal(signal.SIGTERM)
        output, _ = service.communicate(timeout=60)

    assert service.returncode == 0, output
    assert action.json() == {"status": "OK"}
    # not a terminal: everything goes to the log file only
    assert output == ""
    log = (frame.directory / "logs" / "ePiframe.log").read_text()
    assert "ePiframe Service: STARTED" in log
    assert "ePiframe Service: Activity triggered" in log
    # the lines of the update (epiframe) are written by the service
    assert "Sending to display..." in log
    assert log.rstrip().endswith("ePiframe Service: STOPPED")


def test_service_help(frame: Frame) -> None:
    result = subprocess.run(
        [sys.executable, str(REPOSITORY / "ePiframe_service.py"), "--help"],
        cwd=frame.directory,
        env=frame.environment(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0
    assert "{web,telegram}" in result.stdout
    assert "systemctl" in result.stdout


def pixel(path: Path, place: tuple[int, int]) -> object:
    try:
        with Image.open(path) as image:
            return image.convert("RGB").getpixel(place)
    except OSError:  # not there yet, or being replaced
        return None


def wait_until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT
    while not condition():
        assert time.monotonic() < deadline, f"no {what}"
        time.sleep(0.1)


@needs_imagemagick
def test_service_shows_the_error_icon(frame: Frame) -> None:
    shown = fake_viewer(frame)
    photo = frame.add_photo("a.jpg", "red", 1_600_000_000)
    port = free_port()
    frame.configure(
        use_web="1",
        web_host="127.0.0.1",
        web_port=str(port),
        start_times=NEVER,
        stop_times=NEVER,
        allow_triggers="1",
        control_display_power="0",
        busy_icon="1",
        error_icon="1",
        icons_position="0",
        icons_size="32",
    )
    state = frame.directory / "display.json"
    service = subprocess.Popen(
        [sys.executable, str(REPOSITORY / "ePiframe_service.py")],
        cwd=frame.directory,
        env=frame.environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for(f"http://127.0.0.1:{port}/")
        requests.get(f"http://127.0.0.1:{port}/api/action=next", timeout=5)
        wait_until((frame.directory / "display_frame.png").exists, "photo")
        photo.unlink()  # the next update fails: no photos
        requests.get(f"http://127.0.0.1:{port}/api/action=next", timeout=5)
        wait_until(
            lambda: (
                state.exists() and json.loads(state.read_text())["shown"] == ["error"]
            ),
            "error icon",
        )
    finally:
        service.send_signal(signal.SIGTERM)
        output, _ = service.communicate(timeout=60)

    assert service.returncode == 0, output
    # the ring on the left edge of the icon (margin 10), white inside, the photo
    # (red, white bars at the sides) around
    assert pixel(shown, (26, 14)) == (255, 255, 255)
    assert pixel(shown, (100, 26)) == (255, 0, 0)
