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
    assert arguments == ["-vt", "3", "-noverbose", "-a", "photo.bmp"]


def test_test_display_shows_given_file(frame: Frame) -> None:
    shown = fake_viewer(frame)
    image = frame.add_photo("ready.bmp", "blue", 1_600_000_000)

    result = frame.run("test-display", str(image))

    assert result.returncode == 0, result.stdout + result.stderr
    assert wait_for(shown).read_bytes() == image.read_bytes()


def test_display_error_is_reported(frame: Frame) -> None:
    not_executable = frame.directory / "fbi"
    not_executable.write_text("")
    frame.configure(display_type="HDMI", fbi_bin_path=str(not_executable))
    image = frame.add_photo("ready.bmp", "blue", 1_600_000_000)

    result = frame.run("test-display", str(image))

    assert result.returncode != 0
    assert "Error sending photo to display: Can't start" in result.stdout


@needs_imagemagick
def test_redisplay_shows_the_uploaded_photo(frame: Frame) -> None:
    shown = fake_viewer(frame)
    # a photo uploaded in the WebUI is saved as the original photo
    Image.new("RGB", (64, 48), "green").save(frame.directory / "origphoto.png")

    result = frame.run("redisplay")

    assert result.returncode == 0, result.stdout + result.stderr
    with Image.open(wait_for(shown)) as image:
        assert image.size == (800, 480)
    assert not (frame.directory / "pid").exists()


def test_photo_without_conversion_is_shown_as_is(frame: Frame) -> None:
    shown = fake_viewer(frame)
    # converted in advance (epiframe convert); 1.x never showed it
    photo = frame.add_photo("ready.bmp", "blue", 1_600_000_000)
    frame.configure(convert="0")

    result = frame.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Conversion disabled by the 'convert' setting" in result.stdout
    assert wait_for(shown).read_bytes() == photo.read_bytes()


@needs_imagemagick
def test_prepare_converts_without_showing(frame: Frame) -> None:
    shown = fake_viewer(frame)
    frame.add_photo("a.jpg", "red", 1_600_000_000)

    result = frame.run("prepare")

    # the service shows the photo of its update: the update never touches the display
    assert result.returncode == 0, result.stdout + result.stderr
    with Image.open(frame.directory / "photo.bmp") as image:
        assert image.size == (800, 480)
    assert "Sending to display..." not in result.stdout
    time.sleep(1)  # a detached viewer would have copied the image by now
    assert not shown.exists()


@needs_imagemagick
def test_prepare_again_converts_the_original(frame: Frame) -> None:
    fake_viewer(frame)
    Image.new("RGB", (64, 48), "green").save(frame.directory / "origphoto.png")

    result = frame.run("prepare", "--again")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (frame.directory / "photo.bmp").exists()
    assert "Sending to display..." not in result.stdout


def test_display_lock_is_in_the_data_folder(frame: Frame) -> None:
    fake_viewer(frame)
    image = frame.add_photo("ready.bmp", "blue", 1_600_000_000)

    result = frame.run("test-display", str(image))

    assert result.returncode == 0, result.stdout + result.stderr
    assert (frame.directory / "display.lock").exists()
