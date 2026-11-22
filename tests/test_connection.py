import pytest
import requests
from starlette import status
from misc.connection import Connection
from tests.helpers.helpers import not_raises, remove_file


def test_check_internet_ok(requests_mocker):
    url = "http://test-connection.com"

    requests_mocker.get(
        url=url,
        status_code=status.HTTP_200_OK,
    )

    response = Connection.check_internet(url=url, timeout=1)
    assert not response


def test_check_internet_nok(requests_mocker):
    assert Connection.check_internet(
        url="http://non-existing-host-for-testing:12345", timeout=1
    )


def test_ip_ok():
    with not_raises(Exception):
        Connection.is_ip("192.168.8.1")
    with not_raises(Exception):
        Connection.is_ip("127.0.0.1")
    with not_raises(Exception):
        Connection.is_ip("255.255.255.255")


def test_ip_nok():
    with pytest.raises(Exception):
        Connection.is_ip("255.255.255.256")
    with pytest.raises(Exception):
        Connection.is_ip("255.255.255.255.255")
    with pytest.raises(Exception):
        Connection.is_ip("192.168.0.p")
    with pytest.raises(Exception):
        Connection.is_ip("127.0.0.-1")
    with pytest.raises(Exception):
        Connection.is_ip("this_is_not_ip")


def test_download_file_ok(requests_mocker):
    url = "http://test-download.com"
    test_download_filename = "test_download_file"
    test_content = b"test_content"

    requests_mocker.get(url=url, status_code=status.HTTP_200_OK, content=test_content)

    response = Connection.download_file(
        url=url,
        destination_folder=".",
        file_name=test_download_filename,
        code=status.HTTP_200_OK,
        timeout=1,
    )

    assert response == status.HTTP_200_OK

    with open(test_download_filename, "rb") as file:
        data = file.read()
        assert data == test_content
    remove_file(test_download_filename)


def test_download_file_nok(requests_mocker):
    url = "http://test-download.com"

    requests_mocker.get(url=url, status_code=status.HTTP_404_NOT_FOUND)

    with pytest.raises(requests.exceptions.HTTPError):
        Connection.download_file(
            url=url,
            destination_folder=".",
            file_name="filename",
            code=status.HTTP_200_OK,
            timeout=1,
        )
