import importlib
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from epiframe.display.base import Capability, DisplayError
from epiframe.display.options import ColorMode
from epiframe.display.waveshare import (
    INIT_FAILED,
    WaveshareDisplay,
    WaveshareDriver,
)


class FakeEpd:
    """The common subset of the vendor drivers (e.g. epd7in5)."""

    def __init__(self) -> None:
        self.calls: list[Any] = []
        self.init_result = 0

    def init(self) -> int:
        self.calls.append("init")
        return self.init_result

    def getbuffer(self, image: Image.Image) -> str:
        return f"buffer-{image.mode}-{image.getpixel((0, 0))}"

    def display(self, *buffers: str) -> None:
        self.calls.append(("display", *buffers))

    def Clear(self) -> None:
        self.calls.append("Clear")

    def sleep(self) -> None:
        self.calls.append("sleep")


class Epd7in5V2(FakeEpd):
    """Method names of epd7in5_V2 (fast, partial and 4-gray)."""

    def init_fast(self) -> None: ...
    def init_part(self) -> None: ...
    def display_Partial(self) -> None: ...
    def init_4Gray(self) -> None: ...
    def display_4Gray(self) -> None: ...
    def getbuffer_4Gray(self) -> None: ...


class Epd2in13V2(FakeEpd):
    """Partial refresh through ``init(mode)`` + ``displayPartial``."""

    def displayPartial(self) -> None: ...


class Epd1in02:
    """Capitalized names (Init, Sleep) and no getbuffer-free display."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def Init(self) -> None:
        self.calls.append("Init")

    def getbuffer(self, image: Image.Image) -> str:
        return "buffer"

    def display(self, buffer: str) -> None:
        self.calls.append("display")

    def Sleep(self) -> None:
        self.calls.append("Sleep")


class Epd3in7:
    """No ``display`` method (only 1-gray and 4-gray variants)."""

    def init(self) -> None: ...
    def getbuffer(self) -> None: ...
    def sleep(self) -> None: ...


def epdconfig() -> Any:
    """The fake ``waveshare_epd.epdconfig`` (records the driver calls)."""
    return importlib.import_module("waveshare_epd.epdconfig")


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    path = tmp_path / "photo.bmp"
    image = Image.new("RGB", (8, 2), "white")
    image.putpixel((0, 0), (255, 0, 0))
    image.save(path)
    return path


@pytest.mark.parametrize(
    ("epd", "capabilities"),
    [
        (FakeEpd(), {Capability.FULL}),
        (Epd7in5V2(), set(Capability)),
        (Epd2in13V2(), {Capability.FULL, Capability.PARTIAL}),
        (Epd1in02(), {Capability.FULL}),
        (Epd3in7(), set()),
    ],
    ids=["basic", "7in5_V2", "2in13_V2", "1in02", "3in7"],
)
def test_capabilities(epd: object, capabilities: set[Capability]) -> None:
    assert WaveshareDriver(epd).capabilities == capabilities


def test_attribute_that_is_not_a_method_is_ignored() -> None:
    epd = FakeEpd()
    epd.init_fast = None  # type: ignore[attr-defined]

    assert Capability.FAST_FULL not in WaveshareDriver(epd).capabilities


def test_call_missing_method() -> None:
    with pytest.raises(DisplayError, match="no clear method"):
        WaveshareDriver(Epd1in02()).call("clear")


def test_show_black_and_white(photo: Path) -> None:
    epd = FakeEpd()

    display = WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW)
    display.show(photo)

    assert display.capabilities == {Capability.FULL}
    assert epd.calls == ["init", ("display", "buffer-RGB-(255, 0, 0)"), "sleep"]


@pytest.mark.parametrize(
    "color", [ColorMode.BW, ColorMode.C4, ColorMode.C7, ColorMode.OTHER]
)
def test_show_without_color_split(photo: Path, color: ColorMode) -> None:
    epd = FakeEpd()

    WaveshareDisplay(WaveshareDriver(epd), color).show(photo)

    assert epd.calls[1] == ("display", "buffer-RGB-(255, 0, 0)")


@pytest.mark.parametrize(
    ("color", "pixel"),
    [(ColorMode.BWR, (255, 0, 0)), (ColorMode.BWY, (255, 255, 0))],
)
def test_show_three_colors(
    tmp_path: Path, color: ColorMode, pixel: tuple[int, int, int]
) -> None:
    path = tmp_path / "photo.png"
    Image.new("RGB", (8, 2), pixel).save(path)
    epd = FakeEpd()

    WaveshareDisplay(WaveshareDriver(epd), color).show(path)

    # black plane, then color plane: the pixel is ink (0) in the color plane only
    assert epd.calls[1] == ("display", "buffer-1-255", "buffer-1-0")


def test_show_clears_first(photo: Path) -> None:
    epd = FakeEpd()

    WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW, clear=True).show(photo)

    assert epd.calls[:2] == ["init", "Clear"]
    assert epd.calls[-1] == "sleep"


def test_capitalized_driver_methods(photo: Path) -> None:
    epd = Epd1in02()

    WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW).show(photo)

    assert epd.calls == ["Init", "display", "Sleep"]


def test_failed_init(photo: Path) -> None:
    epd = FakeEpd()
    epd.init_result = INIT_FAILED

    with pytest.raises(DisplayError, match="initialization failed"):
        WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW).show(photo)
    assert epd.calls == ["init"]


def test_driver_without_full_refresh() -> None:
    with pytest.raises(DisplayError, match="full refresh"):
        WaveshareDisplay(WaveshareDriver(Epd3in7()), ColorMode.BW)


def test_interrupt_releases_gpio(photo: Path) -> None:
    exits: list[bool] = []

    class Interrupted(FakeEpd):
        def display(self, *buffers: str) -> None:
            raise KeyboardInterrupt

    driver = WaveshareDriver(Interrupted(), lambda: exits.append(True))
    with pytest.raises(KeyboardInterrupt):
        WaveshareDisplay(driver, ColorMode.BW).show(photo)
    assert exits == [True]


def test_interrupt_without_module_exit(photo: Path) -> None:
    class Interrupted(FakeEpd):
        def init(self) -> int:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        WaveshareDisplay(WaveshareDriver(Interrupted()), ColorMode.BW).show(photo)


def test_missing_photo(tmp_path: Path) -> None:
    epd = FakeEpd()

    with pytest.raises(FileNotFoundError):
        WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW).show(tmp_path / "x.bmp")
    assert epd.calls == []


def test_load_from_library(library: Path, photo: Path) -> None:
    display = WaveshareDisplay.load("epdfake", ColorMode.BW, True, library)
    display.show(photo)

    assert epdconfig().CALLS == ["init", "Clear", ("display", "RGB"), "sleep"]


def test_load_interrupted_uses_epdconfig(library: Path, photo: Path) -> None:
    display = WaveshareDisplay.load("epdfake", ColorMode.BW, directory=library)

    def interrupt() -> None:
        raise KeyboardInterrupt

    display._driver._methods["sleep"] = interrupt
    with pytest.raises(KeyboardInterrupt):
        display.show(photo)
    assert epdconfig().CALLS[-1] == "module_exit"


def test_load_unknown_driver(library: Path) -> None:
    with pytest.raises(DisplayError, match="epd_unknown"):
        WaveshareDisplay.load("epd_unknown", ColorMode.BW, directory=library)
