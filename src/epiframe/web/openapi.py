"""The OpenAPI 3.1 document of the REST API, generated from the declarations.

Paths and methods come from the Flask routes under ``/api/`` (also those of the
plugins), the parameters, request bodies and answers from the dataclasses of
:func:`epiframe.web.api.api`. Nothing is written by hand, so the document can't
get out of step with the code.
"""

import re
import types
from collections.abc import Iterator
from dataclasses import MISSING, Field, fields, is_dataclass
from enum import Enum
from http import HTTPStatus
from typing import Any, get_args, get_origin, get_type_hints

from flask import Flask
from werkzeug.datastructures import FileStorage
from werkzeug.routing import Rule

from epiframe.web.api import (
    API_PREFIX,
    DESCRIPTION,
    Endpoint,
    Error,
    declaration,
    is_enum,
    required,
)

OPENAPI_VERSION = "3.1.0"
SCHEMAS = "#/components/schemas/"
RULE_VARIABLE = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")
SKIPPED_METHODS = frozenset({"HEAD", "OPTIONS"})
BINARY = {"type": "string", "format": "binary"}
SCALAR_SCHEMAS: dict[Any, dict[str, str]] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    FileStorage: BINARY,
}
MEDIA_SCHEMAS = {
    "application/json": {"type": "object"},
    "text/plain": {"type": "string"},
}
SECURITY_SCHEMES = {
    "api_key": {
        "type": "apiKey",
        "in": "query",
        "name": "api_key",
        "description": "The API key of a WebUI user (see `epiframe users`).",
    },
    "authorization": {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": "`Basic <API key>`, the key may be Base64 encoded.",
    },
}
DESCRIPTION_TEXT = (
    "Control and status of the ePiframe photo frame. Without any WebUI user the API"
    " is open to everybody, otherwise every request needs the API key of a user"
    " (or the WebUI login). Failed requests are answered with"
    ' `{"error": "<message>"}`.'
)


def openapi_path(rule: str) -> str:
    """``/api/action=<action>`` → ``/api/action={action}``."""
    return RULE_VARIABLE.sub(r"{\1}", rule)


def api_rules(app: Flask) -> Iterator[tuple[Rule, Endpoint | None]]:
    """The routes under ``/api/`` with their declarations (``None``: undeclared)."""
    for rule in sorted(app.url_map.iter_rules(), key=lambda rule: rule.rule):
        if rule.rule.startswith(API_PREFIX):
            yield rule, declaration(app.view_functions[rule.endpoint])


def _paths(app: Flask, schemas: "Schemas") -> dict[str, dict[str, Any]]:
    paths: dict[str, dict[str, Any]] = {}
    for rule, endpoint in api_rules(app):
        if endpoint is not None:
            path = paths.setdefault(openapi_path(rule.rule), {})
            path.update(schemas.operations(rule, endpoint))
    return paths


def document(app: Flask, version: str) -> dict[str, Any]:
    """The OpenAPI document of the declared routes of ``app``."""
    schemas = Schemas()
    paths = _paths(app, schemas)
    return {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": "ePiframe",
            "version": version,
            "description": DESCRIPTION_TEXT,
        },
        "paths": paths,
        "components": {
            "schemas": schemas.components,
            "securitySchemes": SECURITY_SCHEMES,
        },
        "security": [{name: []} for name in SECURITY_SCHEMES],
    }


def _described(item: Field[Any]) -> dict[str, Any]:
    text = item.metadata.get(DESCRIPTION)
    return {"description": text} if text else {}


def _default(item: Field[Any]) -> dict[str, Any]:
    if item.default is MISSING:
        return {}
    value = item.default.value if isinstance(item.default, Enum) else item.default
    return {"default": value}


def _query_style(hint: Any) -> dict[str, Any]:
    if hint is bool:
        return {"allowEmptyValue": True}
    if get_origin(hint) is list:
        return {"style": "form", "explode": False}  # comma separated
    return {}


