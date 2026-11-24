import base64
import os
from unittest.mock import patch

import pytest
from http import HTTPStatus

from datetime import timedelta

from epiframe.config.paths import CONFIG_FILE_DEFAULT
from epiframe.core import system
from epiframe.core.system import Memory, Usage
from epiframe.display import hdmi
from epiframe.stats.store import MetricsStore
from epiframe.version import VERSION
from epiframe.users.model import User
from epiframe.config.manager import ConfigManager
from epiframe.users.store import UserError, Users
from modules import webuimanager
from modules.webuimanager import WebUIManager
from tests.helpers.capturing import Capturing
from tests.helpers.config import Config
from tests.helpers.helpers import not_raises
from tests.helpers.frame import get_frame
from tests.helpers.plugins import get_plugins_manager


@patch("epiframe.config.paths.USERS_DB_FILE", "test_users.db")
def test_init():
    with not_raises(Exception):
        WebUIManager(get_frame())


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
        ("/get_stats", ["GET"], None),
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
        "/api/get_stats",
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
            ConfigManager(CONFIG_FILE_DEFAULT, CONFIG_FILE_DEFAULT),
            "use_local",
        )
        == "Use Local"
    )


def test_adapt_name_deps():
    assert (
        WebUIManager.adapt_name(
            ConfigManager(CONFIG_FILE_DEFAULT, CONFIG_FILE_DEFAULT),
            "local_path",
        )
        == "- Local Path"
    )


def test_load_user_nok():
    manager = get_webui_manager()
    assert not manager.load_user("non_existing_user")


def test_load_user_ok():
    user = User(1, "name", "hash", "api")

    def mocked_get_user(self, username: str) -> User:
        return user

    with patch.object(Users, "by_username", mocked_get_user):
        manager = get_webui_manager()
        assert manager.load_user("name") == user


def test_get_image_login(client):
    response = client.get("/get_image")
    assert response.location == "/login?next=%2Fget_image"
    assert response.status_code == HTTPStatus.FOUND


def test_logout_login(client):
    response = client.get("/logout")
    assert response.location == "/login?next=%2Flogout"
    assert response.status_code == HTTPStatus.FOUND


def test_get_status_login(client):
    response = client.get("/get_status")
    assert response.location == "/login?next=%2Fget_status"
    assert response.status_code == HTTPStatus.FOUND


def test_upload_photo_login(client):
    response = client.post("/_upload_photo")
    assert response.location == "/login?next=%2F_upload_photo"
    assert response.status_code == HTTPStatus.FOUND


def test_log_stream_login(client):
    response = client.get("/_log_stream")
    assert response.location == "/login?next=%2F_log_stream"
    assert response.status_code == HTTPStatus.FOUND


def test_export_login(client):
    response = client.get("/export")
    assert response.location == "/login?next=%2Fexport"
    assert response.status_code == HTTPStatus.FOUND


def test_import_login(client):
    response = client.post("/import")
    assert response.location == "/login?next=%2Fimport"
    assert response.status_code == HTTPStatus.FOUND


def test_plugins_login(client):
    response = client.post("/plugins")
    assert response.location == "/login?next=%2Fplugins"
    assert response.status_code == HTTPStatus.FOUND


def test_stats_login(client):
    response = client.post("/stats")
    assert response.location == "/login?next=%2Fstats"
    assert response.status_code == HTTPStatus.FOUND


def test_logs_login(client):
    response = client.post("/logs")
    assert response.location == "/login?next=%2Flogs"
    assert response.status_code == HTTPStatus.FOUND


def test_tools_login(client):
    response = client.post("/tools")
    assert response.location == "/login?next=%2Ftools"
    assert response.status_code == HTTPStatus.FOUND


def test_settings_login(client):
    response = client.post("/settings")
    assert response.location == "/login?next=%2Fsettings"
    assert response.status_code == HTTPStatus.FOUND


def test_login_login(client):
    response = client.get("/login")
    assert not response.location
    assert response.status_code == HTTPStatus.OK


def test_get_image(client_no_login):
    response = client_no_login.get("/get_image")
    assert not response.location
    assert response.status_code == HTTPStatus.OK
    assert response.data == b"No Photo!"


