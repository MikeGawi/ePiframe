import builtins
import getpass
import logging
from unittest.mock import patch
import pytest
from modules.databasemanager import DatabaseManager
from modules.usersmanager import UsersManager
from tests.helpers.capturing import Capturing
from tests.helpers.inputs import MockedInput
from tests.helpers.helpers import remove_file

db_filename = "test.sqlite"
username = "username"
password = "password"

database_manager: DatabaseManager


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_add(caplog):
    remove_file(db_filename)
    caplog.set_level(logging.INFO, logger="epiframe")

    global database_manager
    database_manager = DatabaseManager()

    output, users_manager = mock_manage(MockedInput(["1", username, "", "", "", "6"]))
    assert "--------Users management: User username added!" in caplog.text

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


def test_change(caplog):
    caplog.set_level(logging.INFO, logger="epiframe")
    output, users_manager = mock_manage(
        MockedInput(["3", username, "", password, password, "", "6"])
    )
    assert "PASSWORD CHANGED SUCCESSFULLY!" in output
    assert "--------Users management: User username password changed!" in caplog.text


def test_check_after():
    output, users_manager = mock_manage(MockedInput(["5", username, password, "", "6"]))
    assert "YOU HAVE LOGGED IN SUCCESSFULLY!" in output


def test_delete_no():
    output, users_manager = mock_manage(MockedInput(["2", username, "n", "", "6"]))
    assert "USER WAS NOT DELETED SUCCESSFULLY!" in output
    users = users_manager.get_by_username(username)
    assert users
    assert len(users) == 1


def test_delete(caplog):
    caplog.set_level(logging.INFO, logger="epiframe")
    output, users_manager = mock_manage(MockedInput(["2", username, "y", "", "6"]))
    assert "USER DELETED SUCCESSFULLY!" in output
    users = users_manager.get_by_username(username)
    assert not users
    assert "--------Users management: User username deleted!" in caplog.text

    remove_file(db_filename)


def mock_manage(inputs: MockedInput):
    users_manager = UsersManager(database_manager)
    with (
        patch.object(builtins, "input", inputs.mock_inputs),
        patch.object(getpass, "getpass", inputs.mock_inputs),
    ):
        with Capturing() as output:
            users_manager.manage()
    return output, users_manager
