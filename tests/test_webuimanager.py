import base64
import os
from typing import List
from unittest.mock import patch

import pytest
from starlette import status

import tests.test_pluginsmanager
from misc.constants import Constants
from misc.user import User
from modules.configmanager import ConfigManager
from modules.usersmanager import UsersManager
from modules.webuimanager import WebUIManager
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import not_raises
from tests.test_backendmanager import get_manager


@patch("misc.constants.Constants.USERS_DB_FILE", "test_users.db")
def test_init():
    with not_raises(Exception):
        WebUIManager(get_manager())


def test_menu_entries():
    manager = get_webui_manager()
    entries = [
        ("Home", "/", "home-menu", "bi bi-house"),
        ("Logs", "/logs", "logs-menu", "bi bi-activity"),
        ("Stats", "/stats", "stats-menu", "bi bi-graph-up"),
        ("Settings", "/settings", "settings-menu", "bi bi-gear"),
        ("Tools", "/tools", "tools-menu", "bi bi-tools"),
        ("Plugins", "/plugins", "plugins-menu", "bi bi-plug"),
    ]

    for entry in entries:
        assert entry in [
            (menu.name, menu.url, menu.id, menu.icon) for menu in manager.MENU
        ]


def test_websites():
    manager = get_webui_manager()
    entries = [
        ("/get_image", ["GET"], None),
        ("/get_status", ["GET"], None),
        ("/_log_stream", ["GET"], None),
        ("/_upload_photo", ["POST"], None),
        ("/_tools$", ["GET"], None),
        ("/_tools$<action>", ["GET"], None),
        ("/<url>", ["GET", "POST"], None),
        ("/", ["GET", "POST"], {"url": ""}),
        (
            "/settings/<variable>",
            ["GET", "POST"],
            {"variable": ""},
        ),
        ("/plugins", ["GET", "POST"], None),
        ("/logout", ["GET"], None),
        ("/login", ["GET", "POST"], None),
        ("/export", ["GET"], None),
        ("/import", ["POST"], None),
    ]

    for entry in entries:
        assert entry in [
            (website.url, website.methods, website.defaults)
            for website in manager.WEBSITES
        ]


def test_api_entries():
    manager = get_webui_manager()
    entries = [
        "/api/get_image",
        "/api/get_status",
        "/api/get_log",
        "/api/upload_photo",
        "/api/action=",
        "/api/action=<action>",
        "/api/display_power=",
        "/api/display_power=<action>",
    ]

    for entry in entries:
        assert entry in [api.url for api in manager.API]


def test_actions():
    manager = get_webui_manager()
    entries = {
        (
            "Next Photo",
            "bi bi-skip-end",
            "next",
        ),
        (
            "Restart Service",
            "bi bi-arrow-repeat",
            "restart",
        ),
        (
            "Reboot",
            "bi bi-arrow-counterclockwise",
            "reboot",
        ),
    }

    for entry in entries:
        assert entry in [
            (action.name, action.icon, action.action)
            for action in manager.ACTIONS.values()
        ]


def test_get_app():
    manager = get_webui_manager()
    assert str(manager.get_app()) == "<Flask 'modules.webuimanager'>"


def test_inject_context():
    manager = get_webui_manager()
    assert manager.inject_context()["dark_theme"] is True
    assert manager.inject_context()["menu"] == manager.MENU


def test_config():
    manager = get_webui_manager()
    assert str(type(manager.config())) == "<class 'tests.helpers.config.Config'>"


def test_add_menu_entries():
    manager = get_webui_manager()
    before = len(manager.MENU)
    manager.add_menu_entries([WebUIManager.MenuEntry("name", "url", "id", "icon")])
    assert before != len(manager.MENU)
    assert len(manager.MENU) == before + 1
    assert ("name", "url", "id", "icon") in [
        (menu.name, menu.url, menu.id, menu.icon) for menu in manager.MENU
    ]


def test_adapt_name_no_deps():
    assert (
        WebUIManager.adapt_name(
            ConfigManager(Constants.CONFIG_FILE_DEFAULT, Constants.CONFIG_FILE_DEFAULT),
            "use_google_photos",
        )
        == "Use Google Photos"
    )


def test_adapt_name_deps():
    assert (
        WebUIManager.adapt_name(
            ConfigManager(Constants.CONFIG_FILE_DEFAULT, Constants.CONFIG_FILE_DEFAULT),
            "cred_file",
        )
        == "- Cred File"
    )


def test_load_user_nok():
    manager = get_webui_manager()
    assert not manager.load_user("non_existing_user")


def test_load_user_ok():
    user = User("id", "name", "pass", "api")

    def mocked_get_user(self, username: str) -> List[User]:
        return [user]

    with patch.object(UsersManager, "get_by_username", mocked_get_user):
        manager = get_webui_manager()
        assert manager.load_user("name") == user


