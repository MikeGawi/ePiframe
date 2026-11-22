"""Shared backend test doubles (used by backend, WebUI and fixture tests)."""

from typing import List
from unittest.mock import patch

from epiframe.config import manager as configmanager
from epiframe.core import interval as intervalmanager
from epiframe.core import schedule as timermanager
from modules.backendmanager import BackendManager
from tests.helpers.config import Config


def event_mock(params):
    print(f"Event triggered {params=}")


class MockedIntervalManager:
    """Double of epiframe.core.interval.IntervalMultiplier."""

    __path = None
    interval = 5

    @classmethod
    def set_interval(cls, interval):
        cls.interval = interval

    def __init__(self, path: str):
        self.__path = path
        print("IntervalManager_init")

    def read(self) -> int:
        print("IntervalManager_read")
        return self.interval

    def save(self, interval: int):
        print(f"IntervalManager_save {interval=}")

    def remove(self):
        print("IntervalManager_remove")


class MockedTimerManager:
    """Double of epiframe.core.schedule.WeeklySchedule."""

    @classmethod
    def from_strings(cls, start_times: List[str], end_times: List[str]):
        print("TimerManager_init")
        return cls()

    def is_active(self) -> bool:
        print("TimerManager_should_i_work_now")
        return True


def get_backend_manager():
    with (
        patch.object(configmanager, "ConfigManager", Config),
        patch.object(timermanager, "WeeklySchedule", MockedTimerManager),
        patch.object(intervalmanager, "IntervalMultiplier", MockedIntervalManager),
    ):
        return BackendManager(event_mock, ".")
