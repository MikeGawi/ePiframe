from collections.abc import Iterator
from http import HTTPStatus

import pytest
import requests
import requests_mock

from epiframe.weather.openweather import (
    API_URL,
    HIDDEN,
    Units,
    Weather,
    WeatherError,
    fetch_weather,
)

KEY = "secret-api-key"
ANSWER = {"weather": [{"icon": "10n", "main": "Rain"}], "main": {"temp": 7.25}}


@pytest.fixture
def http() -> Iterator[requests_mock.Mocker]:
    with requests_mock.Mocker() as mocker:
        yield mocker


def fetch() -> Weather:
    return fetch_weather(KEY, "53.27", "7.77", "metric")


def test_units() -> None:
    assert Units.values() == ["metric", "imperial"]
    assert Units.is_metric("metric")
    assert not Units.is_metric("imperial")


def test_fetch_weather(http: requests_mock.Mocker) -> None:
    http.get(API_URL, json=ANSWER)

    assert fetch() == Weather(7.25, "10n")
    assert http.last_request is not None
    assert http.last_request.qs == {
        "lat": ["53.27"],
        "lon": ["7.77"],
        "units": ["metric"],
        "appid": [KEY],
    }
    assert http.last_request.timeout == 5


def test_fetch_weather_with_session(http: requests_mock.Mocker) -> None:
    http.get(API_URL, json=ANSWER)

    with requests.Session() as session:
        weather = fetch_weather(KEY, "1", "2", "imperial", session=session, timeout=1)

    assert weather == Weather(7.25, "10n")


def test_parameters_are_escaped(http: requests_mock.Mocker) -> None:
    http.get(API_URL, json=ANSWER)

    fetch_weather("a&units=x", "1", "2", "metric")

    assert http.last_request is not None
    assert http.last_request.qs["appid"] == ["a&units=x"]
    assert http.last_request.qs["units"] == ["metric"]


def test_rejected_key(http: requests_mock.Mocker) -> None:
    http.get(API_URL, status_code=HTTPStatus.UNAUTHORIZED, json={"message": "x"})

    with pytest.raises(WeatherError, match=r"API key was rejected \(401\)"):
        fetch()


def test_service_error_with_message(http: requests_mock.Mocker) -> None:
    http.get(API_URL, status_code=400, json={"cod": "400", "message": "wrong latitude"})

    with pytest.raises(WeatherError, match=r"answered 400 wrong latitude$"):
        fetch()


def test_service_error_without_json(http: requests_mock.Mocker) -> None:
    http.get(API_URL, status_code=502, text="Bad gateway")

    with pytest.raises(WeatherError, match=r"answered 502$"):
        fetch()


def test_service_error_json_without_message(http: requests_mock.Mocker) -> None:
    http.get(API_URL, status_code=502, json=["not", "a dict"])

    with pytest.raises(WeatherError, match=r"answered 502$"):
        fetch()


def test_answer_is_not_json(http: requests_mock.Mocker) -> None:
    http.get(API_URL, text="<html>")

    with pytest.raises(WeatherError, match="didn't answer with JSON"):
        fetch()


@pytest.mark.parametrize(
    "answer",
    [
        {},
        {"main": {"temp": 1}},
        {"main": {"temp": 1}, "weather": []},
        {"main": {"temp": "warm"}, "weather": [{"icon": "01d"}]},
        {"main": None, "weather": [{"icon": "01d"}]},
    ],
)
def test_unexpected_answer(http: requests_mock.Mocker, answer: object) -> None:
    http.get(API_URL, json=answer)

    with pytest.raises(WeatherError, match="Unexpected weather data"):
        fetch()


@pytest.mark.parametrize(
    "error", [requests.ConnectionError, requests.Timeout, requests.TooManyRedirects]
)
def test_no_connection_hides_the_key(
    http: requests_mock.Mocker, error: type[Exception]
) -> None:
    # requests puts the URL with appid=<key> into its messages
    http.get(API_URL, exc=error(f"Max retries exceeded with url: /?appid={KEY}"))

    with pytest.raises(WeatherError, match="No connection") as raised:
        fetch()

    assert KEY not in str(raised.value)
    assert f"appid={HIDDEN}" in str(raised.value)


def test_error_with_empty_key(http: requests_mock.Mocker) -> None:
    http.get(API_URL, exc=requests.ConnectionError("refused"))

    with pytest.raises(
        WeatherError, match="No connection to the weather service: refused"
    ):
        fetch_weather("", "1", "2", "metric")


def test_error_message_hides_the_key(http: requests_mock.Mocker) -> None:
    http.get(API_URL, status_code=400, json={"message": f"bad key {KEY}"})

    with pytest.raises(WeatherError) as raised:
        fetch()

    assert KEY not in str(raised.value)