def test_get_image_login(client):
    response = client.get("/get_image")
    assert response.location == "/login?next=%2Fget_image"
    assert response.status_code == status.HTTP_302_FOUND


def test_logout_login(client):
    response = client.get("/logout")
    assert response.location == "/login?next=%2Flogout"
    assert response.status_code == status.HTTP_302_FOUND


def test_get_status_login(client):
    response = client.get("/get_status")
    assert response.location == "/login?next=%2Fget_status"
    assert response.status_code == status.HTTP_302_FOUND


def test_upload_photo_login(client):
    response = client.post("/_upload_photo")
    assert response.location == "/login?next=%2F_upload_photo"
    assert response.status_code == status.HTTP_302_FOUND


def test_log_stream_login(client):
    response = client.get("/_log_stream")
    assert response.location == "/login?next=%2F_log_stream"
    assert response.status_code == status.HTTP_302_FOUND


def test_export_login(client):
    response = client.get("/export")
    assert response.location == "/login?next=%2Fexport"
    assert response.status_code == status.HTTP_302_FOUND


def test_import_login(client):
    response = client.post("/import")
    assert response.location == "/login?next=%2Fimport"
    assert response.status_code == status.HTTP_302_FOUND


def test_plugins_login(client):
    response = client.post("/plugins")
    assert response.location == "/login?next=%2Fplugins"
    assert response.status_code == status.HTTP_302_FOUND


def test_stats_login(client):
    response = client.post("/stats")
    assert response.location == "/login?next=%2Fstats"
    assert response.status_code == status.HTTP_302_FOUND


def test_logs_login(client):
    response = client.post("/logs")
    assert response.location == "/login?next=%2Flogs"
    assert response.status_code == status.HTTP_302_FOUND


def test_tools_login(client):
    response = client.post("/tools")
    assert response.location == "/login?next=%2Ftools"
    assert response.status_code == status.HTTP_302_FOUND


def test_settings_login(client):
    response = client.post("/settings")
    assert response.location == "/login?next=%2Fsettings"
    assert response.status_code == status.HTTP_302_FOUND


def test_login_login(client):
    response = client.get("/login")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK


def test_get_image(client_no_login):
    response = client_no_login.get("/get_image")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK
    assert response.data == b"No Photo!"


def test_get_image_binary(app_no_config):
    response = app_no_config.test_client().get("/get_image")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK
    assert response.mimetype == "image/bmp"


def test_logout(client_no_login):
    response = client_no_login.get("/logout")
    assert response.location == "/"
    assert response.status_code == status.HTTP_302_FOUND


@pytest.mark.parametrize("url", ["/get_status", "/api/get_status"])
def test_get_status(client_no_login, url):
    with patch.object(os, "popen", web_mocked_system), patch.object(
        os, "system", web_mocked_system
    ):
        response = client_no_login.get(url)
        assert not response.location
        assert response.status_code == status.HTTP_200_OK
        assert response.json
        json = response.json
        assert json.keys() == {
            "converted",
            "load",
            "mem",
            "original",
            "service",
            "state",
            "temp",
            "update",
            "uptime",
            "version",
        }

        assert json["converted"] == 0
        assert json["original"] == 0
        assert json["load"] == "data"
        assert json["mem"] == "data%"
        assert json["service"] == "data"
        assert json["state"] == "Idle"
        assert json["temp"] == "data°C"
        assert json["uptime"] == "data"
        assert json["version"] == Constants.EPIFRAME_VERSION
        assert json["update"]


@pytest.mark.parametrize("url", ["/_upload_photo", "/api/upload_photo"])
def test_upload_photo(client_no_login, url):
    response = client_no_login.post(url)
    assert not response.location
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize("url", ["/_log_stream", "/api/get_log"])
def test_log_stream(client_no_login, url):
    response = client_no_login.get(url)
    assert not response.location
    assert response.status_code == status.HTTP_200_OK
    assert "test_message" in response.data.decode()


def test_export(client_no_login):
    response = client_no_login.get("/export")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK
    with open(Constants.CONFIG_FILE_DEFAULT, "r") as file:
        assert "".join(file.readlines()) == response.data.decode() + "\n"


def test_import(client_no_login):
    response = client_no_login.post("/import")
    assert not response.location
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_plugins(client_no_login):
    response = client_no_login.post("/plugins")
    assert (
        response.location == "http://localhost/plugins?plugin=Plugin1&variable=General"
    )
    assert response.status_code == status.HTTP_302_FOUND


def test_stats(client_no_login):
    response = client_no_login.post("/stats")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK


def test_logs(client_no_login):
    response = client_no_login.post("/logs")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK


def test_tools(client_no_login):
    response = client_no_login.post("/tools")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK


