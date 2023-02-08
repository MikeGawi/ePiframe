import builtins
import getpass
from unittest.mock import patch
import pytest
from misc.logs import Logs
from modules.databasemanager import DatabaseManager
from modules.usersmanager import UsersManager
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import remove_file

db_filename = "test.sqlite"
logs_filename = "test_log.log"
username = "username"
password = "password"

database_manager: DatabaseManager


class MockedInput:
    __inputs = []

    def __init__(self, inputs):
        self.__inputs = inputs

    def mock_inputs(self, *args, **kwargs):
        return self.__inputs.pop(0) if self.__inputs else "-"


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_add():
    remove_file(db_filename)
    remove_file(logs_filename)

    logger = Logs(logs_filename)
    global database_manager
    database_manager = DatabaseManager()

    users_manager = UsersManager(database_manager)
    inputs = MockedInput(["1", username, "", "", "", "6"])
    with patch.object(builtins, "input", inputs.mock_inputs), patch.object(
        getpass, "getpass", inputs.mock_inputs
    ):
        users_manager.manage(logger)

    with open(logs_filename, "r") as file:
        assert "--------Users management: User username added!" in file.readline()

    users = users_manager.get_by_username(username)
    assert users
    assert len(users) == 1

    user = users[0]
    assert user.id == 1
    assert user.username == username
    assert user.api
    pytest.api_key = user.api


def test_wrong():
    remove_file(logs_filename)

    logger = Logs(logs_filename)
    inputs = MockedInput(["7", "6"])
    users_manager = UsersManager(database_manager)
    with patch.object(builtins, "input", inputs.mock_inputs), patch.object(
        getpass, "getpass", inputs.mock_inputs
    ):
        with Capturing() as output:
            users_manager.manage(logger)

    assert "Wrong selection. Try again..." in output


def test_check():
    remove_file(logs_filename)
    logger = Logs(logs_filename)
    inputs = MockedInput(["5", username, "", "", "6"])
    users_manager = UsersManager(database_manager)
    with patch.object(builtins, "input", inputs.mock_inputs), patch.object(
        getpass, "getpass", inputs.mock_inputs
    ):
        with Capturing() as output:
            users_manager.manage(logger)

    assert "YOU HAVE LOGGED IN SUCCESSFULLY!" in output


def test_api():
    remove_file(logs_filename)
    logger = Logs(logs_filename)
    inputs = MockedInput(["4", username, "", "", "6"])
    users_manager = UsersManager(database_manager)
    with patch.object(builtins, "input", inputs.mock_inputs), patch.object(
        getpass, "getpass", inputs.mock_inputs
    ):
        with Capturing() as output:
            users_manager.manage(logger)

    assert f"USER {username} API KEY: {pytest.api_key} " in output


def test_change():
    remove_file(logs_filename)
    logger = Logs(logs_filename)
    inputs = MockedInput(["3", username, "", password, password, "", "6"])
    users_manager = UsersManager(database_manager)
    with patch.object(builtins, "input", inputs.mock_inputs), patch.object(
        getpass, "getpass", inputs.mock_inputs
    ):
        with Capturing() as output:
            users_manager.manage(logger)

    assert "PASSWORD CHANGED SUCCESSFULLY!" in output


def test_check_after():
    remove_file(logs_filename)
    logger = Logs(logs_filename)
    inputs = MockedInput(["5", username, password, "", "6"])
    users_manager = UsersManager(database_manager)
    with patch.object(builtins, "input", inputs.mock_inputs), patch.object(
        getpass, "getpass", inputs.mock_inputs
    ):
        with Capturing() as output:
            users_manager.manage(logger)

    assert "YOU HAVE LOGGED IN SUCCESSFULLY!" in output


def test_delete_no():
    remove_file(logs_filename)
    logger = Logs(logs_filename)
    inputs = MockedInput(["2", username, "n", "", "6"])
    users_manager = UsersManager(database_manager)
    with patch.object(builtins, "input", inputs.mock_inputs), patch.object(
        getpass, "getpass", inputs.mock_inputs
    ):
        with Capturing() as output:
            users_manager.manage(logger)

    assert "USER WAS NOT DELETED SUCCESSFULLY!" in output
    users = users_manager.get_by_username(username)
    assert users
    assert len(users) == 1


def test_delete():
    remove_file(logs_filename)
    logger = Logs(logs_filename)
    inputs = MockedInput(["2", username, "y", "", "6"])
    users_manager = UsersManager(database_manager)
    with patch.object(builtins, "input", inputs.mock_inputs), patch.object(
        getpass, "getpass", inputs.mock_inputs
    ):
        with Capturing() as output:
            users_manager.manage(logger)

    assert "USER DELETED SUCCESSFULLY!" in output
    users = users_manager.get_by_username(username)
    assert not users
    remove_file(db_filename)
    remove_file(logs_filename)
