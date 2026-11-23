"""A WebUI user (Flask-Login)."""

from dataclasses import dataclass

from flask_login import UserMixin


@dataclass(eq=False)
class User(UserMixin):  # type: ignore[misc]  # flask_login is untyped
    id: int
    username: str
    password_hash: str
    api_key: str

    def get_id(self) -> str:
        # Flask-Login keeps the username in the session (as 1.x)
        return self.username
