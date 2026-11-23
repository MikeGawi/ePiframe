import logging
import sys
from datetime import datetime
from pathlib import Path

import pytest

from epiframe.photos.model import Photo
from epiframe.plugins.manager import PluginManager
from tests.epiframe.plugins.conftest import DEFAULT_CONFIG, GlobalConfig, WritePlugin


def manager(directory: Path) -> PluginManager:
    return PluginManager(directory, GlobalConfig(), directory.name)


def test_no_plugins(plugins_dir: Path) -> None:
    plugins = manager(plugins_dir)

    assert plugins.plugins == []
    assert plugins.enabled() == []
    assert not plugins.order_file.exists()  # nothing written without plugins


def test_missing_folder(tmp_path: Path) -> None:
    assert PluginManager(tmp_path / "plugins", GlobalConfig()).plugins == []


def test_discovery_in_name_order(plugins_dir: Path, write_plugin: WritePlugin) -> None:
    for folder in ("beta", "alpha", "gamma"):
        write_plugin(folder)
    (plugins_dir / "not_a_plugin").mkdir()

    plugins = manager(plugins_dir)

    assert [plugin.folder for plugin in plugins.plugins] == ["alpha", "beta", "gamma"]
    assert plugins.read_order() == [
        f"{plugins_dir.name}.{f}" for f in ("alpha", "beta", "gamma")
    ]
    assert plugins.plugins[0].logger.name == "epiframe.plugins.alpha"
    assert plugins.plugins[0].path == plugins_dir / "alpha"


def test_saved_order_comes_first(plugins_dir: Path, write_plugin: WritePlugin) -> None:
    for folder in ("alpha", "beta", "gamma", "delta"):
        write_plugin(folder)
    package = plugins_dir.name
    (plugins_dir / "order.cfg").write_text(
        f"{package}.gamma\n\n{package}.removed\n{package}.alpha\n"
    )

    plugins = manager(plugins_dir)

    assert [plugin.folder for plugin in plugins.plugins] == [
        "gamma",
        "alpha",
        "beta",
        "delta",
    ]
    # removed plugins leave the file, new ones are added
    assert plugins.read_order() == [
        f"{package}.{f}" for f in ("gamma", "alpha", "beta", "delta")
    ]


def test_order_written_only_on_change(
    plugins_dir: Path, write_plugin: WritePlugin
) -> None:
    write_plugin("alpha")
    manager(plugins_dir)
    order = plugins_dir / "order.cfg"
    order.touch()
    before = order.stat().st_mtime_ns

    manager(plugins_dir)

    assert order.stat().st_mtime_ns == before


def test_save_order(plugins_dir: Path, write_plugin: WritePlugin) -> None:
    write_plugin("alpha")
    write_plugin("beta")
    plugins = manager(plugins_dir)
    package = plugins_dir.name

    plugins.save_order([f"{package}.beta", f"{package}.alpha"])

    assert [p.folder for p in manager(plugins_dir).plugins] == ["beta", "alpha"]


def test_broken_plugins_are_skipped(
    plugins_dir: Path, write_plugin: WritePlugin, caplog: pytest.LogCaptureFixture
) -> None:
    write_plugin("good")
    write_plugin("syntax", source="this is not python")
    write_plugin("old_api", source="from modules.base.pluginbase import PluginBase\n")
    write_plugin("no_class", source="x = 1\n")
    write_plugin("wrong_class", source="class Plugin:\n    pass\n")
    write_plugin(
        "failing", source="from epiframe.plugins.base import Plugin\n"
    )  # no name
    write_plugin("bad-name")

    plugins = manager(plugins_dir)

    assert [plugin.folder for plugin in plugins.plugins] == ["good"]
    for folder in ("syntax", "old_api", "no_class", "wrong_class", "failing"):
        assert f"Error loading plugin {folder!r}, skipped" in caplog.text
    assert "must subclass epiframe.plugins.base.Plugin" in caplog.text
    assert (
        "'bad-name' skipped: the name must be a valid Python identifier" in caplog.text
    )
    assert "rename it to 'bad_name'" in caplog.text


def test_enabled_and_hooks(plugins_dir: Path, write_plugin: WritePlugin) -> None:
    source = """
from epiframe.photos.model import Photo
from epiframe.plugins.base import Plugin as Base


class Plugin(Base):
    name = "Source"

    def source_photos(self):
        return [Photo("a.jpg", self.source, datetime(2024, 1, 1, 10))]
"""
    write_plugin("source", source=source)
    write_plugin(
        "off",
        source=source,
        config=DEFAULT_CONFIG.replace("is_enabled=1", "is_enabled=0"),
    )
    write_plugin("plain")

    plugins = manager(plugins_dir)

    assert [p.folder for p in plugins.enabled()] == ["plain", "source"]
    assert [p.folder for p in plugins.sources()] == ["source"]
    assert plugins.with_hook("postprocess_photo") == []
    found = plugins.source_of(Photo("a.jpg", "plugin:source", datetime(2024, 1, 1)))
    assert found is not None
    assert found.folder == "source"
    assert plugins.source_of(Photo("a.jpg", "plugin:off", datetime(2024, 1, 1))) is None
    assert plugins.source_of(Photo("a.jpg", "local", datetime(2024, 1, 1))) is None


def test_package_is_bound_to_the_folder(
    tmp_path: Path, write_plugin: WritePlugin, plugins_dir: Path
) -> None:
    # a regular package of the same name elsewhere must not win (repo plugins/)
    other = tmp_path / "elsewhere" / plugins_dir.name
    other.mkdir(parents=True)
    (other / "__init__.py").write_text("")
    sys.path.insert(0, str(other.parent))
    write_plugin("alpha")

    plugins = manager(plugins_dir)
    again = manager(plugins_dir)  # already bound: kept

    assert [p.folder for p in plugins.plugins] == ["alpha"]
    assert [p.folder for p in again.plugins] == ["alpha"]
    assert list(sys.modules[plugins_dir.name].__path__) == [str(plugins_dir)]


def test_plugin_can_import_its_own_modules(
    plugins_dir: Path, write_plugin: WritePlugin
) -> None:
    package = plugins_dir.name
    path = write_plugin(
        "multi",
        source=f"""
from {package}.multi.helper import NAME
from epiframe.plugins.base import Plugin as Base


class Plugin(Base):
    name = NAME
""",
    )
    (path / "helper.py").write_text('NAME = "From helper"\n')

    assert manager(plugins_dir).plugins[0].name == "From helper"


def test_logging_name(
    plugins_dir: Path, write_plugin: WritePlugin, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="epiframe")
    write_plugin("talker")

    plugin = manager(plugins_dir).plugins[0]
    plugin.logger.info("hello")

    assert caplog.records[-1].name == "epiframe.plugins.talker"
