"""Color reduction of a photo to the palette of an e-Paper display."""

from collections.abc import Sequence
from itertools import chain
from typing import TypeAlias

from PIL import Image

Color: TypeAlias = Sequence[int]  # (red, green, blue)

WHITE: Color = (255, 255, 255)
BLACK: Color = (0, 0, 0)
RED: Color = (255, 0, 0)
YELLOW: Color = (255, 255, 0)


def palette_image(colors: Sequence[Color]) -> Image.Image:
    """Return a ``P`` image whose palette is exactly ``colors``.

    1.x padded the palette to 256 colors with black: harmless while the palette
    has pure black, but with a blended palette the padding black was chosen for
    dark pixels (an index the display doesn't have).
    """
    palette = list(chain.from_iterable(colors))
    image = Image.new("P", (1, 1))
    image.putpalette(palette)
    return image


def quantize(image: Image.Image, colors: Sequence[Color]) -> Image.Image:
    """Reduce ``image`` to ``colors`` (dithered); pixel values are their indexes."""
    return image.convert("RGB").quantize(palette=palette_image(colors))


def _plane(quantized: Image.Image, index: int) -> Image.Image:
    # 1-bit plane: 0 (ink) where the pixel has the color ``index``
    def lookup(pixel: int) -> int:
        return 1 if pixel != index else 3

    return quantized.point(lookup).convert("1")


def split_two_color(
    image: Image.Image, color: Color
) -> tuple[Image.Image, Image.Image]:
    """Split ``image`` into the black and the ``color`` planes of a 3-color display.

    The photo is reduced to black, white and ``color``; each plane has ``0`` where
    its ink is used (Waveshare buffer convention).
    """
    quantized = quantize(image, [color, WHITE, BLACK])
    return _plane(quantized, 2), _plane(quantized, 0)
