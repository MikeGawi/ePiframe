from __future__ import annotations

import sys
import os
import importlib
import itertools
from types import ModuleType

from PIL import Image
from typing import TYPE_CHECKING

from misc.constants import Constants
from modules.base.displaybase import DisplayBase

if TYPE_CHECKING:
    from modules.configmanager import ConfigManager


library_directory = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"
)

if os.path.exists(library_directory):
    sys.path.append(library_directory)


class PimoroniDisplay(DisplayBase):
    COLOR_MAP = {
        Constants.COLOR_BW: "black",
        Constants.COLOR_BWR: "red",
        Constants.COLOR_BWY: "yellow",
    }

    def __init__(self, config: ConfigManager):
        super().__init__(config)
        color = self._config.get("epaper_color")
        color_schema = self.COLOR_MAP[color] if color in self.COLOR_MAP else ""
        module = importlib.import_module("inky." + self._display)

        displays_dict = {
            "phat": self.__init_inky_phat,
            "what": self.__init_inky_what,
            "inky_ssd1608": self.__init_inky_ssd,
            "inky_uc8159": self.__init_inky_uc,
            "inky_ssd1683": self.__init_inky_ssd,
            "inky_ac073tc1a": self.__init_inky_ssd,
        }

        display_method = displays_dict.get(self._display, None)

        if not display_method:
            raise Exception(f"No Pimoroni display package {self._display} in lib.inky!")

        display_method.__call__(color_schema, module)

    def __init_inky_phat(self, color_schema: str, module: ModuleType):
        self.__inky = (
            module.InkyPHAT(colour=color_schema) if color_schema else module.InkyPHAT()
        )
        self.__palette_filter = self.__get_palette(module)

    def __init_inky_what(self, color_schema: str, module: ModuleType):
        self.__inky = (
            module.InkyWHAT(colour=color_schema) if color_schema else module.InkyWHAT()
        )
        self.__palette_filter = self.__get_palette(module)

    def __init_inky_uc(self, color_schema: str, module: ModuleType):
        self.__inky = module.Inky()
        self.__palette_filter = module.DESATURATED_PALETTE

    def __init_inky_ssd(self, color_schema: str, module: ModuleType):
        self.__inky = (
            module.Inky(colour=color_schema) if color_schema else module.Inky()
        )
        self.__palette_filter = self.__get_palette(module)

    def clear(self):
        self.__inky.set_border(
            self.__inky.BLACK
            if self._config.get("background_color").lower().strip()
            == Constants.BACK_BLACK
            else self.__inky.WHITE
        )

    def __power_off(self):
        pass

    def show_image(self, photo_path: str):
        if bool(self._config.getint("clear_display")):
            self.clear()
        image = Image.open(photo_path)
        self.__inky.set_image(
            self.__convert(image),
            saturation=float(self._config.get("pimoroni_saturation")),
        ) if self._display == "inky_uc8159" else self.__inky.set_image(
            self.__convert(image)
        )
        self.__inky.show()

    def __get_palette(self, module: ModuleType) -> list:
        color = self._config.get("epaper_color")
        palette = self.__get_first_color(module)
        palette.append([0, 0, 0]) if module.BLACK == 1 else palette.append(
            [255, 255, 255]
        )

        if color == Constants.COLOR_BWR:
            palette.append([255, 0, 0])
        elif color == Constants.COLOR_BWY:
            palette.append([255, 255, 0])
        elif color == "7 colors":
            palette = self.__inky.SATURATED_PALETTE

        return palette

    @staticmethod
    def __get_first_color(module):
        return [[255, 255, 255]] if module.WHITE == 0 else [[0, 0, 0]]

    def __convert(self, image: Image) -> Image:
        palette = tuple(itertools.chain(*self.__palette_filter)) + (0, 0, 0) * (
            256 - len(self.__palette_filter)
        )
        pal_image = Image.new("P", (1, 1))
        pal_image.putpalette(palette)
        return image.convert("RGB").quantize(palette=pal_image)
