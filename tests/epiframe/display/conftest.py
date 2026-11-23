"""Fake vendor display libraries written to ``tmp_path``."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

PACKAGES = ("waveshare_epd", "inky")


FAKE_INKY = """
BLACK = 0
WHITE = 1
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

# like the real library (pimoroni/inky main, 2026-10): inky.phat / inky.what have
# no module-level color constants, only the display classes have them
INKY_MODULES = {
    "phat": "from inky.fake import CALLS, InkyPHAT  # noqa: F401\n",
    "what": "from inky.fake import CALLS, InkyWHAT  # noqa: F401\n",
    "inky_ssd1608": "from inky.fake import *  # noqa: F403\n",
    "inky_ssd1683": "from inky.fake import *  # noqa: F403\n",
}

# multicolor panels: only the default colour is accepted, set_image quantizes
# itself with the saturation
FAKE_MULTICOLOR = """from inky.fake import CALLS, InkyBase


class Inky(InkyBase):
    DESATURATED_PALETTE = [
        [0, 0, 0], [255, 255, 255], [0, 255, 0], [0, 0, 255],
        [255, 0, 0], [255, 255, 0], [255, 140, 0], [255, 255, 255],
    ]
    SATURATED_PALETTE = [
        [57, 48, 57], [255, 255, 255], [58, 91, 70], [61, 59, 94],
        [156, 72, 75], [208, 190, 71], [177, 106, 73], [255, 255, 255],
    ]

    def __init__(self, colour="{default}"):
        if colour != "{default}":
            raise ValueError(f"Colour {{colour}} is not supported!")
        super().__init__()

    def set_image(self, image, saturation=0.5):
        CALLS.append(("set_image", image.mode, saturation))
"""
MULTICOLOR_DEFAULTS = {
    "inky_uc8159": "multi",
    "inky_ac073tc1a": "multi",
    "inky_e640": "multi",
    "inky_e673": "multi",
    "inky_el133uf1": "multi",
    "inky_jd79661": "red/yellow",
    "inky_jd79668": "red/yellow",
    "inky_ssd2683": "red/yellow",
}

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
    for name, source in INKY_MODULES.items():
        (inky / f"{name}.py").write_text(source)
    for name, default in MULTICOLOR_DEFAULTS.items():
        (inky / f"{name}.py").write_text(FAKE_MULTICOLOR.format(default=default))
    monkeypatch.setattr(sys, "path", list(sys.path))
    _forget_packages()
    yield folder
    _forget_packages()
