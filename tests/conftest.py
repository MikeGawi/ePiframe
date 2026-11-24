import glob
import os
import shutil

from unittest.mock import patch
import pytest
import requests_mock
from epiframe.config.paths import CONFIG_FILE_DEFAULT
from epiframe.config import manager as configmanager
from epiframe.service import frame as frame_module
from epiframe.service.frame import Frame
from modules.webuimanager import WebUIManager
from tests.helpers.config import Config
from tests.helpers.frame import event_mock
from tests.helpers.helpers import remove_file
from tests.helpers.plugins import ORDER_FILE, plugin_manager_for_tests


@pytest.fixture(scope="module")
def requests_mocker():
    with requests_mock.mock(real_http=True) as mocker:
        yield mocker


@pytest.fixture()
@patch("epiframe.config.paths.CONFIG_FILE", CONFIG_FILE_DEFAULT)
@patch("epiframe.config.paths.USERS_DB_FILE", "test_users.db")
def app_no_login():
    with patch.object(frame_module, "PluginManager", plugin_manager_for_tests):
        frame = Frame(event_mock, CONFIG_FILE_DEFAULT, "")
        web_manager = WebUIManager(frame)
    app = web_manager.app
    app.config.update(
        {
            "LOGIN_DISABLED": True,
            "TESTING": True,
        }
    )
    return app


@pytest.fixture()
@patch("epiframe.config.paths.USERS_DB_FILE", "test_users.db")
def app_no_config():
    with patch.object(configmanager, "ConfigManager", Config):
        frame = Frame(event_mock, ".", ".")
        web_manager = WebUIManager(frame)
    app = web_manager.app
    app.config.update(
        {
            "LOGIN_DISABLED": True,
            "TESTING": True,
        }
    )
    return app


@pytest.fixture()
@patch("epiframe.config.paths.CONFIG_FILE", CONFIG_FILE_DEFAULT)
@patch("epiframe.config.paths.USERS_DB_FILE", "test_users.db")
def app():
    frame = Frame(event_mock, CONFIG_FILE_DEFAULT, ".")
    web_manager = WebUIManager(frame)
    app = web_manager.app
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def client_no_login(app_no_login):
    return app_no_login.test_client()


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
            "test_fixture_client",
            "test_fixture_client_no_login",
        ]
    ]
    return first