def test_settings(client_no_login):
    response = client_no_login.post("/settings")
    assert response.location == "/settings/Sources"
    assert response.status_code == status.HTTP_302_FOUND


def test_dummy(client_no_login):
    response = client_no_login.post("/dummy")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK


def test_get_image_api_thumb(client_no_login):
    response = client_no_login.get("/api/get_image?thumb")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK
    assert response.data == b"No Photo!"


def test_get_image_api_original(client_no_login):
    response = client_no_login.get("/api/get_image?original")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK
    assert response.data == b"No Photo!"


def test_get_image_api_original_thumb(client_no_login):
    response = client_no_login.get("/api/get_image?original&thumb")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK
    assert response.data == b"No Photo!"


@pytest.mark.parametrize("url", ["/api/get_image?original", "/api/get_image"])
def test_get_image_api_original_binary(app_no_config, url):
    response = app_no_config.test_client().get(url)
    assert not response.location
    assert response.status_code == status.HTTP_200_OK
    assert response.mimetype == "image/bmp"


def test_display_power_empty(client_no_login):
    with patch.object(os, "popen", web_mocked_system):
        response = client_no_login.get("/api/display_power=")
        assert not response.location
        assert response.status_code == status.HTTP_200_OK
        assert response.json == {"state": "data"}


def test_display_power_wrong(client_no_login):
    response = client_no_login.post("/api/display_power=")
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize("action", ["0", "false", "off"])
def test_display_power_off(client_no_login, action):
    with patch.object(os, "popen", web_mocked_system), Capturing() as output:
        response = client_no_login.get(f"/api/display_power={action}")
        assert response.status_code == status.HTTP_200_OK

    assert output == ["sudo vcgencmd display_power 0 2> /dev/null"]


@pytest.mark.parametrize("action", ["1", "true", "on"])
def test_display_power_on(client_no_login, action):
    with patch.object(os, "popen", web_mocked_system), Capturing() as output:
        response = client_no_login.get(f"/api/display_power={action}")
        assert response.status_code == status.HTTP_200_OK

    assert output == ["sudo vcgencmd display_power 1 2> /dev/null"]


def test_login_ok(client):
    with patch.object(UsersManager, "check", mock_check), patch.object(
        UsersManager, "get_by_username", mock_load_user
    ):
        response = client.post(
            "/login",
            data=dict(
                username="test@gmail.com", password="test", login_form="", remember=True
            ),
            follow_redirects=True,
        )
        assert not response.location
        assert response.status_code == status.HTTP_200_OK
        assert Constants.EPIFRAME_VERSION in response.data.decode()


def test_login_nok(client):
    with patch.object(UsersManager, "check", mock_check_nok):
        response = client.post(
            "/login",
            data=dict(
                username="test@gmail.com", password="test", login_form="", remember=True
            ),
            follow_redirects=True,
        )
        assert response.status_code == status.HTTP_200_OK
        assert Constants.EPIFRAME_VERSION not in response.data.decode()
        assert "Remember me" in response.data.decode()
        assert (
            "Please check your login details and try again!" in response.data.decode()
        )


def test_login_nok_empty(client):
    with patch.object(UsersManager, "check", mock_check_nok):
        response = client.post(
            "/login",
            data=dict(password="test", login_form="", remember=True),
            follow_redirects=True,
        )
        assert response.status_code == status.HTTP_200_OK
        assert Constants.EPIFRAME_VERSION not in response.data.decode()
        assert "Remember me" in response.data.decode()
        assert "Please fill in all required data!" in response.data.decode()


def test_load_from_request(client):
    with patch.object(os, "popen", web_mocked_system), patch.object(
        UsersManager, "get_by_api", mock_get_by_api
    ):
        response = client.get(
            "/api/display_power=?api_key=api_key",
        )
        assert not response.location
        assert response.status_code == status.HTTP_200_OK
        assert response.json == {"state": "data"}


def test_load_from_request_nok(client):
    with patch.object(os, "popen", web_mocked_system), patch.object(
        UsersManager, "get_by_api", mock_get_by_api
    ):
        response = client.get(
            "/api/display_power=?api_key=not_an_api_key",
        )
        assert (
            response.location
            == "/login?next=%2Fapi%2Fdisplay_power%253D%3Fapi_key%3Dnot_an_api_key"
        )
        assert response.status_code == status.HTTP_302_FOUND
        assert not response.json


def test_load_from_header(client):
    with patch.object(os, "popen", web_mocked_system), patch.object(
        UsersManager, "get_by_api", mock_get_by_api
    ):
        response = client.get(
            "/api/display_power=",
            headers={
                "Authorization": f"Basic {base64.b64encode('api_key'.encode()).decode()}"
            },
        )
        assert not response.location
        assert response.status_code == status.HTTP_200_OK
        assert response.json == {"state": "data"}


