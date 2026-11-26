from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from epiframe.core.media_types import EXTENSIONS
from epiframe.photos.index import PhotoIndex
from epiframe.photos.model import Photo
from epiframe.sources.drive import DRIVE_SOURCE, FOLDER_TYPE, DriveFile, DriveSource
from epiframe.sources.local import LOCAL_SOURCE
from epiframe.update import UpdateError
from epiframe.update.sources import NO_SOURCES, Sources, drive_source
from tests.epiframe.update.conftest import MakeConfig, add_photo, make_plugin
from tests.helpers.fake_drive import ROOT, FakeDrive, photo
from tests.helpers.service_account import ACCOUNT, write_key

FOLDER = "1AbC-dEf_123456789"
CREATED = datetime(2024, 5, 1, 10)


def fake_drive() -> FakeDrive:
    drive = FakeDrive()
    drive.files[ROOT] = DriveFile(ROOT, "Photos", FOLDER_TYPE)
    return drive


def unused_drive() -> DriveSource:
    raise AssertionError("Drive is disabled")


@pytest.fixture
def index(tmp_path: Path) -> Iterator[PhotoIndex]:
    with PhotoIndex(tmp_path / "photos.db") as index:
        yield index


def ids(index: PhotoIndex, source: str) -> int:
    return index.count_source(source)


def test_no_sources(make_config: MakeConfig, plugins: MagicMock) -> None:
    sources = Sources(make_config(use_local="0"), plugins, unused_drive)

    with pytest.raises(UpdateError, match=NO_SOURCES):
        sources.check()


@pytest.mark.parametrize(
    "entries", [{"use_local": "1"}, {"use_local": "0", "use_drive": "1"}]
)
def test_enabled_source(
    make_config: MakeConfig, plugins: MagicMock, entries: dict[str, str]
) -> None:
    Sources(make_config(**entries), plugins, unused_drive).check()


def test_plugin_source_is_enough(make_config: MakeConfig, plugins: MagicMock) -> None:
    plugins.sources.return_value = [make_plugin(source_photos=[])]

    Sources(make_config(use_local="0"), plugins, unused_drive).check()


def test_local_source(
    make_config: MakeConfig,
    plugins: MagicMock,
    index: PhotoIndex,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    add_photo(tmp_path / "photos", "a.jpg")
    add_photo(tmp_path / "photos", "2024/b.png")
    sources = Sources(make_config(), plugins, unused_drive)

    sources.sync(index)
    sources.sync(index)

    assert ids(index, LOCAL_SOURCE) == 2
    assert "Success! 2 photos, 2 of 2 folders read (full scan)" in caplog.text
    assert "Success! 2 photos, 0 of 2 folders read (incremental scan)" in caplog.text


def test_disabled_source_is_removed(
    make_config: MakeConfig, plugins: MagicMock, index: PhotoIndex, tmp_path: Path
) -> None:
    add_photo(tmp_path / "photos", "a.jpg")
    Sources(make_config(), plugins, unused_drive).sync(index)
    plugins.sources.return_value = [make_plugin(source_photos=[])]

    Sources(make_config(use_local="0"), plugins, unused_drive).sync(index)

    assert index.count() == 0


def test_drive_source(
    make_config: MakeConfig,
    plugins: MagicMock,
    index: PhotoIndex,
    caplog: pytest.LogCaptureFixture,
) -> None:
    drive = fake_drive()
    drive.add(photo("p1"))
    source = DriveSource(drive, [ROOT], True, ["jpg"])

    Sources(make_config(use_drive="1"), plugins, lambda: source).sync(index)

    assert ids(index, DRIVE_SOURCE) == 1
    assert f"Getting data from Google Drive source (as {ACCOUNT})..." in caplog.text
    assert "Success! 1 photos (full listing)" in caplog.text


def test_drive_changes(
    make_config: MakeConfig, plugins: MagicMock, index: PhotoIndex
) -> None:
    drive = fake_drive()
    source = DriveSource(drive, [ROOT], True, ["jpg"])
    sources = Sources(make_config(use_drive="1"), plugins, lambda: source)
    sources.sync(index)
    drive.add(photo("p1"))

    sources.sync(index)

    assert ids(index, DRIVE_SOURCE) == 1


def test_drive_error_keeps_known_photos(
    make_config: MakeConfig,
    plugins: MagicMock,
    index: PhotoIndex,
    caplog: pytest.LogCaptureFixture,
) -> None:
    index.add_photos([Photo("p1", DRIVE_SOURCE, CREATED)])

    def offline() -> DriveSource:
        raise OSError("no network")

    Sources(make_config(use_local="0", use_drive="1"), plugins, offline).sync(index)

    assert "Error getting data from Google Drive source: no network" in caplog.text
    assert ids(index, DRIVE_SOURCE) == 1


def test_plugin_source(
    make_config: MakeConfig,
    plugins: MagicMock,
    index: PhotoIndex,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plugin = make_plugin(source_photos=[Photo("x", "plugin:clock", CREATED)])
    plugins.sources.return_value = [plugin]

    Sources(make_config(use_local="0"), plugins, unused_drive).sync(index)

    assert ids(index, "plugin:clock") == 1
    assert "Getting data from plugin 'Clock' source..." in caplog.text


def test_plugin_source_error(
    make_config: MakeConfig, plugins: MagicMock, index: PhotoIndex
) -> None:
    def broken() -> list[Photo]:
        raise ValueError("broken")

    plugins.sources.return_value = [make_plugin(source_photos=broken)]
    sources = Sources(make_config(use_local="0"), plugins, unused_drive)

    with pytest.raises(
        UpdateError,
        match=r"Error getting data from plugin 'Clock' source: ValueError\('broken'\)",
    ):
        sources.sync(index)


def test_drive_source_of_config(make_config: MakeConfig, tmp_path: Path) -> None:
    key = write_key(tmp_path / "drive_key.json")
    config = make_config(
        drive_key_file=str(key),
        drive_folders=f"{FOLDER},https://drive.google.com/drive/folders/{FOLDER}x",
        drive_subfolders="0",
    )

    source = drive_source(config)

    assert source.drive.account == ACCOUNT
    assert source.roots == (FOLDER, f"{FOLDER}x")
    assert not source.recursive
    assert source.extensions == {e.lower() for e in EXTENSIONS}
