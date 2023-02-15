import pytest
from modules.weatherstampmanager import WeatherStampManager
from tests.helpers.helpers import not_raises


def test_get_positions():
    positions = WeatherStampManager.get_positions()
    assert positions == [0, 1, 2, 3]


def test_verify_position_ok():
    with not_raises(Exception):
        WeatherStampManager.verify_position(str(WeatherStampManager.get_positions()[0]))


def test_verify_position_nok():
    with pytest.raises(Exception):
        WeatherStampManager.verify_position("")


def test_get_colors():
    colors = WeatherStampManager.get_colors()
    assert colors == ["white", "black"]


def test_verify_color_ok():
    with not_raises(Exception):
        WeatherStampManager.verify_color(str(WeatherStampManager.get_colors()[0]))


def test_verify_color_nok():
    with pytest.raises(Exception):
        WeatherStampManager.verify_color("")
