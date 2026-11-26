"""REST API endpoints: one declaration per endpoint.

A view of the REST API is decorated with :func:`api`; the declaration names the
dataclasses of its parameters and result::

    @dataclass(frozen=True)
    class ImageQuery:
        thumb: bool = field(default=False, metadata=doc("The thumbnail"))

    @api("The displayed photo", query=ImageQuery, media_type="image/*")
    def get_image(query: ImageQuery) -> Response: ...

From the declaration the decorator:

- requires the login (the WebUI session or the API key, see
  :mod:`epiframe.web.auth`);
- parses the path, query and form values into the dataclasses (``query=``,
  ``path=``, ``form=``) and passes them to the view as keyword arguments of the
  same names; bad input is answered with ``400`` and ``{"error": "<message>"}``;
- answers a returned dataclass as JSON (other results, e.g. files, are passed
  through) and :class:`ApiError` raised by the view as ``{"error": ...}``;
- keeps the declaration on the view for the OpenAPI document
  (:mod:`epiframe.web.openapi`).

Field types: ``str``, ``int``, ``float``, ``bool``, ``Enum``, ``list[...]``
(comma separated in a query), ``X | None``, nested dataclasses (results only) and
``FileStorage`` (a file of a form). A ``bool`` query value may be empty
(``?thumb`` means true); ``1``/``true``/``yes``/``on`` and
``0``/``false``/``no``/``off`` are accepted in any case.
"""

import functools
import types
from collections.abc import Callable, Mapping
from dataclasses import MISSING, Field, dataclass, field, fields, is_dataclass
from enum import Enum
from http import HTTPStatus
from typing import Any, TypeVar, Union, cast, get_args, get_origin, get_type_hints

import flask_login
from flask import Response, jsonify, request
from werkzeug.datastructures import FileStorage

API_PREFIX = "/api/"
DECLARATION = "api_endpoint"  # attribute of a declared view
DESCRIPTION = "description"  # field metadata key
UNIONS = (Union, types.UnionType)
TRUE = frozenset({"", "1", "true", "yes", "on"})
FALSE = frozenset({"0", "false", "no", "off"})

T = TypeVar("T")
View = Callable[..., Any]
V = TypeVar("V", bound=View)
Converter = Callable[[Any, str], Any]


def login_required(view: V) -> V:
    """``flask_login.login_required`` (untyped) for typed views."""
    return cast(V, flask_login.login_required(view))


def doc(description: str) -> dict[str, str]:
    """Field metadata with the description of a parameter or result field."""
    return {DESCRIPTION: description}


class ApiError(Exception):
    """A request the endpoint can't serve: ``{"error": message}`` with ``status``."""

    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass(frozen=True)
class Error:
    """The answer to a failed request."""

    error: str = field(metadata=doc("What went wrong"))


@dataclass(frozen=True)
class Done:
    """The answer to a request that was carried out."""

    status: str = field(metadata=doc("Always OK"))


DONE = Done("OK")


@dataclass(frozen=True)
class Endpoint:
    """The declaration of a REST API endpoint."""

    summary: str
    description: str = ""
    query: type[Any] | None = None
    path: type[Any] | None = None
    form: type[Any] | None = None
    response: type[Any] | None = None  # a dataclass answered as JSON
    media_type: str | None = None  # the type of other answers ("image/*")
    errors: tuple[int, ...] = ()  # documented error statuses


def api(  # noqa: PLR0913 (the fields of Endpoint)
    summary: str,
    *,
    description: str = "",
    query: type[Any] | None = None,
    path: type[Any] | None = None,
    form: type[Any] | None = None,
    response: type[Any] | None = None,
    media_type: str | None = None,
    errors: tuple[int, ...] = (),
) -> Callable[[View], View]:
    """Declare a REST API view (see the module documentation)."""
    endpoint = Endpoint(
        summary, description, query, path, form, response, media_type, errors
    )

    def decorate(view: View) -> View:
        @functools.wraps(view)
        def handle(*arguments: Any, **path_values: Any) -> Any:
            try:
                parsed = _arguments(endpoint, path_values)
                return _answer(view(*arguments, **parsed))
            except ApiError as error:
                return error_response(error.message, error.status)

        setattr(handle, DECLARATION, endpoint)
        return login_required(handle)

    return decorate


