import os
from unittest.mock import patch
import pytest
from misc.user import User
from modules.databasemanager import DatabaseManager
from modules.usersmanager import UsersManager
from tests.helpers.helpers import remove_file, not_raises

db_filename = "test.sqlite"
user_id = "user_id"
username = "username"
password = "password"

database_manager: DatabaseManager


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_api_key_fix():
    remove_file(db_filename)
    global database_manager
    database_manager = DatabaseManager()
    assert os.path.exists(db_filename)


def test_login_needed_on_empty_db():
    users_manager = UsersManager(database_manager)
    assert not users_manager.login_needed()


def test_add_user():
    user: User = User(identifier=user_id, username=username, password=password, api="")
    users_manager = UsersManager(database_manager)
    assert not users_manager.get()
    users_manager.add(user)

    users_manager = UsersManager(database_manager)
    users = users_manager.get()
    assert users
    assert len(users) == 1
    assert users[0].api
    pytest.api_key = users[0].api
    pytest.user_password = users[0].password


def test_add_same_user():
    user: User = User(identifier=user_id, username=username, password=password, api="")
    users_manager = UsersManager(database_manager)
    with pytest.raises(Exception) as exception:
        users_manager.add(user)

    assert str(exception.value) == "User already exists!"


def test_login_needed_on_full_db():
    users_manager = UsersManager(database_manager)
    assert users_manager.login_needed()


def test_get_by_username():
    users_manager = UsersManager(database_manager)
    users = users_manager.get_by_username(username)
    assert users
    assert len(users) == 1

    user = users[0]
    assert user.id == 1
    assert user.username == username
    assert user.password != password
    assert user.api == pytest.api_key


def test_get_by_wrong_username():
    users_manager = UsersManager(database_manager)
    users = users_manager.get_by_username("non_existing_username")
    assert not users


def test_get_by_api():
    users_manager = UsersManager(database_manager)
    users = users_manager.get_by_api(pytest.api_key)
    assert users
    assert len(users) == 1

    user = users[0]
    assert user.id == 1
    assert user.username == username
    assert user.password != password
    assert user.api == pytest.api_key


def test_get_by_wrong_api():
    users_manager = UsersManager(database_manager)
    users = users_manager.get_by_api("non_existing_api")
    assert not users


def test_check_user():
    users_manager = UsersManager(database_manager)
    with not_raises(Exception):
        users_manager.check(username, password)


def test_check_user_fail():
    users_manager = UsersManager(database_manager)
    with pytest.raises(Exception) as exception:
        users_manager.check(username, "wrong_password")

    assert str(exception.value) == "Wrong password!"


def test_check_user_wrong_user():
    users_manager = UsersManager(database_manager)
    with pytest.raises(Exception) as exception:
        users_manager.check("non_existing_username", password)

    assert str(exception.value) == "User doesn't exist!"


def test_change_password():
    users_manager = UsersManager(database_manager)
    users_manager.change_password(username, password, "new_password")

    with not_raises(Exception):
        users_manager.check(username, "new_password")

    users = users_manager.get_by_username(username)
    assert users[0].password != pytest.user_password


def test_change_password_wrong_user():
    users_manager = UsersManager(database_manager)
    with pytest.raises(Exception) as exception:
        users_manager.change_password("non_existing_username", password, "new_password")

    assert str(exception.value) == "User doesn't exist!"


def test_change_password_wrong_password():
    users_manager = UsersManager(database_manager)
    with pytest.raises(Exception) as exception:
        users_manager.change_password(username, "wrong_password", "new_password")

    assert str(exception.value) == "Wrong password!"


def test_delete_wrong_user():
    users_manager = UsersManager(database_manager)
    with pytest.raises(Exception) as exception:
        users_manager.delete("non_existing_username")

    assert str(exception.value) == "User doesn't exist!"


def test_delete_user():
    users_manager = UsersManager(database_manager)
    with not_raises(Exception):
        users_manager.delete(username)
    users = users_manager.get()
    assert not users


def test_delete_user_again():
    users_manager = UsersManager(database_manager)
    with pytest.raises(Exception) as exception:
        users_manager.delete(username)

    assert str(exception.value) == "User doesn't exist!"


def test_user_with_empty_password():
    user: User = User(identifier=user_id, username=username, password="", api="api_key")
    users_manager = UsersManager(database_manager)
    users_manager.add(user)
    users = users_manager.get()
    assert users
    assert len(users) == 1
    assert users[0].password

    with not_raises(Exception):
        users_manager.check(username, "")

    with not_raises(Exception):
        users_manager.delete(username)

    users = users_manager.get()
    assert not users


def test_login_needed_last_time():
    users_manager = UsersManager(database_manager)
    assert not users_manager.login_needed()
    remove_file(db_filename)
