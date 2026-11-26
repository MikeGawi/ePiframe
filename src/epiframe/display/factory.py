"""Creates the display chosen in the configuration."""

from epiframe.config.property import ValueSource
from epiframe.display.base import Display
from epiframe.display.hdmi import HdmiDisplay
from epiframe.display.options import ColorMode, DisplayType, EpaperType
from epiframe.display.pimoroni import PimoroniDisplay
from epiframe.display.waveshare import WaveshareDisplay


def create_display(config: ValueSource, fast: bool = False) -> Display:
    """Return the display of ``display_type`` / ``epaper_type`` (driver loaded);
    ``fast``: use the fast full refresh (if the display has it)."""
    if DisplayType.is_hdmi(config.get("display_type")):
        return HdmiDisplay(config.get("fbi_bin_path"), config.getint("tty"))
    name = config.get("display")
    color = ColorMode(config.get("epaper_color"))
    clear = bool(config.getint("clear_display"))
    if config.get("epaper_type").lower() == EpaperType.PIMORONI.lower():
        return PimoroniDisplay.load(
            name,
            color,
            background=config.get("background_color"),
            clear=clear,
            saturation=float(config.get("pimoroni_saturation")),
        )
    return WaveshareDisplay.load(name, color, clear, fast=fast)
