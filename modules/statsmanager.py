from __future__ import annotations

from misc.constants import Constants
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.backendmanager import BackendManager


class StatsManager:

    __RRA_IND = "RRA:AVERAGE:{}"
    __RRA = ["0.5:1:8640", "0.5:6:2880", "0.5:60:2016", "0.5:180:1488", "0.5:360:8784"]
    __DS = "DS:{}:GAUGE:600:U:U"
    __CREATE_CMD = "{} create {} --step {} {} {}"
    __UPDATE_CMD = "{} update {} N:{}"
    __EXTENSION = ".rrd"
    __PATH = "static/data/"

    __FILES = {
        "load": ["load1", "load5", "load15"],
        "mem": ["total", "used", "free", "available"],
        "temp": ["temp"],
    }

    __CMDS = {
        "load": 'awk \'{print $1" " $2" "$3}\' /proc/loadavg 2> /dev/null',
        "mem": 'free -m 2> /dev/null | awk \'FNR==2{print $2" "$3" "$4" "$7}\' 2> /dev/null',
        "temp": "/opt/vc/bin/vcgencmd measure_temp 2> /dev/null | awk -F \"[=']\" '{print $2}' 2> /dev/null",
    }

    def __init__(self, backend: BackendManager):
        self.__backend = backend
        self.__tool = self.__backend.get_config().get("rrdtool_bin_path")
        self.__init_files()

    def __init_files(self):
        if not os.path.exists(os.path.join(self.__backend.get_path(), self.__PATH)):
            os.makedirs(
                os.path.dirname(os.path.join(self.__backend.get_path(), self.__PATH)),
                exist_ok=True,
            )

        for file in self.__FILES.keys():
            path = os.path.join(
                self.__backend.get_path(), self.__PATH, file + self.__EXTENSION
            )
            if not os.path.exists(path):
                try:
                    os.system(
                        self.__CREATE_CMD.format(
                            self.__tool,
                            path,
                            Constants.STATS_STEP,
                            " ".join(
                                [
                                    self.__DS.format(value)
                                    for value in self.__FILES[file]
                                ]
                            ),
                            " ".join(
                                [self.__RRA_IND.format(value) for value in self.__RRA]
                            ),
                        )
                    )
                except Exception:
                    pass

    def feed_stats(self):
        for file in self.__CMDS.keys():
            path = os.path.join(
                self.__backend.get_path(), self.__PATH, file + self.__EXTENSION
            )
            if os.path.exists(path):
                out = os.popen(self.__CMDS[file]).read().strip().split()
                if out and file == "temp" and not self.__backend.is_metric():
                    out = [self.__backend.calc_to_f("".join(out))]
                if out:
                    os.system(
                        self.__UPDATE_CMD.format(self.__tool, path, ":".join(out))
                    )
