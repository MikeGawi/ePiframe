from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path

import pytest
import requests
import requests_mock
from pytest_mock import MockerFixture

from epiframe.core import network

URL = "http://test-connection.invalid/file.jpg"


@pytest.fixture
def mocker_http() -> Iterator[requests_mock.Mocker]:
    with requests_mock.Mocker() as mocker:
        yield mocker


def test_check_internet_ok(mocker_http: requests_mock.Mocker) -> None:
    mocker_http.get(URL, status_code=HTTPStatus.OK)
    assert network.check_internet(URL, timeout=1) is None


def test_check_internet_http_error_counts_as_connected(
    mocker_http: requests_mock.Mocker,
) -> None:
    mocker_http.get(URL, status_code=HTTPStatus.SERVICE_UNAVAILABLE)
    assert network.check_internet(URL, timeout=1) is None


@pytest.mark.parametrize(
    "exception", [requests.ConnectionError("no route"), requests.ReadTimeout("slow")]
)
def test_check_internet_failure(
    mocker_http: requests_mock.Mocker, exception: requests.RequestException
) -> None:
    mocker_http.get(URL, exc=exception)
    assert network.check_internet(URL, timeout=1) == str(exception)


# 0.0.0.0 is the default web_host (all interfaces), it must stay valid
ALL_INTERFACES = "0.0.0.0"  # noqa: S104


@pytest.mark.parametrize(
    "value",
    [ALL_INTERFACES, "127.0.0.1", "192.168.8.1", "255.255.255.255", "::", "::1"],
)
def test_validate_ip_ok(value: str) -> None:
    network.validate_ip(value)


@pytest.mark.parametrize(
    "value",
    [
        "255.255.255.256",
        "255.255.255.255.255",
        "192.168.0.p",
        "127.0.0.-1",
        "this_is_not_ip",
        "",
    ],
)
def test_validate_ip_nok(value: str) -> None:
    with pytest.raises(ValueError, match="Not a valid IP address!"):
        network.validate_ip(value)


def test_download_file(mocker_http: requests_mock.Mocker, tmp_path: Path) -> None:
    content = b"x" * (network.CHUNK_SIZE * 2 + 10)
    mocker_http.get(URL, content=content)
    target = tmp_path / "photo.jpg"

    assert network.download_file(URL, target, timeout=1) == target
    assert target.read_bytes() == content
    assert list(tmp_path.iterdir()) == [target]


def test_download_file_with_session(
    mocker_http: requests_mock.Mocker, tmp_path: Path
) -> None:
    mocker_http.get(URL, content=b"data", request_headers={"Authorization": "Bearer t"})
    session = requests.Session()
    session.headers["Authorization"] = "Bearer t"

    target = network.download_file(URL, str(tmp_path / "photo.jpg"), 1, session)
    assert target.read_bytes() == b"data"


def test_download_file_http_error_keeps_old_file(
    mocker_http: requests_mock.Mocker, tmp_path: Path
) -> None:
    mocker_http.get(URL, status_code=HTTPStatus.NOT_FOUND)
    target = tmp_path / "photo.jpg"
    target.write_bytes(b"old")

    with pytest.raises(requests.HTTPError):
        network.download_file(URL, target, timeout=1)
    assert target.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [target]


def test_download_file_interrupted_leaves_no_partial_file(
    mocker_http: requests_mock.Mocker, mocker: MockerFixture, tmp_path: Path
) -> None:
    mocker_http.get(URL, content=b"data")
    mocker.patch.object(
        requests.Response,
        "iter_content",
        side_effect=requests.ConnectionError("connection lost"),
    )
    target = tmp_path / "photo.jpg"

    with pytest.raises(requests.ConnectionError):
        network.download_file(URL, target, timeout=1)
    assert list(tmp_path.iterdir()) == []
