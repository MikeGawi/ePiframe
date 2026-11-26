from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Optional

import fastjsonschema
import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage

from epiframe.version import VERSION
from epiframe.web.api import Done, api
from epiframe.web.app import WebUI
from epiframe.web.openapi import (
    OPENAPI_VERSION,
    Schemas,
    api_rules,
    document,
    openapi_path,
)
from tests.epiframe.web.conftest import MakeWeb
from tests.epiframe.web.test_api import Color, NamePath, Query, Upload


@dataclass(frozen=True)
class Node:
    name: str
    children: list["Node"]
    parent: Optional["Node"] = None
    tags: dict[str, int] = field(default_factory=dict)


def test_openapi_path() -> None:
    assert openapi_path("/api/action=<action>") == "/api/action={action}"
    assert openapi_path("/api/a/<int:x>/<path:y>") == "/api/a/{x}/{y}"


@pytest.mark.parametrize(
    ("hint", "schema"),
    [
        (str, {"type": "string"}),
        (int, {"type": "integer"}),
        (float, {"type": "number"}),
        (bool, {"type": "boolean"}),
        (FileStorage, {"type": "string", "format": "binary"}),
        (Color, {"enum": ["red", "green"]}),
        (list[int], {"type": "array", "items": {"type": "integer"}}),
        (int | None, {"anyOf": [{"type": "integer"}, {"type": "null"}]}),
    ],
)
def test_schemas(hint: Any, schema: dict[str, Any]) -> None:
    assert Schemas().of(hint) == schema


def test_dataclasses_are_components() -> None:
    schemas = Schemas()

    assert schemas.of(Node) == {"$ref": "#/components/schemas/Node"}
    assert schemas.components == {
        "Node": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "children": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/Node"},
                },
                "parent": {
                    "anyOf": [{"$ref": "#/components/schemas/Node"}, {"type": "null"}],
                    "default": None,
                },
                "tags": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"},
                },
            },
            "required": ["name", "children"],
        }
    }


@api(
    "Search",
    description="Finds things.",
    path=NamePath,
    query=Query,
    response=Done,
    errors=(HTTPStatus.BAD_REQUEST,),
)
def search(path: NamePath, query: Query) -> Done:
    raise NotImplementedError


@api("Upload", form=Upload, media_type="image/*")
def upload(form: Upload) -> Done:
    raise NotImplementedError


def undeclared() -> str:
    raise NotImplementedError


@pytest.fixture
def app() -> Flask:
    app = Flask(__name__)
    app.add_url_rule("/api/search/<name>", view_func=search, methods=["GET", "POST"])
    app.add_url_rule("/api/search", view_func=search, endpoint="search_all")
    app.add_url_rule("/api/upload", view_func=upload, methods=["PUT"])
    app.add_url_rule("/api/undeclared", view_func=undeclared)
    app.add_url_rule("/page", view_func=undeclared, endpoint="page")
    return app


def test_api_rules(app: Flask) -> None:
    rules = [(rule.rule, endpoint) for rule, endpoint in api_rules(app)]

    assert [rule for rule, _ in rules] == [
        "/api/search",
        "/api/search/<name>",
        "/api/undeclared",
        "/api/upload",
    ]
    assert rules[2][1] is None


def test_document(app: Flask) -> None:
    result = document(app, "1.2.3")

    assert result["openapi"] == OPENAPI_VERSION
    assert result["info"]["version"] == "1.2.3"
    assert list(result["paths"]) == ["/api/search", "/api/search/{name}", "/api/upload"]
    assert set(result["components"]["schemas"]) == {"Done", "Error", "Upload"}
    assert result["security"] == [{"api_key": []}, {"authorization": []}]


def test_operation(app: Flask) -> None:
    paths = document(app, "1")["paths"]
    get = paths["/api/search/{name}"]["get"]

    assert get["operationId"] == "search"
    assert paths["/api/search/{name}"]["post"]["operationId"] == "search_2"
    assert paths["/api/search"]["get"]["operationId"] == "search_all"
    assert (get["summary"], get["description"]) == ("Search", "Finds things.")
    assert set(get["responses"]) == {"200", "400", "401"}
    assert get["responses"]["400"]["description"] == "Bad Request"
    assert get["responses"]["200"]["content"] == {
        "application/json": {"schema": {"$ref": "#/components/schemas/Done"}}
    }


def test_parameters(app: Flask) -> None:
    paths = document(app, "1")["paths"]
    parameters = {
        item["name"]: item for item in paths["/api/search/{name}"]["get"]["parameters"]
    }
    # without the variable in the rule the path parameter is left out
    without_path = paths["/api/search"]["get"]["parameters"]

    assert parameters["name"] == {
        "name": "name",
        "in": "path",
        "required": True,
        "schema": {"type": "string", "description": "A name"},
        "description": "A name",
    }
    assert parameters["count"]["schema"] == {"type": "integer", "default": 1}
    assert parameters["count"]["required"] is False
    assert parameters["flag"]["allowEmptyValue"] is True
    assert parameters["color"]["schema"]["default"] == "red"
    assert (parameters["names"]["style"], parameters["names"]["explode"]) == (
        "form",
        False,
    )
    assert "name" not in {item["name"] for item in without_path}


def test_request_body_and_media_type(app: Flask) -> None:
    put = document(app, "1")["paths"]["/api/upload"]["put"]

    assert put["requestBody"] == {
        "required": True,
        "content": {
            "multipart/form-data": {"schema": {"$ref": "#/components/schemas/Upload"}}
        },
    }
    assert put["responses"]["200"]["content"] == {
        "image/*": {"schema": {"type": "string", "format": "binary"}}
    }
    assert "parameters" not in put


# ----------------------------------------------------------- the ePiframe API


@pytest.fixture
def plugin_web(make_web: MakeWeb) -> WebUI:
    return make_web(plugins=True)


def test_every_api_route_is_declared(plugin_web: WebUI) -> None:
    undeclared = [
        rule.rule for rule, endpoint in api_rules(plugin_web.app) if not endpoint
    ]

    assert undeclared == []


def test_epiframe_document(plugin_web: WebUI) -> None:
    result = document(plugin_web.app, VERSION)

    assert sorted(result["paths"]) == [
        "/api/action={action}",
        "/api/display_power=",
        "/api/display_power={power}",
        "/api/get_image",
        "/api/get_log",
        "/api/get_stats",
        "/api/get_status",
        "/api/get_text/{text}",  # the test plugin
        "/api/openapi.json",
        "/api/upload_photo",
    ]
    assert list(result["paths"]["/api/upload_photo"]) == ["post"]
    # the component schemas are valid JSON schemas
    for schema in result["components"]["schemas"].values():
        fastjsonschema.compile(schema | {"components": result["components"]})


def test_served_document(plugin_web: WebUI) -> None:
    response = plugin_web.app.test_client().get("/api/openapi.json")

    assert response.status_code == HTTPStatus.OK
    assert response.json == document(plugin_web.app, VERSION)


def test_answer_without_content() -> None:
    @api("Nothing")
    def nothing() -> None:
        raise NotImplementedError

    app = Flask(__name__)
    app.add_url_rule("/api/nothing", view_func=nothing)

    answer = document(app, "1")["paths"]["/api/nothing"]["get"]["responses"]["200"]

    assert answer == {"description": "OK"}
