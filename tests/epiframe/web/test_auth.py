import base64
from http import HTTPStatus

import pytest

from epiframe.users.store import Users
from epiframe.web.app import WebUI
from epiframe.web.auth import header_key
from tests.epiframe.web.conftest import PASSWORD


def encoded(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


@pytest.mark.parametrize(
    ("header", "key"),
    [
        ("Basic plain-key", "plain-key"),
        (f"Basic {encoded('my key')}", "my key"),
        (encoded("my key"), "my key"),
        ("Basic " + encoded("a\x00b"), encoded("a\x00b")),  # not printable
        ("Basic //4=", "//4="),  # b'\xff\xfe': not UTF-8
    ],
)
def test_header_key(header: str, key: str) -> None:
    assert header_key(header) == key


def test_api_needs_a_key(secured: WebUI, user_key: str) -> None:
    response = secured.app.test_client().get("/api/get_status")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json == {"error": "Unauthorized"}  # 1.x: the login page


def test_pages_redirect_to_the_login(secured: WebUI, user_key: str) -> None:
    response = secured.app.test_client().get("/settings?x=1")

    assert response.status_code == HTTPStatus.FOUND
    assert response.location == "/login?next=%2Fsettings%3Fx%3D1"


def test_key_in_the_query(secured: WebUI, user_key: str) -> None:
    client = secured.app.test_client()

    accepted = client.get("/api/display_power=", query_string={"api_key": user_key})
    refused = client.get("/api/display_power=", query_string={"api_key": "wrong"})

    assert accepted.status_code == HTTPStatus.OK
    assert accepted.json == {"state": "1"}
    assert refused.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize("plain", [True, False])
def test_key_in_the_header(secured: WebUI, user_key: str, plain: bool) -> None:
    key = user_key if plain else encoded(user_key)

    response = secured.app.test_client().get(
        "/api/display_power=", headers={"Authorization": f"Basic {key}"}
    )

    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize("injection", ["' OR '1'='1", "x' OR 1=1 --"])
def test_api_key_sql_injection_is_refused(
    secured: WebUI, user_key: str, injection: str
) -> None:
    # 1.x built the SQL from the key: "?api_key=' OR '1'='1" logged in
    response = secured.app.test_client().get(
        "/api/display_power=", query_string={"api_key": injection}
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_session_login(secured: WebUI, users: Users) -> None:
    users.add("login-test", PASSWORD)
    client = secured.app.test_client()

    wrong = client.post("/login", data={"username": "login-test", "password": "x"})
    before = client.get("/api/get_status")
    right = client.post("/login", data={"username": "login-test", "password": PASSWORD})
    after = client.get("/api/get_status")
    client.get("/logout")
    logged_out = client.get("/api/get_status")

    assert wrong.status_code == right.status_code == HTTPStatus.FOUND
    assert before.status_code == HTTPStatus.UNAUTHORIZED
    assert after.status_code == HTTPStatus.OK
    assert logged_out.status_code == HTTPStatus.UNAUTHORIZED


def test_session_of_a_deleted_user(secured: WebUI, users: Users) -> None:
    users.add("gone", PASSWORD)
    client = secured.app.test_client()
    client.post("/login", data={"username": "gone", "password": PASSWORD})
    users.delete("gone")

    assert client.get("/api/get_status").status_code == HTTPStatus.UNAUTHORIZED
