import requests
from http import HTTPStatus


def test_fixture_request_mocker(requests_mocker):
    url = "http://test-connection.com"
    data = {"data": "value"}
    requests_mocker.get(url=url, status_code=HTTPStatus.OK, json=data)

    response = requests.get(url)
    assert response
    assert response.status_code == HTTPStatus.OK
    assert response.json() == data
