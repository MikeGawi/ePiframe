import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from PIL import Image

from epiframe.display import colors
from epiframe.display.base import Capability, DisplayError
from epiframe.display.library import load_driver
from epiframe.display.options import Background, ColorMode
from epiframe.display.pimoroni import PimoroniDisplay, palette_for
from tests.epiframe.display.helpers import RECORDED_1X, digest, recorded_images

IMAGES = recorded_images()
# Recorded with the 1.x fakes, which had module-level WHITE/BLACK everywhere. Not
# comparable (1.x failed with the real library): phat (1.x read the module
# constants, the real inky.phat has none) and inky_ac073tc1a (1.x passed
# colour="black"/"red"/"yellow" and a 2-color palette to a 7-color panel).
NOT_COMPARABLE = {"phat", "inky_ac073tc1a"}
CASES_1X = [
    case
    for case in RECORDED_1X["pimoroni"]
    if "error" not in case and case["display"] not in NOT_COMPARABLE
]
# 7 colors on a non-Impression panel crashed in 1.x (no SATURATED_PALETTE)
FAILED_1X = [
    case
    for case in RECORDED_1X["pimoroni"]
    if "error" in case and case["display"] not in NOT_COMPARABLE
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
    path = tmp_path / "photo.png"
    Image.new("RGB", (4, 4), "white").save(path)
    return path


@pytest.mark.parametrize(
    "case", CASES_1X, ids=lambda case: f"{case['display']}-{case['color']}"
)
def test_matches_1x(library: Path, case: dict[str, Any]) -> None:
    display = PimoroniDisplay.load(
        case["display"], ColorMode(case["color"]), directory=library
    )

    assert calls() == [("init", colour_1x(case))]
    assert [list(color) for color in display._palette] == case["palette"]
    for name, image in IMAGES.items():
        assert digest(colors.quantize(image, display._palette)) == case["images"][name]


@pytest.mark.parametrize(
    "case", FAILED_1X, ids=lambda case: f"{case['display']}-{case['color']}"
)
def test_seven_colors_not_supported(library: Path, case: dict[str, Any]) -> None:
    with pytest.raises(DisplayError, match="doesn't support 7 colors"):
        PimoroniDisplay.load(case["display"], ColorMode.C7, directory=library)


def test_seven_colors_from_display() -> None:
    class Impression:
        SATURATED_PALETTE = ([1, 2, 3], [4, 5, 6])

    module = ModuleType("inky.fake_impression")

    assert palette_for(Impression(), module, ColorMode.C7) == [[1, 2, 3], [4, 5, 6]]


def test_seven_colors_from_module() -> None:
    module = ModuleType("inky.fake_impression")
    module.SATURATED_PALETTE = [[1, 2, 3]]  # type: ignore[attr-defined]

    assert palette_for(object(), module, ColorMode.C7) == [[1, 2, 3]]


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

    assert [list(c) for c in display._palette] == palette


@pytest.mark.parametrize("color", list(ColorMode))
def test_impression_7_3(library: Path, photo: Path, color: ColorMode) -> None:
    display = PimoroniDisplay.load(
        "inky_ac073tc1a", color, saturation=0.6, directory=library
    )
    display.show(photo)

    # no colour argument (only "multi" is accepted), the library's palette
    assert calls() == [("init", None), ("set_image", "P", 0.6), ("show",)]
    assert display._palette == [[0, 0, 0], [255, 255, 255], [0, 255, 0]]


def test_multicolor_palette_missing(library: Path) -> None:
    fake: Any = load_driver("inky", "inky_uc8159", library)
    del fake.DESATURATED_PALETTE

    with pytest.raises(DisplayError, match="has no DESATURATED_PALETTE"):
        PimoroniDisplay.load("inky_uc8159", ColorMode.C7, directory=library)


def test_show(library: Path, photo: Path) -> None:
    display = PimoroniDisplay.load("what", ColorMode.BWR, directory=library)
    calls().clear()

    display.show(photo)

    assert display.capabilities == {Capability.FULL}
    assert calls() == [("set_image", "P", None), ("show",)]


def test_show_with_saturation(library: Path, photo: Path) -> None:
    display = PimoroniDisplay.load(
        "inky_uc8159", ColorMode.C7, saturation=0.8, directory=library
    )
    calls().clear()

    display.show(photo)

    assert calls() == [("set_image", "P", 0.8), ("show",)]


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