def test_get_image_binary(app_no_config):
    response = app_no_config.test_client().get("/get_image")
    assert not response.location
    assert response.status_code == HTTPStatus.OK
    assert response.mimetype == "image/bmp"


def test_logout(client_no_login):
    response = client_no_login.get("/logout")
    assert response.location == "/"
    assert response.status_code == HTTPStatus.FOUND


@pytest.mark.parametrize("url", ["/get_status", "/api/get_status"])
def test_get_status(client_no_login, url):
    with (
        patch.object(system, "memory", return_value=Memory(Usage(1, 4), Usage(0, 0))),
        patch.object(system, "load_average", return_value=(0.5, 0.25, 0.125)),
        patch.object(system, "uptime", return_value=timedelta(days=1, seconds=5)),
        patch.object(system, "temperature", return_value=48.3),
        patch.object(system, "service_running", return_value=True),
    ):
        response = client_no_login.get(url)
        assert not response.location
        assert response.status_code == HTTPStatus.OK
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
        assert json["load"] == "0.50 0.25 0.12"
        assert json["mem"] == "25%"
        assert json["service"] == "Running"
        assert json["state"] == "Idle"
        assert json["temp"] == "48.3°C"
        assert json["uptime"] == "up 1 day"
        assert json["version"] == VERSION
        assert json["update"]


def test_get_stats_login(client):
    response = client.get("/get_stats")
    assert response.location == "/login?next=%2Fget_stats"
    assert response.status_code == HTTPStatus.FOUND


@pytest.mark.parametrize("url", ["/get_stats", "/api/get_stats"])
def test_get_stats(app_no_config, url, tmp_path):
    database = tmp_path / "stats.db"
    MetricsStore(database).add({"load1": 0.5, "temperature": 50, "cpu": 7})
    settings = {"stats_db_file": str(database), "units": "imperial"}

    with patch.dict(Config.settings, settings):
        response = app_no_config.test_client().get(
            url, query_string={"metrics": "load1,temperature"}
        )

    assert response.status_code == HTTPStatus.OK
    json = response.json
    assert json["period"] == "day"
    assert json["step"] == 10
    assert len(json["time"]) == 1
    assert [
        (metric["name"], metric["unit"], metric["values"]) for metric in json["metrics"]
    ] == [
        ("load1", "", [0.5]),
        ("temperature", "°F", [122.0]),
    ]


def test_get_stats_without_data(app_no_config, tmp_path):
    database = tmp_path / "stats.db"

    with patch.dict(Config.settings, {"stats_db_file": str(database)}):
        json = app_no_config.test_client().get("/api/get_stats?period=year").json

    assert json["period"] == "year"
    assert json["time"] == []
    assert all(metric["values"] == [] for metric in json["metrics"])
    assert not database.exists()


@pytest.mark.parametrize(
    ("query", "error"),
    [("period=hour", "Unknown period 'hour'"), ("metrics=x", "Unknown metrics: x")],
)
def test_get_stats_bad_request(client_no_login, query, error):
    response = client_no_login.get(f"/api/get_stats?{query}")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json["error"].startswith(error)


def test_get_status_nothing_available(client_no_login):
    with (
        patch.object(system, "memory", return_value=None),
        patch.object(system, "load_average", return_value=None),
        patch.object(system, "uptime", return_value=None),
        patch.object(system, "temperature", return_value=None),
        patch.object(system, "service_running", return_value=False),
    ):
        json = client_no_login.get("/api/get_status").json

    assert (json["mem"], json["load"], json["uptime"], json["temp"]) == ("-",) * 4
    assert json["service"] == "Not running!"


@pytest.mark.parametrize(
    ("celsius", "metric", "expected"),
    [(50, True, "50.0°C"), (50, False, "122.0°F"), (None, False, "-")],
)
def test_temperature_text(celsius, metric, expected):
    assert webuimanager.temperature_text(celsius, metric) == expected


@pytest.mark.parametrize(
    ("uptime", "expected"),
    [
        (
            timedelta(days=8, hours=14, minutes=52, seconds=7),
            "up 1 week, 1 day, 14 hours, 52 minutes",
        ),
        (timedelta(weeks=2, minutes=1), "up 2 weeks, 1 minute"),
        (timedelta(seconds=59), "up 0 minutes"),
        (None, "-"),
    ],
)
def test_uptime_text(uptime, expected):
    assert webuimanager.uptime_text(uptime) == expected


