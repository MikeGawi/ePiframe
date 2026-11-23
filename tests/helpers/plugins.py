"""Plugin manager bound to the test plugins in tests/plugins."""

from pathlib import Path

from epiframe.plugins.manager import PluginManager

TEST_PLUGINS = Path(__file__).resolve().parents[1] / "plugins"
ORDER_FILE = str(TEST_PLUGINS / "order.cfg")


class GlobalConfig:
    """The ePiframe configuration seen by the test plugins."""

    def get(self, name: str) -> str:
        return {"rotation": "90", "convert_bin_path": "convert"}.get(name, "")

    def getint(self, name: str) -> int:
        return int(self.get(name) or 0)


def get_plugins_manager(config: object = None) -> PluginManager:
    return PluginManager(TEST_PLUGINS, config or GlobalConfig(), "tests.plugins")


def plugin_manager_for_tests(directory: object, config: object) -> PluginManager:
    """Replacement of ``PluginManager`` in the backend: always the test plugins."""
    return PluginManager(TEST_PLUGINS, config, "tests.plugins")
