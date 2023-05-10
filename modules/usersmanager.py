from __future__ import annotations

from typing import List
from misc.constants import Constants
from misc.logs import Logs
from misc.user import User
import crypt
import hashlib
import getpass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.databasemanager import DatabaseManager


class UsersManager:

    __ADD_ERROR = "There was a problem during user insertion to DB"
    __IN_ERROR = "User already exists!"
    __NO_USER_ERROR = "User doesn't exist!"
    __PASSWORD_ERROR = "Wrong password!"

    def __init__(self, database_manager: DatabaseManager):
        self.__choice = None
        self.__databasemanager = database_manager
        self.__schema = database_manager.get_schema(Constants.USERS_TABLE_NAME)

        self.__populate_api_key()

    def __populate_api_key(self):
        # populate api key for old users
        users = self.get()
        if users and len(users):
            self.__set_users(users)

    def __set_users(self, users):
        for item in [user.id for user in users if not user.api]:
            self.__update_api_key(item)

    def __update_api_key(self, item):
        self.__databasemanager.update(
            Constants.USERS_TABLE_NAME,
            Constants.USERS_TABLE_API_HEADER,
            f"'{str(self.__gen_api())}'",
            Constants.USERS_TABLE_ID_HEADER + " IS " + str(item),
        )

    def __get_column(self, name: str):
        return next(column[0] for column in self.__schema if column[1] == name)

    def __to_object(self, rows) -> List[User]:
        result = []
        if rows and len(rows) > 0:
            for row in rows:
                result.append(
                    User(
                        row[self.__get_column(Constants.USERS_TABLE_ID_HEADER)],
                        row[self.__get_column(Constants.USERS_TABLE_USERNAME_HEADER)],
                        row[self.__get_column(Constants.USERS_TABLE_HASH_HEADER)],
                        row[self.__get_column(Constants.USERS_TABLE_API_HEADER)],
                    )
                )
        return result

    def get(self) -> List[User]:
        return self.__to_object(
            self.__databasemanager.select(
                Constants.DB_ALL, Constants.USERS_TABLE_NAME, ""
            )
        )

    def get_by_username(self, username: str) -> List[User]:
        return self.__to_object(
            self.__databasemanager.select(
                Constants.DB_ALL,
                Constants.USERS_TABLE_NAME,
                Constants.USERS_TABLE_USERNAME_HEADER + " IS " + f"'{username}'",
            )
        )

    def get_by_api(self, api: str) -> List[User]:
        return self.__to_object(
            self.__databasemanager.select(
                Constants.DB_ALL,
                Constants.USERS_TABLE_NAME,
                Constants.USERS_TABLE_API_HEADER + " IS " + f"'{api}'",
            )
        )

    def login_needed(self) -> bool:
        user = self.get()
        return user and len(user) > 0 or False

    @staticmethod
    def __add_salt(password: str, salt: str = "") -> (str, str):
        salt = crypt.mksalt(crypt.METHOD_SHA512) if not salt else salt
        return hashlib.md5((password + salt).encode()).hexdigest(), salt

    def __gen_api(self) -> str:
        return self.__add_salt("", "")[0]

    def add(self, user_obj: User):
        ids = self.get_by_username(user_obj.username)
        if not ids:
            password, salt = self.__add_salt(user_obj.password)
            self.__databasemanager.insert(
                Constants.USERS_TABLE_NAME,
                [Constants.DB_NULL, user_obj.username, str(password), user_obj.api],
            )
            ids = self.get_by_username(user_obj.username)

            if ids and len(ids) > 0:
                self.__databasemanager.insert(
                    Constants.SALTS_TABLE_NAME,
                    [Constants.DB_NULL, str(ids[0].id), str(salt)],
                )
            else:
                raise Exception(self.__ADD_ERROR)
        else:
            raise Exception(self.__IN_ERROR)

    def delete(self, username: str):
        ids = self.get_by_username(username)
        if ids and len(ids) > 0:
            self.__databasemanager.delete(
                Constants.USERS_TABLE_NAME,
                Constants.USERS_TABLE_USERNAME_HEADER + f" IS '{username}'",
            )
            self.__databasemanager.delete(
                Constants.SALTS_TABLE_NAME,
                Constants.SALTS_TABLE_USERID_HEADER + " IS " + str(ids[0].id),
            )
        else:
            raise Exception(self.__NO_USER_ERROR)

    def change_password(self, username: str, old_password: str, new_password: str):
        try:
            self.check(username, old_password)
            ids = self.get_by_username(username)
            if ids and len(ids) > 0:
                password, salt = self.__add_salt(new_password)
                self.__databasemanager.update(
                    Constants.USERS_TABLE_NAME,
                    Constants.USERS_TABLE_HASH_HEADER,
                    f"'{str(password)}'",
                    Constants.USERS_TABLE_ID_HEADER + " IS " + str(ids[0].id),
                )
                self.__databasemanager.update(
                    Constants.SALTS_TABLE_NAME,
                    Constants.SALTS_TABLE_SALT_HEADER,
                    f"'{str(salt)}'",
                    Constants.SALTS_TABLE_USERID_HEADER + " IS " + str(ids[0].id),
                )
            else:
                raise Exception(self.__NO_USER_ERROR)
        except Exception as exception:
            raise exception

    def check(self, username: str, password: str):
        ids = self.get_by_username(username)
        if ids and len(ids) > 0:
            salt = self.__databasemanager.select(
                Constants.SALTS_TABLE_SALT_HEADER,
                Constants.SALTS_TABLE_NAME,
                Constants.SALTS_TABLE_USERID_HEADER + " IS " + str(ids[0].id),
            )[0]
            if salt:
                password = self.__add_salt(password, salt[0])
                if not password[0] == ids[0].password:
                    raise Exception(self.__PASSWORD_ERROR)
        else:
            raise Exception(self.__NO_USER_ERROR)

    @staticmethod
    def __result(action: str, result: bool = True):
        print(action, "SUCCESSFULLY!" if result else "")
        input("Press any key to continue...")

    def __user_check(self, exist: bool = True) -> str:
        while True:
            username = input("Username: ")
            if exist:
                if self.get_by_username(username):
                    break
                print(self.__NO_USER_ERROR)
            else:
                if not self.get_by_username(username):
                    break
                print(self.__IN_ERROR)

        return username

    def __password(self, username: str, title: str) -> str:
        while True:
            password = getpass.getpass(title)
            try:
                self.check(username, password)
                break
            except Exception:
                pass
                print(self.__PASSWORD_ERROR)

        return password

    @staticmethod
    def __new_password(title: str, title_confirm: str) -> str:
        while True:
            new_password = getpass.getpass(title)
            new_password2 = getpass.getpass(title_confirm)
            if new_password == new_password2:
                break
            print("Passwords are not the same!")

        return new_password

    def manage(self, log: Logs):
        valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
        loop = True

        while loop:
            loop = self.__loop(log, loop, valid)

    def __loop(self, log: Logs, loop: bool, valid: dict) -> bool:
        self.__show_help()
        choice = input("Enter your choice [1-6]: ")

        choices = [
            "Adding new user",
            "Deleting user",
            "Changing user password",
            "Showing user API key",
            "Testing user password",
        ]

        if not choice.isdigit() or int(choice) not in range(1, len(choices) + 2):
            print("Wrong selection. Try again...")
            return loop

        if int(choice) in range(1, len(choices) + 1):
            methods = [
                self._add_user,
                self._delete_user,
                self._change_password,
                self._show_api_key,
                self._test_password,
            ]

            print(5 * "-", choices[int(choice) - 1], 5 * "-")
            methods[int(choice) - 1].__call__(log, valid)
            return loop

        print("Exiting...")
        return False

    def __show_help(self):
        users = self.get()
        title = 10 * "-" + " ePiframe user management " + 10 * "-"
        print(title)
        print(2 * "-", "Changing anything needs service restart!", 2 * "-")
        print("USERS:")
        print("\n".join([user.username for user in users]) if users else "<NO USERS!>")
        print()
        print("1. Add new user")
        print("2. Delete user")
        print("3. Change user password")
        print("4. Show user API key")
        print("5. Test user password")
        print("6. Exit")
        print(len(title) * "-")

    def _test_password(self, log: Logs, valid: dict):
        username = self.__user_check()
        self.__password(username, "Password: ")
        self.__result("YOU HAVE LOGGED IN")

    def _show_api_key(self, log: Logs, valid: dict):
        username = self.__user_check()
        self.__password(username, "Password: ")
        user_obj = self.get_by_username(username)[0]
        self.__result(f"USER {username} API KEY: {user_obj.api}", False)

    def _change_password(self, log: Logs, valid: dict):
        username = self.__user_check()
        current_password = self.__password(username, "Current password: ")
        new_password = self.__new_password(
            "New password [empty possible]: ",
            "Confirm new password [empty possible]: ",
        )
        self.change_password(username, current_password, new_password)
        log.log(Constants.USERS_ACTIONS_TAG + f"User {username} password changed!")
        self.__result("PASSWORD CHANGED")

    def _delete_user(self, log: Logs, valid: dict):
        username = self.__user_check()
        while True:
            choice = (
                input("Do You really want to delete this user? [y/N]: ").lower() or "no"
            )
            if choice in valid:
                if valid[choice]:
                    self.delete(username)
                    log.log(Constants.USERS_ACTIONS_TAG + f"User {username} deleted!")
                    self.__result("USER DELETED")
                else:
                    self.__result("USER WAS NOT DELETED")
                break
            else:
                print("Please respond with 'yes' or 'no' (or 'y' or 'n')")

    def _add_user(self, log: Logs, valid: dict):
        username = self.__user_check(False)
        password = self.__new_password(
            "Password [empty possible]: ", "Confirm password [empty possible]: "
        )
        self.add(User("", username, password, self.__gen_api()))
        log.log(Constants.USERS_ACTIONS_TAG + f"User {username} added!")
        self.__result("USER ADDED")
