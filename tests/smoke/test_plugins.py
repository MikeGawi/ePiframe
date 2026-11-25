"""Smoke tests of Plugin API v2: plugins loaded by the real ePiframe process."""

import json
import shutil
from pathlib import Path

from epiframe.config import paths
from tests.smoke.conftest import Frame, needs_imagemagick

DEFAULT_CONFIG = """[General]

# Set 1 to enable plugin, 0 to disable.
# Default: 1 (enabled)
is_enabled=1

# Folder with the photos of this source.
# Default: plugin_photos
folder=plugin_photos
"""

SOURCE_PLUGIN = """
import json
from datetime import datetime
from pathlib import Path

from epiframe.config.property import ConfigProperty, PropertyType
from epiframe.photos.model import Photo
from epiframe.plugins.base import Plugin as Base


class Plugin(Base):
    name = "Smoke source"

    def settings(self):
        return [*super().settings(), ConfigProperty("folder", PropertyType.FILE)]

    def source_photos(self):
        folder = Path(self.config.get("folder")).resolve()
        return [
            Photo(str(path), self.source, datetime(2024, 1, 1 + index))
            for index, path in enumerate(sorted(folder.glob("*.png")))
        ]

    def postprocess_photo(self, photo):
        Path("postprocessed.json").write_text(json.dumps({
            "path": str(photo.path),
            "photo": photo.photo.id if photo.photo else None,
            "size": [photo.width, photo.height],
            "horizontal": photo.horizontal,
        }))
"""

OLD_PLUGIN = "from modules.base.pluginbase import PluginBase\n"


def add_plugin(frame: Frame, folder: str, source: str) -> Path:
    path = frame.directory / "plugins" / folder
    (path / "default").mkdir(parents=True)
    (path / "_plugin.py").write_text(source)
    (path / "default" / "config.default").write_text(DEFAULT_CONFIG)
    shutil.copy(path / "default" / "config.default", path / "config.cfg")
    return path


def plugins_env(frame: Frame) -> dict[str, str]:
    return {paths.PLUGINS_DIR_ENV: str(frame.directory / "plugins")}


@needs_imagemagick
def test_plugin_source_and_postprocessing(frame: Frame) -> None:
    frame.configure(use_local="0")
    photo = frame.add_photo("../plugin_photos/a.png", "red", 1_600_000_000)
    add_plugin(frame, "smoke_source", SOURCE_PLUGIN)
    add_plugin(frame, "old_plugin", OLD_PLUGIN)

    result = frame.run("test", env=plugins_env(frame))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Error loading plugin 'old_plugin', skipped" in result.stdout
    assert "Getting data from plugin 'Smoke source' source..." in result.stdout
    assert "Postprocessing photo by plugin 'Smoke source'..." in result.stdout
    report = json.loads((frame.directory / "postprocessed.json").read_text())
    assert report["photo"] == str(photo.resolve())
    assert report["size"] == [800, 480]
    assert report["horizontal"] is True
    assert Path(report["path"]).name == "photo.bmp"
    order = (frame.directory / "plugins" / "order.cfg").read_text().split()
    assert order == ["plugins.old_plugin", "plugins.smoke_source"]


def test_check_config_with_plugins(frame: Frame) -> None:
    path = add_plugin(frame, "smoke_source", SOURCE_PLUGIN)
    (path / "config.cfg").write_text(
        DEFAULT_CONFIG.replace("folder=plugin_photos", "folder=missing")
    )

    result = frame.run("check-config", env=plugins_env(frame))

    assert result.returncode != 0
    assert (
        "Error verifying configuration file for 'Smoke source' plugin!" in result.stdout
    )
