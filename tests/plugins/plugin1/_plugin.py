from misc.configproperty import ConfigProperty
from modules.base.configbase import ConfigBase
from modules.base.pluginbase import PluginBase


class Plugin(PluginBase):
    name = "Plugin1"
    author = "Author Name"
    description = "Test Plugin1"
    site = "Plugin site URL and documentation"
    info = "Additional info, license, etc."
    SOURCE = "'{}' plugin source".format(name)

    class PluginConfigManager(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    "is_enabled", self, prop_type=ConfigProperty.BOOLEAN_TYPE
                )
            ]

    def __init__(
        self,
        path: str,
        pid_manager,
        logging,
        global_config: ConfigBase,
    ):
        super().__init__(path, pid_manager, logging, global_config)

    def add_photo_source(
        self,
        id_label: str,
        creation_label: str,
        source_label: str,
        photo_manager,
    ):
        print("add_photo_source")

    def add_photo_source_get_file(
        self,
        photo,
        path: str,
        filename: str,
        id_label: str,
        creation_label: str,
        source_label: str,
        photo_manager,
    ):
        print("add_photo_source_get_file")

    def change_photos_list(
        self,
        id_label: str,
        creation_label: str,
        source_label: str,
        photo_list,
        photo_manager,
        index_manager,
        filtering_manager,
    ):
        print("change_photos_list")

    def preprocess_photo(
        self,
        original_photo: str,
        is_horizontal: bool,
        convert_manager,
        photo,
        id_label: str,
        creation_label: str,
        source_label: str,
    ):
        print("preprocess_photo")

    def postprocess_photo(
        self,
        final_photo: str,
        width: int,
        height: int,
        is_horizontal: bool,
        convert_manager,
        photo,
        id_label: str,
        creation_label: str,
        source_label: str,
    ):
        print("postprocess_photo")

    def extend_api(
        self,
        web_manager,
        users_manager,
        backend,
    ):
        print("extend_api")

    def add_website(
        self,
        web_manager,
        users_manager,
        backend,
    ):
        print("add_website")

    def add_action(
        self,
        web_manager,
        users_manager,
        backend,
    ):
        print("add_action")

    def add_service_thread(self, service, backend):
        print("add_service_thread")