@pytest.mark.parametrize("url", ["/_upload_photo", "/api/upload_photo"])
def test_upload_photo(client_no_login, url):
    response = client_no_login.post(url)
    assert not response.location
    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize("url", ["/_log_stream", "/api/get_log"])
def test_log_stream(app_no_config, url):
    log_file = Config.settings["log_files"]
    with open(log_file, "w") as file:
        file.write("2026-11-21 12:00:00 : test_message\n")
    try:
        response = app_no_config.test_client().get(url)
    finally:
        os.remove(log_file)
    assert not response.location
    assert response.status_code == HTTPStatus.OK
    assert "test_message" in response.data.decode()


def test_export(client_no_login):
    response = client_no_login.get("/export")
    assert not response.location
    assert response.status_code == HTTPStatus.OK
    with open(CONFIG_FILE_DEFAULT, "r") as file:
        assert "".join(file.readlines()) == response.data.decode()


def test_import(client_no_login):
    response = client_no_login.post("/import")
    assert not response.location
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_plugins(client_no_login):
    response = client_no_login.post("/plugins")
    assert (
        response.location == "http://localhost/plugins?plugin=Plugin1&variable=General"
    )
    assert response.status_code == HTTPStatus.FOUND


def test_stats(client_no_login):
    response = client_no_login.post("/stats")
    assert not response.location
    assert response.status_code == HTTPStatus.OK
    # one chart per group of metrics, one choice per period
    assert b'<option value="load1,load5,load15" selected>Load</option>' in response.data
    assert b'<option value="year">Year</option>' in response.data


def test_logs(client_no_login):
    response = client_no_login.post("/logs")
    assert not response.location
    assert response.status_code == HTTPStatus.OK


def test_tools(client_no_login):
    response = client_no_login.post("/tools")
    assert not response.location
    assert response.status_code == HTTPStatus.OK


def test_settings(client_no_login):
    response = client_no_login.post("/settings")
    assert response.location == "/settings/Sources"
    assert response.status_code == HTTPStatus.FOUND


def test_dummy(client_no_login):
    response = client_no_login.post("/dummy")
    assert not response.location
    assert response.status_code == HTTPStatus.OK


def test_get_image_api_thumb(client_no_login):
    response = client_no_login.get("/api/get_image?thumb")
    assert not response.location
    assert response.status_code == HTTPStatus.OK
    assert response.data == b"No Photo!"


def test_get_image_api_original(client_no_login):
    response = client_no_login.get("/api/get_image?original")
    assert not response.location
    assert response.status_code == HTTPStatus.OK
    assert response.data == b"No Photo!"


def test_get_image_api_original_thumb(client_no_login):
    response = client_no_login.get("/api/get_image?original&thumb")
    assert not response.location
    assert response.status_code == HTTPStatus.OK
    assert response.data == b"No Photo!"


@pytest.mark.parametrize("url", ["/api/get_image?original", "/api/get_image"])
def test_get_image_api_original_binary(app_no_config, url):
    response = app_no_config.test_client().get(url)
    assert not response.location
    assert response.status_code == HTTPStatus.OK
    assert response.mimetype == "image/bmp"


def test_display_power_empty(client_no_login):
    with patch.object(hdmi.HdmiPower, "state", return_value=True):
        response = client_no_login.get("/api/display_power=")
        assert not response.location
        assert response.status_code == HTTPStatus.OK
        assert response.json == {"state": "1"}


def test_display_power_wrong(client_no_login):
    response = client_no_login.post("/api/display_power=")
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.parametrize("action", ["0", "false", "off"])
def test_display_power_off(client_no_login, action):
    with patch.object(hdmi.HdmiPower, "set") as power:
        response = client_no_login.get(f"/api/display_power={action}")
        assert response.status_code == HTTPStatus.OK

    power.assert_called_once_with(False)


@pytest.mark.parametrize("action", ["1", "true", "on"])
def test_display_power_on(client_no_login, action):
    with patch.object(hdmi.HdmiPower, "set") as power:
        response = client_no_login.get(f"/api/display_power={action}")
        assert response.status_code == HTTPStatus.OK

    power.assert_called_once_with(True)


