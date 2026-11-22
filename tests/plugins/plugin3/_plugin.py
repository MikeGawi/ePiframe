from epiframe.config.property import ConfigProperty, PropertyType
from epiframe.config.base import ConfigBase
from modules.base.pluginbase import PluginBase


class Plugin(PluginBase):
    name = "Plugin3"
    author = "Author Name"
    description = "Test Plugin3"
    site = "Plugin site URL and documentation"
    info = "Additional info, license, etc."

    class PluginConfigManager(ConfigBase):
        def load_settings(self):
            return [ConfigProperty("is_enabled", type=PropertyType.BOOLEAN)]

    def __init__(
        self,
        path: str,
        pid_manager,
        logger,
        global_config: ConfigBase,
    ):
        super().__init__(path, pid_manager, logger, global_config)

    def add_photo_source(
        self,
        id_label: str,
        creation_label: str,
        source_label: str,
        photo_manager,
    ):
        print("add_photo_source")
