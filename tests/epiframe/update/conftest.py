"""An update in ``tmp_path``: real configuration and photo index, fake
ImageMagick, plugins and display."""

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, create_autospec

import pytest
from PIL import Image

from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.display.base import Display
from epiframe.plugins.base import Plugin
from epiframe.plugins.manager import PluginManager
from epiframe.processing.imagemagick import ImageMagick
from epiframe.update.pipeline import Pipeline

MakeConfig = Callable[..., ConfigManager]


@pytest.fixture(autouse=True)
def info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="epiframe")


@pytest.fixture
def make_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MakeConfig:
    """The configuration in ``tmp_path`` (the working directory) with ``entries``."""
    monkeypatch.chdir(tmp_path)  # relative paths of the default config

    def make(**entries: str) -> ConfigManager:
        config = ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)
        for name, value in entries.items():
            config.set(name, value)
        config.save()
        return config

    return make


@pytest.fixture
def config(make_config: MakeConfig) -> ConfigManager:
    return make_config()


def fake_convert(source: str, target: str, *arguments: Any) -> None:
    Path(target).write_bytes(Path(source.removesuffix("[0]")).read_bytes())


@pytest.fixture
def magick() -> MagicMock:
    """ImageMagick that copies the photo as the conversion."""
    mock: MagicMock = create_autospec(ImageMagick, instance=True)
    mock.image_format.return_value = "JPEG"
    mock.comment.return_value = ""
    mock.auto_orient.return_value = False
    mock.convert.side_effect = fake_convert
    return mock


@pytest.fixture
def plugins() -> MagicMock:
    mock: MagicMock = create_autospec(PluginManager, instance=True)
    mock.sources.return_value = []
    mock.with_hook.return_value = []
    mock.enabled.return_value = []
    mock.source_of.return_value = None
    return mock


def make_plugin(name: str = "Clock", **hooks: Any) -> MagicMock:
    """A plugin implementing ``hooks`` (callables or return values)."""
    plugin: MagicMock = create_autospec(Plugin, instance=True)
    plugin.name = name
    plugin.source = f"plugin:{name.lower()}"
    plugin.implements.side_effect = lambda hook: hook in hooks
    for hook, value in hooks.items():
        target = getattr(plugin, hook)
        if callable(value):
            target.side_effect = value
        else:
            target.return_value = value
    return plugin


@pytest.fixture
def display() -> MagicMock:
    mock: MagicMock = create_autospec(Display, instance=True)
    return mock


@pytest.fixture
def make_pipeline(
    make_config: MakeConfig, magick: MagicMock, plugins: MagicMock, display: MagicMock
) -> Callable[..., Pipeline]:
    """The pipeline of the configuration with ``entries``."""

    def make(*, spi: bool = True, **entries: str) -> Pipeline:
        return Pipeline(
            make_config(**entries),
            plugins,
            magick,
            display_factory=lambda settings: display,
            spi_check=lambda: spi,
        )

    return make


def add_photo(directory: Path, name: str, mtime: float = 1_600_000_000) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 6), "red").save(path)
    os.utime(path, (mtime, mtime))
    return path