def declaration(view: Any) -> Endpoint | None:
    """The declaration of ``view``, ``None`` if it isn't a REST API view."""
    found = getattr(view, DECLARATION, None)
    return found if isinstance(found, Endpoint) else None


def error_response(message: str, status: int) -> tuple[Response, int]:
    return jsonify(error=message), status


def _answer(result: Any) -> Any:
    return jsonify(result) if is_dataclass(result) else result


def _form() -> dict[str, Any]:
    return request.form.to_dict() | request.files.to_dict()


def _arguments(endpoint: Endpoint, path_values: Mapping[str, Any]) -> dict[str, Any]:
    sources: dict[str, tuple[type[Any] | None, Callable[[], Mapping[str, Any]]]] = {
        "path": (endpoint.path, lambda: path_values),
        "query": (endpoint.query, lambda: request.args),
        "form": (endpoint.form, _form),
    }
    return {
        name: parse(declared, values())
        for name, (declared, values) in sources.items()
        if declared is not None
    }


# ----------------------------------------------------------------------- parsing


def parse(cls: type[T], values: Mapping[str, Any]) -> T:
    """``cls`` (a dataclass) from the request ``values`` (strings or files).

    Raises :class:`ApiError` with a message for the user.
    """
    hints = get_type_hints(cls)
    arguments = {
        item.name: _value(item, hints[item.name], values)
        for item in fields(cast(Any, cls))
    }
    return cls(
        **{name: value for name, value in arguments.items() if value is not MISSING}
    )


def _value(item: Field[Any], hint: Any, values: Mapping[str, Any]) -> Any:
    if item.name in values:
        return converter(hint)(values[item.name], item.name)
    if required(item):
        raise ApiError(f"Missing parameter {item.name!r}")
    return MISSING


def required(item: Field[Any]) -> bool:
    return item.default is MISSING and item.default_factory is MISSING


def without_none(hint: Any) -> Any:
    """``X`` of ``X | None``."""
    (inner,) = (argument for argument in get_args(hint) if argument is not type(None))
    return inner


def is_enum(hint: Any) -> bool:
    return isinstance(hint, type) and issubclass(hint, Enum)


def converter(hint: Any) -> Converter:
    """The function converting a request value to ``hint``."""
    origin = get_origin(hint)
    if origin in UNIONS:
        return converter(without_none(hint))
    if origin is list:
        return functools.partial(_items, converter(get_args(hint)[0]))
    if is_enum(hint):
        return functools.partial(_choice, hint)
    return SCALARS[hint]


def split(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def _items(convert: Converter, text: str, name: str) -> list[Any]:
    return [convert(item, name) for item in split(text)]


def _choice(cls: type[Enum], text: str, name: str) -> Enum:
    try:
        return cls(text)
    except ValueError:
        choices = ", ".join(str(member.value) for member in cls)
        raise ApiError(f"Wrong {name} {text!r}, use one of: {choices}") from None


def _number(cls: type[T]) -> Converter:
    def convert(text: str, name: str) -> T:
        try:
            return cls(text)  # type: ignore[call-arg]
        except ValueError:
            raise ApiError(f"Wrong {name} {text!r}, expected {cls.__name__}") from None

    return convert


def _bool(text: str, name: str) -> bool:
    value = text.lower()
    if value not in TRUE | FALSE:
        raise ApiError(f"Wrong {name} {text!r}, expected true or false")
    return value in TRUE


def _str(text: str, name: str) -> str:
    return text


def _file(value: Any, name: str) -> FileStorage:
    if not isinstance(value, FileStorage):
        raise ApiError(f"{name!r} must be a file")
    return value


SCALARS: dict[Any, Converter] = {
    str: _str,
    int: _number(int),
    float: _number(float),
    bool: _bool,
    FileStorage: _file,
}
