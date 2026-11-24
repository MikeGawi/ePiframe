import sqlite3
from pathlib import Path

import pytest

from epiframe.users.store import Users

ASSETS = Path(__file__).with_name("assets")
# a users.db written by the 1.x UsersManager (md5 hashes + salts):
# alice/"secret", bob/"" (empty), carol/"changed" (changed from "p@ss w0rd")
LEGACY_PASSWORDS = {"alice": "secret", "bob": "", "carol": "changed"}
# cheap scrypt parameters keep the tests fast
FAST_METHOD = "scrypt:1024:8:1"


@pytest.fixture
def database(tmp_path: Path) -> Path:
    return tmp_path / "users.db"


@pytest.fixture
def legacy_database(database: Path) -> Path:
    with sqlite3.connect(database) as db:
        db.executescript((ASSETS / "users_1x.sql").read_text())
    db.close()
    return database


@pytest.fixture
def users(database: Path) -> Users:
    return Users(database, method=FAST_METHOD)
