import glob
import os
import shutil
from unittest.mock import patch
import pytest
import requests_mock
from misc.constants import Constants
from modules import timermanager, intervalmanager, configmanager
from modules.backendmanager import BackendManager
from modules.webuimanager import WebUIManager
from tests.helpers.config import Config
from tests.helpers.helpers import remove_file
from tests.test_backendmanager import (
    event_mock,
    MockedIntervalManager,
    MockedTimerManager,
)


@pytest.fixture(scope="module")
def requests_mocker():
    with requests_mock.mock(real_http=True) as mocker:
        yield mocker


@pytest.fixture()
@patch("misc.constants.Constants.CONFIG_FILE", Constants.CONFIG_FILE_DEFAULT)
@patch("misc.constants.Constants.USERS_DB_FILE", "test_users.db")
def app_no_login():
    with patch.object(timermanager, "TimerManager", MockedTimerManager), patch.object(
        intervalmanager, "IntervalManager", MockedIntervalManager
    ):
        backend = BackendManager(event_mock, ".")
        web_manager = WebUIManager(backend)
    app = web_manager.app
    app.config.update(
        {
            "LOGIN_DISABLED": True,
            "TESTING": True,
        }
    )
    return app


@pytest.fixture()
@patch("misc.constants.Constants.USERS_DB_FILE", "test_users.db")
def app_no_config():
    with patch.object(timermanager, "TimerManager", MockedTimerManager), patch.object(
        intervalmanager, "IntervalManager", MockedIntervalManager
    ), patch.object(configmanager, "ConfigManager", Config):
        backend = BackendManager(event_mock, ".")
        web_manager = WebUIManager(backend)
    app = web_manager.app
    app.config.update(
        {
            "LOGIN_DISABLED": True,
            "TESTING": True,
        }
    )
    return app


@pytest.fixture()
@patch("misc.constants.Constants.CONFIG_FILE", Constants.CONFIG_FILE_DEFAULT)
@patch("misc.constants.Constants.USERS_DB_FILE", "test_users.db")
def app():
    with patch.object(timermanager, "TimerManager", MockedTimerManager), patch.object(
        intervalmanager, "IntervalManager", MockedIntervalManager
    ):
        backend = BackendManager(event_mock, ".")
        web_manager = WebUIManager(backend)
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
        shutil.rmtree("PATH")
        remove_file("log.test")
        remove_file("test_users.db")

    request.addfinalizer(clean)


def pytest_collection_modifyitems(session, config, items: list):
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
    items[:] = [item for item in items if item not in first]
    [items.insert(0, item) for item in first]