def test_load_from_header_nok(client):
    with patch.object(os, "popen", web_mocked_system), patch.object(
        UsersManager, "get_by_api", mock_get_by_api
    ):
        response = client.get(
            "/api/display_power=",
            headers={
                "Authorization": f"Basic {base64.b64encode('not_an_api_key'.encode()).decode()}"
            },
        )
        assert response.location == "/login?next=%2Fapi%2Fdisplay_power%253D"
        assert response.status_code == status.HTTP_302_FOUND
        assert not response.json


@pytest.mark.parametrize("url", ["/api/action=", "/_tools$"])
def test_action_empty(client_no_login, url):
    with patch.object(os, "popen", web_mocked_system):
        response = client_no_login.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json == {"error": "No Action!"}


@pytest.mark.parametrize("url", ["/api/action=do_a_flip", "/_tools$do_a_flip"])
def test_action_wrong(client_no_login, url):
    with patch.object(os, "popen", web_mocked_system):
        response = client_no_login.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json == {"error": "Action Unknown!"}


@pytest.mark.parametrize("url", ["/api/action=next", "/_tools$next"])
def test_action_next(client_no_login, url):
    with Capturing() as output:
        response = client_no_login.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json == {"status": "OK"}

    assert output == ["IntervalManager_remove", "Event triggered params='NOPARAMS'"]


@pytest.mark.parametrize("url", ["/api/action=restart", "/_tools$restart"])
def test_action_restart(client_no_login, url):
    with patch.object(os, "system", web_mocked_system), Capturing() as output:
        response = client_no_login.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json == {"status": "OK"}

    assert output == ["sudo systemctl restart ePiframe.service"]


@pytest.mark.parametrize("url", ["/api/action=reboot", "/_tools$reboot"])
def test_action_reboot(client_no_login, url):
    with patch.object(os, "system", web_mocked_system), Capturing() as output:
        response = client_no_login.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json == {"status": "OK"}

    assert output == ["sudo reboot"]


@pytest.mark.parametrize("url", ["/api/action=poweroff", "/_tools$poweroff"])
def test_action_power_off(client_no_login, url):
    with patch.object(os, "system", web_mocked_system), Capturing() as output:
        response = client_no_login.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json == {"status": "OK"}

    assert output == ["sudo poweroff"]


def test_settings_pages(client_no_login):
    config = ConfigManager(Constants.CONFIG_FILE_DEFAULT, Constants.CONFIG_FILE_DEFAULT)
    for section in config.get_sections():
        response = client_no_login.get(f"/settings/{section}")
        assert response.status_code == status.HTTP_200_OK
        for setting in config.get_section_properties(section):
            assert WebUIManager.adapt_name(config, setting) in response.data.decode()


def test_plugin_settings_pages(client_no_login):
    plugins = tests.test_pluginsmanager.get_manager()
    for plugin in plugins.get_plugins():
        for section in plugin.config.get_sections():
            response = client_no_login.get(
                f"/plugins?plugin={plugin.name.title()}&variable={section}"
            )
            assert response.status_code == status.HTTP_200_OK
            for setting in plugin.config.get_section_properties(section):
                assert (
                    WebUIManager.adapt_name(plugin.config, setting)
                    in response.data.decode()
                )


def test_plugin_api(client_no_login):
    response = client_no_login.get("/api/get_text/my_text")
    assert response.status_code == status.HTTP_200_OK
    assert response.data.decode() == '{"text_label":"my_text"}\n'


def test_plugin_menu(client_no_login):
    response = client_no_login.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert (
        '<a href="127.0.0.1" class="nav-link align-middle px-1 link-secondary server-menu d-none d-md-block">'
        in response.data.decode()
    )
    assert (
        '<i class="fs-6 bi bi-server"></i> <span>Server</span>'
        in response.data.decode()
    )


def test_plugin_action(client_no_login):
    with Capturing() as output:
        response = client_no_login.get("/api/action=lightoff")
        assert response.status_code == status.HTTP_200_OK
    assert "I'm dummy" in output


class WebMockRead:
    def read(self):
        return "data"


def mock_check(self, username: str, password: str):
    return True


def mock_check_nok(self, username: str, password: str):
    raise Exception("error")


def mock_load_user(self, username: str) -> List[User]:
    return [User("user", "username", "password", "api")]


def mock_get_by_api(self, api: str) -> List[User]:
    if api != "api_key":
        raise Exception("error")
    return [User("user", "username", "password", "api")]


def web_mocked_system(*args, **kwargs):
    print("".join(args) + "".join(kwargs))
    return WebMockRead()


@patch("misc.constants.Constants.USERS_DB_FILE", "test_users.db")
def get_webui_manager():
    return WebUIManager(get_manager())
