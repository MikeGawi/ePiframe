"""Current weather from OpenWeather (https://openweathermap.org/current)."""

from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import Any

import requests

API_URL = "https://api.openweathermap.org/data/2.5/weather"
TIMEOUT = 5
HIDDEN = "***"


class Units(StrEnum):
    """Temperature units (``units`` setting)."""

    METRIC = "metric"
    IMPERIAL = "imperial"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def is_metric(cls, value: str) -> bool:
        return value == cls.METRIC


class WeatherError(Exception):
    """The weather can't be retrieved (the message never contains the API key)."""


@dataclass(frozen=True)
class Weather:
    temperature: float
    icon: str  # OpenWeather icon code, e.g. "01d"


def _hide(text: str, api_key: str) -> str:
    # requests puts the whole URL (with appid=<key>) into its error messages
    return text.replace(api_key, HIDDEN) if api_key else text


def _error_message(response: requests.Response) -> str:
    if response.status_code == HTTPStatus.UNAUTHORIZED:
        return (
            "The weather API key was rejected (401): check apikey"
            " (a new key can take a few hours to become active)"
        )
    try:
        detail = response.json().get("message", "")
    except (ValueError, AttributeError):
        detail = ""
    return f"The weather service answered {response.status_code} {detail}".strip()


def _parse(data: Any) -> Weather:
    try:
        return Weather(float(data["main"]["temp"]), str(data["weather"][0]["icon"]))
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise WeatherError(f"Unexpected weather data: {error!r}") from None


def fetch_weather(  # noqa: PLR0913 - the request settings
    api_key: str,
    latitude: str,
    longitude: str,
    units: str,
    *,
    session: requests.Session | None = None,
    timeout: float = TIMEOUT,
) -> Weather:
    """Return the current weather at ``latitude``, ``longitude``."""
    params = {"lat": latitude, "lon": longitude, "units": units, "appid": api_key}
    try:
        response = (session or requests).get(API_URL, params=params, timeout=timeout)
    except requests.RequestException as error:
        raise WeatherError(
            _hide(f"No connection to the weather service: {error}", api_key)
        ) from None
    if not response.ok:
        raise WeatherError(_hide(_error_message(response), api_key))
    try:
        data = response.json()
    except ValueError:
        raise WeatherError("The weather service didn't answer with JSON") from None
    return _parse(data)
