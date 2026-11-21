"""Plugins manager bound to the test plugins in tests/plugins."""

from unittest import mock
from unittest.mock import PropertyMock

from modules.pluginsmanager import PluginsManager

ORDER_FILE = "tests/plugins/order.cfg"


def get_plugins_manager():
    with (
        mock.patch.object(
            PluginsManager,
            "_PluginsManager__PLUGINS_DIR",
            return_value="tests/plugins/",
            new_callable=PropertyMock,
        ),
        mock.patch.object(
            PluginsManager,
            "_PluginsManager__ORDER_FILE",
            return_value=ORDER_FILE,
            new_callable=PropertyMock,
        ),
    ):
        manager = PluginsManager("", None, None)
    return manager
