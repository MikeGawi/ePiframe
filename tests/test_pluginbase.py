import pytest
from modules.base.pluginbase import PluginBase
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import not_raises


def test_enabled():
    plugin = PluginMock("path", None, None, None)
    assert plugin.is_enabled() is True


def test_disabled():
    plugin = PluginOverrideMock("path", None, None, None)
    assert plugin.is_enabled() is False


def test_config():
    with Capturing() as output:
        PluginMock("path", None, None, None)
    assert output == ["path/config.cfg path/default/config.default"]


def test_function_used():
    plugin = PluginOverrideMock("path", None, None, None)
    assert plugin.is_function_used("add_photo_source") is True


def test_function_not_used():
    plugin = PluginOverrideMock("path", None, None, None)
    assert plugin.is_function_used("change_photos_list") is False


def test_function_wrong():
    plugin = PluginOverrideMock("path", None, None, None)
    with pytest.raises(Exception) as exception:
        plugin.is_function_used("non_existing_function")
    assert (
        str(exception)
        == "<ExceptionInfo AttributeError(\"type object 'PluginOverrideMock' has no attribute "
        "'non_existing_function'\") tblen=2>"
    )


def test_add_photo_source():
    with Capturing() as output:
        PluginMock("path", None, None, None).add_photo_source(None, None, None, None)
    assert output == ["path/config.cfg path/default/config.default", "add_photo_source"]


def test_add_photo_source_get_file():
    with Capturing() as output:
        PluginMock("path", None, None, None).add_photo_source_get_file(
            None, None, None, None, None, None, None
        )
    assert output == [
        "path/config.cfg path/default/config.default",
        "add_photo_source_get_file",
    ]


def test_change_photos_list():
    with Capturing() as output:
        PluginMock("path", None, None, None).change_photos_list(
            None, None, None, None, None, None, None
        )
    assert output == [
        "path/config.cfg path/default/config.default",
        "change_photos_list",
    ]


def test_preprocess_photo():
    with Capturing() as output:
        PluginMock("path", None, None, None).preprocess_photo(
            None, False, None, None, None, None, None
        )
    assert output == [
        "path/config.cfg path/default/config.default",
        "preprocess_photo",
    ]


def test_postprocess_photo():
    with Capturing() as output:
        PluginMock("path", None, None, None).postprocess_photo(
            None, 0, 0, False, None, None, None, None, None
        )
    assert output == [
        "path/config.cfg path/default/config.default",
        "postprocess_photo",
    ]


def test_extend_api():
    with Capturing() as output:
        PluginMock("path", None, None, None).extend_api(None, None, None)
    assert output == [
        "path/config.cfg path/default/config.default",
        "extend_api",
    ]


def test_add_website():
    with Capturing() as output:
        PluginMock("path", None, None, None).add_website(None, None, None)
    assert output == [
        "path/config.cfg path/default/config.default",
        "add_website",
    ]


def test_add_action():
    with Capturing() as output:
        PluginMock("path", None, None, None).add_action(None, None, None)
    assert output == [
        "path/config.cfg path/default/config.default",
        "add_action",
    ]


def test_add_service_thread():
    with Capturing() as output:
        PluginMock("path", None, None, None).add_service_thread(None, None)
    assert output == [
        "path/config.cfg path/default/config.default",
        "add_service_thread",
    ]


class PluginMock(PluginBase, object):
    class PluginConfigManager:
        def __init__(self, path: str, path2: str, self_object):
            print(path, path2)

        def getint(self, name: str):
            return True

    def get_config(self):
        return self.config

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


def test_run_plugin():
    plugin = PluginOverrideMock("path", None, None, None)
    with not_raises(Exception):
        plugin.add_action(None, None, None)
        plugin.add_photo_source(None, None, None, None)
        plugin.add_photo_source_get_file(None, None, None, None, None, None, None)
        plugin.add_service_thread(None, None)
        plugin.add_website(None, None, None)
        plugin.change_photos_list(None, None, None, None, None, None, None)
        plugin.preprocess_photo(None, None, None, None, None, None, None)
        plugin.postprocess_photo(None, None, None, None, None, None, None, None, None)
        plugin.extend_api(None, None, None)


class PluginOverrideMock(PluginBase):
    def add_photo_source(
        self,
        id_label: str,
        creation_label: str,
        source_label: str,
        photo_manager,
    ):
        print("add_photo_source")

    class PluginConfigManager:
        def __init__(self, path: str, path2: str, self_object):
            print(path, path2)
            self.self_object = self_object

        def self_object(self):
            return self.self_object

        def getint(self, name: str):
            return False
