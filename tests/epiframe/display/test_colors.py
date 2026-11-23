from typing import Any

import pytest
from PIL import Image

from epiframe.display import colors
from tests.epiframe.display.helpers import RECORDED_1X, digest, recorded_images

IMAGES = recorded_images()
SECOND = {"BW+Red": colors.RED, "BW+Yellow": colors.YELLOW}


def test_palette_image_has_only_the_colors() -> None:
    palette = colors.palette_image([colors.WHITE, colors.RED]).getpalette()

    assert palette == [255, 255, 255, 255, 0, 0]


def test_quantize_never_picks_a_color_outside_the_palette() -> None:
    # no pure black in the palette: dark pixels go to the darkest color
    image = Image.new("RGB", (2, 1))
    image.putdata([(0, 0, 0), (250, 250, 250)])

    quantized = colors.quantize(image, [(255, 255, 255), (57, 48, 57)])

    assert [quantized.getpixel((x, 0)) for x in range(2)] == [1, 0]


def test_quantize_uses_palette_indexes() -> None:
    image = Image.new("RGB", (3, 1))
    image.putdata([(250, 250, 250), (5, 5, 5), (240, 20, 10)])

    quantized = colors.quantize(image, [colors.BLACK, colors.WHITE, colors.RED])

    assert quantized.mode == "P"
    assert [quantized.getpixel((x, 0)) for x in range(3)] == [1, 0, 2]


def test_split_two_color_planes() -> None:
    image = Image.new("RGB", (3, 1))
    image.putdata([(255, 0, 0), (255, 255, 255), (0, 0, 0)])

    black, red = colors.split_two_color(image, colors.RED)

    # 0 = ink: the black plane at the black pixel, the color plane at the red one
    assert [black.getpixel((x, 0)) for x in range(3)] == [255, 255, 0]
    assert [red.getpixel((x, 0)) for x in range(3)] == [0, 255, 255]


@pytest.mark.parametrize(
    "case",
    RECORDED_1X["waveshare"],
    ids=lambda case: f"{case['image']}-{case['color']}",
)
def test_split_two_color_matches_1x(case: dict[str, Any]) -> None:
    black, color = colors.split_two_color(IMAGES[case["image"]], SECOND[case["color"]])

    assert black.mode == color.mode == case["mode"]
    assert digest(black) == case["black"]
    assert digest(color) == case["color_plane"]
