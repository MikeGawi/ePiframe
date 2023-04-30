import os
import subprocess
from typing import AnyStr


class PIDManager:

    __pid = None
    __path = None

    def __init__(self, path: str):
        self.__path = path
        self.__pid = os.getpid()

    def read(self) -> int:
        pid = 0

        try:
            if os.path.exists(self.__path):
                with open(self.__path, "r") as file_data:
                    lines = file_data.readlines()
                    pid = str(lines[0]).rstrip()
                    file_data.close()
        except Exception:
            self.remove()

        return int(pid)

    def save(self):
        with open(self.__path, "w") as file:
            file.write(str(self.__pid))
            file.close()

    def remove(self):
        if os.path.exists(self.__path):
            os.remove(self.__path)

    def get_pid(self) -> int:
        return int(self.__pid)

    @staticmethod
    def get_pid_name(pid: int) -> AnyStr:
        process = subprocess.Popen(
            [f"ps -o cmd= {pid}"], stdout=subprocess.PIPE, shell=True
        )
        process.wait()
        out, error = process.communicate()

        return out
