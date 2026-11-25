"""The frame (epiframe.service.frame.Frame) for the WebUI and fixture tests."""

from unittest.mock import patch

from epiframe.config import manager as configmanager
from epiframe.service.frame import Frame, Trigger
from tests.helpers.config import Config


def event_mock(trigger: Trigger) -> None:
    print(f"Event triggered {trigger}")


def get_frame() -> Frame:
    """A frame with the configuration of ``tests.helpers.config.Config``."""
    with patch.object(configmanager, "ConfigManager", Config):
        return Frame(event_mock, ".", ".")
