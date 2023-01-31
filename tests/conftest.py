import pytest
import requests_mock


@pytest.fixture(scope="module")
def requests_mocker():
    with requests_mock.mock(real_http=True) as mocker:
        yield mocker
