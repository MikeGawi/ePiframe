"""A WebUI of a frame in ``tmp_path`` (config, users, secret key, photos)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, create_autospec

import fastjsonschema
import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.display.hdmi import HdmiPower
from epiframe.plugins.base import Settings
from epiframe.plugins.manager import PluginManager
from epiframe.service import frame as frame_module
from epiframe.service.frame import Frame, Trigger
from epiframe.users.store import Users
from epiframe.web.app import WebUI
from epiframe.web.openapi import document, openapi_path
from tests.helpers.plugins import TEST_PLUGINS

REPOSITORY = Path(__file__).resolve().parents[3]  # templates/ and static/
PASSWORD = "secret"  # noqa: S105 (test user)
FAST_HASH = "scrypt:1024:8:1"

MakeWeb = Callable[..., WebUI]


@pytest.fixture
def triggers() -> list[Trigger]:
    return []


@pytest.fixture
def hdmi() -> MagicMock:
    power: MagicMock = create_autospec(HdmiPower, instance=True)
    power.state.return_value = True
    return power


@pytest.fixture
def users(tmp_path: Path) -> Users:
    return Users(tmp_path / "users.db", FAST_HASH)


def _plugins(directory: Path, config: Settings) -> PluginManager:
    # "tests.plugins": the package isn't rebound in sys.modules
    return PluginManager(directory, config, "tests.plugins")


def write_config(path: Path, **entries: str) -> None:
    config = ConfigManager(path, paths.CONFIG_FILE_DEFAULT)
    for name, value in entries.items():
        config.set(name, value)
    config.save()


@pytest.fixture
def make_web(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    triggers: list[Trigger],
    hdmi: MagicMock,
    users: Users,
) -> MakeWeb:
    """``make_web(plugins=False, login=False, **config entries)``."""
    monkeypatch.chdir(tmp_path)  # relative paths of the default config
    monkeypatch.setattr(frame_module, "PluginManager", _plugins)

    def make(*, plugins: bool = False, login: bool = False, **entries: str) -> WebUI:
        write_config(tmp_path / "config.cfg", **entries)
        frame = Frame(
            triggers.append,
            tmp_path / "config.cfg",
            REPOSITORY,
            plugins_dir=TEST_PLUGINS if plugins else tmp_path / "plugins",
            hdmi=hdmi,
        )
        web = WebUI(frame, users, tmp_path / "secret.key")
        web.app.config.update(TESTING=True, LOGIN_DISABLED=not login)
        return web

    return make


@pytest.fixture
def web(make_web: MakeWeb) -> WebUI:
    return make_web()


@pytest.fixture
def frame(web: WebUI) -> Frame:
    return web.frame


@pytest.fixture
def app(web: WebUI) -> Flask:
    return web.app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Without users: no login needed."""
    return app.test_client()


@pytest.fixture
def secured(make_web: MakeWeb) -> WebUI:
    """A WebUI with the login (use ``user`` for an account)."""
    return make_web(login=True)


@pytest.fixture
def user_key(users: Users) -> str:
    return users.add("user", PASSWORD).api_key


# ----------------------------------------------------- responses vs the document


class Checker:
    """Checks answers of ``app`` against its OpenAPI document."""

    def __init__(self, app: Flask) -> None:
        self.document = document(app, "test")
        self._compiled: dict[tuple[str, str, int], Callable[[Any], Any]] = {}

    def schema(self, rule: str, method: str, status: int) -> dict[str, Any]:
        operation = self.document["paths"][openapi_path(rule)][method]
        content = operation["responses"][str(status)]["content"]
        schema: dict[str, Any] = content["application/json"]["schema"]
        return schema | {"components": self.document["components"]}

    def __call__(self, response: TestResponse, rule: str, method: str = "get") -> Any:
        key = (rule, method, response.status_code)
        if key not in self._compiled:
            self._compiled[key] = fastjsonschema.compile(self.schema(*key))
        self._compiled[key](response.json)
        return response.json


@pytest.fixture
def check(app: Flask) -> Checker:
    return Checker(app)
