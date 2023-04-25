import datetime
import os
from typing import List
from unittest.mock import patch

import pytest

from misc.constants import Constants
from modules import configmanager, timermanager, intervalmanager
from modules.backendmanager import BackendManager
from tests.helpers.capturing import Capturing
from tests.helpers.config import Config
from tests.helpers.helpers import not_raises, remove_file


def test_init():
    with patch.object(configmanager, "ConfigManager", Config), patch.object(
        timermanager, "TimerManager", MockedTimerManager
    ), patch.object(intervalmanager, "IntervalManager", MockedIntervalManager):
        with not_raises(Exception):
            BackendManager(event_mock, ".")


def test_last_date():
    manager = get_manager()
    assert manager.get_last_date(Constants.CONFIG_FILE)


def test_get_path():
    manager = get_manager()
    assert manager.get_path() == "."


def test_get_plugins():
    manager = get_manager()
    assert (
        str(type(manager.get_plugins()))
        == "<class 'modules.pluginsmanager.PluginsManager'>"
    )


def test_get_config():
    manager = get_manager()
    assert str(type(manager.get_config())) == "<class 'tests.helpers.config.Config'>"


def test_refresh():
    with Capturing() as output:
        manager = get_manager()
        manager.refresh()

    assert output == [
        "IntervalManager_init",
        "TimerManager_init",
        "IntervalManager_remove",
        "IntervalManager_read",
        "TimerManager_should_i_work_now",
    ]


def test_log():
    remove_file("log.test")
    message = "test_message"
    manager = get_manager()
    manager.log(message, True)

    with open("log.test", "r") as file:
        assert message in file.readline()


def test_should_i_work_now():
    manager = get_manager()
    assert manager.should_i_work_now() is True


def test_next_time():
    manager = get_manager()
    next_update = datetime.datetime.now(
        datetime.datetime.now().astimezone().tzinfo
    ) + datetime.timedelta(seconds=600)
    assert (
        manager.next_time()
        == next_update.isoformat().replace("T", " at ").split(".")[0]
    )


def test_update_time():
    manager = get_manager()
    with Capturing() as output:
        manager.update_time()

    assert output == [
        "IntervalManager_read",
        "TimerManager_should_i_work_now",
    ]


def test_fire_event():
    manager = get_manager()
    with Capturing() as output:
        manager.fire_event()

    assert output == ["IntervalManager_remove", "Event triggered params=None"]


def test_next_photo():
    manager = get_manager()
    with Capturing() as output:
        manager.next_photo()

    assert output == ["IntervalManager_remove", "Event triggered params='NOPARAMS'"]


def test_get_empty_params():
    manager = get_manager()
    assert manager.get_empty_params() == "NOPARAMS"


def test_refresh_frame():
    manager = get_manager()
    with Capturing() as output:
        manager.refresh_frame()

    assert output == [
        "IntervalManager_remove",
        "Event triggered params='--test-convert --test-display'",
    ]


def test_remove_interval():
    manager = get_manager()
    with Capturing() as output:
        manager.remove_interval()

    assert output == [
        "IntervalManager_remove",
    ]


def test_get_interval():
    manager = get_manager()
    with Capturing() as output:
        assert manager.get_interval() == 5

    assert output == [
        "IntervalManager_read",
    ]


def test_save_interval():
    manager = get_manager()
    with Capturing() as output:
        manager.save_interval(5)

    assert output == [
        "IntervalManager_save interval=5",
    ]


def test_get_token():
    manager = get_manager()
    assert manager.get_token() == "token"


def test_is_metric():
    manager = get_manager()
    assert manager.is_metric() is True


def test_get_max_interval():
    manager = get_manager()
    assert manager.get_max_interval() == 6


def test_is_interval_mult_enabled():
    manager = get_manager()
    assert manager.is_interval_mult_enabled() is True


def test_triggers_enabled():
    manager = get_manager()
    assert manager.triggers_enabled() is True


def test_pid_file_exists():
    manager = get_manager()
    assert manager.pid_file_exists() is False


def test_get_download_file():
    manager = get_manager()
    assert manager.get_download_file() == "tests/assets/waveshare"


def test_get_chat_id():
    manager = get_manager()
    assert manager.get_chat_id() == "chats"


def test_get_slide_interval():
    manager = get_manager()
    assert manager.get_slide_interval() == 600


def test_is_telebot_enabled():
    manager = get_manager()
    assert manager.is_telebot_enabled() is True


def test_is_web_enabled():
    manager = get_manager()
    assert manager.is_web_enabled() is True


def test_stats_enabled():
    manager = get_manager()
    assert manager.stats_enabled() is True


def test_get_state_idle():
    manager = get_manager()
    assert manager.get_state() == "Idle"


def test_get_state_busy():
    with patch.object(configmanager, "ConfigManager", Config) as config, patch.object(
        timermanager, "TimerManager", MockedTimerManager
    ), patch.object(intervalmanager, "IntervalManager", MockedIntervalManager):
        manager = BackendManager(event_mock, ".")
        config.set("pid_file", Constants.CONFIG_FILE_DEFAULT)
        assert manager.get_state() == "Busy"


