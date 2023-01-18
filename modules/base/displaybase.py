from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.configmanager import ConfigManager


class DisplayBase:
    __PROCESS_NAME = "fbi"
    __DISPLAY_PHOTO_CODE = "sudo killall -SIGKILL {} > /dev/null 2>&1;sudo {} -vt {} -noverbose -a {} > /dev/null 2>&1"

    _binary: str = None
    _vt: int = 1
    _display: str = None
    _config: ConfigManager = None

    def __init__(self, config: ConfigManager):
        self._binary = config.get("fbi_bin_path")
        self._vt = int(config.get("tty"))
        self._display = config.get("display")
        self._config = config

    def clear(self):
        pass

    def __power_off(self):
        pass

    def show_image(self, photo_path: str):
        os.popen(
            self.__DISPLAY_PHOTO_CODE.format(
                self.__PROCESS_NAME, self._binary, self._vt, photo_path
            )
        )

    def get_display(self):
        return self._display

    def get_vt(self):
        return self._vt
