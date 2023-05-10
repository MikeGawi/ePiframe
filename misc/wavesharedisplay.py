from __future__ import annotations

import importlib
import itertools
import os
import sys
from typing import TYPE_CHECKING

from PIL import Image

from misc.constants import Constants
from modules.base.displaybase import DisplayBase

if TYPE_CHECKING:
    from modules.configmanager import ConfigManager


library_directory = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"
)

if os.path.exists(library_directory):
    sys.path.append(library_directory)


class WaveshareDisplay(DisplayBase):
    def __init__(self, config: ConfigManager):
        super().__init__(config)
        # it's like : from waveshare_epd import 'display'
        module = importlib.import_module("waveshare_epd." + self._display)
        self.__epd = module.EPD()
        self.__epd.init()

    def clear(self):
        self.__epd.Clear()

    def __power_off(self):
        self.__epd.sleep()

    def show_image(self, photo_path: str):
        try:
            self.__clear_display()
            image = Image.open(photo_path)
            color_schema = self._config.get("epaper_color")
            no_convert = self.get_no_convert()

            if color_schema.lower() in no_convert:
                self.__epd.display(self.__epd.getbuffer(image))
            elif color_schema.lower() == Constants.COLOR_BWR.lower():
                black, red = self.convert(image, [255, 0, 0])
                self.__epd.display(
                    self.__epd.getbuffer(black), self.__epd.getbuffer(red)
                )
            elif color_schema.lower() == Constants.COLOR_BWY.lower():
                black, yellow = self.convert(image, [255, 255, 0])
                self.__epd.display(
                    self.__epd.getbuffer(black), self.__epd.getbuffer(yellow)
                )

            self.__power_off()
        except KeyboardInterrupt:
            self.__epd.epdconfig.module_exit()
            raise

    @staticmethod
    def get_no_convert():
        return [
            schema.lower()
            for schema in [
                Constants.COLOR_BW,
                Constants.COLOR_4C,
                Constants.COLOR_7C,
                Constants.COLOR_OTHER,
            ]
        ]

    def __clear_display(self):
        if bool(self._config.getint("clear_display")):
            self.clear()

    @staticmethod
    def convert(image: Image, color: list) -> (Image, Image):
        palette_filter = [color, [255, 255, 255], [0, 0, 0]]
        palette = tuple(itertools.chain(*palette_filter)) + (0, 0, 0) * (
            256 - len(palette_filter)
        )
        pal_image = Image.new("P", (1, 1))
        pal_image.putpalette(palette)
        quantized = image.convert("RGB").quantize(palette=pal_image)
        return (
            quantized.point(lambda p: 1 if p != 2 else 3).convert("1"),
            quantized.point(lambda p: 1 if p != 0 else 3).convert("1"),
        )
