from flask_login import UserMixin


class User(UserMixin):

    id = None
    username = None
    password = None
    api = None

    def __init__(self, identifier: str, username: str, password: str, api: str):
        self.id = identifier
        self.username = username
        self.password = password
        self.api = api

    # overridden
    def get_id(self):
        return str(self.username)
