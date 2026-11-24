"""Users stored in SQLite (``users.db``, compatible with 1.x files).

Passwords are hashed with scrypt (Werkzeug's ``generate_password_hash``, salt and
parameters in the hash string). 1.x stored ``md5(password + salt)`` with the
salt in the ``salts`` table; such a hash is still accepted and replaced by a
scrypt hash on the first successful login (also when :data:`PASSWORD_METHOD`
changes). Every query is parameterized (1.x built SQL from strings).

A connection is opened per operation: the WebUI calls from several threads, and
the file is small.
"""

import hashlib
import hmac
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from epiframe.users.model import User

# Werkzeug's default; about 60 ms on a desktop, measure on a Pi Zero
PASSWORD_METHOD = "scrypt:32768:8:1"  # noqa: S105 - not a password
API_KEY_BYTES = 16  # 32 hex characters, as 1.x

# the 1.x schema (kept, so 1.x files need no migration)
CREATE_USERS = (
    "CREATE TABLE users (id INTEGER PRIMARY KEY ASC, username text, hash text,"
    " api text)"
)
CREATE_SALTS = (
    "CREATE TABLE salts (id INTEGER PRIMARY KEY ASC, userid INTEGER, salt text,"
    " FOREIGN KEY(userid) REFERENCES users(id))"
)
COLUMNS = "id, username, hash, api"


class UserError(Exception):
    """A user operation failed (unknown user, wrong password, ...)."""


def new_api_key() -> str:
    return secrets.token_hex(API_KEY_BYTES)


def _legacy_match(password: str, salt: str, stored: str) -> bool:
    # 1.x: md5(password + salt), hex
    digest = hashlib.md5((password + salt).encode(), usedforsecurity=False)
    return hmac.compare_digest(digest.hexdigest(), stored)


def _names(db: sqlite3.Connection, query: str, column: int) -> set[str]:
    return {row[column] for row in db.execute(query)}


def _row_to_user(row: tuple[int, str, str, str | None]) -> User:
    identifier, username, password_hash, api_key = row
    return User(identifier, username, password_hash or "", api_key or "")


class Users:
    """The users of the WebUI (``path`` = ``users.db``)."""

    def __init__(self, path: Path | str, method: str = PASSWORD_METHOD):
        self._path = Path(path)
        self._method = method
        with self._connect() as db:
            self._create_schema(db)
            self._fill_api_keys(db)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """A connection with one transaction (committed on success), then closed."""
        with closing(sqlite3.connect(self._path)) as db, db:
            yield db

    @staticmethod
    def _create_schema(db: sqlite3.Connection) -> None:
        tables = _names(db, "SELECT name FROM sqlite_master", 0)
        if "users" not in tables:
            db.execute(CREATE_USERS)
        if "salts" not in tables:
            db.execute(CREATE_SALTS)
        if "api" not in _names(db, "PRAGMA table_info(users)", 1):
            # users.db of 1.x versions before the API keys
            db.execute("ALTER TABLE users ADD COLUMN api text")

    @staticmethod
    def _fill_api_keys(db: sqlite3.Connection) -> None:
        missing = db.execute("SELECT id FROM users WHERE api IS NULL OR api = ''")
        for (identifier,) in missing.fetchall():
            db.execute(
                "UPDATE users SET api = ? WHERE id = ?", (new_api_key(), identifier)
            )

    def _one(self, column: str, value: str) -> User | None:
        with self._connect() as db:
            row = db.execute(
                f"SELECT {COLUMNS} FROM users WHERE {column} = ? ORDER BY id",  # noqa: S608 - fixed column names
                (value,),
            ).fetchone()
        return _row_to_user(row) if row else None

    def all(self) -> list[User]:
        with self._connect() as db:
            rows = db.execute(f"SELECT {COLUMNS} FROM users ORDER BY id").fetchall()  # noqa: S608
        return [_row_to_user(row) for row in rows]

    def by_username(self, username: str) -> User | None:
        return self._one("username", username)

    def by_api_key(self, api_key: str) -> User | None:
        return self._one("api", api_key) if api_key else None

    def login_needed(self) -> bool:
        """The WebUI asks for a login only when there are users (as 1.x)."""
        with self._connect() as db:
            return db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def add(self, username: str, password: str) -> User:
        """Add a user (an empty password is allowed, as 1.x)."""
        if not username:
            raise UserError("Username can't be empty!")
        if self.by_username(username):
            raise UserError("User already exists!")
        with self._connect() as db:
            db.execute(
                "INSERT INTO users (username, hash, api) VALUES (?, ?, ?)",
                (username, self._hash(password), new_api_key()),
            )
        return self._existing(username)

    def delete(self, username: str) -> None:
        user = self._existing(username)
        with self._connect() as db:
            db.execute("DELETE FROM salts WHERE userid = ?", (user.id,))
            db.execute("DELETE FROM users WHERE id = ?", (user.id,))

    def change_password(
        self, username: str, old_password: str, new_password: str
    ) -> None:
        user = self.authenticate(username, old_password)
        self._set_password(user, new_password)

    def authenticate(self, username: str, password: str) -> User:
        """Return the user if ``password`` is right, else raise :class:`UserError`."""
        user = self._existing(username)
        if self._is_current(user.password_hash):
            if not check_password_hash(user.password_hash, password):
                raise UserError("Wrong password!")
            return user
        if not self._legacy_check(user, password):
            raise UserError("Wrong password!")
        self._set_password(user, password)  # upgrade the 1.x / outdated hash
        return self._existing(username)

    def _existing(self, username: str) -> User:
        user = self.by_username(username)
        if user is None:
            raise UserError("User doesn't exist!")
        return user

    def _hash(self, password: str) -> str:
        return generate_password_hash(password, method=self._method)

    def _is_current(self, password_hash: str) -> bool:
        return password_hash.partition("$")[0] == self._method

    def _legacy_check(self, user: User, password: str) -> bool:
        if "$" in user.password_hash:  # Werkzeug hash with other parameters
            return check_password_hash(user.password_hash, password)
        with self._connect() as db:
            row = db.execute(
                "SELECT salt FROM salts WHERE userid = ? ORDER BY id", (user.id,)
            ).fetchone()
        return row is not None and _legacy_match(password, row[0], user.password_hash)

    def _set_password(self, user: User, password: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE users SET hash = ? WHERE id = ?",
                (self._hash(password), user.id),
            )
            db.execute("DELETE FROM salts WHERE userid = ?", (user.id,))
