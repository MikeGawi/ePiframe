from dataclasses import dataclass, field
from enum import StrEnum
from http import HTTPStatus
from io import BytesIO
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.datastructures import FileStorage

from epiframe.web.api import (
    DONE,
    ApiError,
    Done,
    Endpoint,
    api,
    converter,
    declaration,
    doc,
    parse,
    split,
)


class Color(StrEnum):
    RED = "red"
    GREEN = "green"


@dataclass(frozen=True)
class Query:
    count: int = 1
    ratio: float = 0.5
    flag: bool = False
    color: Color = Color.RED
    names: list[str] = field(default_factory=list)
    limit: int | None = None


@dataclass(frozen=True)
class NamePath:
    name: str = field(metadata=doc("A name"))


@dataclass(frozen=True)
class Upload:
    file: FileStorage
    title: str = ""


@dataclass(frozen=True)
class Echo:
    path: str
    query: Query
    form: str


@api("Echo", path=NamePath, query=Query, response=Echo)
def echo(path: NamePath, query: Query) -> Echo:
    return Echo(path.name, query, "")


@api("Upload", form=Upload, response=Echo)
def upload(form: Upload) -> Echo:
    return Echo(form.file.filename or "", Query(), form.title)


@api("Fails", errors=(HTTPStatus.CONFLICT,))
def fails() -> Done:
    raise ApiError("Busy!", HTTPStatus.CONFLICT)


@api("Text", media_type="text/plain")
def text() -> str:
    return "plain"


@pytest.fixture
def test_client() -> FlaskClient:
    app = Flask(__name__)
    app.config.update(TESTING=True, LOGIN_DISABLED=True)
    app.add_url_rule("/api/echo/<name>", view_func=echo)
    app.add_url_rule("/api/upload", view_func=upload, methods=["POST"])
    app.add_url_rule("/api/fails", view_func=fails)
    app.add_url_rule("/api/text", view_func=text)
    return app.test_client()


def test_declaration_is_kept() -> None:
    endpoint = declaration(echo)

    assert endpoint == Endpoint("Echo", path=NamePath, query=Query, response=Echo)
    assert echo.__name__ == "echo"  # the Flask endpoint name
    assert declaration(test_declaration_is_kept) is None


def test_defaults(test_client: FlaskClient) -> None:
    response = test_client.get("/api/echo/x")

    assert response.status_code == HTTPStatus.OK
    assert response.json == {
        "path": "x",
        "form": "",
        "query": {
            "count": 1,
            "ratio": 0.5,
            "flag": False,
            "color": "red",
            "names": [],
            "limit": None,
        },
    }


def test_query_values(test_client: FlaskClient) -> None:
    query = "count=3&ratio=2.5&flag&color=green&names=a,%20b,,c&limit=7"

    json: Any = test_client.get(f"/api/echo/x?{query}").json

    assert json["query"] == {
        "count": 3,
        "ratio": 2.5,
        "flag": True,
        "color": "green",
        "names": ["a", "b", "c"],
        "limit": 7,
    }


@pytest.mark.parametrize(
    ("query", "error"),
    [
        ("count=x", "Wrong count 'x', expected int"),
        ("ratio=1,5", "Wrong ratio '1,5', expected float"),
        ("flag=maybe", "Wrong flag 'maybe', expected true or false"),
        ("color=blue", "Wrong color 'blue', use one of: red, green"),
        ("limit=", "Wrong limit '', expected int"),
    ],
)
def test_bad_query(test_client: FlaskClient, query: str, error: str) -> None:
    response = test_client.get(f"/api/echo/x?{query}")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json == {"error": error}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", True),
        ("1", True),
        ("ON", True),
        ("Yes", True),
        ("0", False),
        ("off", False),
    ],
)
def test_bool(text: str, expected: bool) -> None:
    assert converter(bool)(text, "flag") is expected


def test_form_with_file(test_client: FlaskClient) -> None:
    data = {"file": (BytesIO(b"x"), "photo.jpg"), "title": "Hi"}

    response = test_client.post("/api/upload", data=data)

    assert response.status_code == HTTPStatus.OK
    assert response.json is not None
    assert (response.json["path"], response.json["form"]) == ("photo.jpg", "Hi")


def test_missing_parameter(test_client: FlaskClient) -> None:
    response = test_client.post("/api/upload", data={"title": "Hi"})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json == {"error": "Missing parameter 'file'"}


def test_text_instead_of_file() -> None:
    with pytest.raises(ApiError, match="'file' must be a file"):
        parse(Upload, {"file": "photo.jpg"})


def test_error_of_the_view(test_client: FlaskClient) -> None:
    response = test_client.get("/api/fails")

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json == {"error": "Busy!"}


def test_other_answers_are_passed_through(test_client: FlaskClient) -> None:
    assert test_client.get("/api/text").data == b"plain"


def test_login_is_required() -> None:
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.add_url_rule("/api/text", view_func=text)

    # no login manager: flask_login asks the app for one
    with pytest.raises(AttributeError, match="login_manager"):
        app.test_client().get("/api/text")


def test_method_views() -> None:
    class Plugin:
        prefix = ">"

        @api("Method", path=NamePath)
        def view(self, path: NamePath) -> str:
            return self.prefix + path.name

    app = Flask(__name__)
    app.config.update(TESTING=True, LOGIN_DISABLED=True)
    plugin = Plugin()
    app.add_url_rule("/api/m/<name>", view_func=plugin.view)

    assert declaration(plugin.view) is not None
    assert app.test_client().get("/api/m/x").data == b">x"


def test_split() -> None:
    assert split(" a, ,b,") == ["a", "b"]


def test_done() -> None:
    assert Done("OK") == DONE
