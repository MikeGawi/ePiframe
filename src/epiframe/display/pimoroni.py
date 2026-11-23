"""Pimoroni Inky e-Paper displays (``inky`` library)."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from PIL import Image

from epiframe.display import colors
from epiframe.display.base import Capability, DisplayError
from epiframe.display.library import load_driver
from epiframe.display.options import Background, ColorMode

PACKAGE = "inky"

# inky module -> its display class
CLASSES: Mapping[str, str] = {
    "phat": "InkyPHAT",
    "what": "InkyWHAT",
    "inky_ssd1608": "Inky",
    "inky_uc8159": "Inky",
    "inky_ssd1683": "Inky",
    "inky_ac073tc1a": "Inky",
}
# 7-color Impression panels: own palette, take a saturation, accept no ``colour``
# argument (the library allows only "multi")
MULTICOLOR = frozenset({"inky_uc8159", "inky_ac073tc1a"})

COLOUR: Mapping[ColorMode, str] = {
    ColorMode.BW: "black",
    ColorMode.BWR: "red",
    ColorMode.BWY: "yellow",
}
SECOND_COLOR: Mapping[ColorMode, colors.Color] = {
    ColorMode.BWR: colors.RED,
    ColorMode.BWY: colors.YELLOW,
}


def _two_color_palette(inky: Any) -> list[colors.Color]:
    # palette index = the library's color value (WHITE/BLACK are 0 and 1); the
    # values are attributes of the display class (``inky.phat`` / ``inky.what``
    # have no module-level constants)
    palette = [colors.BLACK, colors.BLACK]
    palette[inky.WHITE] = colors.WHITE
    palette[inky.BLACK] = colors.BLACK
    return palette


def _library_palette(inky: object, module: ModuleType, name: str) -> list[colors.Color]:
    # the palettes are class attributes (ac073tc1a) or module constants (uc8159)
    for owner in (inky, module):
        palette = getattr(owner, name, None)
        if palette is not None:
            return list(palette)
    raise DisplayError(f"The display library has no {name}!")


def palette_for(inky: Any, module: ModuleType, color: ColorMode) -> list[colors.Color]:
    """Colors of a black/white(/color) display in the library's order."""
    if color == ColorMode.C7:
        try:
            return _library_palette(inky, module, "SATURATED_PALETTE")
        except DisplayError:
            raise DisplayError("The display doesn't support 7 colors!") from None
    second = SECOND_COLOR.get(color)
    return _two_color_palette(inky) + ([second] if second else [])


class PimoroniDisplay:
    """Shows photos on a Pimoroni Inky panel."""

    capabilities = frozenset({Capability.FULL})

    def __init__(
        self,
        inky: Any,
        palette: Sequence[colors.Color],
        *,
        border_black: bool = False,
        clear: bool = False,
        saturation: float | None = None,
    ):
        self._inky = inky
        self._palette = palette
        self._border_black = border_black
        self._clear = clear
        self._saturation = saturation

    @classmethod
    def load(  # noqa: PLR0913 - the display settings
        cls,
        name: str,
        color: ColorMode,
        *,
        background: str = Background.WHITE,
        clear: bool = False,
        saturation: float = 0.0,
        directory: Path | str | None = None,
    ) -> "PimoroniDisplay":
        """Load the ``inky.<name>`` module (e.g. ``what``) and its display."""
        if name not in CLASSES:
            raise DisplayError(f"No Pimoroni display package {name} in lib.inky!")
        module = load_driver(PACKAGE, name, directory)
        display_class = getattr(module, CLASSES[name])
        multicolor = name in MULTICOLOR
        if multicolor:
            inky = display_class()
            palette = _library_palette(inky, module, "DESATURATED_PALETTE")
        else:
            colour = COLOUR.get(color)
            inky = display_class(colour=colour) if colour else display_class()
            palette = palette_for(inky, module, color)
        return cls(
            inky,
            palette,
            border_black=background.lower().strip() == Background.BLACK,
            clear=clear,
            saturation=saturation if multicolor else None,
        )

    def show(self, path: Path | str) -> None:
        if self._clear:
            self._inky.set_border(
                self._inky.BLACK if self._border_black else self._inky.WHITE
            )
        with Image.open(path) as image:
            converted = colors.quantize(image, self._palette)
        if self._saturation is None:
            self._inky.set_image(converted)
        else:
            self._inky.set_image(converted, saturation=self._saturation)
        self._inky.show()
