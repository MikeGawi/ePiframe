import os.path
import sqlite3
from unittest.mock import patch
from modules.databasemanager import (
    DB_ALL,
    DB_NULL,
    SALTS_TABLE_NAME,
    SALTS_TABLE_USERID_HEADER,
    USERS_TABLE_HASH_HEADER,
    USERS_TABLE_ID_HEADER,
    USERS_TABLE_NAME,
    USERS_TABLE_USERNAME_HEADER,
)
from modules.databasemanager import DatabaseManager
from tests.helpers.helpers import remove_file, not_raises

db_filename = "test.sqlite"
username = "username"
password = "password"
salt = "salt"
api_key = "api_key"


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_database_create():
    remove_file(db_filename)
    DatabaseManager()

    assert os.path.exists(db_filename)


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_database_reopen():
    with not_raises(Exception):
        DatabaseManager()


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_database_schema():
    db = DatabaseManager()
    assert [
        (0, "id", "INTEGER", 0, None, 1),
        (1, "username", "TEXT", 0, None, 0),
        (2, "hash", "TEXT", 0, None, 0),
        (3, "api", "TEXT", 0, None, 0),
    ] == db.get_schema(USERS_TABLE_NAME)


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_database_get_create():
    db = DatabaseManager()
    assert [
        (
            "CREATE TABLE users (id INTEGER PRIMARY KEY ASC, username text, hash text, api text)",
        )
    ] == db.get_create(USERS_TABLE_NAME)


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_database_insert():
    db = DatabaseManager()

    with not_raises(Exception):
        db.insert(
            USERS_TABLE_NAME,
            [DB_NULL, username, password, api_key],
        )


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_database_select():
    db = DatabaseManager()

    with not_raises(Exception):
        select = db.select(
            DB_ALL,
            USERS_TABLE_NAME,
            USERS_TABLE_USERNAME_HEADER + " IS " + f"'{username}'",
        )

    assert [(1, "username", "password", "api_key")] == select

    with not_raises(Exception):
        db.insert(
            SALTS_TABLE_NAME,
            [DB_NULL, str(1), salt],
        )

    with not_raises(Exception):
        select = db.select(
            DB_ALL,
            SALTS_TABLE_NAME,
            SALTS_TABLE_USERID_HEADER + " IS " + str(1),
        )

    assert [(1, 1, "salt")] == select


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_database_update():
    db = DatabaseManager()

    with not_raises(Exception):
        db.update(
            USERS_TABLE_NAME,
            USERS_TABLE_HASH_HEADER,
            f"'{password}_new'",
            USERS_TABLE_ID_HEADER + " IS " + str(1),
        )

    with not_raises(Exception):
        select = db.select(
            DB_ALL,
            USERS_TABLE_NAME,
            USERS_TABLE_USERNAME_HEADER + " IS " + f"'{username}'",
        )

    assert [(1, "username", "password_new", "api_key")] == select


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_database_select_nok():
    db = DatabaseManager()

    with not_raises(Exception):
        select = db.select(
            DB_ALL,
            USERS_TABLE_NAME,
            USERS_TABLE_USERNAME_HEADER + " IS " + "'non_existing_username'",
        )

    assert [] == select


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_database_delete():
    db = DatabaseManager()

    with not_raises(Exception):
        db.delete(
            USERS_TABLE_NAME,
            USERS_TABLE_USERNAME_HEADER + f" IS '{username}'",
        )

    with not_raises(Exception):
        select = db.select(
            DB_ALL,
            USERS_TABLE_NAME,
            USERS_TABLE_USERNAME_HEADER + " IS " + f"'{username}'",
        )

    assert [] == select
    remove_file(db_filename)


@patch("epiframe.config.paths.USERS_DB_FILE", db_filename)
def test_database_backward_compatibility():
    with sqlite3.connect(db_filename, check_same_thread=False) as dbconnection:
        cur = dbconnection.cursor()
        dbs = {
            USERS_TABLE_NAME: "CREATE TABLE {} (id INTEGER PRIMARY KEY ASC, username text, hash text)".format(
                USERS_TABLE_NAME
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
    ] == db.get_create(USERS_TABLE_NAME)
    remove_file(db_filename)
