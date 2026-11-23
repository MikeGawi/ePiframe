"""Smoke tests of the last step: sending the photo to the display.

e-Paper displays need the SPI hardware, so the chain is checked with the HDMI
display and a fake ``fbi`` that copies the shown image to a file.
"""

import stat
import time
from pathlib import Path

from PIL import Image

from tests.smoke.conftest import Frame, needs_imagemagick

WAIT = 30  # seconds for the detached viewer to finish


def fake_viewer(frame: Frame) -> Path:
    """A viewer like ``fbi -vt <tty> -noverbose -a <image>``: copies the image."""
    # unique name: the display stops running viewers by name (pkill)
    viewer = frame.directory / "epiframe-fbi"
    viewer.write_text(
        "#!/bin/sh\n"
        f'echo "$@" > "{frame.directory}/viewer.args"\n'
        f'cp "$5" "{frame.directory}/shown.tmp"\n'
        f'mv "{frame.directory}/shown.tmp" "{frame.directory}/shown.bmp"\n'
    )
    viewer.chmod(viewer.stat().st_mode | stat.S_IXUSR)
    frame.configure(display_type="HDMI", fbi_bin_path=str(viewer), tty="3")
    return frame.directory / "shown.bmp"


def wait_for(path: Path) -> Path:
    deadline = time.monotonic() + WAIT
    while not path.exists():
        assert time.monotonic() < deadline, f"{path} was not created"
        time.sleep(0.1)
    return path


@needs_imagemagick
def test_photo_is_sent_to_display(frame: Frame) -> None:
    shown = fake_viewer(frame)
    frame.add_photo("a.jpg", "red", 1_600_000_000)

    result = frame.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Sending to display..." in result.stdout
    with Image.open(wait_for(shown)) as image:
        assert image.size == (800, 480)
    arguments = (frame.directory / "viewer.args").read_text().split()
    assert arguments == ["-vt", "3", "-noverbose", "-a", "./photo.bmp"]


def test_test_display_shows_given_file(frame: Frame) -> None:
    shown = fake_viewer(frame)
    image = frame.add_photo("ready.bmp", "blue", 1_600_000_000)

    result = frame.run("--test-display", str(image))

    assert result.returncode == 0, result.stdout + result.stderr
    assert wait_for(shown).read_bytes() == image.read_bytes()


def test_display_error_is_reported(frame: Frame) -> None:
    not_executable = frame.directory / "fbi"
    not_executable.write_text("")
    frame.configure(display_type="HDMI", fbi_bin_path=str(not_executable))
    image = frame.add_photo("ready.bmp", "blue", 1_600_000_000)

    result = frame.run("--test-display", str(image))

    assert result.returncode != 0
    assert "Error sending photo to display: Can't start" in result.stdout
