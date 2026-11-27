import glob
import os
import shutil

import pytest
import requests_mock

from epiframe.config import paths
from tests.helpers.helpers import remove_file
from tests.helpers.plugins import ORDER_FILE


@pytest.fixture(scope="module")
def requests_mocker():
    with requests_mock.mock(real_http=True) as mocker:
        yield mocker


@pytest.fixture(scope="session")
def display_folder(tmp_path_factory):
    return tmp_path_factory.mktemp("display")


@pytest.fixture(autouse=True)
def display_files(display_folder, monkeypatch):
    """Tests that show photos use display files of their own (not ``misc/``).

    Per test: ``test_paths.py`` reloads ``paths`` (back to the real values).
    """
    monkeypatch.setattr(
        paths, "DISPLAY_LOCK_FILE", str(display_folder / "display.lock")
    )
    monkeypatch.setattr(
        paths, "DISPLAY_STATE_FILE", str(display_folder / "display.json")
    )
    return display_folder


@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    def clean():
        files = glob.glob("test_log.log.*.gz")
        files.extend(glob.glob("logs/ePiframe.log.*.gz"))
        for file in files:
            os.remove(file)
        if os.path.exists("PATH"):
            shutil.rmtree("PATH")
        remove_file("log.test")
        remove_file("test_users.db")
        remove_file(ORDER_FILE)

    request.addfinalizer(clean)


def pytest_collection_modifyitems(session, config, items: list):
    first = get_first(items)
    items[:] = [item for item in items if item not in first]
    [items.insert(0, item) for item in first]


def get_first(items):
    first = [
        item
        for item in items
        if item.name
        in [
            "test_fixture_request_mocker",
        ]
    ]
    return first