def test_login_ok(client):
    with (
        patch.object(Users, "authenticate", mock_check),
        patch.object(Users, "by_username", mock_load_user),
    ):
        response = client.post(
            "/login",
            data=dict(
                username="test@gmail.com", password="test", login_form="", remember=True
            ),
            follow_redirects=True,
        )
        assert not response.location
        assert response.status_code == HTTPStatus.OK
        assert VERSION in response.data.decode()


def test_login_nok(client):
    with patch.object(Users, "authenticate", mock_check_nok):
        response = client.post(
            "/login",
            data=dict(
                username="test@gmail.com", password="test", login_form="", remember=True
            ),
            follow_redirects=True,
        )
        assert response.status_code == HTTPStatus.OK
        assert VERSION not in response.data.decode()
        assert "Remember me" in response.data.decode()
        assert (
            "Please check your login details and try again!" in response.data.decode()
        )


def test_login_nok_empty(client):
    with patch.object(Users, "authenticate", mock_check_nok):
        response = client.post(
            "/login",
            data=dict(password="test", login_form="", remember=True),
            follow_redirects=True,
        )
        assert response.status_code == HTTPStatus.OK
        assert VERSION not in response.data.decode()
        assert "Remember me" in response.data.decode()
        assert "Please fill in all required data!" in response.data.decode()


def test_load_from_request(client):
    with (
        patch.object(hdmi.HdmiPower, "state", return_value=True),
        patch.object(Users, "by_api_key", mock_get_by_api),
    ):
        response = client.get(
            "/api/display_power=?api_key=api_key",
        )
        assert not response.location
        assert response.status_code == HTTPStatus.OK
        assert response.json == {"state": "1"}


def test_load_from_request_nok(client):
    with (
        patch.object(hdmi.HdmiPower, "state", return_value=True),
        patch.object(Users, "by_api_key", mock_get_by_api),
    ):
        response = client.get(
            "/api/display_power=?api_key=not_an_api_key",
        )
        assert (
            response.location
            == "/login?next=%2Fapi%2Fdisplay_power%3D%3Fapi_key%3Dnot_an_api_key"
        )
        assert response.status_code == HTTPStatus.FOUND
        assert not response.json


def test_load_from_header(client):
    with (
        patch.object(hdmi.HdmiPower, "state", return_value=True),
        patch.object(Users, "by_api_key", mock_get_by_api),
    ):
        response = client.get(
            "/api/display_power=",
            headers={
                "Authorization": f"Basic {base64.b64encode('api_key'.encode()).decode()}"
            },
        )
        assert not response.location
        assert response.status_code == HTTPStatus.OK
        assert response.json == {"state": "1"}


def test_load_from_header_nok(client):
    with (
        patch.object(hdmi.HdmiPower, "state", return_value=True),
        patch.object(Users, "by_api_key", mock_get_by_api),
    ):
        response = client.get(
            "/api/display_power=",
            headers={
                "Authorization": f"Basic {base64.b64encode('not_an_api_key'.encode()).decode()}"
            },
        )
        assert response.location == "/login?next=%2Fapi%2Fdisplay_power%3D"
        assert response.status_code == HTTPStatus.FOUND
        assert not response.json


@pytest.mark.parametrize("url", ["/api/action=", "/_tools$"])
def test_action_empty(client_no_login, url):
    response = client_no_login.get(url)
    assert response.status_code == HTTPStatus.OK
    assert response.json == {"error": "No Action!"}


@pytest.mark.parametrize("url", ["/api/action=do_a_flip", "/_tools$do_a_flip"])
def test_action_wrong(client_no_login, url):
    response = client_no_login.get(url)
    assert response.status_code == HTTPStatus.OK
    assert response.json == {"error": "Action Unknown!"}


@pytest.mark.parametrize("url", ["/api/action=next", "/_tools$next"])
def test_action_next(client_no_login, url):
    with Capturing() as output:
        response = client_no_login.get(url)
        assert response.status_code == HTTPStatus.OK
        assert response.json == {"status": "OK"}

    assert output == ["Event triggered Trigger.NEXT_PHOTO"]