def test_get_service_state_not_running():
    manager = get_manager()
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("")
        assert manager.get_service_state() == "Not running!"

    assert output == [
        "systemctl is-active --quiet ePiframe.service && echo Running 2> /dev/null"
    ]


def test_get_service_state_running():
    manager = get_manager()
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("Running")
        assert manager.get_service_state() == "Running"

    assert output == [
        "systemctl is-active --quiet ePiframe.service && echo Running 2> /dev/null"
    ]


def test_get_uptime():
    manager = get_manager()
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("")
        assert manager.get_uptime() == "-"

    assert output == ["uptime --pretty 2> /dev/null"]


def test_get_load():
    manager = get_manager()
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("")
        assert manager.get_load() == "-"

    assert output == ['awk \'{print $1" "$2" "$3}\' /proc/loadavg 2> /dev/null']


def test_reboot():
    manager = get_manager()
    with patch.object(os, "system", mocked_system), Capturing() as output:
        MockRead.set("")
        manager.reboot()

    assert output == ["sudo reboot"]


def test_restart():
    manager = get_manager()
    with patch.object(os, "system", mocked_system), Capturing() as output:
        MockRead.set("")
        manager.restart()

    assert output == ["sudo systemctl restart ePiframe.service"]


def test_power_off():
    manager = get_manager()
    with patch.object(os, "system", mocked_system), Capturing() as output:
        MockRead.set("")
        manager.power_off()

    assert output == ["sudo poweroff"]


def test_get_mem():
    manager = get_manager()
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("")
        assert manager.get_mem() == "-"

    assert output == [
        "awk '/MemAvailable/{free=$2} /MemTotal/{total=$2} END{print int(100-(free*100)/total)}' /proc/meminfo 2> "
        "/dev/null "
    ]


def test_start_system_command():
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("returned_value")
        assert BackendManager.start_system_command("command") == "returned_value"

    assert output == ["command"]


def test_get_display_power_on():
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("display_power=1")
        assert BackendManager.get_display_power() == "1"

    assert output == ["sudo vcgencmd display_power  2> /dev/null"]


def test_get_display_power_off():
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("display_power=0")
        assert BackendManager.get_display_power() == "0"

    assert output == ["sudo vcgencmd display_power  2> /dev/null"]


def test_get_display_power_none():
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("")
        assert BackendManager.get_display_power() == "0"

    assert output == ["sudo vcgencmd display_power  2> /dev/null"]


def test_display_power_on():
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("")
        BackendManager.display_power(on_off=True)

    assert output == ["sudo vcgencmd display_power 1 2> /dev/null"]


def test_display_power_off():
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("")
        BackendManager.display_power(on_off=False)

    assert output == ["sudo vcgencmd display_power 0 2> /dev/null"]


def test_display_power_config_spi():
    with patch.object(configmanager, "ConfigManager", Config) as config, patch.object(
        timermanager, "TimerManager", MockedTimerManager
    ), patch.object(intervalmanager, "IntervalManager", MockedIntervalManager):
        manager = BackendManager(event_mock, ".")
        config.set("display_type", "SPI")
        with patch.object(os, "popen", mocked_system), Capturing() as output:
            MockRead.set("")
            manager.display_power_config(on_off=True)

    assert output == []


def test_display_power_config_on():
    with patch.object(configmanager, "ConfigManager", Config) as config, patch.object(
        timermanager, "TimerManager", MockedTimerManager
    ), patch.object(intervalmanager, "IntervalManager", MockedIntervalManager):
        manager = BackendManager(event_mock, ".")
        config.set("display_type", "HDMI")
        with patch.object(os, "popen", mocked_system), Capturing() as output:
            MockRead.set("")
            manager.display_power_config(on_off=True)

    assert output == ["sudo vcgencmd display_power 1 2> /dev/null"]


def test_display_power_config_off():
    with patch.object(configmanager, "ConfigManager", Config) as config, patch.object(
        timermanager, "TimerManager", MockedTimerManager
    ), patch.object(intervalmanager, "IntervalManager", MockedIntervalManager):
        manager = BackendManager(event_mock, ".")
        config.set("display_type", "HDMI")
        with patch.object(os, "popen", mocked_system), Capturing() as output:
            MockRead.set("")
            manager.display_power_config(on_off=False)

    assert output == ["sudo vcgencmd display_power 0 2> /dev/null"]


def get_manager():
    with patch.object(configmanager, "ConfigManager", Config), patch.object(
        timermanager, "TimerManager", MockedTimerManager
    ), patch.object(intervalmanager, "IntervalManager", MockedIntervalManager):
        return BackendManager(event_mock, ".")


@pytest.mark.parametrize(
    "celcius, fahrenheit",
    [
        (0, "32.0"),
        (20, "68.0"),
        (37.8, "100.0"),
        ("abc", "-"),
    ],
)
def test_calc_to_f(celcius, fahrenheit):
    assert BackendManager.calc_to_f(celcius) == fahrenheit


