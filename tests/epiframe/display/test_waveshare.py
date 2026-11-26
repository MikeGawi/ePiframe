import importlib
import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from epiframe.display.base import Capability, DisplayError
from epiframe.display.options import ColorMode
from epiframe.display.waveshare import (
    ALIASES,
    INIT_ARGUMENTS,
    INIT_FAILED,
    NO_FAST,
    NO_FAST_WITH_ICONS,
    NO_PARTIAL,
    PARTIAL_DRIVERS,
    PartialRecipe,
    Style,
    WaveshareDisplay,
    WaveshareDriver,
)
from tests.epiframe.display.helpers import ASSETS


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

    FULL_UPDATE = 0

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
    ("epd", "name", "capabilities"),
    [
        (FakeEpd(), "", {Capability.FULL}),
        (Epd7in5V2(), "epd7in5_V2", set(Capability)),
        # partial refresh only with a recipe for the driver
        (Epd7in5V2(), "", set(Capability) - {Capability.PARTIAL}),
        (Epd2in13V2(), "epd2in13_V2", {Capability.FULL}),  # no displayPartBaseImage
        (Epd1in02(), "epd1in02", {Capability.FULL}),
        (Epd3in7(), "", set()),
    ],
    ids=["basic", "7in5_V2", "unknown name", "2in13_V2", "1in02", "3in7"],
)
def test_capabilities(epd: object, name: str, capabilities: set[Capability]) -> None:
    assert WaveshareDriver(epd, name=name).capabilities == capabilities


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
    display = WaveshareDisplay.load("epdfake", ColorMode.BW, library, clear=True)
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


# ------------------------------------------------------------- fast refresh


class FastEpd(FakeEpd):
    """``init_fast`` + the usual ``display`` (epd7in5_V2)."""

    def init_fast(self) -> int:
        self.calls.append("init_fast")
        return self.init_result


class FastDisplayEpd(FakeEpd):
    """``init_Fast`` + ``display_Fast`` (epd2in9_V3)."""

    def init_Fast(self) -> int:
        self.calls.append("init_Fast")
        return 0

    def display_Fast(self, *buffers: str) -> None:
        self.calls.append(("display_Fast", *buffers))


class FastModeEpd(FastDisplayEpd):
    """``init_fast(mode)`` with the mode attributes (epd4in2_V2)."""

    def __init__(self) -> None:
        super().__init__()
        self.Seconds_1_5S = 0
        self.Seconds_1S = 1

    def init_fast(self, mode: int) -> int:
        self.calls.append(("init_fast", mode))
        return 0


def test_fast_refresh(photo: Path) -> None:
    epd = FastEpd()

    WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW, fast=True).show(photo)

    assert epd.calls == ["init_fast", ("display", "buffer-RGB-(255, 0, 0)"), "sleep"]


def test_fast_refresh_with_own_display_method(photo: Path) -> None:
    epd = FastDisplayEpd()

    WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW, True, fast=True).show(photo)

    assert epd.calls == [
        "init_Fast",
        "Clear",
        ("display_Fast", "buffer-RGB-(255, 0, 0)"),
        "sleep",
    ]


def test_fast_refresh_mode(photo: Path) -> None:
    epd = FastModeEpd()

    WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW, fast=True).show(photo)

    assert epd.calls[0] == ("init_fast", 0)  # Seconds_1_5S


def test_failed_fast_init(photo: Path) -> None:
    epd = FastEpd()
    epd.init_result = INIT_FAILED

    with pytest.raises(DisplayError, match="initialization failed"):
        WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW, fast=True).show(photo)


def test_fast_refresh_not_supported(
    photo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    epd = FakeEpd()
    caplog.set_level(logging.INFO, logger="epiframe")

    WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW, fast=True).show(photo)

    assert epd.calls[0] == "init"
    assert caplog.messages == [NO_FAST]


def test_full_refresh_on_a_fast_panel(photo: Path) -> None:
    epd = FastEpd()

    WaveshareDisplay(WaveshareDriver(epd), ColorMode.BW).show(photo)

    assert epd.calls[0] == "init"


