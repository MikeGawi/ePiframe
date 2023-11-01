from typing import List
import pandas as pd
import os
import glob
import itertools
import datetime


class LocalSourceManager:
    def __init__(self, directory: str, recursive: bool, extensions: List[str]):
        self.__directory = directory if not directory.endswith("/") else directory[0:-1]
        self.__scope = "/**/*." if recursive else "/*."
        self.__recursive = recursive
        self.__extensions = extensions

    @staticmethod
    def __format_timestamp(time_stamp) -> str:
        return (
            datetime.datetime.fromtimestamp(time_stamp).strftime("%Y-%m-%dT%H:%M:%S")
            + "Z"
        )

    def get_files(self) -> List[str]:
        return list(
            itertools.chain(
                *[
                    glob.glob(
                        self.__directory + self.__scope + extension.lower(),
                        recursive=self.__recursive,
                    )
                    + glob.glob(
                        self.__directory + self.__scope + extension.upper(),
                        recursive=self.__recursive,
                    )
                    for extension in self.__extensions
                ]
            )
        )

    def get_dates(self, files_list: List[str]) -> List[str]:
        return [self.__format_timestamp(os.stat(file).st_mtime) for file in files_list]

    def get_local_photos(
        self, id_label: str, creation_label: str, source_label: str, source: str
    ):
        photos = pd.DataFrame()

        files = self.get_files()
        if files and len(files) > 0:
            files = sorted(files)
            dates = self.get_dates(files)
            photos = pd.DataFrame(
                list(zip(files, dates)), columns=[id_label, creation_label]
            )
            photos[source_label] = source

        return photos

    @staticmethod
    def create_directory(directory: str) -> str:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        return directory
