"""Status icons drawn on the shown photo: busy, offline and error.

Each icon is a white disc with a black ring and a black glyph (readable on any
photo, also on a dithered black and white one). The icons are drawn in a row
from one corner (``icons_position``), the first one nearest to the corner, with
the size ``icons_size``. They are rendered 8 times larger and reduced to pure
black and white, never dithered: they look the same on every display.
"""

from collections.abc import Callable, Collection
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from typing import Protocol, Self

from PIL import Image, ImageColor, ImageDraw

from epiframe.processing.orientation import Orientation, Position

MARGIN = 10  # pixels from the edges, like the weather stamp
SUPERSAMPLING = 8
GLYPH = 0.58  # glyph size in a disc
RING = 16  # ring width: 1/16 of the size (2 pixels at least)
MODES = ("1", "L", "RGB")  # other image modes are drawn on in RGB
MIN_SIZE = 16


class Settings(Protocol):
    def get(self, name: str) -> str: ...

    def getint(self, name: str) -> int: ...


class Icon(StrEnum):
    """The status icons, in the order they are drawn from the corner."""

    BUSY = "busy"  # a photo change is running
    OFFLINE = "offline"  # no internet connection
    ERROR = "error"  # the last photo change failed

    @property
    def setting(self) -> str:
        """The configuration entry that enables the icon (e.g. ``busy_icon``)."""
        return f"{self.value}_icon"


def enabled_icons(config: Settings) -> frozenset[Icon]:
    """The icons turned on in the configuration."""
    return frozenset(icon for icon in Icon if config.getint(icon.setting))


# entries of the configuration check :func:`check_corner`
CORNER_CHECK_ENTRIES = (
    "icons_position",
    "show_weather",
    "position",
    *(icon.setting for icon in Icon),
)


def check_corner(values: list[str]) -> None:
    """Raise ``ValueError`` when the icons are drawn where the weather stamp is
    (``values`` of :data:`CORNER_CHECK_ENTRIES`)."""
    corner, weather, weather_corner, *enabled = values
    if weather == "1" and "1" in enabled and corner == weather_corner:
        raise ValueError(
            "the status icons are in the same corner as the weather stamp"
            " (position in [Weather])"
        )


@dataclass(frozen=True)
class IconSettings:
    """Which icons may be drawn, and where."""

    enabled: frozenset[Icon]
    position: Position
    size: int
    orientation: Orientation

    @classmethod
    def from_config(cls, config: Settings) -> Self:
        return cls(
            enabled=enabled_icons(config),
            position=Position(config.getint("icons_position")),
            size=config.getint("icons_size"),
            orientation=Orientation.from_config(config),
        )


def draw_icons(
    image: Image.Image, icons: Collection[Icon], settings: IconSettings
) -> Image.Image:
    """A copy of ``image`` with ``icons`` drawn on it."""
    upright = settings.orientation.upright(
        image if image.mode in MODES else image.convert("RGB")
    )
    row = _row(icons, settings.position)
    black = ImageColor.getcolor("black", upright.mode)
    white = ImageColor.getcolor("white", upright.mode)
    for icon, place in zip(row, _places(upright.size, len(row), settings), strict=True):
        white_mask, black_mask = render(icon, settings.size)
        upright.paste(white, place, white_mask)
        upright.paste(black, place, black_mask)
    return settings.orientation.stored(upright)


def _row(icons: Collection[Icon], position: Position) -> list[Icon]:
    """``icons`` from left to right (the first icon nearest to the corner)."""
    row = [icon for icon in Icon if icon in icons]
    return row[::-1] if position.right else row


