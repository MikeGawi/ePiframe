"""Smoke test of the real service (``ePiframe_service.py``) in an isolated frame."""

import signal
import subprocess
import sys

import requests

from tests.smoke.conftest import REPOSITORY, Frame, needs_imagemagick
from tests.smoke.test_display import fake_viewer
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
    # the lines of ePiframe.py are written by the service
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
