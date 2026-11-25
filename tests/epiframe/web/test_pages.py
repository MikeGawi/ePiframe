from http import HTTPStatus
from io import BytesIO
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.service.frame import Frame, Trigger
from epiframe.version import VERSION
from epiframe.web.app import WebUI
from epiframe.web.forms import label
from tests.epiframe.web.conftest import PASSWORD, MakeWeb


def flashes(client: FlaskClient) -> list[str]:
    with client.session_transaction() as session:
        return [message for _, message in session.get("_flashes", [])]


# -------------------------------------------------------------------- simple pages


@pytest.mark.parametrize(
    ("url", "text"),
    [
        ("/", "Drop photo here to upload!"),
        ("/tools", "Restart Service"),
        ("/logs", "get_log"),
        ("/stats", '<option value="load1,load5,load15" selected>Load</option>'),
        ("/stats", '<option value="year">Year</option>'),
        ("/stats", "/api/get_stats"),
    ],
)
def test_pages(client: FlaskClient, url: str, text: str) -> None:
    response = client.get(url)

    assert response.status_code == HTTPStatus.OK
    assert text in response.text


def test_tools_buttons(client: FlaskClient) -> None:
    page = client.get("/tools").text

    assert 'id="next"' in page
    assert page.count('id="poweroff"') == 1  # the page's own button
    assert "/api/action=" in page


def test_unknown_page(client: FlaskClient) -> None:
    response = client.get("/dummy")

    assert response.status_code == HTTPStatus.NOT_FOUND  # 1.x: the home page
    assert "<html" in response.text.lower()


def test_login_page(secured: WebUI) -> None:
    response = secured.app.test_client().get("/login")

    assert response.status_code == HTTPStatus.OK
    assert "Remember me" in response.text


def test_login(secured: WebUI, user_key: str) -> None:
    client = secured.app.test_client()

    response = client.post(
        "/login",
        data={"username": "user", "password": PASSWORD, "remember": "1"},
        follow_redirects=True,
    )

    assert response.status_code == HTTPStatus.OK
    assert VERSION in response.text


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"username": "user", "password": "x"}, "Please check your login details"),
        ({"password": PASSWORD}, "Please fill in all required data!"),
    ],
)
def test_failed_login(
    secured: WebUI, user_key: str, data: dict[str, str], message: str
) -> None:
    client = secured.app.test_client()

    response = client.post("/login", data=data, follow_redirects=True)

    assert VERSION not in response.text
    assert message in response.text


# -------------------------------------------------------------------- upload page


def test_upload_page(
    client: FlaskClient, frame: Frame, triggers: list[Trigger]
) -> None:
    data = {"file": (BytesIO(b"png"), "a.png")}

    response = client.post("/_upload_photo", data=data)

    assert response.status_code == HTTPStatus.FOUND
    assert response.location == "/"
    assert frame.download_file("png").read_bytes() == b"png"
    assert triggers == [Trigger.REDISPLAY]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({}, "No file!"),
        ({"file": (BytesIO(b"x"), "a.txt")}, "Unknown file type 'a.txt'!"),
    ],
)
def test_upload_page_errors(
    client: FlaskClient, data: dict[str, object], message: str
) -> None:
    response = client.post("/_upload_photo", data=data)

    assert response.location == "/"
    assert flashes(client) == [message]


# ------------------------------------------------------------------------ settings


def test_settings_home(client: FlaskClient) -> None:
    response = client.get("/settings")

    assert response.location == "/settings/Sources"


def test_settings_pages(client: FlaskClient) -> None:
    config = ConfigManager(paths.CONFIG_FILE_DEFAULT, paths.CONFIG_FILE_DEFAULT)
    for section in config.get_sections():
        page = client.get(f"/settings/{section}").text
        for name in config.get_section_properties(section):
            assert label(config, name) in page


def test_unknown_settings_section(client: FlaskClient) -> None:
    assert client.get("/settings/Nothing").status_code == HTTPStatus.NOT_FOUND


