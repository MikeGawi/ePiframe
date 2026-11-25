import logging
import socket
import threading
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from flask import Blueprint

from epiframe.config import paths
from epiframe.service.frame import Frame
from epiframe.users.store import Users
from epiframe.web import app as app_module
from epiframe.web.api import api
from epiframe.web.app import MENU, WebUI, serve_test
from epiframe.web.extensions import MenuEntry, Route
from tests.epiframe.web.conftest import PASSWORD, MakeWeb


def test_menu(make_web: MakeWeb) -> None:
    web = make_web(dark_theme="1")

    with web.app.test_request_context():
        context = web.template_context()

    assert context["menu"] == list(MENU)
    assert context["dark_theme"] is True


def test_menu_without_stats(make_web: MakeWeb) -> None:
    web = make_web(show_stats="0", dark_theme="0")

    with web.app.test_request_context():
        context = web.template_context()

    assert "/stats" not in [entry.url for entry in context["menu"]]
    assert context["dark_theme"] is False


def test_builtin_actions(web: WebUI) -> None:
    actions = web.context.actions

    assert list(actions) == ["next", "restart", "reboot", "poweroff"]
    assert [action.button for action in actions.values()] == [True, True, True, False]


def test_add_menu_entries(web: WebUI) -> None:
    entry = MenuEntry("name", "/url", "id", "icon")

    web.add_menu_entries([entry])

    assert web.context.menu[-1] == entry


@pytest.fixture
def plugin_web(make_web: MakeWeb, caplog: pytest.LogCaptureFixture) -> WebUI:
    caplog.set_level(logging.INFO, logger="epiframe")
    return make_web(plugins=True)


def test_plugin_api(plugin_web: WebUI) -> None:
    client = plugin_web.app.test_client()

    response = client.get("/api/get_text/my_text")

    assert response.status_code == HTTPStatus.OK
    assert response.json == {"text_label": "my_text"}
    assert "get_text" in plugin_web.app.view_functions  # url_for("get_text")


def test_plugin_routes_must_be_declared_api(
    plugin_web: WebUI, caplog: pytest.LogCaptureFixture
) -> None:
    client = plugin_web.app.test_client()

    assert client.get("/api/undeclared").status_code == HTTPStatus.NOT_FOUND
    assert client.get("/not_api/x").status_code == HTTPStatus.NOT_FOUND
    logged = " ".join(record.getMessage() for record in caplog.get_records("setup"))
    assert "/api/undeclared skipped" in logged
    assert "/not_api/<text> skipped" in logged


def test_plugin_action(plugin_web: WebUI, capsys: pytest.CaptureFixture[str]) -> None:
    client = plugin_web.app.test_client()

    response = client.get("/api/action=lightoff")
    page = client.get("/tools").text

    assert response.json == {"status": "OK"}
    assert "I'm dummy" in capsys.readouterr().out
    assert "Turn Light Off" in page


def test_plugin_menu(plugin_web: WebUI) -> None:
    page = plugin_web.app.test_client().get("/").text

    assert '<i class="fs-6 bi bi-server"></i> <span>Server</span>' in page


