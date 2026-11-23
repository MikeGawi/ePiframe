"""Fake vendor display libraries written to ``tmp_path``."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

PACKAGES = ("waveshare_epd", "inky")


FAKE_INKY = """
BLACK = 0
WHITE = 1
DESATURATED_PALETTE = [
    [0, 0, 0],
    [255, 255, 255],
    [0, 255, 0],
    [0, 0, 255],
    [255, 0, 0],
    [255, 255, 0],
    [255, 140, 0],
    [255, 255, 255],
]
CALLS = []


class InkyBase:
    BLACK = 0
    WHITE = 1

    def __init__(self, colour=None):
        CALLS.append(("init", colour))

    def set_border(self, colour):
        CALLS.append(("set_border", colour))

    def set_image(self, image, saturation=None):
        CALLS.append(("set_image", image.mode, saturation))

    def show(self):
        CALLS.append(("show",))


class InkyPHAT(InkyBase):
    BLACK = 1
    WHITE = 0


class InkyWHAT(InkyBase):
    pass


class Inky(InkyBase):
    pass
"""

INKY_MODULES = (
    "phat",
    "what",
    "inky_ssd1608",
    "inky_uc8159",
    "inky_ssd1683",
    "inky_ac073tc1a",
)

FAKE_EPD = """
from . import epdconfig

CALLS = epdconfig.CALLS


class EPD:
    def init(self):
        CALLS.append("init")
        return 0

    def getbuffer(self, image):
        return image.mode

    def display(self, *buffers):
        CALLS.append(("display", *buffers))

    def Clear(self):
        CALLS.append("Clear")

    def sleep(self):
        CALLS.append("sleep")
"""

FAKE_EPDCONFIG = """
CALLS = []


def module_exit():
    CALLS.append("module_exit")
"""


def _forget_packages() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in PACKAGES:
            del sys.modules[name]


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A library folder with fake ``waveshare_epd`` and ``inky`` packages."""
    folder = tmp_path / "lib"
    waveshare = folder / "waveshare_epd"
    waveshare.mkdir(parents=True)
    (waveshare / "__init__.py").write_text("")
    (waveshare / "epdconfig.py").write_text(FAKE_EPDCONFIG)
    (waveshare / "epdfake.py").write_text(FAKE_EPD)
    inky = folder / "inky"
    inky.mkdir()
    (inky / "__init__.py").write_text("")
    (inky / "fake.py").write_text(FAKE_INKY)
    for name in INKY_MODULES:
        (inky / f"{name}.py").write_text("from inky.fake import *  # noqa: F403\n")
    monkeypatch.setattr(sys, "path", list(sys.path))
    _forget_packages()
    yield folder
    _forget_packages()