def test_load_fast(library: Path, photo: Path) -> None:
    display = WaveshareDisplay.load(
        "epdfake", ColorMode.BW, directory=library, fast=True
    )

    assert display._fast is False  # the fake driver has no init_fast


def test_load_icons(library: Path) -> None:
    display = WaveshareDisplay.load("epdfake", ColorMode.BW, library, icons=True)

    assert display._base is False  # no partial refresh


# ---------------------------------------------------------- partial refresh


class PartialEpd(FastEpd):
    """Partial refresh of the whole frame (like epd2in9_V3)."""

    width = 2  # in the panel's own orientation
    height = 8
    PART_UPDATE = "part-lut"

    def init_part(self, *arguments: object) -> int:
        self.calls.append(("init_part", *arguments))
        return self.init_result

    def display_Base(self, *buffers: str) -> None:
        self.calls.append(("display_Base", *buffers))

    def display_Partial(self, *arguments: object) -> None:
        self.calls.append(("display_Partial", *arguments))


@pytest.fixture
def partial_driver(monkeypatch: pytest.MonkeyPatch) -> Callable[..., WaveshareDriver]:
    """A ``PartialEpd`` driver with the given recipe."""

    def make(recipe: PartialRecipe, epd: PartialEpd | None = None) -> WaveshareDriver:
        monkeypatch.setitem(PARTIAL_DRIVERS, "epdtest", recipe)
        return WaveshareDriver(epd or PartialEpd(), name="epdtest")

    return make


@pytest.fixture
def frames(tmp_path: Path) -> tuple[Path, Path]:
    """The new and the previous image."""
    new, old = tmp_path / "new.png", tmp_path / "old.png"
    Image.new("RGB", (8, 2), "black").save(new)
    Image.new("RGB", (8, 2), "white").save(old)
    return new, old


def test_partial_whole_frame(
    partial_driver: Callable[..., WaveshareDriver], frames: tuple[Path, Path]
) -> None:
    driver = partial_driver(PartialRecipe(Style.FRAME, "init_partial"))
    epd = driver._epd
    assert isinstance(epd, PartialEpd)

    WaveshareDisplay(driver, ColorMode.BW).show_partial(*frames)

    assert epd.calls == [
        ("init_part",),
        ("display_Partial", "buffer-RGB-(0, 0, 0)"),
        "sleep",
    ]


def test_partial_window_is_the_whole_panel(
    partial_driver: Callable[..., WaveshareDriver], frames: tuple[Path, Path]
) -> None:
    epd = PartialEpd()
    driver = partial_driver(PartialRecipe(Style.WINDOW), epd)

    WaveshareDisplay(driver, ColorMode.BW).show_partial(*frames)

    assert epd.calls == [
        "init",
        ("display_Partial", "buffer-RGB-(0, 0, 0)", 0, 0, 2, 8),
        "sleep",
    ]


def test_partial_old_and_new(
    partial_driver: Callable[..., WaveshareDriver], frames: tuple[Path, Path]
) -> None:
    epd = PartialEpd()
    driver = partial_driver(
        PartialRecipe(Style.OLD_NEW, "init_partial", ("PART_UPDATE", 1)), epd
    )

    WaveshareDisplay(driver, ColorMode.BW).show_partial(*frames)

    assert epd.calls == [
        ("init_part", "part-lut", 1),  # attribute names become the attributes
        ("display_Partial", "buffer-RGB-(255, 255, 255)", "buffer-RGB-(0, 0, 0)"),
        "sleep",
    ]


def test_partial_on_three_colors_sends_black_only(
    partial_driver: Callable[..., WaveshareDriver], frames: tuple[Path, Path]
) -> None:
    epd = PartialEpd()
    driver = partial_driver(PartialRecipe(Style.FRAME), epd)

    WaveshareDisplay(driver, ColorMode.BWR).show_partial(*frames)

    assert len(epd.calls[1]) == 2  # display_Partial(black buffer)


