from datetime import timedelta
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask.testing import FlaskClient
from PIL import Image

from epiframe.core import system
from epiframe.core.system import Memory, Usage
from epiframe.service.frame import Frame, Trigger
from epiframe.stats.store import MetricsStore
from epiframe.version import VERSION
from epiframe.web.endpoints import ImageQuery, image_file
from tests.epiframe.web.conftest import Checker, MakeWeb


def photo(path: Path, color: str = "red", size: tuple[int, int] = (8, 6)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


# ------------------------------------------------------------------------ images


@pytest.fixture
def photos(frame: Frame) -> dict[str, Path]:
    return {
        "converted": photo(frame.path("photo_convert_filename")),
        "thumb_converted": photo(frame.path("thumb_photo_convert_filename")),
        "original": photo(frame.download_file("png")),
        "thumb_original": photo(frame.path("thumb_photo_download_name")),
    }


@pytest.mark.parametrize(
    ("query", "name"),
    [
        (ImageQuery(), "converted"),
        (ImageQuery(thumb=True), "thumb_converted"),
        (ImageQuery(original=True), "original"),
        (ImageQuery(thumb=True, original=True), "thumb_original"),
    ],
)
def test_image_file(
    frame: Frame, photos: dict[str, Path], query: ImageQuery, name: str
) -> None:
    assert image_file(frame, query) == photos[name]


@pytest.mark.parametrize(
    ("url", "mimetype"),
    [
        ("/api/get_image", "image/bmp"),
        ("/api/get_image?original", "image/png"),
        ("/api/get_image?original=&thumb=", "image/jpeg"),
        ("/api/get_image?original=1&thumb=1", "image/jpeg"),
        ("/api/get_image?original=0", "image/bmp"),
    ],
)
def test_get_image(
    client: FlaskClient, photos: dict[str, Path], url: str, mimetype: str
) -> None:
    response = client.get(url)

    assert response.status_code == HTTPStatus.OK
    assert response.mimetype == mimetype
    response.close()


def test_no_image(client: FlaskClient, check: Checker) -> None:
    response = client.get("/api/get_image?thumb")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert check(response, "/api/get_image") == {"error": "No photo!"}


def test_upload_photo(
    client: FlaskClient, frame: Frame, triggers: list[Trigger], check: Checker
) -> None:
    data = {"file": (BytesIO(b"jpeg data"), "Holiday.JPG")}

    response = client.post("/api/upload_photo", data=data)

    assert response.status_code == HTTPStatus.OK
    assert check(response, "/api/upload_photo", "post") == {"status": "OK"}
    assert frame.download_file("jpg").read_bytes() == b"jpeg data"
    assert triggers == [Trigger.REDISPLAY]


def test_upload_unknown_file(
    client: FlaskClient, triggers: list[Trigger], check: Checker
) -> None:
    data = {"file": (BytesIO(b"text"), "notes.txt")}

    response = client.post("/api/upload_photo", data=data)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert check(response, "/api/upload_photo", "post") == {
        "error": "Unknown file type 'notes.txt'!"
    }
    assert triggers == []  # 1.x redisplayed the old photo


def test_upload_without_file(client: FlaskClient) -> None:
    response = client.post("/api/upload_photo")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json == {"error": "Missing parameter 'file'"}


def test_upload_needs_post(client: FlaskClient, check: Checker) -> None:
    response = client.get("/api/upload_photo")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert response.json == {"error": "Method Not Allowed"}


# ------------------------------------------------------------------------ status


def test_get_status(client: FlaskClient, frame: Frame, check: Checker) -> None:
    converted = photo(frame.path("thumb_photo_convert_filename"))
    with (
        patch.object(system, "memory", return_value=Memory(Usage(1, 4), Usage(0, 0))),
        patch.object(system, "load_average", return_value=(0.5, 0.25, 0.125)),
        patch.object(system, "uptime", return_value=timedelta(days=1, seconds=5)),
        patch.object(system, "temperature", return_value=48.3),
        patch.object(system, "service_running", return_value=True),
    ):
        response = client.get("/api/get_status")

    json = check(response, "/api/get_status")
    assert json == {
        "converted": converted.stat().st_mtime,
        "original": 0,
        "load": "0.50 0.25 0.12",
        "mem": "25%",
        "service": "Running",
        "state": "Idle",
        "temp": "48.3°C",
        "update": frame.next_update_text(),
        "uptime": "up 1 day",
        "version": VERSION,
    }


def test_get_stats(make_web: MakeWeb, tmp_path: Path, check: Checker) -> None:
    web = make_web(units="imperial")
    MetricsStore(web.frame.stats_file).add({"load1": 0.5, "temperature": 50, "cpu": 7})
    query = {"metrics": "load1,temperature", "period": "day"}

    response = web.app.test_client().get("/api/get_stats", query_string=query)

    json = check(response, "/api/get_stats")
    assert (json["period"], json["step"], len(json["time"])) == ("day", 10, 1)
    assert [
        (metric["name"], metric["unit"], metric["values"]) for metric in json["metrics"]
    ] == [("load1", "", [0.5]), ("temperature", "°F", [122.0])]


def test_get_stats_without_data(client: FlaskClient, frame: Frame) -> None:
    json = client.get("/api/get_stats?period=year").json

    assert json is not None
    assert (json["period"], json["time"]) == ("year", [])
    assert all(metric["values"] == [] for metric in json["metrics"])
    assert not frame.stats_file.exists()


@pytest.mark.parametrize(
    ("query", "error"),
    [
        ("period=hour", "Wrong period 'hour', use one of: day, week"),
        ("metrics=x,cpu,y", "Unknown metrics: x, y"),
    ],
)
def test_get_stats_bad_request(
    client: FlaskClient, check: Checker, query: str, error: str
) -> None:
    response = client.get(f"/api/get_stats?{query}")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert check(response, "/api/get_stats")["error"].startswith(error)


def test_get_log(client: FlaskClient, frame: Frame) -> None:
    log = Path(frame.config.get("log_files"))
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("12:00:00 : test message\n")

    response = client.get("/api/get_log")

    assert response.mimetype == "text/plain"
    assert response.text == "12:00:00 : test message\n"


def test_get_log_without_file(client: FlaskClient, frame: Frame) -> None:
    assert client.get("/api/get_log").text == ""
    assert not Path(frame.config.get("log_files")).exists()  # 1.x created it


# ----------------------------------------------------------------------- control


def test_action_next(
    client: FlaskClient, triggers: list[Trigger], check: Checker
) -> None:
    response = client.get("/api/action=next")

    assert check(response, "/api/action=<action>") == {"status": "OK"}
    assert triggers == [Trigger.NEXT_PHOTO]


@pytest.mark.parametrize(
    ("action", "command"),
    [("restart", "restart_service"), ("reboot", "reboot"), ("poweroff", "power_off")],
)
def test_system_actions(client: FlaskClient, action: str, command: str) -> None:
    with patch.object(system, command) as run:
        response = client.get(f"/api/action={action}")

    assert response.json == {"status": "OK"}
    run.assert_called_once_with()


def test_unknown_action(client: FlaskClient, check: Checker) -> None:
    response = client.get("/api/action=do_a_flip")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert check(response, "/api/action=<action>") == {
        "error": "Unknown action 'do_a_flip'!"
    }


def test_no_action(client: FlaskClient) -> None:
    response = client.get("/api/action=")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json == {"error": "Not Found"}


@pytest.mark.parametrize(("on", "state"), [(True, "1"), (False, "0"), (None, "0")])
def test_display_power_state(
    client: FlaskClient, hdmi: MagicMock, check: Checker, on: bool | None, state: str
) -> None:
    hdmi.state.return_value = on

    response = client.get("/api/display_power=")

    assert check(response, "/api/display_power=") == {"state": state}


@pytest.mark.parametrize(
    ("value", "on"),
    [("0", False), ("false", False), ("OFF", False), ("1", True), ("on", True)],
)
def test_display_power(
    client: FlaskClient, hdmi: MagicMock, check: Checker, value: str, on: bool
) -> None:
    response = client.get(f"/api/display_power={value}")

    assert check(response, "/api/display_power=<power>") == {"status": "OK"}
    hdmi.set.assert_called_once_with(on)


def test_display_power_wrong(client: FlaskClient, hdmi: MagicMock) -> None:
    response = client.get("/api/display_power=dim")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    hdmi.set.assert_not_called()
