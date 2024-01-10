import os
import json
from json import JSONDecodeError


class IndexManager:

    __index = -1
    __id = None
    __path = None

    def __init__(self, path: str):
        self.__path = path

        # read index from file to change after each run
        if os.path.exists(path):
            try:
                with open(path, "r") as index_file:
                    index_data = json.load(index_file)
                    self.__index = int(index_data.get("index"))
                    self.__id = index_data.get("id").rstrip()
            except JSONDecodeError:
                # legacy
                with open(path, "r") as file_lines:
                    lines = file_lines.readlines()
                    if len(lines) == 2:
                        self.__id = str(lines[0]).rstrip()
                        self.__index = int(lines[1])
                    file_lines.close()

    def save(self):
        with open(self.__path, "w") as file_data:
            json.dump({"id": str(self.__id), "index": int(self.__index)}, file_data)

    def get_index(self) -> int:
        return self.__index

    def get_id(self) -> str:
        return self.__id

    def set_index(self, value: int):
        self.__index = value

    def set_id(self, value: str):
        self.__id = value

    def check_index(self, max_value: int):
        self.__index = 0 if self.__index >= max_value else self.__index
