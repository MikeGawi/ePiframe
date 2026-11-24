import gc
import sqlite3
import warnings
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from epiframe.users.model import User
from epiframe.users.store import (
    PASSWORD_METHOD,
    UserError,
    Users,
    new_api_key,
)
from tests.epiframe.users.conftest import FAST_METHOD, LEGACY_PASSWORDS


def rows(
    database: Path, query: str, parameters: tuple[object, ...] = ()
) -> list[tuple[object, ...]]:
    with sqlite3.connect(database) as db:
        result = db.execute(query, parameters).fetchall()
    db.close()
    return result


def test_new_database_has_the_1x_schema(users: Users, database: Path) -> None:
    schema = {
        str(name): str(sql)
        for name, sql in rows(database, "SELECT name, sql FROM sqlite_master")
    }

    assert schema["users"] == (
        "CREATE TABLE users (id INTEGER PRIMARY KEY ASC, username text, hash text,"
        " api text)"
    )
    assert "FOREIGN KEY(userid) REFERENCES users(id)" in schema["salts"]
    assert not users.login_needed()
    assert users.all() == []


def test_add_and_find(users: Users) -> None:
    user = users.add("alice", "secret")

    assert user.id == 1
    assert user.username == "alice"
    assert user.password_hash.startswith(f"{FAST_METHOD}$")
    assert "secret" not in user.password_hash
    assert len(user.api_key) == 32
    assert users.login_needed()
    assert [u.username for u in users.all()] == ["alice"]
    assert users.by_username("alice") == user
    assert users.by_api_key(user.api_key) == user


def test_api_keys_are_unique(users: Users) -> None:
    keys = {users.add(name, "").api_key for name in ("a", "b", "c")}

    assert len(keys) == 3
    assert new_api_key() != new_api_key()


def test_unknown_user(users: Users) -> None:
    users.add("alice", "secret")

    assert users.by_username("bob") is None
    assert users.by_api_key("nope") is None
    assert users.by_api_key("") is None


@pytest.mark.parametrize(
    "injection",
    ["' OR '1'='1", "x' OR 1=1 --", '" OR ""="', "%", "_" * 32],
)
def test_sql_injection_finds_nobody(users: Users, injection: str) -> None:
    # 1.x built the SQL from strings: "?api_key=' OR '1'='1" logged in
    users.add("alice", "secret")

    assert users.by_api_key(injection) is None
    assert users.by_username(injection) is None
    with pytest.raises(UserError, match="doesn't exist"):
        users.authenticate(injection, "secret")


def test_odd_usernames_are_stored_as_they_are(users: Users) -> None:
    name = "o'brien\"; DROP TABLE users; --"

    users.add(name, "pw")

    assert users.authenticate(name, "pw").username == name
    assert len(users.all()) == 1


def test_add_existing_or_empty(users: Users) -> None:
    users.add("alice", "secret")

    with pytest.raises(UserError, match="already exists"):
        users.add("alice", "other")
    with pytest.raises(UserError, match="can't be empty"):
        users.add("", "pw")


def test_authenticate(users: Users) -> None:
    users.add("alice", "secret")

    assert users.authenticate("alice", "secret").username == "alice"
    with pytest.raises(UserError, match="Wrong password"):
        users.authenticate("alice", "Secret")
    with pytest.raises(UserError, match="doesn't exist"):
        users.authenticate("bob", "secret")


def test_empty_password(users: Users) -> None:
    users.add("kiosk", "")

    assert users.authenticate("kiosk", "").username == "kiosk"
    with pytest.raises(UserError):
        users.authenticate("kiosk", " ")


def test_change_password(users: Users) -> None:
    users.add("alice", "secret")

    users.change_password("alice", "secret", "new")

    assert users.authenticate("alice", "new")
    with pytest.raises(UserError, match="Wrong password"):
        users.authenticate("alice", "secret")
    with pytest.raises(UserError, match="Wrong password"):
        users.change_password("alice", "secret", "x")
    with pytest.raises(UserError, match="doesn't exist"):
        users.change_password("bob", "secret", "x")


def test_delete(users: Users) -> None:
    users.add("alice", "secret")
    users.add("bob", "pw")

    users.delete("alice")

    assert [u.username for u in users.all()] == ["bob"]
    with pytest.raises(UserError, match="doesn't exist"):
        users.delete("alice")


def test_default_method_is_scrypt(database: Path) -> None:
    user = Users(database).add("alice", "secret")

    assert PASSWORD_METHOD.startswith("scrypt:")
    assert user.password_hash.startswith(f"{PASSWORD_METHOD}$")


