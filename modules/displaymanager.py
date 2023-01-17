from __future__ import annotations

import os
from typing import TYPE_CHECKING

from misc.constants import Constants
from modules.base.displaybase import DisplayBase
from misc.pimoronidisplay import PimoroniDisplay
from misc.wavesharedisplay import WaveshareDisplay

if TYPE_CHECKING:
    from modules.configmanager import ConfigManager


class DisplayManager:
    __DISPLAY_HDMI = "HDMI"
    __DISPLAY_SPI = "SPI"
    __DISPLAY_VALUES = [__DISPLAY_SPI, __DISPLAY_HDMI]

    __ERROR_VALUE_TEXT = "Configuration display_type should be one of {}"
    __ERROR_VALUE_TEXT_EPAPER = "Configuration epaper_type should be one of {}"
    __ERROR_VALUE_TEXT_COLOR = "Configuration Display_color should be one of {}"

    __DISPLAY_POWER = "display_power"
    __DISPLAY_POWER_CODE = "sudo vcgencmd " + __DISPLAY_POWER + " {} 2> /dev/null"
    __DISPLAY_POWER_OFF = "0"
    __DISPLAY_POWER_ON = "1"

    __PIMORONI_EPAPER = "Pimoroni"
    __WAVESHARE_EPAPER = "Waveshare"
    __EPAPER_TYPES = [__WAVESHARE_EPAPER, __PIMORONI_EPAPER]

    def __init__(self, config: ConfigManager):
        self.__use_hdmi = self.is_hdmi(config.get("display_type"))
        self.__config = config

        if self.__use_hdmi:
            self.__display = DisplayBase(config)
        elif config.get("display_type").lower() == self.__PIMORONI_EPAPER.lower():
            self.__display = PimoroniDisplay(config)
        else:
            self.__display = WaveshareDisplay(config)

    def show_image(self, photo_path: str):
        self.__display.show_image(photo_path)

    def get_display(self) -> str:
        return self.__display.get_display()

    def get_vt(self) -> int:
        return self.__display.get_vt()

    def is_display_hdmi(self) -> bool:
        return self.__use_hdmi

    @classmethod
    def verify_display(cls, value: str):
        if value not in [key.lower() for key in cls.__DISPLAY_VALUES]:
            raise Exception(cls.__ERROR_VALUE_TEXT.format(cls.__DISPLAY_VALUES))

    @classmethod
    def verify_epaper(cls, value: str):
        if value not in [key.lower() for key in cls.__EPAPER_TYPES]:
            raise Exception(cls.__ERROR_VALUE_TEXT_EPAPER.format(cls.__EPAPER_TYPES))

    @classmethod
    def verify_color(cls, value: str):
        if value not in [key.lower() for key in Constants.COLOR_VALUES]:
            raise Exception(cls.__ERROR_VALUE_TEXT_COLOR.format(Constants.COLOR_VALUES))

    @classmethod
    def get_displays(cls) -> list:
        return cls.__DISPLAY_VALUES

    @classmethod
    def get_epapers(cls) -> list:
        return cls.__EPAPER_TYPES

    @classmethod
    def get_pimoroni(cls) -> str:
        return cls.__PIMORONI_EPAPER

    @classmethod
    def get_colors(cls) -> list:
        return Constants.COLOR_VALUES

    @classmethod
    def get_hdmi(cls) -> str:
        return cls.__DISPLAY_HDMI

    @classmethod
    def get_spi(cls) -> str:
        return cls.__DISPLAY_SPI

    @classmethod
    def is_hdmi(cls, value: str) -> bool:
        return True if value and value.lower() == cls.__DISPLAY_HDMI.lower() else False

    @classmethod
    def control_display_power(cls, on_off: bool):
        os.popen(
            cls.__DISPLAY_POWER_CODE.format(
                cls.__DISPLAY_POWER_ON if on_off else cls.__DISPLAY_POWER_OFF
            )
        )

    @classmethod
    def get_display_power(cls) -> str:
        return (
            os.popen(cls.__DISPLAY_POWER_CODE.format(""))
            .read()
            .strip()
            .replace(cls.__DISPLAY_POWER, "")
            .replace("=", "")
            or cls.__DISPLAY_POWER_OFF
        )

    @classmethod
    def should_convert(cls, colors_schema: str) -> bool:
        return colors_schema.lower() == Constants.COLOR_BW.lower()
