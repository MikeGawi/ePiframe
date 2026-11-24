"""Waveshare e-Paper displays (``waveshare_epd`` library from waveshareteam/e-Paper).

The vendor drivers don't share an interface: the same feature has different
method names (``init_fast`` / ``init_Fast``, ``display_Partial`` /
``displayPartial``, ``sleep`` / ``Sleep``, ...). :class:`WaveshareDriver` maps
them to one set of names and tells which :class:`Capability` a panel has.
"""

from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

from PIL import Image

from epiframe.display import colors
from epiframe.display.base import Capability, DisplayError
from epiframe.display.library import load_driver
from epiframe.display.options import ColorMode

PACKAGE = "waveshare_epd"
INIT_FAILED = -1  # what ``init()`` returns when the GPIO/SPI setup fails

# our name -> driver method names, in order of preference
ALIASES: Mapping[str, tuple[str, ...]] = {
    "init": ("init", "Init"),
    "display": ("display",),
    "clear": ("Clear", "clear"),
    "sleep": ("sleep", "Sleep"),
    "getbuffer": ("getbuffer",),
    "init_fast": ("init_fast", "init_Fast"),
    "display_fast": ("display_fast", "display_Fast"),
    "init_partial": ("init_part", "init_Part", "init_Partial", "Partial_Init"),
    "display_partial": (
        "display_Partial",
        "displayPartial",
        "DisplayPartial",
        "displayPart",
        "EPD_4IN2_PartialDisplay",
    ),
    "init_gray4": ("init_4Gray", "Init_4Gray", "init_4GRAY"),
    "display_gray4": ("display_4Gray",),
    "getbuffer_gray4": ("getbuffer_4Gray",),
}

# capability -> methods it needs (the partial refresh windows differ per driver,
# the partial init is often a parameter of ``init``, so only the display method counts)
REQUIREMENTS: Mapping[Capability, tuple[str, ...]] = {
    Capability.FULL: ("init", "display", "getbuffer"),
    Capability.FAST_FULL: ("init_fast", "display", "getbuffer"),
    Capability.PARTIAL: ("display_partial",),
    Capability.GRAY4: ("init_gray4", "display_gray4", "getbuffer_gray4"),
}

# 3-color panels: the photo is split into a black and a color plane
SECOND_COLOR: Mapping[ColorMode, colors.Color] = {
    ColorMode.BWR: colors.RED,
    ColorMode.BWY: colors.YELLOW,
}


def _resolve(epd: object) -> dict[str, Callable[..., Any]]:
    methods = {}
    for name, candidates in ALIASES.items():
        found = next((getattr(epd, c) for c in candidates if hasattr(epd, c)), None)
        if callable(found):
            methods[name] = found
    return methods


class WaveshareDriver:
    """One vendor ``EPD`` object behind uniform method names."""

    def __init__(self, epd: object, module_exit: Callable[[], object] | None = None):
        self._methods = _resolve(epd)
        self._module_exit = module_exit
        self.capabilities = frozenset(
            capability
            for capability, needed in REQUIREMENTS.items()
            if all(name in self._methods for name in needed)
        )

    @classmethod
    def from_module(cls, module: ModuleType) -> "WaveshareDriver":
        config = getattr(module, "epdconfig", None)
        return cls(module.EPD(), getattr(config, "module_exit", None))

    def call(self, name: str, *arguments: object) -> Any:
        """Call the driver method known as ``name`` (see :data:`ALIASES`)."""
        try:
            method = self._methods[name]
        except KeyError:
            raise DisplayError(f"The display driver has no {name} method!") from None
        return method(*arguments)

    def module_exit(self) -> None:
        """Release the GPIO/SPI resources (after an interrupted refresh)."""
        if self._module_exit is not None:
            self._module_exit()


class WaveshareDisplay:
    """Shows photos on a Waveshare e-Paper panel with a full refresh."""

    def __init__(self, driver: WaveshareDriver, color: ColorMode, clear: bool = False):
        if Capability.FULL not in driver.capabilities:
            raise DisplayError(
                "The display driver doesn't support a full refresh"
                " (init, display and getbuffer methods)!"
            )
        self._driver = driver
        self._color = color
        self._clear = clear

    @classmethod
    def load(
        cls,
        name: str,
        color: ColorMode,
        clear: bool = False,
        directory: Path | str | None = None,
    ) -> "WaveshareDisplay":
        """Load the ``waveshare_epd.<name>`` driver (e.g. ``epd7in5_V2``)."""
        module = load_driver(PACKAGE, name, directory)
        return cls(WaveshareDriver.from_module(module), color, clear)

    @property
    def capabilities(self) -> frozenset[Capability]:
        return self._driver.capabilities

    def show(self, path: Path | str) -> None:
        with Image.open(path) as image:
            image.load()
        try:
            self._refresh(image)
        except KeyboardInterrupt:
            self._driver.module_exit()
            raise

    def _refresh(self, image: Image.Image) -> None:
        # the panel sleeps between refreshes: every refresh starts with an init
        if self._driver.call("init") == INIT_FAILED:
            raise DisplayError("The display initialization failed (GPIO/SPI)!")
        if self._clear:
            self._driver.call("clear")
        self._driver.call("display", *self._buffers(image))
        self._driver.call("sleep")

    def _buffers(self, image: Image.Image) -> list[object]:
        second = SECOND_COLOR.get(self._color)
        planes = [image] if second is None else colors.split_two_color(image, second)
        return [self._driver.call("getbuffer", plane) for plane in planes]
