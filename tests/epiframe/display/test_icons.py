import pytest
from PIL import Image, ImageChops

from epiframe.display.icons import (
    CORNER_CHECK_ENTRIES,
    MARGIN,
    MIN_SIZE,
    Icon,
    IconSettings,
    check_corner,
    draw_icons,
    enabled_icons,
    render,
)
from epiframe.processing.orientation import Orientation, Position

WIDTH, HEIGHT = 200, 100


class Config:
    def __init__(self, **values: str) -> None:
        self.values = {
            "busy_icon": "1",
            "offline_icon": "0",
            "error_icon": "1",
            "icons_position": "2",
            "icons_size": "24",
            "horizontal": "0",
            "turned": "1",
            "rotation": "270",
        } | values

    def get(self, name: str) -> str:
        return self.values[name]

    def getint(self, name: str) -> int:
        return int(self.values[name])


def settings(
    position: Position = Position.TOP_LEFT,
    size: int = 20,
    orientation: Orientation | None = None,
) -> IconSettings:
    return IconSettings(frozenset(Icon), position, size, orientation or Orientation())


def changed_box(before: Image.Image, after: Image.Image) -> tuple[int, int, int, int]:
    box = ImageChops.difference(before.convert("L"), after.convert("L")).getbbox()
    assert box is not None
    return box


def gray_photo() -> Image.Image:
    # gray: both the black and the white parts of the icons change it
    return Image.new("L", (WIDTH, HEIGHT), 128)


def test_icon_settings() -> None:
    assert [icon.setting for icon in Icon] == [
        "busy_icon",
        "offline_icon",
        "error_icon",
    ]
    assert enabled_icons(Config()) == {Icon.BUSY, Icon.ERROR}
    assert IconSettings.from_config(Config()) == IconSettings(
        frozenset({Icon.BUSY, Icon.ERROR}),
        Position.BOTTOM_LEFT,
        24,
        Orientation(horizontal=False, turned=False, rotation=270),
    )


@pytest.mark.parametrize("icon", list(Icon))
@pytest.mark.parametrize("size", [MIN_SIZE, 32, 77])
def test_render(icon: Icon, size: int) -> None:
    white, black = render(icon, size)

    assert white.mode == black.mode == "1"
    assert white.size == black.size == (size, size)
    assert white.getpixel((0, 0)) == 0  # a disc: the corners stay the photo
    assert white.getpixel((size // 2, size // 2)) == 255
    assert black.getpixel((0, size // 2)) == 255  # the ring
    assert black.getpixel((size // 2, size // 2)) == 255  # the glyph in the middle
    assert render(icon, size) is render(icon, size)  # cached


@pytest.mark.parametrize(
    ("position", "box"),
    [
        (Position.TOP_LEFT, (MARGIN, MARGIN)),
        (Position.TOP_RIGHT, (WIDTH - MARGIN - 70, MARGIN)),
        (Position.BOTTOM_LEFT, (MARGIN, HEIGHT - MARGIN - 20)),
        (Position.BOTTOM_RIGHT, (WIDTH - MARGIN - 70, HEIGHT - MARGIN - 20)),
    ],
)
def test_row_in_every_corner(position: Position, box: tuple[int, int]) -> None:
    photo = gray_photo()

    result = draw_icons(photo, set(Icon), settings(position))

    # 3 icons of 20 pixels, gaps of 5
    x, y = box
    assert changed_box(photo, result) == (x, y, x + 70, y + 20)
    assert photo.getcolors() == [(WIDTH * HEIGHT, 128)]  # the photo is not changed


@pytest.mark.parametrize(
    ("position", "x"),
    [(Position.TOP_LEFT, MARGIN), (Position.TOP_RIGHT, WIDTH - MARGIN - 20)],
)
def test_first_icon_nearest_to_the_corner(position: Position, x: int) -> None:
    photo = gray_photo()
    busy_only = draw_icons(photo, {Icon.BUSY}, settings(position))
    all_icons = draw_icons(photo, set(Icon), settings(position))

    corner = (x, MARGIN, x + 20, MARGIN + 20)
    assert busy_only.crop(corner).tobytes() == all_icons.crop(corner).tobytes()


def test_no_icons() -> None:
    photo = gray_photo()

    assert draw_icons(photo, set(), settings()).tobytes() == photo.tobytes()


def test_icons_are_pure_black_and_white() -> None:
    photo = Image.new("L", (WIDTH, HEIGHT), 128)

    result = draw_icons(photo, set(Icon), settings(size=40))

    assert set(result.getcolors() or []) <= {
        (n, v) for n, v in result.getcolors() or []
    }
    assert {value for _, value in result.getcolors() or []} == {0, 128, 255}


def test_other_modes_are_drawn_in_rgb() -> None:
    photo = Image.new("RGB", (WIDTH, HEIGHT), "gray").convert("P")

    result = draw_icons(photo, {Icon.ERROR}, settings())

    assert result.mode == "RGB"
    assert result.getpixel((MARGIN + 10, MARGIN + 3)) == (255, 255, 255)
    assert result.getpixel((MARGIN + 10, MARGIN)) == (0, 0, 0)  # the ring


@pytest.mark.parametrize(
    ("orientation", "box"),
    [
        # upside down: the top left corner of the viewer is the bottom right one
        (Orientation(turned=True), (WIDTH - MARGIN - 20, HEIGHT - MARGIN - 20)),
        # vertical, stored turned by 90 degrees clockwise: the viewer's top left
        # is the stored top right
        (Orientation(horizontal=False, rotation=90), (WIDTH - MARGIN - 20, MARGIN)),
        (Orientation(horizontal=False, rotation=270), (MARGIN, HEIGHT - MARGIN - 20)),
    ],
)
def test_orientation(orientation: Orientation, box: tuple[int, int]) -> None:
    photo = gray_photo()

    result = draw_icons(photo, {Icon.BUSY}, settings(orientation=orientation))

    x, y = box
    assert result.size == photo.size
    assert changed_box(photo, result) == (x, y, x + 20, y + 20)


@pytest.mark.parametrize(
    ("values", "same"),
    [
        (["1", "1", "1", "1", "0", "0"], True),
        (["1", "1", "1", "0", "0", "1"], True),
        (["1", "1", "2", "1", "1", "1"], False),  # other corners
        (["1", "0", "1", "1", "1", "1"], False),  # no weather stamp
        (["1", "1", "1", "0", "0", "0"], False),  # no icons
    ],
)
def test_check_corner(values: list[str], same: bool) -> None:
    assert len(values) == len(CORNER_CHECK_ENTRIES)
    if same:
        with pytest.raises(ValueError, match="same corner as the weather stamp"):
            check_corner(values)
    else:
        check_corner(values)
