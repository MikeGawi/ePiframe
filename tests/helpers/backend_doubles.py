"""Shared backend test doubles (used by backend, WebUI and fixture tests)."""

from typing import List
from unittest.mock import patch

from modules import configmanager, intervalmanager, timermanager
from modules.backendmanager import BackendManager
from tests.helpers.config import Config


def event_mock(params):
    print(f"Event triggered {params=}")


class MockedIntervalManager:
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
    def __init__(self, start_times: List[str], end_times: List[str]):
        print("TimerManager_init")

        self.__start_times = start_times
        self.__end_times = end_times

    def should_i_work_now(self) -> bool:
        print("TimerManager_should_i_work_now")
        return True


def get_backend_manager():
    with (
        patch.object(configmanager, "ConfigManager", Config),
        patch.object(timermanager, "TimerManager", MockedTimerManager),
        patch.object(intervalmanager, "IntervalManager", MockedIntervalManager),
    ):
        return BackendManager(event_mock, ".")