def test_partial_init_failed(
    partial_driver: Callable[..., WaveshareDriver], frames: tuple[Path, Path]
) -> None:
    epd = PartialEpd()
    epd.init_result = INIT_FAILED

    with pytest.raises(DisplayError, match="initialization failed"):
        WaveshareDisplay(
            partial_driver(PartialRecipe(Style.FRAME), epd), ColorMode.BW
        ).show_partial(*frames)
    assert epd.calls == ["init"]


def test_partial_interrupted_releases_gpio(
    partial_driver: Callable[..., WaveshareDriver], frames: tuple[Path, Path]
) -> None:
    released: list[bool] = []

    class Interrupted(PartialEpd):
        def display_Partial(self, *arguments: object) -> None:
            raise KeyboardInterrupt

    driver = partial_driver(PartialRecipe(Style.FRAME), Interrupted())
    driver._module_exit = lambda: released.append(True)

    with pytest.raises(KeyboardInterrupt):
        WaveshareDisplay(driver, ColorMode.BW).show_partial(*frames)
    assert released == [True]


def test_no_partial_refresh(frames: tuple[Path, Path]) -> None:
    with pytest.raises(DisplayError, match=re.escape(NO_PARTIAL)):
        WaveshareDisplay(WaveshareDriver(FakeEpd()), ColorMode.BW).show_partial(*frames)


def test_recipe_without_its_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    # e.g. an older library: the partial refresh is not offered
    monkeypatch.setitem(
        PARTIAL_DRIVERS,
        "epdtest",
        PartialRecipe(Style.FRAME, "init_partial", base=True),
    )

    assert WaveshareDriver(Epd2in13V2(), name="epdtest").partial is None


def test_icons_use_the_base_refresh(
    partial_driver: Callable[..., WaveshareDriver], photo: Path
) -> None:
    epd = PartialEpd()
    driver = partial_driver(PartialRecipe(Style.FRAME, base=True), epd)

    WaveshareDisplay(driver, ColorMode.BW, icons=True).show(photo)

    assert epd.calls == ["init", ("display_Base", "buffer-RGB-(255, 0, 0)"), "sleep"]


def test_no_base_refresh_without_icons(
    partial_driver: Callable[..., WaveshareDriver], photo: Path
) -> None:
    epd = PartialEpd()
    driver = partial_driver(PartialRecipe(Style.FRAME, base=True), epd)

    WaveshareDisplay(driver, ColorMode.BW).show(photo)

    assert epd.calls[1][0] == "display"