def test_broken_plugin_is_skipped(
    make_web: MakeWeb, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(*arguments: object) -> list[object]:
        raise RuntimeError("bug")

    with patch("tests.plugins.plugin1._plugin.Plugin.add_action", broken):
        web = make_web(plugins=True)

    assert "Plugin Plugin1 failed to extend the WebUI" in caplog.text
    assert "lightoff" not in web.context.actions
    assert "get_text" in web.app.view_functions  # the other hooks work


def test_page_errors_stay_html(web: WebUI) -> None:
    response = web.app.test_client().post("/tools")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert response.mimetype == "text/html"


def test_defaults(
    frame: Frame, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths, "USERS_DB_FILE", str(tmp_path / "default-users.db"))
    monkeypatch.setattr(paths, "SECRET_KEY_FILE", str(tmp_path / "default.key"))

    web = WebUI(frame)
    web.users.add("x", PASSWORD)

    assert (
        web.app.config["SECRET_KEY"] == (tmp_path / "default.key").read_text().strip()
    )
    assert (tmp_path / "default-users.db").exists()


@pytest.mark.parametrize(("has_user", "disabled"), [(False, True), (True, False)])
def test_start(web: WebUI, users: Users, has_user: bool, disabled: bool) -> None:
    if has_user:
        users.add("x", PASSWORD)

    with (
        patch.object(socket, "create_server") as create_server,
        patch.object(app_module, "make_server") as make_server,
    ):
        web.start()

    create_server.assert_called_once_with(("0.0.0.0", 80), family=socket.AF_INET)  # noqa: S104
    listening = create_server.return_value.__enter__.return_value
    make_server.assert_called_once_with(
        "0.0.0.0",  # noqa: S104
        80,
        web.app,
        threaded=True,
        fd=listening.fileno.return_value,
    )
    make_server.return_value.serve_forever.assert_called_once_with()
    assert web.app.config["LOGIN_DISABLED"] is disabled
    assert logging.getLogger("werkzeug").level == logging.CRITICAL


def test_plugin_website(make_web: MakeWeb) -> None:
    website = Blueprint("plugin_page", __name__)
    website.add_url_rule("/plugin_page", view_func=lambda: "plugin page")

    def add_website(*arguments: object) -> list[Blueprint]:
        return [website]

    with patch("tests.plugins.plugin1._plugin.Plugin.add_website", add_website):
        web = make_web(plugins=True)

    assert web.app.test_client().get("/plugin_page").text == "plugin page"


def test_plugin_endpoint_name_taken(
    make_web: MakeWeb, caplog: pytest.LogCaptureFixture
) -> None:
    @api("Status of the plugin")
    def get_status() -> str:
        return "plugin status"

    def extend_api(*arguments: object) -> list[Route]:
        return [Route("/api/plugin_status", get_status)]

    with patch("tests.plugins.plugin1._plugin.Plugin.extend_api", extend_api):
        web = make_web(plugins=True)

    assert "Plugin Plugin1 failed to extend the WebUI" in caplog.text
    status = web.app.test_client().get("/api/get_status").json
    assert status is not None
    assert status["state"] == "Idle"


def test_start_on_another_address(web: WebUI) -> None:
    with (
        patch.object(socket, "create_server") as create_server,
        patch.object(app_module, "make_server"),
    ):
        web.start("::1", 8080)

    create_server.assert_called_once_with(("::1", 8080), family=socket.AF_INET6)


def test_server_answers(web: WebUI) -> None:
    server = web.server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        port = server.socket.getsockname()[1]
        answer = requests.get(f"http://127.0.0.1:{port}/api/get_status", timeout=5)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert answer.status_code == HTTPStatus.OK
    assert answer.json()["state"] == "Idle"


def test_server_address_in_use(web: WebUI) -> None:
    with socket.create_server(("127.0.0.1", 0)) as taken:
        port = taken.getsockname()[1]
        with pytest.raises(OSError, match="in use"):
            web.server("127.0.0.1", port)


def test_serve_test(
    make_web: MakeWeb,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    make_web()  # the config file in tmp_path
    monkeypatch.setattr(paths, "CONFIG_FILE", str(tmp_path / "config.cfg"))
    monkeypatch.setattr(paths, "USERS_DB_FILE", str(tmp_path / "users.db"))
    monkeypatch.setattr(paths, "SECRET_KEY_FILE", str(tmp_path / "secret.key"))
    served: list[WebUI] = []

    def start(self: WebUI, host: str, port: int) -> None:
        served.append(self)
        self.app.config.update(TESTING=True, LOGIN_DISABLED=True)
        self.app.test_client().get("/api/action=next")

    with patch.object(WebUI, "start", start):
        serve_test("127.0.0.1", 8080)

    assert served[0].frame.config_file == tmp_path / "config.cfg"
    assert "only the ePiframe service changes photos" in caplog.text
