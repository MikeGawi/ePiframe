import importlib
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from epiframe.display import colors
from epiframe.display.base import Capability, DisplayError
from epiframe.display.options import Background, ColorMode
from epiframe.display.pimoroni import (
    BLENDED,
    CLASSES,
    MULTICOLOR,
    SEVEN_COLORS,
    PimoroniDisplay,
    blended_palette,
)
from tests.epiframe.display.conftest import MULTICOLOR_DEFAULTS
from tests.epiframe.display.helpers import RECORDED_1X, digest, recorded_images

IMAGES = recorded_images()
# Recorded with the 1.x fakes, which had module-level WHITE/BLACK everywhere. Only
# the black/white(/color) panels whose class constants equal those values are
# comparable: 1.x failed on the real phat (no module constants) and
# inky_ac073tc1a (colour argument), and multicolor panels now get the RGB photo.
COMPARABLE = {"what", "inky_ssd1608", "inky_ssd1683"}
CASES_1X = [
    case
    for case in RECORDED_1X["pimoroni"]
    if "error" not in case and case["display"] in COMPARABLE
]
# 7 colors on a black/white(/color) panel crashed in 1.x (no SATURATED_PALETTE)
FAILED_1X = [
    case
    for case in RECORDED_1X["pimoroni"]
    if "error" in case and case["display"] in COMPARABLE | {"phat"}
]


def calls() -> list[Any]:
    fake: Any = importlib.import_module("inky.fake")
    return fake.CALLS  # type: ignore[no-any-return]


def colour_1x(case: dict[str, Any]) -> str | None:
    # 1.x printed "colour='red'" when the colour argument was given
    lines = [line for line in case["init"] if line.startswith("colour=")]
    return lines[0].split("'")[1] if lines else None


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    # a palette image (as ImageMagick may write it)
    path = tmp_path / "photo.bmp"
    Image.new("RGB", (4, 4), "white").convert("P").save(path)
    return path


def test_every_multicolor_module_is_known() -> None:
    assert BLENDED <= MULTICOLOR <= CLASSES.keys()
    assert set(MULTICOLOR_DEFAULTS) == MULTICOLOR


@pytest.mark.parametrize(
    "case", CASES_1X, ids=lambda case: f"{case['display']}-{case['color']}"
)
def test_matches_1x(library: Path, case: dict[str, Any]) -> None:
    display = PimoroniDisplay.load(
        case["display"], ColorMode(case["color"]), directory=library
    )

    assert calls() == [("init", colour_1x(case))]
    assert display._palette is not None
    assert [list(color) for color in display._palette] == case["palette"]
    for name, image in IMAGES.items():
        assert digest(colors.quantize(image, display._palette)) == case["images"][name]


@pytest.mark.parametrize(
    "case", FAILED_1X, ids=lambda case: f"{case['display']}-{case['color']}"
)
def test_seven_colors_not_supported(library: Path, case: dict[str, Any]) -> None:
    with pytest.raises(DisplayError, match="doesn't support 7 colors"):
        PimoroniDisplay.load(case["display"], ColorMode.C7, directory=library)


@pytest.mark.parametrize(
    ("color", "palette"),
    [
        (ColorMode.BW, [[255, 255, 255], [0, 0, 0]]),
        (ColorMode.BWY, [[255, 255, 255], [0, 0, 0], [255, 255, 0]]),
    ],
)
def test_phat_palette_from_class_constants(
    library: Path, color: ColorMode, palette: list[list[int]]
) -> None:
    # InkyPHAT: WHITE = 0, BLACK = 1 (the module has no constants)
    display = PimoroniDisplay.load("phat", color, directory=library)

    assert display._palette is not None
    assert [list(c) for c in display._palette] == palette


def test_show_black_white_red(library: Path, photo: Path) -> None:
    display = PimoroniDisplay.load("what", ColorMode.BWR, directory=library)
    calls().clear()

    display.show(photo)

    assert display.capabilities == {Capability.FULL}
    # reduced by ePiframe, no saturation
    assert calls() == [("set_image", "P", None), ("show",)]


@pytest.mark.parametrize("name", sorted(MULTICOLOR - BLENDED))
@pytest.mark.parametrize("color", list(ColorMode))
def test_multicolor_gets_rgb_photo(
    library: Path, photo: Path, name: str, color: ColorMode
) -> None:
    display = PimoroniDisplay.load(name, color, saturation=0.6, directory=library)
    display.show(photo)

    # default colour only, the library reduces the RGB photo with the saturation
    assert calls() == [("init", None), ("set_image", "RGB", 0.6), ("show",)]
    assert display._palette is None


@pytest.mark.parametrize("name", sorted(BLENDED))
@pytest.mark.parametrize("color", list(ColorMode))
def test_seven_color_impression_gets_blended_palette(
    library: Path, photo: Path, name: str, color: ColorMode
) -> None:
    display = PimoroniDisplay.load(name, color, saturation=0.6, directory=library)
    display.show(photo)

    # ePiframe reduces the photo; a "P" image is used by the library as it is
    assert calls() == [("init", None), ("set_image", "P", 0.5), ("show",)]
    assert display._palette == blended_palette(display._inky, 0.6)


@pytest.mark.parametrize(
    ("saturation", "first", "orange"),
    [
        (0.0, (0, 0, 0), (255, 140, 0)),  # DESATURATED_PALETTE
        (1.0, (57, 48, 57), (177, 106, 73)),  # SATURATED_PALETTE
        (0.5, (28, 24, 28), (216, 123, 36)),  # int(s * 0.5 + d * 0.5)
    ],
)
def test_blended_palette(
    library: Path,
    saturation: float,
    first: tuple[int, ...],
    orange: tuple[int, ...],
) -> None:
    display = PimoroniDisplay.load("inky_uc8159", ColorMode.C7, directory=library)

    palette = blended_palette(display._inky, saturation)

    # 7 colors: the library's 8th one ("clean", no ink) is never chosen
    assert len(palette) == SEVEN_COLORS
    assert palette[0] == first
    assert palette[6] == orange


@pytest.mark.parametrize(
    ("background", "border"),
    [(Background.BLACK, 1), (" Black ", 1), (Background.WHITE, 0), ("photo", 0)],
)
def test_clear_sets_border(
    library: Path, photo: Path, background: str, border: int
) -> None:
    # InkyPHAT: BLACK = 1, WHITE = 0
    display = PimoroniDisplay.load(
        "phat", ColorMode.BW, background=background, clear=True, directory=library
    )
    calls().clear()

    display.show(photo)

    assert calls()[0] == ("set_border", border)


def test_unknown_display(library: Path) -> None:
    with pytest.raises(DisplayError, match="No Pimoroni display package x in"):
        PimoroniDisplay.load("x", ColorMode.BW, directory=library)
