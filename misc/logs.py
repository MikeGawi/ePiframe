import gzip
import logging
import os
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from time import gmtime
from time import strftime


class Logs:
    def __init__(self, path=""):
        if path:
            self.__path = path

            pathos = Path(path)
            pathos.parent.mkdir(parents=True, exist_ok=True)

            self.__logger = logging.getLogger("ePiframe")
            self.__logger.setLevel(logging.INFO)

            handler = TimedRotatingFileHandler(
                path, when="midnight", interval=1, backupCount=6
            )

            def namer(name):
                return name + ".gz"

            def rotator(source, destination):
                with open(source, "rb") as sf:
                    data = sf.read()
                    with gzip.open(destination, "wb") as df:
                        df.write(data)
                os.remove(source)

            handler.rotator = rotator
            handler.namer = namer

            self.__logger.addHandler(handler)
        else:
            self.__path = ""

    @staticmethod
    def show_log(text: str):
        time_obj = datetime.now().strftime("%Y-%m-%d %H:%M:%S :")
        print(time_obj, text)

    @staticmethod
    def start_time() -> float:
        return time.time()

    @staticmethod
    def end_time() -> float:
        return time.time()

    @staticmethod
    def execution_time(start_time: float, end_time: float):
        return strftime(
            " %H:%M:%S",
            gmtime(int("{:.0f}".format(float(str((end_time - start_time)))))),
        )

    def log(self, text: str, silent: bool = False):
        time_obj = datetime.now().strftime("%Y-%m-%d %H:%M:%S :")
        if not silent:
            print(time_obj, text)
        if self.__path:
            self.__logger.info(time_obj + " " + text)
