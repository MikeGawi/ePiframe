import logging
from pathlib import Path

import pytest

from epiframe.users.console import USERS_ACTIONS_TAG, UsersConsole, read_password
from epiframe.users.store import Users
from tests.epiframe.users.conftest import FAST_METHOD, LEGACY_PASSWORDS
from tests.helpers.console import Answer, Console

ENTER = ""  # "Press Enter to continue..."
EXIT = "6"


def run(users: Users, *answers: Answer) -> Console:
    console = Console(*answers)
    code = UsersConsole(users, console.ask, console.ask, console.say).run()
    assert code == 0
    return console


@pytest.fixture
def alice(users: Users) -> Users:
    users.add("alice", "secret")
    return users


def test_menu_and_exit(users: Users) -> None:
    console = run(users, EXIT)

    assert "<NO USERS!>" in console.lines
    assert "6. Exit" in console.lines
    assert console.prompts == ["Enter your choice [1-6]: "]
    assert console.lines[-1] == "Exiting..."


@pytest.mark.parametrize("choice", ["0", "7", "x", ""])
def test_wrong_selection(users: Users, choice: str) -> None:
    console = run(users, choice, EXIT)

    assert "Wrong selection. Try again..." in console.lines


@pytest.mark.parametrize("stop", [EOFError(), KeyboardInterrupt()])
def test_ctrl_c_or_end_of_input(alice: Users, stop: BaseException) -> None:
    # in the middle of adding a user: nothing is saved
    console = run(alice, "1", "bob", stop)

    assert console.lines[-1] == "Exiting..."
    assert alice.by_username("bob") is None


def test_add_user(users: Users, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="epiframe")

    console = run(users, "1", "bob", "pw", "typo", "pw", "pw", ENTER, EXIT)

    assert "----- Adding new user -----" in console.lines
    assert "Passwords are not the same!" in console.lines
    assert "USER ADDED SUCCESSFULLY!" in console.lines
    assert users.authenticate("bob", "pw")
    assert f"{USERS_ACTIONS_TAG}User bob added!" in caplog.text
    # the next menu lists the user
    assert console.lines.count("bob") == 1


def test_add_user_with_empty_password(users: Users) -> None:
    run(users, "1", "kiosk", "", "", ENTER, EXIT)

    assert users.authenticate("kiosk", "")


def test_add_existing_or_empty_username(alice: Users) -> None:
    console = run(alice, "1", "alice", "", "bob", "", "", ENTER, EXIT)

    assert "User already exists!" in console.lines
    assert "Username can't be empty!" in console.lines
    assert alice.by_username("bob")


def test_delete_user(alice: Users, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="epiframe")

    console = run(alice, "2", "nobody", "alice", "maybe", "y", ENTER, EXIT)

    assert "User doesn't exist!" in console.lines
    assert "Please respond with 'yes' or 'no' (or 'y' or 'n')" in console.lines
    assert "USER DELETED SUCCESSFULLY!" in console.lines
    assert alice.all() == []
    assert f"{USERS_ACTIONS_TAG}User alice deleted!" in caplog.text


@pytest.mark.parametrize("answer", ["n", "No", ""])
def test_delete_user_cancelled(alice: Users, answer: str) -> None:
    console = run(alice, "2", "alice", answer, ENTER, EXIT)

    assert "USER WAS NOT DELETED" in console.lines
    assert alice.by_username("alice")


def test_change_password(alice: Users, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="epiframe")

    console = run(alice, "3", "alice", "wrong", "secret", "new", "new", ENTER, EXIT)

    assert "Wrong password!" in console.lines
    assert "PASSWORD CHANGED SUCCESSFULLY!" in console.lines
    assert alice.authenticate("alice", "new")
    assert f"{USERS_ACTIONS_TAG}User alice password changed!" in caplog.text
    assert "Confirm new password [empty possible]: " in console.prompts


def test_show_api_key(alice: Users) -> None:
    key = alice.by_username("alice").api_key  # type: ignore[union-attr]

    console = run(alice, "4", "alice", "secret", ENTER, EXIT)

    assert f"USER alice API KEY: {key}" in console.lines


def test_test_password(alice: Users) -> None:
    console = run(alice, "5", "alice", "nope", "secret", ENTER, EXIT)

    assert "Wrong password!" in console.lines
    assert "YOU HAVE LOGGED IN SUCCESSFULLY!" in console.lines


def test_1x_user_logs_in(legacy_database: Path) -> None:
    users = Users(legacy_database, method=FAST_METHOD)

    console = run(users, "5", "alice", LEGACY_PASSWORDS["alice"], ENTER, EXIT)

    assert "YOU HAVE LOGGED IN SUCCESSFULLY!" in console.lines
    assert users.by_username("alice").password_hash.startswith(FAST_METHOD)  # type: ignore[union-attr]


@pytest.mark.parametrize(("terminal", "reader"), [(True, "getpass"), (False, "input")])
def test_read_password(
    monkeypatch: pytest.MonkeyPatch, terminal: bool, reader: str
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: terminal)
    monkeypatch.setattr("getpass.getpass", lambda _: "getpass")
    monkeypatch.setattr("builtins.input", lambda _: "input")

    assert read_password("Password: ") == reader