def test_get_temp_c():
    with patch.object(configmanager, "ConfigManager", Config) as config, patch.object(
        timermanager, "TimerManager", MockedTimerManager
    ), patch.object(intervalmanager, "IntervalManager", MockedIntervalManager):
        manager = BackendManager(event_mock, ".")
        config.set("units", "metric")
        with patch.object(os, "popen", mocked_system), Capturing() as output:
            MockRead.set("temp=20'C")
            assert manager.get_temp() == "20\N{DEGREE SIGN}C"

    assert output == ["vcgencmd measure_temp 2> /dev/null"]


def test_get_temp_f():
    with patch.object(configmanager, "ConfigManager", Config) as config, patch.object(
        timermanager, "TimerManager", MockedTimerManager
    ), patch.object(intervalmanager, "IntervalManager", MockedIntervalManager):
        manager = BackendManager(event_mock, ".")
        config.set("units", "imperial")
        with patch.object(os, "popen", mocked_system), Capturing() as output:
            MockRead.set("temp=20'C")
            assert manager.get_temp() == "68.0\N{DEGREE SIGN}F"

    assert output == ["vcgencmd measure_temp 2> /dev/null"]


def test_get_next_time_short():
    manager = get_manager()
    manager.update_time()
    next_update = datetime.datetime.now(
        datetime.datetime.now().astimezone().tzinfo
    ) + datetime.timedelta(seconds=600 * 5)
    delta = next_update - datetime.datetime.now(
        datetime.datetime.now().astimezone().tzinfo
    )
    period = manager.get_period(delta, "in {m} mins {s} secs")
    time = "at " + next_update.isoformat().split("T")[1].split(".")[0]
    get_next_time = manager.get_next_time()
    assert time in get_next_time
    assert period in get_next_time


def test_get_next_time_longer():
    manager = get_manager()
    MockedIntervalManager.set_interval(55)
    manager.update_time()
    next_update = datetime.datetime.now(
        datetime.datetime.now().astimezone().tzinfo
    ) + datetime.timedelta(seconds=600 * 55)
    delta = next_update - datetime.datetime.now(
        datetime.datetime.now().astimezone().tzinfo
    )
    period = manager.get_period(delta, "in {h} hours {m} mins {s} secs")
    time = "at " + next_update.isoformat().split("T")[1].split(".")[0]
    get_next_time = manager.get_next_time()
    assert time in get_next_time
    assert period in get_next_time


def test_get_next_time_longest():
    manager = get_manager()
    MockedIntervalManager.set_interval(555)
    manager.update_time()
    next_update = datetime.datetime.now(
        datetime.datetime.now().astimezone().tzinfo
    ) + datetime.timedelta(seconds=600 * 555)
    delta = next_update - datetime.datetime.now(
        datetime.datetime.now().astimezone().tzinfo
    )
    period = manager.get_period(delta, "in {d} days {h} hours {m} mins {s} secs")
    time = "at " + next_update.isoformat().split("T")[1].split(".")[0]
    get_next_time = manager.get_next_time()
    assert time in get_next_time
    assert period in get_next_time


def test_get_original_file():
    manager = get_manager()
    assert manager.get_original_file() == "tests/assets/waveshare.bmp"


def test_get_current_file():
    manager = get_manager()
    assert manager.get_current_file() == "tests/assets/waveshare.bmp"


def test_get_filename_if_exists_ok():
    manager = get_manager()
    assert (
        manager.get_filename_if_exists("photo_convert_filename")
        == "tests/assets/waveshare.bmp"
    )


def test_get_filename_if_exists_nok():
    manager = get_manager()
    assert manager.get_filename_if_exists("pid_file") == ""


def test_get_filename_modification_time_if_exists_ok():
    manager = get_manager()
    assert (
        manager.get_filename_modification_time_if_exists("photo_convert_filename") > 0
    )


def test_get_filename_modification_time_if_exists_nok():
    manager = get_manager()
    assert manager.get_filename_modification_time_if_exists("pid_file") == 0
    remove_file("log.test")


def event_mock(params):
    print(f"Event triggered {params=}")


class MockRead:

    text = ""

    def read(self):
        return self.text

    @classmethod
    def set(cls, text):
        cls.text = text


def mocked_system(*args, **kwargs):
    print("".join(args) + "".join(kwargs))
    return MockRead()


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

    def save_interval(self, interval: str, hot_word: str, max_value: int):
        print(f"IntervalManager_save_interval {interval=} {hot_word=} {max_value=}")


class MockedTimerManager:
    def __init__(self, start_times: List[str], end_times: List[str]):
        print("TimerManager_init")

        self.__start_times = start_times
        self.__end_times = end_times

    def should_i_work_now(self) -> bool:
        print("TimerManager_should_i_work_now")
        return True

    def when_i_work_next(self) -> datetime:
        print("TimerManager_when_i_work_next")
        return datetime.datetime.now()
