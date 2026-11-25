import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest
from PIL import Image

from tests.helpers.service_account import write_key
from tests.smoke.conftest import (
    DEFAULT_CONFIG,
    REPOSITORY,
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
        result = frame.run("test", *arguments)
        assert result.returncode == 0, result.stdout + result.stderr
        line = next(line for line in result.stdout.splitlines() if "Photo(id=" in line)
        names.append(Path(line.split("'")[1]).name)
    return names


def test_help(frame: Frame) -> None:
    result = frame.run("--help")

    assert result.returncode == 0
    for command in ("check-config", "test", "setup-drive", "service"):
        assert command in result.stdout


def test_1x_option_is_refused(frame: Frame) -> None:
    result = frame.run("--test")

    assert result.returncode == 2
    assert "unrecognized arguments: --test" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        [sys.executable, str(REPOSITORY / "ePiframe.py")],
        [sys.executable, "-m", "epiframe"],
    ],
    ids=["ePiframe.py", "python -m epiframe"],
)
def test_other_entry_points(frame: Frame, command: list[str]) -> None:
    result = frame.run_command([*command, "--version"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("ePiframe v2.")


def test_no_banner_and_clean_config_error(frame: Frame) -> None:
    frame.configure(use_web="1", web_port="70000")

    result = frame.run("check-config")

    assert result.returncode == 1
    assert "Traceback" not in result.stdout + result.stderr  # 1.x printed one
    assert "e-Paper Raspberry Pi Photo Frame" not in result.stdout


def test_check_config_creates_default_config(tmp_path: Path) -> None:
    frame = Frame(tmp_path)

    result = frame.run("check-config")

    # the result depends on the machine (ImageMagick, fbi), only the load is checked
    assert "Verifying configuration..." in result.stdout
    assert frame.config_file.read_text() == DEFAULT_CONFIG.read_text()


def test_check_config(frame: Frame) -> None:
    result = frame.run("check-config")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK!" in result.stdout


def test_check_config_migrates_1x_config(frame: Frame) -> None:
    shutil.copyfile(CONFIG_V1, frame.config_file)
    frame.configure(**machine_independent_paths())

    result = frame.run("check-config")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Obsolete configuration entries removed: use_google_photos" in result.stdout
    migrated = frame.config_file.read_text()
    assert "use_google_photos" not in migrated
    assert "photo_db_file=photos.db" in migrated


def test_check_config_reports_errors(frame: Frame) -> None:
    frame.configure(use_web="1", web_port="70000")

    result = frame.run("check-config")

    assert result.returncode != 0
    assert "web_port configuration entry should be <= 65535" in result.stdout


def test_check_config_with_drive(frame: Frame) -> None:
    write_key(frame.directory / "drive_key.json")
    frame.configure(use_drive="1", drive_folders=DRIVE_FOLDER)

    result = frame.run("check-config")

    assert result.returncode == 0, result.stdout + result.stderr


def test_check_config_reports_drive_errors(frame: Frame) -> None:
    frame.configure(use_drive="1", drive_folders="not a folder")

    result = frame.run("check-config")

    assert result.returncode != 0
    assert "drive_folders configuration entry error" in result.stdout


def test_check_config_with_telegram_offline(frame: Frame) -> None:
    token = "123456:SECRET-token"  # noqa: S105 (fake)
    frame.configure(use_telebot="1", token=token)

    result = frame.run("check-config", env=OFFLINE)

    # no connection is a warning: the frame works, the bot starts when it can
    assert result.returncode == 0, result.stdout + result.stderr
    assert "token configuration entry error" in result.stdout
    assert "SECRET" not in result.stdout + result.stderr


def test_check_config_reports_malformed_telegram_token(frame: Frame) -> None:
    frame.configure(use_telebot="1", token="no-colon")  # noqa: S106 (fake)

    result = frame.run("check-config", env=OFFLINE)

    assert result.returncode != 0
    assert "Token must contain a colon" in result.stdout


def test_telegram_test_offline(frame: Frame) -> None:
    token = "123456:SECRET-token"  # noqa: S105 (fake)

    result = frame.run("test-telegram", env=OFFLINE, answers=f"{token}\n")

    assert result.returncode == 1
    assert "Connecting to Telegram..." in result.stdout
    assert "Error: " in result.stdout
    assert "SECRET" not in result.stdout + result.stderr


def test_weather_test_offline(frame: Frame) -> None:
    result = frame.run(
        "test-weather", env=OFFLINE, answers="secret-api-key\n53.27\n7.77\n"
    )

    assert result.returncode == 1
    assert "Error: No connection to the weather service" in result.stdout
    assert "secret-api-key" not in result.stdout + result.stderr


def test_setup_drive(frame: Frame) -> None:
    # an unfinished Drive configuration doesn't block the setup
    frame.configure(use_drive="1")
    key = write_key(frame.directory / "downloaded.json")
    # skip the steps, the key, the folder; offline check fails: don't check
    # again, save anyway
    answers = f"n\n{key}\n{DRIVE_FOLDER}\nn\ny\n"

    result = frame.run("setup-drive", env=OFFLINE, answers=answers)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "No connection to Google" in result.stdout
    config = frame.config_file.read_text()
    assert "drive_folders=1AbC-dEf_123456789" in config
    assert (frame.directory / "drive_key.json").read_text() == key.read_text()
    assert frame.run("check-config").returncode == 0


def test_no_photos(frame: Frame) -> None:
    result = frame.run("test")

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
    with closing(sqlite3.connect(frame.directory / "photos.db")) as database:
        assert database.execute("SELECT COUNT(*) FROM photos").fetchone() == (3,)


@needs_imagemagick
def test_new_photo_is_found_incrementally(frame: Frame) -> None:
    frame.add_photo("a.jpg", "red", 1_600_000_000)
    assert shown_photos(frame, 1) == ["a.jpg"]

    frame.add_photo("b.jpg", "blue", 1_700_000_000)
    result = frame.run("test")

    assert "incremental scan" in result.stdout
    assert "Found 2 photos" in result.stdout


@needs_imagemagick
def test_drive_offline_still_shows_local_photos(frame: Frame) -> None:
    write_key(frame.directory / "drive_key.json")
    frame.configure(use_drive="1", drive_folders=DRIVE_FOLDER)
    frame.add_photo("a.jpg", "red", 1_600_000_000)

    result = frame.run("test", env=OFFLINE)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Getting data from Google Drive source (as frame@" in result.stdout
    assert "Error getting data from Google Drive source" in result.stdout
    assert "Found 1 photos" in result.stdout


@needs_imagemagick
def test_broken_photo_is_reported(frame: Frame) -> None:
    broken = frame.photos / "broken.jpg"
    broken.parent.mkdir(parents=True)
    broken.write_text("not a photo")
    frame.configure(auto_orientation="1")

    result = frame.run("test")

    # 1.x didn't read the ImageMagick errors and reported success
    assert result.stdout.count("Fail! convert:") == 2, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert not (frame.directory / "photo.bmp").exists()


@needs_imagemagick
def test_auto_orientation(frame: Frame) -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: shown 90 degrees clockwise
    frame.photos.mkdir()
    Image.new("RGB", (64, 48), "red").save(frame.photos / "turned.jpg", exif=exif)
    frame.configure(auto_orientation="1")

    result = frame.run("test")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Auto-orientate the photo...\n" in result.stdout
    with Image.open(frame.directory / "origphoto.jpg") as original:
        assert original.size == (48, 64)


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

    result = frame.run("convert", str(source), str(target))

    assert result.returncode == 0, result.stdout + result.stderr
    with Image.open(target / "photo.bmp") as image:
        assert image.size == (800, 480)


@needs_imagemagick
def test_convert_command_leaves_the_source_alone(frame: Frame) -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: shown 90 degrees clockwise
    source = frame.directory / "my.photo.jpg"
    Image.new("RGB", (64, 48), "red").save(source, exif=exif)
    original = source.read_bytes()
    frame.configure(auto_orientation="1")

    target = frame.directory / "my.result.jpg"

    result = frame.run("convert", str(source), str(target))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Auto-orientate the photo...\n" in result.stdout
    assert source.read_bytes() == original  # 1.x turned the source file
    assert (frame.directory / "my.result.bmp").is_file()  # 1.x: myresult.bmp


@needs_imagemagick
def test_weather_offline_still_shows_the_photo(frame: Frame) -> None:
    frame.configure(show_weather="1", apikey="secret-api-key", lat="53.27", lon="7.77")
    frame.add_photo("a.jpg", "red", 1_600_000_000)

    result = frame.run("test", env=OFFLINE)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Getting weather data..." in result.stdout
    assert "Fail! No connection to the weather service" in result.stdout
    assert "secret-api-key" not in result.stdout + result.stderr
    assert (frame.directory / "photo.bmp").exists()


def test_users_management(frame: Frame) -> None:
    # piped input: passwords are read without a terminal (no getpass)
    answers = "\n".join(
        ["1", "admin", "secret", "secret", "", "5", "admin", "secret", "", "6", ""]
    )

    result = frame.run("users", answers=answers)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "USER ADDED SUCCESSFULLY!" in result.stdout
    assert "YOU HAVE LOGGED IN SUCCESSFULLY!" in result.stdout
    assert "User admin added!" in result.stdout
    with sqlite3.connect(frame.directory / "users.db") as database:
        (password_hash,) = database.execute("SELECT hash FROM users").fetchone()
    database.close()
    assert password_hash.startswith("scrypt:")