@pytest.mark.parametrize("url", ["/api/action=restart", "/_tools$restart"])
def test_action_restart(client_no_login, url):
    with patch.object(system, "restart_service") as command:
        response = client_no_login.get(url)
        assert response.status_code == HTTPStatus.OK
        assert response.json == {"status": "OK"}

    command.assert_called_once_with()


@pytest.mark.parametrize("url", ["/api/action=reboot", "/_tools$reboot"])
def test_action_reboot(client_no_login, url):
    with patch.object(system, "reboot") as command:
        response = client_no_login.get(url)
        assert response.status_code == HTTPStatus.OK
        assert response.json == {"status": "OK"}

    command.assert_called_once_with()


@pytest.mark.parametrize("url", ["/api/action=poweroff", "/_tools$poweroff"])
def test_action_power_off(client_no_login, url):
    with patch.object(system, "power_off") as command:
        response = client_no_login.get(url)
        assert response.status_code == HTTPStatus.OK
        assert response.json == {"status": "OK"}

    command.assert_called_once_with()


def test_settings_pages(client_no_login):
    config = ConfigManager(CONFIG_FILE_DEFAULT, CONFIG_FILE_DEFAULT)
    for section in config.get_sections():
        response = client_no_login.get(f"/settings/{section}")
        assert response.status_code == HTTPStatus.OK
        for setting in config.get_section_properties(section):
            assert WebUIManager.adapt_name(config, setting) in response.data.decode()


def test_plugin_settings_pages(client_no_login):
    plugins = get_plugins_manager()
    for plugin in plugins.plugins:
        for section in plugin.config.get_sections():
            response = client_no_login.get(
                f"/plugins?plugin={plugin.name.title()}&variable={section}"
            )
            assert response.status_code == HTTPStatus.OK
            for setting in plugin.config.get_section_properties(section):
                assert (
                    WebUIManager.adapt_name(plugin.config, setting)
                    in response.data.decode()
                )


def test_plugin_api(client_no_login):
    response = client_no_login.get("/api/get_text/my_text")
    assert response.status_code == HTTPStatus.OK
    assert response.data.decode() == '{"text_label":"my_text"}\n'


def test_plugin_menu(client_no_login):
    response = client_no_login.get("/")
    assert response.status_code == HTTPStatus.OK
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
        assert response.status_code == HTTPStatus.OK
    assert "I'm dummy" in output


def mock_check(self, username: str, password: str) -> User:
    return User(1, "username", "hash", "api")


def mock_check_nok(self, username: str, password: str):
    raise UserError("Wrong password!")


def mock_load_user(self, username: str) -> User:
    return User(1, "username", "hash", "api")


def mock_get_by_api(self, api: str) -> User | None:
    return User(1, "username", "hash", "api") if api == "api_key" else None


@patch("epiframe.config.paths.USERS_DB_FILE", "test_users.db")
def get_webui_manager():
    return WebUIManager(get_frame())


@pytest.mark.parametrize("injection", ["' OR '1'='1", "x' OR 1=1 --"])
def test_api_key_sql_injection_is_refused(client, injection):
    # 1.x built the SQL from the key: "?api_key=' OR '1'='1" logged in as the
    # first user; the app fixture uses the real users database "test_users.db"
    users = Users("test_users.db")
    user = users.add("injection-test", "secret")
    try:
        refused = client.get("/api/display_power=", query_string={"api_key": injection})
        with patch.object(hdmi.HdmiPower, "state", return_value=True):
            accepted = client.get(
                "/api/display_power=", query_string={"api_key": user.api_key}
            )
    finally:
        users.delete("injection-test")

    assert refused.status_code == HTTPStatus.FOUND
    assert refused.location.startswith("/login")
    assert accepted.status_code == HTTPStatus.OK


def test_login_with_real_users_database(client):
    users = Users("test_users.db")
    users.add("login-test", "secret")
    try:
        wrong = client.post(
            "/login", data={"username": "login-test", "password": "nope"}
        )
        right = client.post(
            "/login", data={"username": "login-test", "password": "secret"}
        )
        page = client.get("/")
    finally:
        users.delete("login-test")

    assert wrong.status_code == right.status_code == HTTPStatus.FOUND
    assert page.status_code == HTTPStatus.OK
    assert VERSION in page.data.decode()
