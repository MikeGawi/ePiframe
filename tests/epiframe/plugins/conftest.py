import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

DEFAULT_CONFIG = """[General]

# Set 1 to enable plugin, 0 to disable.
# Default: 1 (enabled)
is_enabled=1

# A number.
# Default: 5
size=5
"""

PLUGIN = """
from epiframe.config.property import ConfigProperty, PropertyType
from epiframe.plugins.base import Plugin as Base


class Plugin(Base):
    name = "{name}"

    def settings(self):
        return [*super().settings(), ConfigProperty("size", PropertyType.INTEGER)]
"""

WritePlugin = Callable[..., Path]


class GlobalConfig:
    def get(self, name: str) -> str:
        return "90" if name == "rotation" else ""

    def getint(self, name: str) -> int:
        return int(self.get(name) or 0)


@pytest.fixture
def global_config() -> GlobalConfig:
    return GlobalConfig()


@pytest.fixture
def plugins_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """An empty plugins folder whose name is a unique package name."""
    directory = tmp_path / f"plugins_{uuid.uuid4().hex}"
    directory.mkdir()
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield directory
    for module in [m for m in sys.modules if m.split(".")[0] == directory.name]:
        del sys.modules[module]


@pytest.fixture
def write_plugin(plugins_dir: Path) -> WritePlugin:
    def write(
        folder: str,
        source: str | None = None,
        default: str = DEFAULT_CONFIG,
        config: str | None = None,
    ) -> Path:
        path = plugins_dir / folder
        (path / "default").mkdir(parents=True)
        (path / "_plugin.py").write_text(source or PLUGIN.format(name=folder.title()))
        (path / "default" / "config.default").write_text(default)
        (path / "config.cfg").write_text(config if config is not None else default)
        return path

    return write
