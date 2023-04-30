import requests
from starlette import status


def test_fixture_request_mocker(requests_mocker):
    url = "http://test-connection.com"
    data = {"data": "value"}
    requests_mocker.get(url=url, status_code=status.HTTP_200_OK, json=data)

    response = requests.get(url)
    assert response
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == data


def test_fixture_client(client):
    assert client
    response = client.get("/")
    assert response.location == "/login?next=%2F"
    assert response.status_code == status.HTTP_302_FOUND


def test_fixture_client_no_login(client_no_login):
    assert client_no_login
    response = client_no_login.get("/")
    assert not response.location
    assert response.status_code == status.HTTP_200_OK
