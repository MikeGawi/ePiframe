"""Who sends a request: the WebUI session or the API key of a user.

The key comes in the ``api_key`` query parameter or in the ``Authorization``
header (``Basic <key>``, the key may be Base64 encoded, as in 1.x).
"""

import base64
import binascii
from http import HTTPStatus
from typing import Any

from flask import Request, redirect, request
from flask_login import login_url

from epiframe.users.model import User
from epiframe.web.api import API_PREFIX, error_response
from epiframe.web.context import context

BASIC = "Basic "


def header_key(header: str) -> str:
    """The API key of an ``Authorization`` header (plain or Base64)."""
    key = header.removeprefix(BASIC).strip()
    try:
        decoded = base64.b64decode(key, validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        return key
    return decoded if decoded.isprintable() else key


def request_key(incoming: Request) -> str | None:
    header = incoming.headers.get("Authorization")
    return incoming.args.get("api_key") or (header_key(header) if header else None)


def user_from_request(incoming: Request) -> User | None:
    key = request_key(incoming)
    return context().users.by_api_key(key) if key else None


def user_from_session(username: str) -> User | None:
    return context().users.by_username(username)


def unauthorized() -> Any:
    """REST API: ``401`` with an error; WebUI pages: the login page."""
    if request.path.startswith(API_PREFIX):
        return error_response("Unauthorized", HTTPStatus.UNAUTHORIZED)
    return redirect(login_url("login", request.url))
