from __future__ import annotations

import os
from typing import List, Any
from misc.configproperty import ConfigProperty
from misc.logs import Logs
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ePiframe_service import Service
    from modules.backendmanager import BackendManager
    from modules.base.configbase import ConfigBase
    from modules.configmanager import ConfigManager
    from modules.convertmanager import ConvertManager
    from modules.filteringmanager import FilteringManager
    from modules.indexmanager import IndexManager
    from modules.photomanager import PhotoManager
    from modules.pidmanager import PIDManager
    from modules.usersmanager import UsersManager
    from modules.webuimanager import WebUIManager


class PluginBase:
    CONFIG_FILE = "config.cfg"
    DEFAULT_CONFIG_FILE = "default/config.default"
    SOURCE = None
    config: ConfigManager
    name: str
    SETTINGS: List[ConfigProperty]

    def __init__(
        self,
        path: str,
        pid_manager: PIDManager,
        logging: Logs,
        global_config: ConfigBase,
    ):
        self.pid_manager = pid_manager
        self.logging = logging
        self.global_config = global_config
        self.path = path
        self.load_config()

    def is_function_used(self, function: Any):
        return getattr(type(self), function) != getattr(PluginBase, function)

    def load_config(self):
        self.config = self.PluginConfigManager(
            os.path.join(self.path, self.CONFIG_FILE),
            os.path.join(self.path, self.DEFAULT_CONFIG_FILE),
            self,
        )

    def is_enabled(self):
        return bool(self.config.getint("is_enabled"))

    def add_photo_source(
        self,
        id_label: str,
        creation_label: str,
        source_label: str,
        photo_manager: PhotoManager,
    ):
        pass

    def add_photo_source_get_file(
        self,
        photo,
        path: str,
        filename: str,
        id_label: str,
        creation_label: str,
        source_label: str,
        photo_manager: PhotoManager,
    ):
        pass

    def change_photos_list(
        self,
        id_label: str,
        creation_label: str,
        source_label: str,
        photo_list,
        photo_manager: PhotoManager,
        index_manager: IndexManager,
        filtering_manager: FilteringManager,
    ):
        pass

    def preprocess_photo(
        self,
        original_photo: str,
        is_horizontal: bool,
        convert_manager: ConvertManager,
        photo,
        id_label: str,
        creation_label: str,
        source_label: str,
    ):
        pass

    def postprocess_photo(
        self,
        final_photo: str,
        width: int,
        height: int,
        is_horizontal: bool,
        convert_manager: ConvertManager,
        photo,
        id_label: str,
        creation_label: str,
        source_label: str,
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
