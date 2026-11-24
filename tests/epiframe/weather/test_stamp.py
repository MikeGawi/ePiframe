import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from epiframe.weather.openweather import Weather, WeatherError
from epiframe.weather.stamp import (
    ICONS,
    TEXT_FONT,
    WEATHER_FONT,
    FontColor,
    Position,
    StampSettings,
    draw_stamp,
    round_half_up,
    temperature_text,
)

ASSETS = Path(__file__).with_name("assets")
# results of the 1.x WeatherStampManager.compose for a matrix of settings; the
# temperatures are ones where 1.x (always up) and round_half_up agree
CASES_1X: list[dict[str, Any]] = json.loads((ASSETS / "stamp_1x.json").read_text())
# every icon code of https://openweathermap.org/weather-conditions
OPENWEATHER_ICONS = {
    f"{number}{time}"
    for number in ("01", "02", "03", "04", "09", "10", "11", "13", "50")
    for time in "dn"
}


class Config:
    def __init__(self, **values: str) -> None:
        self.values = values

    def get(self, name: str) -> str:
        return self.values[name]

    def getint(self, name: str) -> int:
        return int(self.values[name])


def base_image(mode: str) -> Image.Image:
    """The input image used when recording 1.x."""
    image = Image.new("RGB", (200, 120))
    image.putdata(
        [
            ((x * 3) % 256, (y * 2) % 256, ((x + y) * 5) % 256)
            for y in range(120)
            for x in range(200)
        ]
    )
    return image.convert(mode)


def case_id(case: dict[str, Any]) -> str:
    keys = ("mode", "position", "color", "horizontal", "rotation", "units", "temp")
    return "-".join(str(case[key]) for key in keys) + f"-{case['icon']}-{case['font']}"


@pytest.mark.parametrize("case", CASES_1X, ids=case_id)
def test_matches_1x(tmp_path: Path, case: dict[str, Any]) -> None:
    path = tmp_path / "photo.bmp"
    base_image(case["mode"]).save(path)
    settings = StampSettings(
        font_size=case["font"],
        color=FontColor(case["color"]),
        position=Position(case["position"]),
        horizontal=case["horizontal"],
        rotation=case["rotation"],
    )

    draw_stamp(path, Weather(case["temp"], case["icon"]), case["units"], settings)

    with Image.open(path) as result:
        assert result.mode == case["result"]["mode"]
        assert list(result.size) == case["result"]["size"]
        digest = hashlib.sha256(result.tobytes()).hexdigest()
        assert digest == case["result"]["digest"]


def test_recorded_temperatures_round_the_same() -> None:
    # 1.x rounded up: the recordings are only comparable where the rules agree
    for case in CASES_1X:
        assert math.ceil(case["temp"]) == round_half_up(case["temp"])


def test_unknown_icon_leaves_the_photo(tmp_path: Path) -> None:
    path = tmp_path / "photo.bmp"
    base_image("RGB").save(path)
    before = path.read_bytes()

    with pytest.raises(WeatherError, match="Unknown weather icon '99x'"):
        draw_stamp(
            path,
            Weather(1, "99x"),
            "metric",
            StampSettings(20, FontColor.WHITE, Position.TOP_LEFT),
        )

    assert path.read_bytes() == before


def test_every_openweather_icon_has_a_glyph() -> None:
    assert set(ICONS) == OPENWEATHER_ICONS


def test_fonts_are_package_data() -> None:
    assert WEATHER_FONT.is_file()
    assert TEXT_FONT.is_file()


@pytest.mark.parametrize(
    ("temperature", "degrees"),
    [
        (0.0, 0),
        (0.49, 0),
        (0.5, 1),
        (0.99, 1),
        (20.2, 20),
        (20.5, 21),  # round() would give 20 (halves to even)
        (21.5, 22),
        (99.5, 100),
        (-0.4, 0),
        (-0.49, 0),
        (-0.5, -1),  # halves away from zero
        (-0.51, -1),
        (-3.4, -3),
        (-3.5, -4),
        (-3.6, -4),
    ],
)
def test_round_half_up(temperature: float, degrees: int) -> None:
    assert round_half_up(temperature) == degrees


@pytest.mark.parametrize(
    ("temperature", "units", "text"),
    [
        (20.2, "metric", "20\u00b0C"),
        (20.5, "metric", "21\u00b0C"),
        (-0.4, "metric", "0\u00b0C"),  # no "-0"
        (-0.5, "metric", "-1\u00b0C"),
        (-3.6, "imperial", "-4\u00b0F"),
        (70.0, "imperial", "70\u00b0F"),
    ],
)
def test_temperature_text(temperature: float, units: str, text: str) -> None:
    assert temperature_text(temperature, units) == text


def test_positions() -> None:
    assert Position.values() == [0, 1, 2, 3]
    assert [(p.right, p.bottom) for p in Position] == [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ]
    # config values compare as strings
    assert str(Position.BOTTOM_LEFT) == "2"


def test_font_colors() -> None:
    assert FontColor.values() == ["white", "black"]
    assert FontColor.WHITE.opposite == FontColor.BLACK
    assert FontColor.BLACK.opposite == FontColor.WHITE


def test_settings_from_config() -> None:
    config = Config(
        font="24", font_color="black", position="3", horizontal="0", rotation="270"
    )

    assert StampSettings.from_config(config) == StampSettings(
        24, FontColor.BLACK, Position.BOTTOM_RIGHT, horizontal=False, rotation=270
    )
