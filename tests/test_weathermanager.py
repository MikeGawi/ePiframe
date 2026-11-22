import pytest
from starlette import status
from modules.weathermanager import WeatherManager
from tests.helpers.helpers import not_raises


api_key = "API_KEY"
lat = "123"
lon = "321"


def test_get_units():
    assert WeatherManager.get_units() == ["metric", "imperial"]


def test_verify_units():
    units = WeatherManager.get_units()

    with not_raises(Exception):
        WeatherManager.verify_units(units[0])

    with not_raises(Exception):
        WeatherManager.verify_units(units[1])

    with pytest.raises(Exception):
        WeatherManager.verify_units("non_existing_unit")


def test_metric_check():
    units = WeatherManager.get_units()

    assert WeatherManager.is_metric(units[0])
    assert not WeatherManager.is_metric(units[1])


def test_weather_manager(requests_mocker):
    weather = WeatherManager(api_key, "metric", lat, lon)

    assert not weather.get_data()

    url = "https://weatherdata/weather?lat={}&lon={}&units={}&appid={}"
    desired_url = url.format(lat, lon, "metric", api_key)
    payload = {"main": {"position": {"icon": "weather_icon"}, "temperature": "30.5"}}
    requests_mocker.get(url=desired_url, status_code=status.HTTP_200_OK, json=payload)

    weather.send_request(url, 5)
    assert weather.get_data() == payload
    assert weather.get_weather_icon("main", "position", "icon") == "weather_icon"
    assert weather.get_temperature("main", "temperature") == "30.5"


def test_weather_manager_nok(requests_mocker):
    weather = WeatherManager(api_key, "metric", lat, lon)
    url = "https://non-existing-host-for-testing:12345/weather?lat={}&lon={}&units={}&appid={}"

    weather.send_request(url, 5)
    assert not weather.get_data()
