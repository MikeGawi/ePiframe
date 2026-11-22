import datetime
import os.path
from epiframe.core.media_types import EXTENSIONS
from epiframe.photos.model import Photo
from modules.localsourcemanager import LOCAL_SOURCE, LocalSourceManager

test_directory = "test.directory"


def test_directory_creation():
    if os.path.exists(test_directory):
        os.rmdir(test_directory)

    LocalSourceManager.create_directory(test_directory)

    assert os.path.exists(test_directory)
    assert os.path.isdir(test_directory)
    os.rmdir(test_directory)


def test_get_files_nok():
    lsm = LocalSourceManager("tests/", False, EXTENSIONS)
    assert lsm.get_files() == []


def test_get_files_ok():
    lsm = LocalSourceManager("tests/assets", False, EXTENSIONS)
    assert lsm.get_files() == ["tests/assets/waveshare.bmp"]


def test_get_files_path():
    lsm = LocalSourceManager("tests/assets/", False, EXTENSIONS)
    assert lsm.get_files() == ["tests/assets/waveshare.bmp"]


def test_get_files_recursive():
    lsm = LocalSourceManager("tests/", True, EXTENSIONS)
    assert lsm.get_files() == [
        "tests/assets/waveshare.bmp",
        "tests/assets/recursive/waveshare2.bmp",
    ]


def test_get_files_non_existing_extension():
    lsm = LocalSourceManager("tests/", True, ["some_non_existing_extension"])
    assert lsm.get_files() == []


def test_get_photos():
    lsm = LocalSourceManager("tests/", True, EXTENSIONS)
    files = sorted(lsm.get_files())
    assert lsm.get_local_photos() == [
        Photo(
            file,
            LOCAL_SOURCE,
            datetime.datetime.fromtimestamp(os.stat(file).st_mtime),
        )
        for file in files
    ]
    assert [photo.id for photo in lsm.get_local_photos()] == [
        "tests/assets/recursive/waveshare2.bmp",
        "tests/assets/waveshare.bmp",
    ]


def test_get_photos_empty():
    assert LocalSourceManager("tests/", False, EXTENSIONS).get_local_photos() == []
