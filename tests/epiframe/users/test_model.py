from epiframe.users.model import User


def test_user_for_flask_login() -> None:
    user = User(3, "alice", "hash", "key")

    assert user.get_id() == "alice"
    assert user.is_authenticated
    assert user.is_active
    assert not user.is_anonymous
