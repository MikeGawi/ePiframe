import os
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from epiframe.config.manager import ConfigManager
from epiframe.photos.model import Photo
from epiframe.processing.imagemagick import ImageMagickError
from epiframe.sources.drive import DRIVE_SOURCE, DriveSource
from epiframe.sources.local import LOCAL_SOURCE
from epiframe.update.fetch import Fetched, Fetcher, Originals, extension
from tests.epiframe.update.conftest import add_photo, make_plugin
from tests.helpers.fake_drive import FakeDrive, photo

CREATED = datetime(2024, 5, 1, 10)


@pytest.mark.parametrize(
    ("image_format", "name", "expected"),
    [
        ("JPEG", "a.JPEG", "jpg"),
        ("PNG", "a.jpg", "png"),  # the format wins (1.x kept "jpg")
        ("HEIC", "a.HEIC", "heic"),  # unknown format name: the file's extension
        ("", "a.Tif", "tif"),
    ],
)
def test_extension(
    magick: MagicMock, image_format: str, name: str, expected: str
) -> None:
    magick.image_format.return_value = image_format

    assert extension(magick, Path(name)) == expected


def test_extension_of_unreadable_file(magick: MagicMock) -> None:
    magick.image_format.side_effect = ImageMagickError("broken")

    assert extension(magick, Path("x/broken.JPG")) == "jpg"


@pytest.fixture
def originals(config: ConfigManager, magick: MagicMock) -> Originals:
    return Originals(config, magick)


def test_originals(originals: Originals, tmp_path: Path) -> None:
    assert originals.directory == Path(".")
    assert originals.name == "origphoto"
    assert originals.files() == []
    assert originals.newest() is None
    add_photo(tmp_path, "origphoto.png")
    add_photo(tmp_path, "origphoto.jpg")
    add_photo(tmp_path, "origphoto_thumb.jpg")

    assert sorted(originals.files()) == [Path("origphoto.jpg"), Path("origphoto.png")]

    originals.remove()

    assert originals.files() == []
    assert (tmp_path / "origphoto_thumb.jpg").exists()


def test_newest_original(originals: Originals, tmp_path: Path) -> None:
    jpg = add_photo(tmp_path, "origphoto.jpg")
    png = add_photo(tmp_path, "origphoto.png")
    while jpg.stat().st_ctime_ns <= png.stat().st_ctime_ns:  # coarse clock
        time.sleep(0.01)
        os.chmod(jpg, 0o600)  # changes the ctime: the newest file now

    assert originals.newest() == Path("origphoto.jpg")


def test_copy(originals: Originals, tmp_path: Path, magick: MagicMock) -> None:
    source = add_photo(tmp_path / "photos", "a.JPEG")

    copy = originals.copy(source)

    assert copy == Path("origphoto.jpg")
    assert copy.read_bytes() == source.read_bytes()
    magick.image_format.assert_called_once_with(str(source))


def test_copy_of_the_original_itself(originals: Originals, tmp_path: Path) -> None:
    original = add_photo(tmp_path, "origphoto.jpg")

    assert originals.copy(original) == Path("origphoto.jpg")
    assert original.exists()


# -------------------------------------------------------------------- Fetcher


def unused_drive() -> DriveSource:
    raise AssertionError("not a Drive photo")


def test_fetch_local_photo(
    originals: Originals, plugins: MagicMock, tmp_path: Path
) -> None:
    source = add_photo(tmp_path / "photos", "a.jpg")
    fetcher = Fetcher(originals, plugins, unused_drive)

    fetched = fetcher.fetch(Photo(str(source), LOCAL_SOURCE, CREATED))

    assert fetched == Fetched(Path("origphoto.jpg"), "")
    assert fetched.path.read_bytes() == source.read_bytes()


def test_fetch_missing_local_photo(
    originals: Originals, plugins: MagicMock, tmp_path: Path
) -> None:
    fetcher = Fetcher(originals, plugins, unused_drive)

    with pytest.raises(FileNotFoundError):
        fetcher.fetch(Photo(str(tmp_path / "gone.jpg"), LOCAL_SOURCE, CREATED))


def test_fetch_drive_photo(originals: Originals, plugins: MagicMock) -> None:
    drive = FakeDrive()
    drive.files["p1"] = photo("p1")
    drive.descriptions["p1"] = "Frame 3"
    source = DriveSource(drive, ["root"], True, ["jpg"])
    fetcher = Fetcher(originals, plugins, lambda: source)

    fetched = fetcher.fetch(Photo("p1", DRIVE_SOURCE, CREATED))

    assert fetched == Fetched(Path("origphoto.jpg"), "Frame 3")
    assert fetched.path.read_bytes() == b"p1"


def test_fetch_plugin_photo(
    originals: Originals, plugins: MagicMock, tmp_path: Path
) -> None:
    def fetch_photo(photo: Photo, directory: Path, name: str) -> Path:
        path = directory / f"{name}.png"
        path.write_text(photo.id)
        return path

    plugins.source_of.return_value = make_plugin(fetch_photo=fetch_photo)
    fetcher = Fetcher(originals, plugins, unused_drive)

    fetched = fetcher.fetch(Photo("remote-1", "plugin:clock", CREATED))

    assert fetched == Fetched(Path("origphoto.png"))
    assert fetched.path.read_text() == "remote-1"


def test_fetch_plugin_photo_without_hook(
    originals: Originals, plugins: MagicMock, tmp_path: Path
) -> None:
    source = add_photo(tmp_path / "plugin", "a.jpg")
    plugins.source_of.return_value = make_plugin(source_photos=[])
    fetcher = Fetcher(originals, plugins, unused_drive)

    fetched = fetcher.fetch(Photo(str(source), "plugin:clock", CREATED))

    assert fetched.path.read_bytes() == source.read_bytes()


def test_plugin_returning_no_file(
    originals: Originals, plugins: MagicMock, tmp_path: Path
) -> None:
    plugins.source_of.return_value = make_plugin(fetch_photo=tmp_path / "none.jpg")
    fetcher = Fetcher(originals, plugins, unused_drive)

    with pytest.raises(FileNotFoundError, match=r"none\.jpg"):
        fetcher.fetch(Photo("x", "plugin:clock", CREATED))
