import pytest
from PIL import Image

from epiframe.processing.orientation import Orientation, Position


class Config:
    def __init__(self, horizontal: str, turned: str, rotation: str = "90") -> None:
        self.values = {"horizontal": horizontal, "turned": turned, "rotation": rotation}

    def getint(self, name: str) -> int:
        return int(self.values[name])


def test_positions() -> None:
    assert Position.values() == [0, 1, 2, 3]
    assert [(p.right, p.bottom) for p in Position] == [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ]


@pytest.mark.parametrize(
    ("config", "orientation"),
    [
        (Config("1", "0"), Orientation(True, False, 90)),
        (Config("1", "1"), Orientation(True, True, 90)),
        # turned is for horizontal frames only
        (Config("0", "1", "270"), Orientation(False, False, 270)),
    ],
)
def test_from_config(config: Config, orientation: Orientation) -> None:
    assert Orientation.from_config(config) == orientation


def marked() -> Image.Image:
    image = Image.new("L", (4, 2), 0)
    image.putpixel((0, 0), 255)  # the stored top left
    return image


@pytest.mark.parametrize(
    ("orientation", "size", "mark"),
    [
        (Orientation(), (4, 2), (0, 0)),
        (Orientation(turned=True), (4, 2), (3, 1)),
        (Orientation(horizontal=False, rotation=90), (2, 4), (0, 3)),
        (Orientation(horizontal=False, rotation=270), (2, 4), (1, 0)),
    ],
)
def test_upright_and_back(
    orientation: Orientation, size: tuple[int, int], mark: tuple[int, int]
) -> None:
    image = marked()

    upright = orientation.upright(image)

    assert upright.size == size
    assert upright.getpixel(mark) == 255
    assert upright is not image  # always a copy
    assert orientation.stored(upright).tobytes() == image.tobytes()
