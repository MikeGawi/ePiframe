import sys
import os
import importlib
from PIL import Image

library_directory = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"
)

if os.path.exists(library_directory):
    sys.path.append(library_directory)


# !!! more displays on https://github.com/waveshare/e-Paper


class DisplayManager:
    __PROCESS_NAME = "fbi"
    __DISPLAY_PHOTO_CODE = "sudo killall -SIGKILL {} > /dev/null 2>&1;sudo {} -vt {} -noverbose -a {} > /dev/null 2>&1"
    __DISPLAY_VALUES = ["SPI", "HDMI"]

    __ERROR_VALUE_TEXT = "Configuration display_type should be one of {}"

    __DISPLAY_POWER = "display_power"
    __DISPLAY_POWER_CODE = "sudo vcgencmd " + __DISPLAY_POWER + " {} 2> /dev/null"
    __DISPLAY_POWER_OFF = "0"
    __DISPLAY_POWER_ON = "1"

    def __init__(
        self, display: str, display_type: str = "", binary: str = "", vt: int = 1
    ):
        self.__use_hdmi = self.is_hdmi(display_type)
        self.__binary = binary
        self.__vt = vt
        self.__display = display

        if not self.__use_hdmi:
            # it's like : from waveshare_epd import 'display'
            module = importlib.import_module("waveshare_epd." + display)

            self.__epd = module.EPD()
            self.__epd.init()

    def clear(self):
        if not self.__use_hdmi:
            self.__epd.Clear()

    def power_off(self):
        if not self.__use_hdmi:
            self.__epd.sleep()

    def show_image(self, photo_path: str):
        if not self.__use_hdmi:
            try:
                # uncomment if experiencing image shadowing
                # self.clear()
                image = Image.open(photo_path)
                self.__epd.display(self.__epd.getbuffer(image))
                self.power_off()
            except KeyboardInterrupt:
                self.__epd.epdconfig.module_exit()
                raise
        else:
            os.popen(
                self.__DISPLAY_PHOTO_CODE.format(
                    self.__PROCESS_NAME, self.__binary, self.__vt, photo_path
                )
            )

    def get_display(self) -> str:
        return self.__display

    def get_vt(self) -> int:
        return self.__vt

    def is_display_hdmi(self) -> bool:
        return self.__use_hdmi

    @classmethod
    def verify_display(cls, value: str):
        if value not in [key for key in cls.__DISPLAY_VALUES]:
            raise Exception(
                cls.__ERROR_VALUE_TEXT.format([key for key in cls.__DISPLAY_VALUES])
            )

    @classmethod
    def get_displays(cls) -> list:
        return cls.__DISPLAY_VALUES

    @classmethod
    def get_hdmi(cls) -> str:
        return cls.__DISPLAY_VALUES[1]

    @classmethod
    def get_spi(cls) -> str:
        return cls.__DISPLAY_VALUES[0]

    @classmethod
    def is_hdmi(cls, value: str) -> bool:
        return (
            True
            if value and value.lower() == cls.__DISPLAY_VALUES[1].lower()
            else False
        )

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
