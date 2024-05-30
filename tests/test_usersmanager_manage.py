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
logger: Logs


class MockedInput:
    __inputs = []

    def __init__(self, inputs: list):
        self.__inputs = inputs

    def mock_inputs(self, *args, **kwargs):
        return self.__inputs.pop(0) if self.__inputs else "-"


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_add():
    remove_file(db_filename)
    remove_file(logs_filename)

    global logger
    logger = Logs(logs_filename)
    global database_manager
    database_manager = DatabaseManager()

    output, users_manager = mock_manage(MockedInput(["1", username, "", "", "", "6"]))
    with open(logs_filename, "r") as file:
        assert "--------Users management: User username added!" in "".join(
            file.readlines()
        )

    users = users_manager.get_by_username(username)
    assert users
    assert len(users) == 1

    user = users[0]
    assert user.id == 1
    assert user.username == username
    assert user.api
    pytest.api_key = user.api


def test_wrong():
    output, users_manager = mock_manage(MockedInput(["7", "6"]))
    assert "Wrong selection. Try again..." in output


def test_check():
    output, users_manager = mock_manage(MockedInput(["5", username, "", "", "6"]))
    assert "YOU HAVE LOGGED IN SUCCESSFULLY!" in output


def test_api():
    output, users_manager = mock_manage(MockedInput(["4", username, "", "", "6"]))
    assert f"USER {username} API KEY: {pytest.api_key} " in output


def test_change():
    output, users_manager = mock_manage(
        MockedInput(["3", username, "", password, password, "", "6"])
    )
    assert "PASSWORD CHANGED SUCCESSFULLY!" in output
    with open(logs_filename, "r") as file:
        assert "--------Users management: User username password changed!" in "".join(
            file.readlines()
        )


def test_check_after():
    output, users_manager = mock_manage(MockedInput(["5", username, password, "", "6"]))
    assert "YOU HAVE LOGGED IN SUCCESSFULLY!" in output


def test_delete_no():
    output, users_manager = mock_manage(MockedInput(["2", username, "n", "", "6"]))
    assert "USER WAS NOT DELETED SUCCESSFULLY!" in output
    users = users_manager.get_by_username(username)
    assert users
    assert len(users) == 1


def test_delete():
    output, users_manager = mock_manage(MockedInput(["2", username, "y", "", "6"]))
    assert "USER DELETED SUCCESSFULLY!" in output
    users = users_manager.get_by_username(username)
    assert not users
    with open(logs_filename, "r") as file:
        assert "--------Users management: User username deleted!" in "".join(
            file.readlines()
        )

    remove_file(db_filename)
    remove_file(logs_filename)


def mock_manage(inputs: MockedInput):
    users_manager = UsersManager(database_manager)
    with patch.object(builtins, "input", inputs.mock_inputs), patch.object(
        getpass, "getpass", inputs.mock_inputs
    ):
        with Capturing() as output:
            users_manager.manage(logger)
    return output, users_manager