def test_save_settings(client: FlaskClient, frame: Frame) -> None:
    form = {"slide_interval": "1200", "SAVE": "SAVE"}

    response = client.post("/settings/Display", data=form)

    assert response.location == "/settings/Display"
    assert "slide_interval=1200" in frame.config_file.read_text()


def test_export(client: FlaskClient, frame: Frame) -> None:
    response = client.get("/export")

    assert response.status_code == HTTPStatus.OK
    assert response.data == frame.config_file.read_bytes()
    assert "attachment; filename=config.cfg" in response.headers["Content-Disposition"]
    response.close()


def test_import(client: FlaskClient, frame: Frame, tmp_path: Path) -> None:
    exported = tmp_path / "exported.cfg"
    exported.write_bytes(frame.config_file.read_bytes())
    config = ConfigManager(exported, paths.CONFIG_FILE_DEFAULT)
    config.set("slide_interval", "900")
    config.save()

    response = client.post(
        "/import", data={"file": (BytesIO(exported.read_bytes()), "x.cfg")}
    )

    assert response.location == "/settings"
    assert flashes(client) == ["File has been imported successfully!"]
    assert frame.config.get("slide_interval") == "900"


def test_import_of_a_wrong_file(client: FlaskClient, frame: Frame) -> None:
    before = frame.config_file.read_text()
    data = {"file": (BytesIO(b"[General]\nslide_interval=x\n"), "x.cfg")}

    client.post("/import", data=data)

    assert flashes(client)[0].startswith("Error importing settings file: ")
    assert frame.config_file.read_text() == before


def test_import_without_file(client: FlaskClient) -> None:
    response = client.post("/import")

    assert response.location == "/settings"
    assert flashes(client) == ["No settings file!"]


# ------------------------------------------------------------------------- plugins


def test_no_plugins(client: FlaskClient) -> None:
    assert (
        "There are no <b>ePiframe</b> plugins installed!" in client.get("/plugins").text
    )


@pytest.fixture
def plugin_client(make_web: MakeWeb) -> FlaskClient:
    return make_web(plugins=True).app.test_client()


def test_plugin_pages(make_web: MakeWeb) -> None:
    web = make_web(plugins=True)
    client = web.app.test_client()
    for plugin in web.frame.plugins.plugins:
        for section in plugin.config.get_sections():
            page = client.get(f"/plugins?plugin={plugin.name}&variable={section}")
            assert page.status_code == HTTPStatus.OK
            for name in plugin.config.get_section_properties(section):
                assert label(plugin.config, name) in page.text


def test_first_plugin_by_default(plugin_client: FlaskClient) -> None:
    page = plugin_client.get("/plugins").text

    assert "Plugin1" in page
    assert "Is Enabled" in page


def test_unknown_plugin(plugin_client: FlaskClient) -> None:
    response = plugin_client.get("/plugins?plugin=Nothing")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_post_plugin_settings(plugin_client: FlaskClient) -> None:
    response = plugin_client.post("/plugins?plugin=Plugin1&variable=General")

    assert response.location == "/plugins?plugin=Plugin1&variable=General"


def test_plugin_order(make_web: MakeWeb) -> None:
    web = make_web(plugins=True)
    client = web.app.test_client()
    manager = web.frame.plugins
    original = manager.read_order()
    try:
        page = client.get("/plugins?plugin=Execution Order")
        saved = client.post(
            "/plugins?plugin=Execution Order",
            data={"SAVE": "SAVE", "list_order": "plugin2,plugin1"},
        )
        order = manager.read_order()
        client.post("/plugins?plugin=Execution Order", data={"DEFAULTS": "DEFAULTS"})
        defaults = manager.read_order()
        client.post("/plugins?plugin=Execution Order", data={})
    finally:
        manager.save_order(original)

    assert "Drag and drop list items" in page.text
    assert saved.location == "/plugins?plugin=Execution+Order"
    assert order[:2] == ["plugin2", "plugin1"]
    assert defaults == sorted(defaults)