def test_icons_need_the_standard_refresh(
    partial_driver: Callable[..., WaveshareDriver],
    photo: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    epd = PartialEpd()
    driver = partial_driver(PartialRecipe(Style.FRAME, base=True), epd)

    WaveshareDisplay(driver, ColorMode.BW, fast=True, icons=True).show(photo)

    assert epd.calls[0] == "init"
    assert caplog.messages == [NO_FAST_WITH_ICONS]


def test_icons_dont_stop_the_fast_refresh_without_base(
    partial_driver: Callable[..., WaveshareDriver], photo: Path
) -> None:
    epd = PartialEpd()
    driver = partial_driver(PartialRecipe(Style.WINDOW), epd)

    WaveshareDisplay(driver, ColorMode.BW, fast=True, icons=True).show(photo)

    assert epd.calls[0] == "init_fast"


def test_init_arguments_for_the_full_refresh(
    monkeypatch: pytest.MonkeyPatch, photo: Path
) -> None:
    class LutEpd(FakeEpd):
        lut_full_update = "full-lut"

        def init(self, *arguments: object) -> int:
            self.calls.append(("init", *arguments))
            return 0

    monkeypatch.setitem(INIT_ARGUMENTS, "epdtest", ("lut_full_update", 0))
    epd = LutEpd()

    WaveshareDisplay(WaveshareDriver(epd, name="epdtest"), ColorMode.BW).show(photo)

    assert epd.calls[0] == ("init", "full-lut", 0)


def test_missing_argument_attribute(
    monkeypatch: pytest.MonkeyPatch, photo: Path
) -> None:
    monkeypatch.setitem(INIT_ARGUMENTS, "epdtest", ("lut_full_update",))
    display = WaveshareDisplay(WaveshareDriver(FakeEpd(), name="epdtest"), ColorMode.BW)

    with pytest.raises(DisplayError, match="no lut_full_update attribute"):
        display.show(photo)


def test_driver_name_from_module(library: Path) -> None:
    display = WaveshareDisplay.load("epdfake", ColorMode.BW, library)

    assert display._driver.size == (0, 0)  # the fake has no width/height


# ------------------------------------------- recorded real drivers (d28b3c4)

RECORDED: dict[str, Any] = json.loads((ASSETS / "waveshare_drivers.json").read_text())[
    "drivers"
]


class RecordedEpd:
    """An ``EPD`` with the methods (signatures) and attributes of a real driver."""

    width = 8
    height = 2

    def __init__(self, name: str) -> None:
        self.calls: list[tuple[object, ...]] = []
        record = RECORDED[name]
        for attribute in record["attributes"]:
            if attribute not in ("width", "height"):
                setattr(self, attribute, f"<{attribute}>")
        for method, signature in record["methods"].items():
            setattr(self, method, self._method(method, signature))

    def _method(self, name: str, signature: dict[str, Any]) -> Callable[..., object]:
        def method(*arguments: object) -> object:
            count = len(arguments)
            if not signature["required"] <= count <= len(signature["parameters"]):
                raise TypeError(f"{name}{tuple(signature['parameters'])} got {count}")
            self.calls.append((name, *arguments))
            return "buffer" if name.startswith("getbuffer") else 0

        return method


def recorded_display(
    name: str, **options: bool
) -> tuple[WaveshareDisplay, RecordedEpd]:
    epd = RecordedEpd(name)
    # 3-color panels take two planes (black, color)
    planes = RECORDED[name]["methods"]["display"]["required"]
    color = ColorMode.BWR if planes == 2 else ColorMode.BW
    return WaveshareDisplay(WaveshareDriver(epd, name=name), color, **options), epd


def test_recipes_and_init_arguments_name_real_drivers() -> None:
    for name in [*PARTIAL_DRIVERS, *INIT_ARGUMENTS]:
        assert name in RECORDED
    for name, arguments in INIT_ARGUMENTS.items():
        for argument in arguments:
            assert isinstance(argument, int) or argument in RECORDED[name]["attributes"]


def test_drivers_with_partial_refresh_have_a_recipe() -> None:
    partial_names = set(ALIASES["display_partial"])
    with_method = {
        name
        for name, record in RECORDED.items()
        if partial_names & set(record["methods"])
    }

    # left out on purpose (see PARTIAL_DRIVERS)
    assert with_method - set(PARTIAL_DRIVERS) == {"epd4in2", "epd7in5b_V2"}


@pytest.mark.parametrize(
    "name",
    sorted(
        name
        for name in RECORDED
        if Capability.FULL in WaveshareDriver(RecordedEpd(name), name=name).capabilities
    ),
)
def test_full_refresh_of_real_drivers(name: str, photo: Path) -> None:
    display, epd = recorded_display(name)

    display.show(photo)  # every call fits the real signature

    assert epd.calls[-1] == ("sleep",) or epd.calls[-1] == ("Sleep",)


@pytest.mark.parametrize("name", sorted(PARTIAL_DRIVERS))
def test_partial_refresh_of_real_drivers(
    name: str, photo: Path, frames: tuple[Path, Path]
) -> None:
    display, epd = recorded_display(name, icons=True)

    assert Capability.PARTIAL in display.capabilities
    display.show(photo)
    display.show_partial(*frames)

    methods = [call[0] for call in epd.calls]
    recipe = PARTIAL_DRIVERS[name]
    base = {"display_Base", "displayPartBaseImage"} & set(methods)
    assert bool(base) == recipe.base
    assert set(methods) & set(ALIASES["display_partial"])
