from typing import List
import os
import glob
import itertools
import datetime

from epiframe.photos.model import Photo

# source name of the local photos in the photo index
LOCAL_SOURCE = "Local"


class LocalSourceManager:
    def __init__(self, directory: str, recursive: bool, extensions: List[str]):
        self.__directory = directory if not directory.endswith("/") else directory[0:-1]
        self.__scope = "/**/*." if recursive else "/*."
        self.__recursive = recursive
        self.__extensions = extensions

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

    def get_local_photos(self) -> List[Photo]:
        # sorted, so the first scan adds the photos in path order
        return [
            Photo(
                file,
                LOCAL_SOURCE,
                datetime.datetime.fromtimestamp(os.stat(file).st_mtime),
            )
            for file in sorted(self.get_files())
        ]

    @staticmethod
    def create_directory(directory: str) -> str:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        return directory
