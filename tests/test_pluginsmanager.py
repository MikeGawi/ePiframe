from unittest import mock
from unittest.mock import PropertyMock
from modules.pluginsmanager import PluginsManager
from tests.helpers.helpers import remove_file, not_raises

order_file = "tests/plugins/order.cfg"


def test_discovery():
    remove_file(order_file)
    manager = get_manager()
    assert [plugin.name for plugin in manager.get_plugins()] == [
        "Plugin1",
        "Plugin2",
        "Plugin3",
    ]
    assert [plugin.name for plugin in manager.get_enabled()] == ["Plugin1", "Plugin2"]


def test_plugin_preprocess():
    manager = get_manager()
    assert [plugin.name for plugin in manager.plugin_preprocess()] == [
        "Plugin1",
    ]


def test_plugin_postprocess():
    manager = get_manager()
    assert [plugin.name for plugin in manager.plugin_postprocess()] == [
        "Plugin1",
    ]


def test_plugin_api():
    manager = get_manager()
    assert [plugin.name for plugin in manager.plugin_api()] == [
        "Plugin1",
    ]


def test_plugin_action():
    manager = get_manager()
    assert [plugin.name for plugin in manager.plugin_action()] == [
        "Plugin1",
    ]


def test_plugin_photos_list():
    manager = get_manager()
    assert [plugin.name for plugin in manager.plugin_photos_list()] == [
        "Plugin1",
    ]


def test_plugin_service_thread():
    manager = get_manager()
    assert [plugin.name for plugin in manager.plugin_service_thread()] == [
        "Plugin1",
    ]


def test_plugin_website():
    manager = get_manager()
    assert [plugin.name for plugin in manager.plugin_website()] == [
        "Plugin1",
    ]


def test_plugin_source():
    manager = get_manager()
    assert [plugin.name for plugin in manager.plugin_source()] == [
        "Plugin1",
        "Plugin2",
    ]


def test_source():
    manager = get_manager()
    assert [plugin.name for plugin in manager.get_plugin_source()] == [
        "Plugin1",
    ]


def test_get_file():
    manager = get_manager()
    assert manager.plugin_source_get_file(manager.get_plugins()[0]) is True
    assert manager.plugin_source_get_file(manager.get_plugins()[1]) is False


def test_run_plugins():
    manager = get_manager()
    with not_raises(Exception):
        manager.get_plugins()[0].add_action(None, None, None)
        manager.get_plugins()[0].add_photo_source(None, None, None, None)
        manager.get_plugins()[0].add_photo_source_get_file(
            None, None, None, None, None, None, None
        )
        manager.get_plugins()[0].add_service_thread(None, None)
        manager.get_plugins()[0].add_website(None, None, None)
        manager.get_plugins()[0].change_photos_list(
            None, None, None, None, None, None, None
        )
        manager.get_plugins()[0].preprocess_photo(
            None, None, None, None, None, None, None
        )
        manager.get_plugins()[0].postprocess_photo(
            None, None, None, None, None, None, None, None, None
        )
        manager.get_plugins()[0].extend_api(None, None, None)

        manager.get_plugins()[1].add_photo_source(None, None, None, None)

        manager.get_plugins()[2].add_photo_source(None, None, None, None)

def test_read_order():
    manager = get_manager()
    with mock.patch.object(
        PluginsManager,
        "_PluginsManager__ORDER_FILE",
        return_value=order_file,
        new_callable=PropertyMock,
    ):
        assert manager.read_order() == [
            "tests.plugins.plugin1",
            "tests.plugins.plugin2",
            "tests.plugins.plugin3",
        ]


def test_change_order():
    remove_file(order_file)
    manager = get_manager()
    with mock.patch.object(
        PluginsManager,
        "_PluginsManager__ORDER_FILE",
        return_value=order_file,
        new_callable=PropertyMock,
    ):
        manager.save_order(
            [
                "tests.plugins.plugin3",
                "tests.plugins.plugin1",
                "tests.plugins.plugin2",
            ]
        )
        assert manager.read_order() == [
            "tests.plugins.plugin3",
            "tests.plugins.plugin1",
            "tests.plugins.plugin2",
        ]
        manager = get_manager()
        assert [plugin.name for plugin in manager.get_plugins()] == [
            "Plugin3",
            "Plugin1",
            "Plugin2",
        ]
    remove_file(order_file)


def get_manager():
    with mock.patch.object(
        PluginsManager,
        "_PluginsManager__PLUGINS_DIR",
        return_value="tests/plugins/",
        new_callable=PropertyMock,
    ), mock.patch.object(
        PluginsManager,
        "_PluginsManager__ORDER_FILE",
        return_value=order_file,
        new_callable=PropertyMock,
    ):
        manager = PluginsManager("", None, None, None)
    return manager
