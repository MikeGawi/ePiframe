import datetime
import os.path
from misc.constants import Constants
from modules.localsourcemanager import LocalSourceManager

test_directory = "test.directory"


def test_directory_creation():
    if os.path.exists(test_directory):
        os.rmdir(test_directory)

    LocalSourceManager.create_directory(test_directory)

    assert os.path.exists(test_directory)
    assert os.path.isdir(test_directory)
    os.rmdir(test_directory)


def test_get_files_nok():
    lsm = LocalSourceManager("tests/", False, Constants.EXTENSIONS)
    assert lsm.get_files() == []


def test_get_files_ok():
    lsm = LocalSourceManager("tests/assets", False, Constants.EXTENSIONS)
    assert lsm.get_files() == ["tests/assets/waveshare.bmp"]


def test_get_files_path():
    lsm = LocalSourceManager("tests/assets/", False, Constants.EXTENSIONS)
    assert lsm.get_files() == ["tests/assets/waveshare.bmp"]


def test_get_files_recursive():
    lsm = LocalSourceManager("tests/", True, Constants.EXTENSIONS)
    assert lsm.get_files() == [
        "tests/assets/waveshare.bmp",
        "tests/assets/recursive/waveshare2.bmp",
    ]


def test_get_files_non_existing_extension():
    lsm = LocalSourceManager("tests/", True, ["some_non_existing_extension"])
    assert lsm.get_files() == []


def test_get_date():
    lsm = LocalSourceManager("tests/assets/", False, Constants.EXTENSIONS)
    assert lsm.get_files() == ["tests/assets/waveshare.bmp"]
    mtime = os.stat(lsm.get_files()[0]).st_mtime
    assert lsm.get_dates(lsm.get_files()) == [
        datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    ]


def test_get_photos():
    lsm = LocalSourceManager("tests/assets/", False, Constants.EXTENSIONS)
    assert lsm.get_files() == ["tests/assets/waveshare.bmp"]
    mtime = os.stat(lsm.get_files()[0]).st_mtime
    time = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    photos = lsm.get_local_photos(
        "id_label", "creation_label", "source_label", "new_source"
    )
    assert photos.columns.values.tolist() == [
        "id_label",
        "creation_label",
        "source_label",
    ]
    assert photos.values.tolist() == [
        ["tests/assets/waveshare.bmp", time, "new_source"]
    ]
