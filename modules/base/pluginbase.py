from __future__ import annotations

import os
from typing import Any
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import logging

    from ePiframe_service import Service
    from modules.backendmanager import BackendManager
    from epiframe.config.base import ConfigBase
    from epiframe.processing.imagemagick import ImageMagick
    from collections.abc import Iterable

    from epiframe.photos.model import Photo
    from epiframe.core.pidfile import PidFile
    from modules.usersmanager import UsersManager
    from modules.webuimanager import WebUIManager


class PluginBase:
    CONFIG_FILE = "config.cfg"
    DEFAULT_CONFIG_FILE = "default/config.default"
    SOURCE = None
    config: ConfigBase
    name: str

    def __init__(
        self,
        path: str,
        pid_manager: PidFile,
        logger: logging.Logger,
        global_config: ConfigBase,
    ):
        self.pid_manager = pid_manager
        self.logger = logger
        self.global_config = global_config
        self.path = path
        self.load_config()

    def is_function_used(self, function: Any):
        return getattr(type(self), function) != getattr(PluginBase, function)

    def load_config(self):
        self.config = self.PluginConfigManager(
            os.path.join(self.path, self.CONFIG_FILE),
            os.path.join(self.path, self.DEFAULT_CONFIG_FILE),
        )

    def is_enabled(self):
        return bool(self.config.getint("is_enabled"))

    def add_photo_source(self) -> Iterable[Photo]:
        # all photos of the source: Photo(id, self.SOURCE, created)
        pass

    def add_photo_source_get_file(self, photo: Photo, path: str, filename: str):
        # returns the path of the retrieved file
        pass

    def preprocess_photo(
        self,
        original_photo: str,
        is_horizontal: bool,
        image_magick: ImageMagick,
        photo: Photo | None,
    ):
        pass

    def postprocess_photo(
        self,
        final_photo: str,
        width: int,
        height: int,
        is_horizontal: bool,
        image_magick: ImageMagick,
        photo: Photo | None,
    ):
        pass

    def extend_api(
        self,
        web_manager: WebUIManager,
        users_manager: UsersManager,
        backend: BackendManager,
    ):
        pass

    def add_website(
        self,
        web_manager: WebUIManager,
        users_manager: UsersManager,
        backend: BackendManager,
    ):
        pass

    def add_action(
        self,
        web_manager: WebUIManager,
        users_manager: UsersManager,
        backend: BackendManager,
    ):
        pass

    def add_service_thread(self, service: Service, backend: BackendManager):
        pass
