"""Console management of the WebUI users (``ePiframe.py --users``).

Same menu as 1.x; Ctrl+C or the end of the input leave it cleanly.
"""

import getpass
import sys
from collections.abc import Callable

from epiframe.core.logs import get_logger
from epiframe.users.store import UserError, Users

Ask = Callable[[str], str]
Say = Callable[[str], None]

USERS_ACTIONS_TAG = "--------Users management: "
TITLES = (
    "Adding new user",
    "Deleting user",
    "Changing user password",
    "Showing user API key",
    "Testing user password",
)
MENU = (
    "Add new user",
    "Delete user",
    "Change user password",
    "Show user API key",
    "Test user password",
    "Exit",
)
EXIT = str(len(MENU))
ANSWERS = {"yes": True, "y": True, "ye": True, "no": False, "n": False}

log = get_logger("users")


def read_password(prompt: str) -> str:
    """Hidden input on a terminal; plain ``input`` when the input is piped.

    ``getpass`` reads ``/dev/tty`` even when stdin is a pipe (installer, tests),
    so a piped run would wait for the keyboard.
    """
    return getpass.getpass(prompt) if sys.stdin.isatty() else input(prompt)


class UsersConsole:
    """The menu (``ask``, ``ask_password``, ``say``: input, read_password, print)."""

    def __init__(
        self,
        users: Users,
        ask: Ask = input,
        ask_password: Ask = read_password,
        say: Say = print,
    ):
        self.users = users
        self.ask = ask
        self.ask_password = ask_password
        self.say = say
        self.actions = (
            self._add_user,
            self._delete_user,
            self._change_password,
            self._show_api_key,
            self._test_password,
        )

    def run(self) -> int:
        """Show the menu until Exit; return the exit code."""
        try:
            while self._menu():
                pass
        except (EOFError, KeyboardInterrupt):
            self.say("")
        self.say("Exiting...")
        return 0

    def _menu(self) -> bool:
        self._show_help()
        choice = self.ask(f"Enter your choice [1-{EXIT}]: ").strip()
        if choice == EXIT:
            return False
        if not choice.isdigit() or not 1 <= int(choice) <= len(self.actions):
            self.say("Wrong selection. Try again...")
            return True
        index = int(choice) - 1
        self.say(f"----- {TITLES[index]} -----")
        self.actions[index]()
        return True

    def _show_help(self) -> None:
        title = 10 * "-" + " ePiframe user management " + 10 * "-"
        names = [user.username for user in self.users.all()]
        self.say(title)
        self.say("-- Changing anything needs service restart! --")
        self.say("USERS:")
        self.say("\n".join(names) if names else "<NO USERS!>")
        self.say("")
        for number, entry in enumerate(MENU, start=1):
            self.say(f"{number}. {entry}")
        self.say(len(title) * "-")

    def _done(self, message: str) -> None:
        self.say(message)
        self.ask("Press Enter to continue...")

    def _existing_user(self) -> str:
        while True:
            username = self.ask("Username: ")
            if self.users.by_username(username):
                return username
            self.say("User doesn't exist!")

    def _new_username(self) -> str:
        while True:
            username = self.ask("Username: ")
            if not username:
                self.say("Username can't be empty!")
            elif self.users.by_username(username):
                self.say("User already exists!")
            else:
                return username

    def _password(self, username: str, prompt: str) -> str:
        while True:
            password = self.ask_password(prompt)
            try:
                self.users.authenticate(username, password)
            except UserError:
                self.say("Wrong password!")
            else:
                return password

    def _new_password(self, prompt: str) -> str:
        while True:
            password = self.ask_password(f"{prompt} [empty possible]: ")
            if password == self.ask_password(
                f"Confirm {prompt.lower()} [empty possible]: "
            ):
                return password
            self.say("Passwords are not the same!")

    def _add_user(self) -> None:
        username = self._new_username()
        self.users.add(username, self._new_password("Password"))
        log.info(USERS_ACTIONS_TAG + f"User {username} added!")
        self._done("USER ADDED SUCCESSFULLY!")

    def _delete_user(self) -> None:
        username = self._existing_user()
        while True:
            answer = self.ask("Do You really want to delete this user? [y/N]: ")
            answer = answer.strip().lower() or "no"
            if answer in ANSWERS:
                break
            self.say("Please respond with 'yes' or 'no' (or 'y' or 'n')")
        if not ANSWERS[answer]:
            self._done("USER WAS NOT DELETED")
            return
        self.users.delete(username)
        log.info(USERS_ACTIONS_TAG + f"User {username} deleted!")
        self._done("USER DELETED SUCCESSFULLY!")

    def _change_password(self) -> None:
        username = self._existing_user()
        current = self._password(username, "Current password: ")
        self.users.change_password(
            username, current, self._new_password("New password")
        )
        log.info(USERS_ACTIONS_TAG + f"User {username} password changed!")
        self._done("PASSWORD CHANGED SUCCESSFULLY!")

    def _show_api_key(self) -> None:
        username = self._existing_user()
        self._password(username, "Password: ")
        user = self.users.by_username(username)
        self._done(f"USER {username} API KEY: {user.api_key if user else ''}")

    def _test_password(self) -> None:
        username = self._existing_user()
        self._password(username, "Password: ")
        self._done("YOU HAVE LOGGED IN SUCCESSFULLY!")
