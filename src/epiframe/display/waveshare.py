"""Waveshare e-Paper displays (``waveshare_epd`` library from waveshareteam/e-Paper).

The vendor drivers don't share an interface: the same feature has different
method names (``init_fast`` / ``init_Fast``, ``display_Partial`` /
``displayPartial``, ``sleep`` / ``Sleep``, ...). :class:`WaveshareDriver` maps
them to one set of names and tells which :class:`Capability` a panel has.

The partial refresh (status icons) differs even more: how the partial mode is
started, which arguments the display method takes and whether the full refresh
must also fill the "old image" memory of the panel (``display_Base``). Every
supported driver has its recipe in :data:`PARTIAL_DRIVERS`, taken from the
vendor examples. ePiframe always sends the whole frame (the window is the whole
panel): only the changed pixels are refreshed, and the buggy window alignment
of the vendor code is never used. Checked against waveshareteam/e-Paper
``d28b3c4``; only ``epd7in5_V2`` was tested on a real panel.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Any, TypedDict, Unpack

from PIL import Image

from epiframe.core.logs import get_logger
from epiframe.display import colors
from epiframe.display.base import Capability, DisplayError
from epiframe.display.library import load_driver
from epiframe.display.options import ColorMode

PACKAGE = "waveshare_epd"
INIT_FAILED = -1  # what ``init()`` returns when the GPIO/SPI setup fails
# attributes passed to ``init_fast`` when the driver has them (epd4in2_V2:
# ``init_fast(mode)``, the 1.5 s mode is the one of the vendor example)
FAST_INIT_MODES = ("Seconds_1_5S",)
NO_FAST = "The display driver has no fast refresh: the full refresh is used"
NO_FAST_WITH_ICONS = (
    "The fast refresh is not used: the status icons need the standard full"
    " refresh on this display"
)
NO_PARTIAL = "The display has no partial refresh!"

log = get_logger("display")

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
    "display_base": ("display_Base", "displayPartBaseImage"),
    "init_gray4": ("init_4Gray", "Init_4Gray", "init_4GRAY"),
    "display_gray4": ("display_4Gray",),
    "getbuffer_gray4": ("getbuffer_4Gray",),
}

# capability -> methods it needs (the partial refresh: see PARTIAL_DRIVERS)
REQUIREMENTS: Mapping[Capability, tuple[str, ...]] = {
    Capability.FULL: ("init", "display", "getbuffer"),
    Capability.FAST_FULL: ("init_fast", "display", "getbuffer"),
    Capability.GRAY4: ("init_gray4", "display_gray4", "getbuffer_gray4"),
}

# Driver arguments: an int is passed as it is, a str is the name of an attribute
# of the vendor ``EPD`` object (e.g. its LUT table or mode constant).
Argument = int | str

# drivers whose ``init`` needs an argument for the standard full refresh
INIT_ARGUMENTS: Mapping[str, tuple[Argument, ...]] = {
    "epd1in54": ("lut_full_update",),
    "epd1in54_V2": (0,),  # isPartial
    "epd2in13": ("lut_full_update",),
    "epd2in13_V2": ("FULL_UPDATE",),
    "epd2in66": (0,),  # mode
    "epd2in9": ("lut_full_update",),
}


class Style(Enum):
    """How the display method of the partial refresh takes the image."""

    FRAME = "frame"  # display_partial(buffer)
    WINDOW = "window"  # display_partial(buffer, x0, y0, x1, y1)
    OLD_NEW = "old_new"  # display_partial(old buffer, new buffer)


@dataclass(frozen=True)
class PartialRecipe:
    """How a driver refreshes partially (black only, on 3-color panels too)."""

    style: Style
    # the method (our name) that starts the partial mode, and its arguments
    # (``None``: those of the standard ``init``)
    init: str = "init"
    arguments: tuple[Argument, ...] | None = None
    # the standard full refresh must use ``display_base`` (it fills the "old
    # image" memory that the partial refresh compares with)
    base: bool = False


# waveshareteam/e-Paper d28b3c4, from the vendor examples; not here: epd4in2
# (its partial display method indexes a list with a float) and epd7in5b_V2 (no
# way to set the old image without blanking the panel)
PARTIAL_DRIVERS: Mapping[str, PartialRecipe] = {
    "epd1in02": PartialRecipe(Style.OLD_NEW, "init_partial"),
    "epd1in54_V2": PartialRecipe(Style.FRAME, arguments=(1,), base=True),
    "epd2in13_V2": PartialRecipe(Style.FRAME, arguments=("PART_UPDATE",), base=True),
    "epd2in13_V3": PartialRecipe(Style.FRAME, base=True),
    "epd2in13_V4": PartialRecipe(Style.FRAME, base=True),
    "epd2in13d": PartialRecipe(Style.FRAME),
    "epd2in7_V2": PartialRecipe(Style.WINDOW, base=True),
    "epd2in9_V2": PartialRecipe(Style.FRAME, base=True),
    "epd2in9_V3": PartialRecipe(Style.FRAME, base=True),
    "epd2in9b_V4": PartialRecipe(Style.WINDOW, base=True),
    "epd2in9d": PartialRecipe(Style.FRAME),
    "epd4in2_V2": PartialRecipe(Style.FRAME),
    "epd4in26": PartialRecipe(Style.FRAME, base=True),
    "epd5in79": PartialRecipe(Style.FRAME, "init_partial", base=True),
    "epd5in83_V2": PartialRecipe(Style.FRAME, "init_partial"),
    "epd7in5_V2": PartialRecipe(Style.WINDOW, "init_partial"),
    "epd7in5_V2_old": PartialRecipe(Style.WINDOW, "init_partial"),
    "epd13in3b": PartialRecipe(Style.WINDOW, base=True),
    "epd13in3k": PartialRecipe(Style.WINDOW, "init_partial", base=True),
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


def _fast_modes(epd: object) -> tuple[object, ...]:
    return tuple(getattr(epd, mode) for mode in FAST_INIT_MODES if hasattr(epd, mode))


class WaveshareDriver:
    """One vendor ``EPD`` object behind uniform method names (``name``: the
    driver module, e.g. ``epd7in5_V2``)."""

    def __init__(
        self,
        epd: object,
        module_exit: Callable[[], object] | None = None,
        name: str = "",
    ):
        self._epd = epd
        self._methods = _resolve(epd)
        self._module_exit = module_exit
        self.fast_init_arguments = _fast_modes(epd)
        self._init_arguments = INIT_ARGUMENTS.get(name, ())
        self.partial = self._partial_recipe(PARTIAL_DRIVERS.get(name))
        self.capabilities = self._capabilities()

    def _capabilities(self) -> frozenset[Capability]:
        capabilities = {
            capability
            for capability, needed in REQUIREMENTS.items()
            if self._has_all(needed)
        }
        if self.partial is not None and Capability.FULL in capabilities:
            capabilities.add(Capability.PARTIAL)
        return frozenset(capabilities)

    def _has_all(self, names: Iterable[str]) -> bool:
        return all(self.has(name) for name in names)

    @classmethod
    def from_module(cls, module: ModuleType) -> "WaveshareDriver":
        config = getattr(module, "epdconfig", None)
        name = module.__name__.rpartition(".")[2]
        return cls(module.EPD(), getattr(config, "module_exit", None), name)

    def _partial_recipe(self, recipe: PartialRecipe | None) -> PartialRecipe | None:
        # the recipe needs the driver's methods (an older library may lack them)
        if recipe is None:
            return None
        needed = ["display_partial", recipe.init] + (
            ["display_base"] if recipe.base else []
        )
        return recipe if self._has_all(needed) else None

    def has(self, name: str) -> bool:
        """Whether the driver has the method known as ``name``."""
        return name in self._methods

    @property
    def init_arguments(self) -> tuple[object, ...]:
        """The arguments of ``init`` for the standard full refresh."""
        return self.arguments(self._init_arguments)

    def arguments(self, values: tuple[Argument, ...]) -> tuple[object, ...]:
        """``values`` with the attribute names replaced by the attributes."""
        return tuple(self._argument(value) for value in values)

    def _argument(self, value: Argument) -> object:
        if isinstance(value, int):
            return value
        try:
            return getattr(self._epd, value)
        except AttributeError:
            raise DisplayError(
                f"The display driver has no {value} attribute!"
            ) from None

    @property
    def size(self) -> tuple[int, int]:
        """The panel width and height in its own orientation."""
        return getattr(self._epd, "width", 0), getattr(self._epd, "height", 0)

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


class Options(TypedDict, total=False):
    """Keyword arguments of :class:`WaveshareDisplay`."""

    clear: bool
    fast: bool
    icons: bool


def _load_image(path: Path | str) -> Image.Image:
    with Image.open(path) as image:
        image.load()
    return image


class WaveshareDisplay:
    """Shows photos on a Waveshare e-Paper panel with a full refresh (``fast``:
    the fast full refresh, if the panel has it; ``icons``: the status icons are
    used, the partial refresh needs the full refresh to prepare it)."""

    def __init__(
        self,
        driver: WaveshareDriver,
        color: ColorMode,
        clear: bool = False,
        fast: bool = False,
        *,
        icons: bool = False,
    ):
        if Capability.FULL not in driver.capabilities:
            raise DisplayError(
                "The display driver doesn't support a full refresh"
                " (init, display and getbuffer methods)!"
            )
        self._driver = driver
        self._color = color
        self._clear = clear
        recipe = driver.partial
        self._base = icons and recipe is not None and recipe.base
        self._fast = self._use_fast(fast)

    def _use_fast(self, fast: bool) -> bool:
        if not fast:
            return False
        if Capability.FAST_FULL not in self._driver.capabilities:
            log.warning(NO_FAST)
            return False
        if self._base:
            log.warning(NO_FAST_WITH_ICONS)
            return False
        return True

    @classmethod
    def load(
        cls,
        name: str,
        color: ColorMode,
        directory: Path | str | None = None,
        **options: Unpack[Options],
    ) -> "WaveshareDisplay":
        """Load the ``waveshare_epd.<name>`` driver (e.g. ``epd7in5_V2``)."""
        module = load_driver(PACKAGE, name, directory)
        return cls(WaveshareDriver.from_module(module), color, **options)

    @property
    def capabilities(self) -> frozenset[Capability]:
        return self._driver.capabilities

    def show(self, path: Path | str) -> None:
        self._safely(self._refresh, _load_image(path))

    def show_partial(self, path: Path | str, previous: Path | str) -> None:
        """Show the image ``path`` with a partial refresh; ``previous`` is the
        image on the panel now."""
        recipe = self._driver.partial
        if recipe is None:
            raise DisplayError(NO_PARTIAL)
        old = _load_image(previous) if recipe.style is Style.OLD_NEW else None
        self._safely(lambda image: self._partial(recipe, image, old), _load_image(path))

    def _safely(
        self, refresh: Callable[[Image.Image], None], image: Image.Image
    ) -> None:
        try:
            refresh(image)
        except KeyboardInterrupt:
            self._driver.module_exit()
            raise

    def _refresh(self, image: Image.Image) -> None:
        # the panel sleeps between refreshes: every refresh starts with an init
        if self._fast:
            self._init("init_fast", *self._driver.fast_init_arguments)
        else:
            self._init("init", *self._driver.init_arguments)
        if self._clear:
            self._driver.call("clear")
        self._driver.call(self._display_method(), *self._buffers(image))
        self._driver.call("sleep")

    def _partial(
        self, recipe: PartialRecipe, image: Image.Image, old: Image.Image | None
    ) -> None:
        arguments = (
            self._driver.init_arguments
            if recipe.arguments is None
            else self._driver.arguments(recipe.arguments)
        )
        self._init(recipe.init, *arguments)
        # the black plane only: the partial refresh is black and white
        buffer = self._buffers(image)[0]
        if recipe.style is Style.WINDOW:
            self._driver.call("display_partial", buffer, 0, 0, *self._driver.size)
        elif old is not None:  # Style.OLD_NEW
            self._driver.call("display_partial", self._buffers(old)[0], buffer)
        else:
            self._driver.call("display_partial", buffer)
        self._driver.call("sleep")

    def _init(self, name: str, *arguments: object) -> None:
        if self._driver.call(name, *arguments) == INIT_FAILED:
            raise DisplayError("The display initialization failed (GPIO/SPI)!")

    def _display_method(self) -> str:
        # some drivers need their own display method after init_fast, others
        # show with the usual one (the waveform comes from init_fast); the
        # partial refresh needs the "old image" memory filled (display_base)
        if self._base:
            return "display_base"
        if self._fast and self._driver.has("display_fast"):
            return "display_fast"
        return "display"

    def _buffers(self, image: Image.Image) -> list[object]:
        second = SECOND_COLOR.get(self._color)
        planes = [image] if second is None else colors.split_two_color(image, second)
        return [self._driver.call("getbuffer", plane) for plane in planes]
