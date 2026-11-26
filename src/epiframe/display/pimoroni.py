"""Pimoroni Inky e-Paper displays (``inky`` library, checked with pimoroni/inky main).

Two kinds of panels:

- **multicolor** (Impression 7-color, Spectra 6, black/white/red/yellow): the
  photo is dithered to the panel's palette blended by ``pimoroni_saturation``
  (between the panel's desaturated and saturated colors); ``epaper_color``
  doesn't apply. Spectra 6 and red/yellow panels get the RGB photo and the
  saturation (the library does it); for the 7-color Impression panels
  (:data:`BLENDED`) ePiframe blends the palette with the library's formula,
  because their ``set_image`` fails on RGB images with Pillow 13 ("empty
  palette": it converts via the private ``Image.im`` without loading the palette);
- **black/white(/red or yellow)** (pHAT, wHAT and their SSD16xx variants): ePiframe
  reduces the photo to the ``epaper_color`` palette (as 1.x).
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
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
    "inky_ssd1608": "Inky",  # pHAT (SSD1608)
    "inky_ssd1683": "Inky",  # wHAT (SSD1683)
    "inky_uc8159": "Inky",  # Impression 5.7" / 4" (7 colors)
    "inky_ac073tc1a": "Inky",  # Impression 7.3" (7 colors)
    "inky_e640": "Inky",  # Impression 4" (Spectra 6)
    "inky_e673": "Inky",  # Impression 7.3" (Spectra 6)
    "inky_el133uf1": "Inky",  # Impression 13.3" (Spectra 6)
    "inky_jd79661": "Inky",  # pHAT 2.13" (black, white, red, yellow)
    "inky_jd79668": "Inky",  # wHAT 4.2" (black, white, red, yellow)
    "inky_ssd2683": "Inky",  # wHAT 4.2" (black, white, red, yellow)
}
# panels whose library quantizes the photo itself (``set_image(image, saturation)``);
# their only accepted ``colour`` is the default ("multi" or "red/yellow")
MULTICOLOR = frozenset(
    {
        "inky_uc8159",
        "inky_ac073tc1a",
        "inky_e640",
        "inky_e673",
        "inky_el133uf1",
        "inky_jd79661",
        "inky_jd79668",
        "inky_ssd2683",
    }
)

# 7-color Impression panels: ePiframe blends the palette (see the module docstring)
BLENDED = frozenset({"inky_uc8159", "inky_ac073tc1a"})
SEVEN_COLORS = 7  # the 8th library color is "clean" (no ink), never chosen

COLOUR: Mapping[ColorMode, str] = {
    ColorMode.BW: "black",
    ColorMode.BWR: "red",
    ColorMode.BWY: "yellow",
}
SECOND_COLOR: Mapping[ColorMode, colors.Color] = {
    ColorMode.BWR: colors.RED,
    ColorMode.BWY: colors.YELLOW,
}


def palette_for(inky: Any, color: ColorMode) -> list[colors.Color]:
    """Colors of a black/white(/color) panel in the library's order.

    Palette index = the library's color value: ``WHITE``/``BLACK`` (0 and 1) are
    attributes of the display class (``inky.phat`` / ``inky.what`` have no
    module-level constants), the second color is 2.
    """
    if color == ColorMode.C7:
        raise DisplayError("The display doesn't support 7 colors!")
    palette = [colors.BLACK, colors.BLACK]
    palette[inky.WHITE] = colors.WHITE
    palette[inky.BLACK] = colors.BLACK
    second = SECOND_COLOR.get(color)
    return palette + ([second] if second else [])


def blended_palette(inky: Any, saturation: float) -> list[colors.Color]:
    """The 7 panel colors at ``saturation`` (as the library's ``_palette_blend``)."""
    pairs = zip(
        inky.SATURATED_PALETTE[:SEVEN_COLORS],
        inky.DESATURATED_PALETTE[:SEVEN_COLORS],
        strict=True,
    )
    return [
        tuple(
            int(vivid * saturation + soft * (1.0 - saturation))
            for vivid, soft in zip(saturated, desaturated, strict=True)
        )
        for saturated, desaturated in pairs
    ]


class PimoroniDisplay:
    """Shows photos on a Pimoroni Inky panel."""

    capabilities = frozenset({Capability.FULL})

    def __init__(
        self,
        inky: Any,
        palette: Sequence[colors.Color] | None,
        *,
        border_black: bool = False,
        clear: bool = False,
        saturation: float = 0.5,
    ):
        """``palette=None``: the library reduces the colors (with ``saturation``)."""
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
        saturation: float = 0.5,
        directory: Path | str | None = None,
    ) -> "PimoroniDisplay":
        """Load the ``inky.<name>`` module (e.g. ``what``) and its display."""
        if name not in CLASSES:
            raise DisplayError(f"No Pimoroni display package {name} in lib.inky!")
        display_class = getattr(load_driver(PACKAGE, name, directory), CLASSES[name])
        if name in BLENDED:
            inky = display_class()
            palette: list[colors.Color] | None = blended_palette(inky, saturation)
        elif name in MULTICOLOR:
            inky, palette = display_class(), None
        else:
            colour = COLOUR.get(color)
            inky = display_class(colour=colour) if colour else display_class()
            palette = palette_for(inky, color)
        return cls(
            inky,
            palette,
            border_black=background.lower().strip() == Background.BLACK,
            clear=clear,
            saturation=saturation,
        )

    def show_partial(self, path: Path | str, previous: Path | str) -> None:
        # set_region() of the newest Spectra 6 drivers is untested: not used yet
        raise DisplayError("The display has no partial refresh!")

    def show(self, path: Path | str) -> None:
        if self._clear:
            self._inky.set_border(
                self._inky.BLACK if self._border_black else self._inky.WHITE
            )
        with Image.open(path) as image:
            if self._palette is None:
                # RGB: a palette ("P") image would skip the library's quantization
                self._inky.set_image(image.convert("RGB"), saturation=self._saturation)
            else:
                self._inky.set_image(colors.quantize(image, self._palette))
        self._inky.show()
