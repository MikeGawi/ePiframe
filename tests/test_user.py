from misc.user import User


def test_user():
    user_id = "user_id"
    username = "user_username"
    password = "user_password"
    api = "user_api_key"
    user: User = User(identifier=user_id, username=username, password=password, api=api)

    assert user
    assert user.id == user_id
    assert user.username == username
    assert user.password == password
    assert user.api == api
    assert user.get_id() == username