def _places(
    image_size: tuple[int, int], count: int, settings: IconSettings
) -> list[tuple[int, int]]:
    """Top left corners of ``count`` icons in a row from the corner."""
    size = settings.size
    gap = max(3, size // 4)
    width, height = image_size
    row_width = count * size + (count - 1) * gap
    x = width - MARGIN - row_width if settings.position.right else MARGIN
    y = height - MARGIN - size if settings.position.bottom else MARGIN
    return [(x + index * (size + gap), y) for index in range(count)]


@cache
def render(icon: Icon, size: int) -> tuple[Image.Image, Image.Image]:
    """The white and the black mask (mode ``1``) of ``icon`` in ``size`` pixels.

    Cached: don't change the returned images.
    """
    big = size * SUPERSAMPLING
    disc = Image.new("L", (big, big), 0)
    ImageDraw.Draw(disc).ellipse((0, 0, big - 1, big - 1), fill=255)
    ring = max(2, round(size / RING)) * SUPERSAMPLING
    black = disc.copy()
    ImageDraw.Draw(black).ellipse((ring, ring, big - 1 - ring, big - 1 - ring), fill=0)
    glyph = round(size * GLYPH) * SUPERSAMPLING
    glyph_black, glyph_white = GLYPHS[icon](glyph)
    offset = ((big - glyph) // 2, (big - glyph) // 2)
    black.paste(255, offset, glyph_black)
    black.paste(0, offset, glyph_white)
    return _reduce(disc, size), _reduce(black, size)


def _reduce(mask: Image.Image, size: int) -> Image.Image:
    small = mask.resize((size, size), Image.Resampling.BOX)
    return small.point(lambda value: 255 if value >= 128 else 0).convert("1")


# ------------------------------------------------------------------ glyphs
# each returns its black and white parts (mode L masks, ``side`` pixels square)

Layers = tuple[Image.Image, Image.Image]


def _layers(side: int) -> tuple[Image.Image, Image.Image]:
    return Image.new("L", (side, side), 0), Image.new("L", (side, side), 0)


def _scaled(side: int, *units: float) -> list[float]:
    return [unit * side for unit in units]


def _points(side: int, *units: float) -> list[tuple[float, float]]:
    values = _scaled(side, *units)
    return list(zip(values[::2], values[1::2], strict=True))


def hourglass(side: int) -> Layers:
    black, white = _layers(side)
    draw = ImageDraw.Draw(black)
    draw.rectangle(_scaled(side, 0.18, 0.06, 0.82, 0.16), fill=255)
    draw.rectangle(_scaled(side, 0.18, 0.84, 0.82, 0.94), fill=255)
    outline = _points(side, 0.26, 0.16, 0.74, 0.16, 0.5, 0.5, 0.74, 0.84, 0.26, 0.84)
    draw.line(
        [*outline, (0.5 * side, 0.5 * side), outline[0]],
        fill=255,
        width=round(0.08 * side),
        joint="curve",
    )
    draw.polygon(_points(side, 0.5, 0.62, 0.66, 0.84, 0.34, 0.84), fill=255)  # sand
    draw.polygon(_points(side, 0.42, 0.34, 0.58, 0.34, 0.5, 0.44), fill=255)
    return black, white


def exclamation(side: int) -> Layers:
    black, white = _layers(side)
    draw = ImageDraw.Draw(black)
    draw.rounded_rectangle(
        _scaled(side, 0.4, 0.06, 0.6, 0.66), radius=0.04 * side, fill=255
    )
    draw.ellipse(_scaled(side, 0.4, 0.74, 0.6, 0.94), fill=255)
    return black, white


def no_wifi(side: int) -> Layers:
    black, white = _layers(side)
    draw = ImageDraw.Draw(black)
    width = round(0.1 * side)
    x, y = 0.5, 0.84
    for radius in (0.24, 0.46, 0.68):
        box = _scaled(side, x - radius, y - radius, x + radius, y + radius)
        draw.arc(box, 225, 315, fill=255, width=width)
    draw.ellipse(_scaled(side, x - 0.1, y - 0.1, x + 0.1, y + 0.1), fill=255)
    # the slash with a white gap around it
    slash = _scaled(side, 0.12, 0.08, 0.88, 0.92)
    gap = round(width * 1.9)
    draw.line(slash, fill=0, width=gap)
    ImageDraw.Draw(white).line(slash, fill=255, width=gap)
    draw.line(slash, fill=255, width=width)
    ImageDraw.Draw(white).line(slash, fill=0, width=width)
    return black, white


GLYPHS: dict[Icon, Callable[[int], Layers]] = {
    Icon.BUSY: hourglass,
    Icon.OFFLINE: no_wifi,
    Icon.ERROR: exclamation,
}
