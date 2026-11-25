import logging
import threading
from datetime import datetime
from pathlib import Path

import pytest

from epiframe.config.base import LegacyEntry
from epiframe.config.property import ConfigError, ConfigProperty, PropertyType
from epiframe.photos.model import Photo
from epiframe.plugins.base import (
    HOOKS,
    PhotoFile,
    Plugin,
    PluginConfig,
    PluginContext,
)
from tests.epiframe.plugins.conftest import DEFAULT_CONFIG, GlobalConfig


class Minimal(Plugin):
    name = "Minimal"


class Everything(Plugin):
    name = "Everything"

    def settings(self) -> list[ConfigProperty]:
        return [*super().settings(), ConfigProperty("size", PropertyType.INTEGER)]

    def source_photos(self) -> list[Photo]:
        return [Photo("a.jpg", self.source, datetime(2024, 1, 1, 10))]

    def preprocess_photo(self, photo: PhotoFile) -> None:
        photo.path.write_text("pre")


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    path = tmp_path / "my_plugin"
    (path / "default").mkdir(parents=True)
    (path / "default" / "config.default").write_text(DEFAULT_CONFIG)
    (path / "config.cfg").write_text(DEFAULT_CONFIG.replace("size=5", "size=7"))
    return path


def context(folder: Path) -> PluginContext:
    return PluginContext(folder, logging.getLogger("test"), GlobalConfig())


def test_minimal_plugin(folder: Path) -> None:
    plugin = Minimal(context(folder))

    assert plugin.enabled
    assert plugin.folder == "my_plugin"
    assert plugin.source == "plugin:my_plugin"
    assert plugin.path == folder
    assert plugin.global_config.get("rotation") == "90"
    assert plugin.logger.name == "test"
    # not declared entries of the default file are plain strings
    assert plugin.config.get("size") == "7"
    assert [hook for hook in HOOKS if plugin.implements(hook)] == []


def test_default_hooks_do_nothing(folder: Path, tmp_path: Path) -> None:
    plugin = Minimal(context(folder))
    photo = PhotoFile(tmp_path / "x.bmp", None, 800, 480, True, 90, None)  # type: ignore[arg-type]

    assert list(plugin.source_photos()) == []
    with pytest.raises(NotImplementedError):
        plugin.fetch_photo(
            Photo("a", plugin.source, datetime(2024, 1, 1)), tmp_path, "photo"
        )
    plugin.preprocess_photo(photo)
    plugin.postprocess_photo(photo)
    assert plugin.extend_api(None) == []  # type: ignore[arg-type]
    assert plugin.add_website(None, None, None) == []
    assert plugin.add_action(None) == []  # type: ignore[arg-type]
    plugin.service_thread(None, threading.Event())  # type: ignore[arg-type]


def test_hooks_and_settings(folder: Path, tmp_path: Path) -> None:
    plugin = Everything(context(folder))

    assert plugin.implements("source_photos")
    assert plugin.implements("preprocess_photo")
    assert not plugin.implements("postprocess_photo")
    assert plugin.config.getint("size") == 7
    assert [photo.id for photo in plugin.source_photos()] == ["a.jpg"]


def test_unknown_hook(folder: Path) -> None:
    with pytest.raises(ValueError, match="Unknown plugin hook 'add_photo_source'"):
        Minimal(context(folder)).implements("add_photo_source")


def test_disabled(folder: Path) -> None:
    (folder / "config.cfg").write_text(
        DEFAULT_CONFIG.replace("is_enabled=1", "is_enabled=0")
    )

    assert not Minimal(context(folder)).enabled


def test_name_is_required(folder: Path) -> None:
    class Nameless(Plugin):
        pass

    with pytest.raises(ConfigError, match="has no name"):
        Nameless(context(folder))


def test_settings_must_contain_is_enabled(folder: Path) -> None:
    with pytest.raises(ConfigError, match="must contain 'is_enabled'"):
        PluginConfig(folder, [ConfigProperty("size", PropertyType.INTEGER)])


def test_invalid_value_is_reported_by_verify(folder: Path) -> None:
    (folder / "config.cfg").write_text(DEFAULT_CONFIG.replace("size=5", "size=many"))

    plugin = Everything(context(folder))

    with pytest.raises(ConfigError, match="size"):
        plugin.config.verify()


def test_legacy_entries_are_migrated(folder: Path) -> None:
    (folder / "config.cfg").write_text("[General]\nis_enabled=1\nold_size=9\n")

    class Renamed(Plugin):
        name = "Renamed"
        LEGACY = (LegacyEntry("old_size", "size", str),)

    plugin = Renamed(context(folder))

    assert plugin.config.get("size") == "9"
    assert "old_size" not in (folder / "config.cfg").read_text()