def test_outdated_scrypt_parameters_are_upgraded(database: Path) -> None:
    Users(database, method="scrypt:2048:8:1").add("alice", "secret")
    users = Users(database, method=FAST_METHOD)

    with pytest.raises(UserError, match="Wrong password"):
        users.authenticate("alice", "wrong")
    user = users.authenticate("alice", "secret")

    assert user.password_hash.startswith(f"{FAST_METHOD}$")


def test_pbkdf2_hash_is_accepted(users: Users, database: Path) -> None:
    users.add("alice", "x")
    pbkdf2 = generate_password_hash("secret", method="pbkdf2:sha256:1000")
    with sqlite3.connect(database) as db:
        db.execute("UPDATE users SET hash = ?", (pbkdf2,))
    db.close()

    assert users.authenticate("alice", "secret").password_hash.startswith(FAST_METHOD)


# ------------------------------------------------------------- 1.x users.db


@pytest.mark.parametrize(("username", "password"), LEGACY_PASSWORDS.items())
def test_1x_passwords_work_and_are_rehashed(
    legacy_database: Path, username: str, password: str
) -> None:
    users = Users(legacy_database, method=FAST_METHOD)

    user = users.authenticate(username, password)

    assert user.password_hash.startswith(f"{FAST_METHOD}$")
    assert (
        rows(legacy_database, "SELECT salt FROM salts WHERE userid = ?", (user.id,))
        == []
    )
    # the API key and the id stay
    assert user.id == {"alice": 1, "bob": 2, "carol": 3}[username]
    assert user.api_key.startswith(username[0] * 4)
    # works again with the new hash
    assert users.authenticate(username, password) == user


def test_1x_wrong_password_keeps_the_old_hash(legacy_database: Path) -> None:
    users = Users(legacy_database, method=FAST_METHOD)
    before = rows(legacy_database, "SELECT * FROM users ORDER BY id")

    with pytest.raises(UserError, match="Wrong password"):
        users.authenticate("alice", "wrong")
    with pytest.raises(UserError, match="Wrong password"):
        users.authenticate("carol", "p@ss w0rd")  # the old password of carol

    assert rows(legacy_database, "SELECT * FROM users ORDER BY id") == before
    assert len(rows(legacy_database, "SELECT * FROM salts")) == 3


def test_1x_hash_without_salt_is_rejected(legacy_database: Path) -> None:
    with sqlite3.connect(legacy_database) as db:
        db.execute("DELETE FROM salts WHERE userid = 1")
    db.close()

    with pytest.raises(UserError, match="Wrong password"):
        Users(legacy_database, method=FAST_METHOD).authenticate("alice", "secret")


def test_1x_api_keys_work(legacy_database: Path) -> None:
    users = Users(legacy_database, method=FAST_METHOD)

    user = users.by_api_key("aaaa1111bbbb2222cccc3333dddd4444")

    assert user == User(
        1, "alice", "1ff3bc398c2ac5cbc6c57b35a587d37f", user.api_key if user else ""
    )
    assert users.login_needed()


def test_1x_delete_removes_the_salt(legacy_database: Path) -> None:
    Users(legacy_database, method=FAST_METHOD).delete("bob")

    assert rows(legacy_database, "SELECT userid FROM salts ORDER BY id") == [(1,), (3,)]


def test_oldest_1x_schema_without_api_keys(database: Path) -> None:
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY ASC, username text, hash text)"
        )
        db.execute("INSERT INTO users (username, hash) VALUES ('old', 'x')")
    db.close()

    users = Users(database, method=FAST_METHOD)

    user = users.by_username("old")
    assert user is not None
    assert len(user.api_key) == 32
    assert "salts" in {
        row[0] for row in rows(database, "SELECT name FROM sqlite_master")
    }


def test_missing_api_keys_are_filled(legacy_database: Path) -> None:
    with sqlite3.connect(legacy_database) as db:
        db.execute("UPDATE users SET api = NULL WHERE id = 1")
        db.execute("UPDATE users SET api = '' WHERE id = 2")
    db.close()

    users = Users(legacy_database, method=FAST_METHOD)

    assert all(len(user.api_key) == 32 for user in users.all())
    assert users.by_username("carol").api_key.startswith("cccc")  # type: ignore[union-attr]


def test_connections_are_closed(database: Path) -> None:
    # 1.x kept one connection open forever: "unclosed database" ResourceWarning
    # (emitted by Python 3.13+ when a connection is garbage collected open)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        users = Users(database, method=FAST_METHOD)
        users.add("alice", "secret")
        users.authenticate("alice", "secret")
        users.delete("alice")
        del users
        gc.collect()

    assert not [w for w in caught if issubclass(w.category, ResourceWarning)]
