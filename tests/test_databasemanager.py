import os.path
import sqlite3
from unittest.mock import patch
from misc.constants import Constants
from modules.databasemanager import DatabaseManager
from tests.helpers.helpers import remove_file, not_raises

db_filename = "test.sqlite"
username = "username"
password = "password"
salt = "salt"
api_key = "api_key"


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_database_create():
    remove_file(db_filename)
    DatabaseManager()

    assert os.path.exists(db_filename)


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_database_reopen():
    with not_raises(Exception):
        DatabaseManager()


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_database_schema():
    db = DatabaseManager()
    assert [
        (0, "id", "INTEGER", 0, None, 1),
        (1, "username", "TEXT", 0, None, 0),
        (2, "hash", "TEXT", 0, None, 0),
        (3, "api", "TEXT", 0, None, 0),
    ] == db.get_schema(Constants.USERS_TABLE_NAME)


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_database_get_create():
    db = DatabaseManager()
    assert [
        (
            "CREATE TABLE users (id INTEGER PRIMARY KEY ASC, username text, hash text, api text)",
        )
    ] == db.get_create(Constants.USERS_TABLE_NAME)


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_database_insert():
    db = DatabaseManager()

    with not_raises(Exception):
        db.insert(
            Constants.USERS_TABLE_NAME,
            [Constants.DB_NULL, username, password, api_key],
        )


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_database_select():
    db = DatabaseManager()

    with not_raises(Exception):
        select = db.select(
            Constants.DB_ALL,
            Constants.USERS_TABLE_NAME,
            Constants.USERS_TABLE_USERNAME_HEADER + " IS " + f"'{username}'",
        )

    assert [(1, "username", "password", "api_key")] == select

    with not_raises(Exception):
        db.insert(
            Constants.SALTS_TABLE_NAME,
            [Constants.DB_NULL, str(1), salt],
        )

    with not_raises(Exception):
        select = db.select(
            Constants.DB_ALL,
            Constants.SALTS_TABLE_NAME,
            Constants.SALTS_TABLE_USERID_HEADER + " IS " + str(1),
        )

    assert [(1, 1, "salt")] == select


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_database_update():
    db = DatabaseManager()

    with not_raises(Exception):
        db.update(
            Constants.USERS_TABLE_NAME,
            Constants.USERS_TABLE_HASH_HEADER,
            f"'{password}_new'",
            Constants.USERS_TABLE_ID_HEADER + " IS " + str(1),
        )

    with not_raises(Exception):
        select = db.select(
            Constants.DB_ALL,
            Constants.USERS_TABLE_NAME,
            Constants.USERS_TABLE_USERNAME_HEADER + " IS " + f"'{username}'",
        )

    assert [(1, "username", "password_new", "api_key")] == select


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_database_select_nok():
    db = DatabaseManager()

    with not_raises(Exception):
        select = db.select(
            Constants.DB_ALL,
            Constants.USERS_TABLE_NAME,
            Constants.USERS_TABLE_USERNAME_HEADER + " IS " + f"'non_existing_username'",
        )

    assert [] == select


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_database_delete():
    db = DatabaseManager()

    with not_raises(Exception):
        db.delete(
            Constants.USERS_TABLE_NAME,
            Constants.USERS_TABLE_USERNAME_HEADER + f" IS '{username}'",
        )

    with not_raises(Exception):
        select = db.select(
            Constants.DB_ALL,
            Constants.USERS_TABLE_NAME,
            Constants.USERS_TABLE_USERNAME_HEADER + " IS " + f"'{username}'",
        )

    assert [] == select
    remove_file(db_filename)


@patch("misc.constants.Constants.USERS_DB_FILE", db_filename)
def test_database_backward_compatibility():
    with sqlite3.connect(db_filename, check_same_thread=False) as dbconnection:
        cur = dbconnection.cursor()
        dbs = {
            Constants.USERS_TABLE_NAME: "CREATE TABLE {} (id INTEGER PRIMARY KEY ASC, username text, hash text)".format(
                Constants.USERS_TABLE_NAME
            ),
        }

        for db in dbs.keys():
            cur.execute(dbs[db])
            dbconnection.commit()

    db = DatabaseManager()
    assert [
        (
            "CREATE TABLE users (id INTEGER PRIMARY KEY ASC, username text, hash text, api text)",
        )
    ] == db.get_create(Constants.USERS_TABLE_NAME)
    remove_file(db_filename)
