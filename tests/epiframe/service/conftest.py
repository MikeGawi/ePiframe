"""A frame with its configuration in ``tmp_path`` (``make_frame(**entries)``)."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest

from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.display.hdmi import HdmiPower
from epiframe.plugins.manager import PluginManager
from epiframe.service import frame as frame_module
from epiframe.service.frame import Frame, Trigger

WORKING = {"start_times": ",".join(["8:00"] * 7), "stop_times": ",".join(["20:00"] * 7)}

MakeFrame = Callable[..., Frame]


@pytest.fixture
def plugins(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    manager: MagicMock = create_autospec(PluginManager)
    monkeypatch.setattr(frame_module, "PluginManager", manager)
    return manager


@pytest.fixture
def triggers() -> list[Trigger]:
    return []


@pytest.fixture
def make_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    plugins: MagicMock,
    triggers: list[Trigger],
) -> MakeFrame:
    monkeypatch.chdir(tmp_path)  # relative paths of the default config

    def make(**entries: str) -> Frame:
        write_config(tmp_path / "config.cfg", **(WORKING | entries))
        return Frame(
            triggers.append,
            tmp_path / "config.cfg",
            tmp_path,
            plugins_dir=tmp_path / "plugins",
            hdmi=create_autospec(HdmiPower, instance=True),
        )

    return make


@pytest.fixture
def frame(make_frame: MakeFrame) -> Frame:
    return make_frame()


def write_config(path: Path, **entries: str) -> None:
    config = ConfigManager(path, paths.CONFIG_FILE_DEFAULT)
    for name, value in entries.items():
        config.set(name, value)
    config.save()
