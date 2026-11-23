import shutil
import sqlite3
from pathlib import Path

from PIL import Image

from tests.helpers.service_account import write_key
from tests.smoke.conftest import (
    DEFAULT_CONFIG,
    Frame,
    machine_independent_paths,
    needs_imagemagick,
)

DRIVE_FOLDER = "https://drive.google.com/drive/folders/1AbC-dEf_123456789"
# every HTTPS request fails at once (connection refused), as without network
OFFLINE = {"HTTPS_PROXY": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9"}

CONFIG_V1 = (
    Path(__file__).parents[1] / "epiframe" / "config" / "assets" / "config_v1.cfg"
)


def shown_photos(frame: Frame, runs: int, *arguments: str) -> list[str]:
    names = []
    for _ in range(runs):
        result = frame.run("--test", *arguments)
        assert result.returncode == 0, result.stdout + result.stderr
        line = next(line for line in result.stdout.splitlines() if "Photo(id=" in line)
        names.append(Path(line.split("'")[1]).name)
    return names


def test_help(frame: Frame) -> None:
    result = frame.run("--help")

    assert result.returncode == 0
    assert "--check-config" in result.stdout


def test_check_config_creates_default_config(tmp_path: Path) -> None:
    frame = Frame(tmp_path)

    result = frame.run("--check-config")

    # the result depends on the machine (ImageMagick, fbi), only the load is checked
    assert "Verifying configuration..." in result.stdout
    assert frame.config_file.read_text() == DEFAULT_CONFIG.read_text()


def test_check_config(frame: Frame) -> None:
    result = frame.run("--check-config")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK!" in result.stdout


def test_check_config_migrates_1x_config(frame: Frame) -> None:
    shutil.copyfile(CONFIG_V1, frame.config_file)
    frame.configure(**machine_independent_paths())

    result = frame.run("--check-config")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Obsolete configuration entries removed: use_google_photos" in result.stdout
    migrated = frame.config_file.read_text()
    assert "use_google_photos" not in migrated
    assert "photo_db_file=photos.db" in migrated


def test_check_config_reports_errors(frame: Frame) -> None:
    frame.configure(use_web="1", web_port="70000")

    result = frame.run("--check-config")

    assert result.returncode != 0
    assert "web_port configuration entry should be <= 65535" in result.stdout


def test_check_config_with_drive(frame: Frame) -> None:
    write_key(frame.directory / "drive_key.json")
    frame.configure(use_drive="1", drive_folders=DRIVE_FOLDER)

    result = frame.run("--check-config")

    assert result.returncode == 0, result.stdout + result.stderr


def test_check_config_reports_drive_errors(frame: Frame) -> None:
    frame.configure(use_drive="1", drive_folders="not a folder")

    result = frame.run("--check-config")

    assert result.returncode != 0
    assert "drive_folders configuration entry error" in result.stdout


def test_setup_drive(frame: Frame) -> None:
    # an unfinished Drive configuration doesn't block the setup
    frame.configure(use_drive="1")
    key = write_key(frame.directory / "downloaded.json")
    # skip the steps, the key, the folder; offline check fails: don't check
    # again, save anyway
    answers = f"n\n{key}\n{DRIVE_FOLDER}\nn\ny\n"

    result = frame.run("--setup-drive", env=OFFLINE, answers=answers)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "No connection to Google" in result.stdout
    config = frame.config_file.read_text()
    assert "drive_folders=1AbC-dEf_123456789" in config
    assert (frame.directory / "drive_key.json").read_text() == key.read_text()
    assert frame.run("--check-config").returncode == 0


def test_no_photos(frame: Frame) -> None:
    result = frame.run("--test")

    assert result.returncode == 1
    assert "No photos in sources!" in result.stdout


@needs_imagemagick
def test_full_chain_converts_photos_in_order(frame: Frame) -> None:
    frame.add_photo("b.jpg", "red", 1_700_000_000)
    frame.add_photo("2024/a.png", "green", 1_600_000_000)
    frame.add_photo("c.jpg", "blue", 1_650_000_000)
    frame.configure(sorting="asc")

    assert shown_photos(frame, 4) == ["a.png", "c.jpg", "b.jpg", "a.png"]

    converted = frame.directory / "photo.bmp"
    with Image.open(converted) as image:
        assert image.size == (800, 480)
    with sqlite3.connect(frame.directory / "photos.db") as database:
        assert database.execute("SELECT COUNT(*) FROM photos").fetchone() == (3,)


@needs_imagemagick
def test_new_photo_is_found_incrementally(frame: Frame) -> None:
    frame.add_photo("a.jpg", "red", 1_600_000_000)
    assert shown_photos(frame, 1) == ["a.jpg"]

    frame.add_photo("b.jpg", "blue", 1_700_000_000)
    result = frame.run("--test")

    assert "incremental scan" in result.stdout
    assert "Found 2 photos" in result.stdout


@needs_imagemagick
def test_drive_offline_still_shows_local_photos(frame: Frame) -> None:
    write_key(frame.directory / "drive_key.json")
    frame.configure(use_drive="1", drive_folders=DRIVE_FOLDER)
    frame.add_photo("a.jpg", "red", 1_600_000_000)

    result = frame.run("--test", env=OFFLINE)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Getting data from Google Drive source (as frame@" in result.stdout
    assert "Error getting data from Google Drive source" in result.stdout
    assert "Found 1 photos" in result.stdout


@needs_imagemagick
def test_random_cycle_shows_every_photo(frame: Frame) -> None:
    for number, color in enumerate(("red", "green", "blue")):
        frame.add_photo(f"{number}.jpg", color, 1_600_000_000 + number)
    frame.configure(randomize="1")

    assert sorted(shown_photos(frame, 3)) == ["0.jpg", "1.jpg", "2.jpg"]


@needs_imagemagick
def test_no_skip_keeps_the_current_photo(frame: Frame) -> None:
    frame.add_photo("a.jpg", "red", 1_600_000_000)
    frame.add_photo("b.jpg", "blue", 1_700_000_000)
    shown_photos(frame, 1)

    assert shown_photos(frame, 2, "--no-skip") == ["b.jpg", "b.jpg"]


@needs_imagemagick
def test_convert_command(frame: Frame) -> None:
    source = frame.add_photo("photo.jpg", "red", 1_600_000_000)
    target = frame.directory / "out"
    target.mkdir()

    result = frame.run("--convert", str(source), str(target))

    assert result.returncode == 0, result.stdout + result.stderr
    with Image.open(target / "photo.bmp") as image:
        assert image.size == (800, 480)
