"""Draws the weather (icon and temperature) in a corner of the converted photo."""

import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, Self

from PIL import Image, ImageColor, ImageDraw, ImageFont

from epiframe.processing.orientation import Orientation, Position
from epiframe.weather.openweather import Units, Weather, WeatherError

FONTS = Path(__file__).with_name("fonts")
WEATHER_FONT = FONTS / "weathericons-regular-webfont.ttf"  # Weather Icons (OFL)
TEXT_FONT = FONTS / "NotoSans-SemiCondensed.ttf"  # Noto Sans (OFL)

MARGIN = 10
SPACE = 5  # between the icon and the temperature
STROKE_WIDTH = 2
DEGREES = "°"

# OpenWeather icon code -> Weather Icons glyph
ICONS = {
    "01d": "",
    "01n": "",
    "02d": "",
    "02n": "",
    "03d": "",
    "03n": "",
    "04d": "",
    "04n": "",
    "09d": "",
    "09n": "",
    "10d": "",
    "10n": "",
    "11d": "",
    "11n": "",
    "13d": "",
    "13n": "",
    "50d": "",
    "50n": "",
}


class FontColor(StrEnum):
    """Color of the stamp (``font_color`` setting); the outline has the other one."""

    WHITE = "white"
    BLACK = "black"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]

    @property
    def opposite(self) -> "FontColor":
        return FontColor.BLACK if self == FontColor.WHITE else FontColor.WHITE


class Settings(Protocol):
    def get(self, name: str) -> str: ...

    def getint(self, name: str) -> int: ...


@dataclass(frozen=True)
class StampSettings:
    font_size: int
    color: FontColor
    position: Position
    horizontal: bool = True
    rotation: int = 90  # of a vertical frame: 90 or 270
    turned: bool = False  # a horizontal frame mounted upside down

    @classmethod
    def from_config(cls, config: Settings) -> Self:
        return cls(
            font_size=config.getint("font"),
            color=FontColor(config.get("font_color")),
            position=Position(config.getint("position")),
            horizontal=bool(config.getint("horizontal")),
            rotation=config.getint("rotation"),
            turned=Orientation.from_config(config).turned,
        )

    @property
    def orientation(self) -> Orientation:
        return Orientation(self.horizontal, self.turned, self.rotation)


def round_half_up(value: float) -> int:
    """Round to whole degrees, halves away from zero (0.5 -> 1, -0.5 -> -1).

    Not ``round()``: it rounds halves to the even number (20.5 -> 20). 1.x always
    rounded up (20.1 -> 21).
    """
    rounded = math.floor(abs(value) + 0.5)
    return -rounded if value < 0 else rounded


def temperature_text(temperature: float, units: str) -> str:
    """E.g. ``21°C``."""
    degrees = round_half_up(temperature)
    return f"{degrees}{DEGREES}{'C' if Units.is_metric(units) else 'F'}"


def draw_stamp(
    path: Path | str, weather: Weather, units: str, settings: StampSettings
) -> None:
    """Draw ``weather`` on the image file at ``path`` (overwritten)."""
    try:
        glyph = ICONS[weather.icon]
    except KeyError:
        raise WeatherError(f"Unknown weather icon {weather.icon!r}") from None
    with Image.open(path) as source:
        image = settings.orientation.upright(source)
    draw = ImageDraw.Draw(image)
    icon_font = ImageFont.truetype(str(WEATHER_FONT), settings.font_size)
    text_font = ImageFont.truetype(str(TEXT_FONT), settings.font_size)
    text = temperature_text(weather.temperature, units)
    icon_width = draw.textlength(glyph, font=icon_font)
    width = icon_width + SPACE + draw.textlength(text, font=text_font)
    x = image.width - width - MARGIN if settings.position.right else MARGIN
    y = (
        image.height - MARGIN - settings.font_size
        if settings.position.bottom
        else MARGIN
    )
    fill = ImageColor.getcolor(settings.color, image.mode)
    outline = ImageColor.getcolor(settings.color.opposite, image.mode)
    for position, value, font in (
        ((x, y), glyph, icon_font),
        ((x + icon_width + SPACE, y), text, text_font),
    ):
        draw.text(
            position,
            value,
            font=font,
            fill=fill,
            stroke_width=STROKE_WIDTH,
            stroke_fill=outline,
        )
    settings.orientation.stored(image).save(path)