class Schemas:
    """JSON schemas of the declared types; dataclasses go to ``components``."""

    def __init__(self) -> None:
        self.components: dict[str, dict[str, Any]] = {}
        self._operation_ids: set[str] = set()

    # ----------------------------------------------------------------- schemas

    def of(self, hint: Any) -> dict[str, Any]:
        origin = get_origin(hint)
        if origin is None:
            return self._plain(hint)
        return self._generic(origin, get_args(hint))

    def _generic(self, origin: Any, arguments: tuple[Any, ...]) -> dict[str, Any]:
        if origin is list:
            return {"type": "array", "items": self.of(arguments[0])}
        if origin is dict:
            return {"type": "object", "additionalProperties": self.of(arguments[1])}
        return self._nullable(arguments)  # X | None

    def _nullable(self, arguments: tuple[Any, ...]) -> dict[str, Any]:
        inner = [self.of(item) for item in arguments if item is not types.NoneType]
        return {"anyOf": [*inner, {"type": "null"}]}

    def _plain(self, hint: Any) -> dict[str, Any]:
        if is_dataclass(hint):
            return self._reference(hint)  # type: ignore[arg-type]
        if is_enum(hint):
            return {"enum": [member.value for member in hint]}
        return dict(SCALAR_SCHEMAS[hint])

    def _reference(self, cls: type[Any]) -> dict[str, Any]:
        name = cls.__name__
        if name not in self.components:
            self.components[name] = {}  # recursive types refer to it
            self.components[name] = self.object(cls)
        return {"$ref": SCHEMAS + name}

    def object(self, cls: type[Any]) -> dict[str, Any]:
        hints = get_type_hints(cls)
        properties = {
            item.name: self.property(item, hints[item.name]) for item in fields(cls)
        }
        needed = [item.name for item in fields(cls) if required(item)]
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        return schema | ({"required": needed} if needed else {})

    def property(self, item: Field[Any], hint: Any) -> dict[str, Any]:
        return self.of(hint) | _described(item) | _default(item)

    # -------------------------------------------------------------- operations

    def operations(self, rule: Rule, endpoint: Endpoint) -> dict[str, Any]:
        methods = sorted((rule.methods or set()) - SKIPPED_METHODS)
        return {method.lower(): self.operation(rule, endpoint) for method in methods}

    def operation(self, rule: Rule, endpoint: Endpoint) -> dict[str, Any]:
        operation: dict[str, Any] = {
            "operationId": self._operation_id(rule.endpoint),
            "summary": endpoint.summary,
            "responses": self.responses(endpoint),
        }
        if endpoint.description:
            operation["description"] = endpoint.description
        return operation | self._parameters(rule, endpoint) | self._body(endpoint)

    def _operation_id(self, name: str) -> str:
        unique, number = name, 1
        while unique in self._operation_ids:
            number += 1
            unique = f"{name}_{number}"
        self._operation_ids.add(unique)
        return unique

    def _parameters(self, rule: Rule, endpoint: Endpoint) -> dict[str, Any]:
        variables = set(RULE_VARIABLE.findall(rule.rule))
        parameters = [
            parameter
            for parameter in self.parameters(endpoint.path, "path")
            if parameter["name"] in variables
        ] + self.parameters(endpoint.query, "query")
        return {"parameters": parameters} if parameters else {}

    def parameters(self, cls: type[Any] | None, location: str) -> list[dict[str, Any]]:
        if cls is None:
            return []
        hints = get_type_hints(cls)
        return [
            self._parameter(item, hints[item.name], location) for item in fields(cls)
        ]

    def _parameter(self, item: Field[Any], hint: Any, location: str) -> dict[str, Any]:
        parameter = {
            "name": item.name,
            "in": location,
            "required": location == "path" or required(item),
            "schema": self.property(item, hint),
        }
        extra = _query_style(hint) if location == "query" else {}
        return parameter | _described(item) | extra

    def _body(self, endpoint: Endpoint) -> dict[str, Any]:
        if endpoint.form is None:
            return {}
        content = {"multipart/form-data": {"schema": self.of(endpoint.form)}}
        return {"requestBody": {"required": True, "content": content}}

    def responses(self, endpoint: Endpoint) -> dict[str, Any]:
        answers = {"200": self._success(endpoint)}
        for status in (*endpoint.errors, HTTPStatus.UNAUTHORIZED):
            answers[str(int(status))] = self._error(HTTPStatus(status))
        return answers

    def _success(self, endpoint: Endpoint) -> dict[str, Any]:
        answer: dict[str, Any] = {"description": "OK"}
        if endpoint.response is not None:
            schema = self.of(endpoint.response)
            answer["content"] = {"application/json": {"schema": schema}}
        elif endpoint.media_type is not None:
            schema = MEDIA_SCHEMAS.get(endpoint.media_type, BINARY)
            answer["content"] = {endpoint.media_type: {"schema": schema}}
        return answer

    def _error(self, status: HTTPStatus) -> dict[str, Any]:
        content = {"application/json": {"schema": self.of(Error)}}
        return {"description": status.phrase, "content": content}
