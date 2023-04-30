from misc.configproperty import ConfigProperty
from modules.base.configbase import ConfigBase
from modules.base.pluginbase import PluginBase


class Plugin(PluginBase):
    name = "Plugin3"
    author = "Author Name"
    description = "Test Plugin3"
    site = "Plugin site URL and documentation"
    info = "Additional info, license, etc."

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
