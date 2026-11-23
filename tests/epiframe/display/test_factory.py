from pathlib import Path

import pytest

from epiframe.config import paths
from epiframe.display.factory import create_display
from epiframe.display.hdmi import HdmiDisplay
from epiframe.display.pimoroni import PimoroniDisplay
from epiframe.display.waveshare import WaveshareDisplay

DEFAULTS = {
    "display_type": "SPI",
    "epaper_type": "Waveshare",
    "epaper_color": "BW",
    "display": "epdfake",
    "clear_display": "1",
    "tty": "3",
    "fbi_bin_path": "/usr/bin/fbi",
    "background_color": "black",
    "pimoroni_saturation": "0.5",
}


class Config:
    def __init__(self, **values: str) -> None:
        self.values = DEFAULTS | values

    def get(self, name: str) -> str:
        return self.values[name]

    def getint(self, name: str) -> int:
        return int(self.values[name])


@pytest.fixture(autouse=True)
def library_dir(library: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "LIBRARY_DIR", str(library))


@pytest.mark.parametrize("display_type", ["HDMI", "hdmi"])
def test_hdmi(display_type: str) -> None:
    display = create_display(Config(display_type=display_type))

    assert isinstance(display, HdmiDisplay)
    assert display._viewer == "/usr/bin/fbi"
    assert display._tty == 3


def test_waveshare() -> None:
    display = create_display(Config(epaper_color="BW+Red"))

    assert isinstance(display, WaveshareDisplay)
    assert display._color == "BW+Red"
    assert display._clear is True


@pytest.mark.parametrize("epaper_type", ["Pimoroni", "pimoroni"])
def test_pimoroni(epaper_type: str) -> None:
    display = create_display(
        Config(epaper_type=epaper_type, display="inky_uc8159", clear_display="0")
    )

    assert isinstance(display, PimoroniDisplay)
    assert display._saturation == 0.5
    assert display._border_black is True
    assert display._clear is False
