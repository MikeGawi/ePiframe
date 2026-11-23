import datetime
import os
from unittest.mock import patch

import pytest

from epiframe.config.paths import CONFIG_FILE, CONFIG_FILE_DEFAULT
from epiframe.config import manager as configmanager
from epiframe.core import interval as intervalmanager
from epiframe.core import schedule as timermanager
from epiframe.display import hdmi
from epiframe.plugins.manager import PluginManager
from modules.backendmanager import BackendManager
from tests.helpers.capturing import Capturing
from tests.helpers.config import Config
from tests.helpers.backend_doubles import (
    MockedIntervalManager,
    MockedTimerManager,
    event_mock,
    get_backend_manager,
)
from tests.helpers.helpers import not_raises, remove_file


def test_init():
    with (
        patch.object(configmanager, "ConfigManager", Config),
        patch.object(timermanager, "WeeklySchedule", MockedTimerManager),
        patch.object(intervalmanager, "IntervalMultiplier", MockedIntervalManager),
    ):
        with not_raises(Exception):
            BackendManager(event_mock, ".")


def test_last_date():
    manager = get_backend_manager()
    assert manager.get_last_date(CONFIG_FILE)


def test_get_path():
    manager = get_backend_manager()
    assert manager.get_path() == "."


def test_get_plugins():
    manager = get_backend_manager()
    assert isinstance(manager.get_plugins(), PluginManager)


def test_get_config():
    manager = get_backend_manager()
    assert str(type(manager.get_config())) == "<class 'tests.helpers.config.Config'>"


def test_refresh():
    with Capturing() as output:
        manager = get_backend_manager()
        manager.refresh()

    assert output == [
        "IntervalManager_init",
        "TimerManager_init",
        "IntervalManager_remove",
        "IntervalManager_read",
        "TimerManager_should_i_work_now",
    ]


def test_should_i_work_now():
    manager = get_backend_manager()
    assert manager.should_i_work_now() is True


def test_next_time():
    manager = get_backend_manager()
    next_update = datetime.datetime.now(
        datetime.datetime.now().astimezone().tzinfo
    ) + datetime.timedelta(seconds=600)
    assert (
        manager.next_time()
        == next_update.isoformat().replace("T", " at ").split(".")[0]
    )


def test_update_time():
    manager = get_backend_manager()
    with Capturing() as output:
        manager.update_time()

    assert output == [
        "IntervalManager_read",
        "TimerManager_should_i_work_now",
    ]


def test_fire_event():
    manager = get_backend_manager()
    with Capturing() as output:
        manager.fire_event()

    assert output == ["IntervalManager_remove", "Event triggered params=None"]


def test_next_photo():
    manager = get_backend_manager()
    with Capturing() as output:
        manager.next_photo()

    assert output == ["IntervalManager_remove", "Event triggered params='NOPARAMS'"]


def test_get_empty_params():
    manager = get_backend_manager()
    assert manager.get_empty_params() == "NOPARAMS"


def test_refresh_frame():
    manager = get_backend_manager()
    with Capturing() as output:
        manager.refresh_frame()

    assert output == [
        "IntervalManager_remove",
        "Event triggered params='--test-convert --test-display'",
    ]


def test_remove_interval():
    manager = get_backend_manager()
    with Capturing() as output:
        manager.remove_interval()

    assert output == [
        "IntervalManager_remove",
    ]


def test_get_interval():
    manager = get_backend_manager()
    with Capturing() as output:
        assert manager.get_interval() == 5

    assert output == [
        "IntervalManager_read",
    ]


def test_save_interval():
    manager = get_backend_manager()
    with Capturing() as output:
        manager.save_interval(5)

    assert output == [
        "IntervalManager_save interval=5",
    ]


def test_get_token():
    manager = get_backend_manager()
    assert manager.get_token() == "token"


def test_is_metric():
    manager = get_backend_manager()
    assert manager.is_metric() is True


def test_get_max_interval():
    manager = get_backend_manager()
    assert manager.get_max_interval() == 6


def test_is_interval_mult_enabled():
    manager = get_backend_manager()
    assert manager.is_interval_mult_enabled() is True


def test_triggers_enabled():
    manager = get_backend_manager()
    assert manager.triggers_enabled() is True


def test_pid_file_exists():
    manager = get_backend_manager()
    assert manager.pid_file_exists() is False


def test_get_download_file():
    manager = get_backend_manager()
    assert manager.get_download_file() == "tests/assets/waveshare"


def test_get_chat_id():
    manager = get_backend_manager()
    assert manager.get_chat_id() == "chats"


def test_get_slide_interval():
    manager = get_backend_manager()
    assert manager.get_slide_interval() == 600


def test_is_telebot_enabled():
    manager = get_backend_manager()
    assert manager.is_telebot_enabled() is True


def test_is_web_enabled():
    manager = get_backend_manager()
    assert manager.is_web_enabled() is True


def test_stats_enabled():
    manager = get_backend_manager()
    assert manager.stats_enabled() is True


def test_get_state_idle():
    manager = get_backend_manager()
    assert manager.get_state() == "Idle"


def test_get_state_busy():
    with (
        patch.object(configmanager, "ConfigManager", Config) as config,
        patch.object(timermanager, "WeeklySchedule", MockedTimerManager),
        patch.object(intervalmanager, "IntervalMultiplier", MockedIntervalManager),
        # Config.settings is shared by all tests, restore it
        patch.dict(Config.settings),
    ):
        manager = BackendManager(event_mock, ".")
        config.set("pid_file", CONFIG_FILE_DEFAULT)
        assert manager.get_state() == "Busy"


def test_get_service_state_not_running():
    manager = get_backend_manager()
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("")
        assert manager.get_service_state() == "Not running!"

    assert output == [
        "systemctl is-active --quiet ePiframe.service && echo Running 2> /dev/null"
    ]


def test_get_service_state_running():
    manager = get_backend_manager()
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("Running")
        assert manager.get_service_state() == "Running"

    assert output == [
        "systemctl is-active --quiet ePiframe.service && echo Running 2> /dev/null"
    ]


def test_get_uptime():
    manager = get_backend_manager()
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("")
        assert manager.get_uptime() == "-"

    assert output == ["uptime --pretty 2> /dev/null"]


def test_get_load():
    manager = get_backend_manager()
    with patch.object(os, "popen", mocked_system), Capturing() as output:
        MockRead.set("")
        assert manager.get_load() == "-"

    assert output == ['awk \'{print $1" "$2" "$3}\' /proc/loadavg 2> /dev/null']


def test_reboot():
    manager = get_backend_manager()
    with patch.object(os, "system", mocked_system), Capturing() as output:
        MockRead.set("")
        manager.reboot()

    assert output == ["sudo reboot"]


def test_restart():
    manager = get_backend_manager()
    with patch.object(os, "system", mocked_system), Capturing() as output:
        MockRead.set("")
        manager.restart()

    assert output == ["sudo systemctl restart ePiframe.service"]


def test_power_off():
    manager = get_backend_manager()
    with patch.object(os, "system", mocked_system), Capturing() as output:
        MockRead.set("")
        manager.power_off()

    assert output == ["sudo poweroff"]


def test_get_mem():
    manager = get_backend_manager()
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


@pytest.mark.parametrize("state, expected", [(True, "1"), (False, "0"), (None, "0")])
def test_get_display_power(state, expected):
    manager = get_backend_manager()
    with patch.object(hdmi.HdmiPower, "state", return_value=state):
        assert manager.get_display_power() == expected


@pytest.mark.parametrize("on_off", [True, False])
def test_display_power(on_off):
    manager = get_backend_manager()
    with patch.object(hdmi.HdmiPower, "set") as power:
        manager.display_power(on_off=on_off)

    power.assert_called_once_with(on_off)


@pytest.mark.parametrize(
    "display_type, control, calls",
    [("SPI", "1", []), ("HDMI", "0", []), ("HDMI", "1", [True]), ("hdmi", "1", [True])],
)
def test_display_power_config(display_type, control, calls):
    with (
        patch.object(configmanager, "ConfigManager", Config),
        patch.object(timermanager, "WeeklySchedule", MockedTimerManager),
        patch.object(intervalmanager, "IntervalMultiplier", MockedIntervalManager),
        patch.dict(
            Config.settings,
            {"display_type": display_type, "control_display_power": control},
        ),
    ):
        manager = BackendManager(event_mock, ".")
        with patch.object(hdmi.HdmiPower, "set") as power:
            manager.display_power_config(on_off=True)

    assert [call.args[0] for call in power.call_args_list] == calls


@pytest.mark.parametrize(
    "celsius, fahrenheit",
    [
        (0, "32.0"),
        (20, "68.0"),
        (37.8, "100.0"),
        ("abc", "-"),
    ],
)
def test_calc_to_f(celsius, fahrenheit):
    assert BackendManager.calc_to_f(celsius) == fahrenheit


def test_get_temp_c():
    with (
        patch.object(configmanager, "ConfigManager", Config) as config,
        patch.object(timermanager, "WeeklySchedule", MockedTimerManager),
        patch.object(intervalmanager, "IntervalMultiplier", MockedIntervalManager),
    ):
        manager = BackendManager(event_mock, ".")
        config.set("units", "metric")
        with patch.object(os, "popen", mocked_system), Capturing() as output:
            MockRead.set("temp=20'C")
            assert manager.get_temp() == "20\N{DEGREE SIGN}C"

    assert output == ["vcgencmd measure_temp 2> /dev/null"]


def test_get_temp_f():
    with (
        patch.object(configmanager, "ConfigManager", Config) as config,
        patch.object(timermanager, "WeeklySchedule", MockedTimerManager),
        patch.object(intervalmanager, "IntervalMultiplier", MockedIntervalManager),
    ):
        manager = BackendManager(event_mock, ".")
        config.set("units", "imperial")
        with patch.object(os, "popen", mocked_system), Capturing() as output:
            MockRead.set("temp=20'C")
            assert manager.get_temp() == "68.0\N{DEGREE SIGN}F"

    assert output == ["vcgencmd measure_temp 2> /dev/null"]


def test_get_next_time_short():
    manager = get_backend_manager()
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
    manager = get_backend_manager()
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
    manager = get_backend_manager()
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
    manager = get_backend_manager()
    assert manager.get_original_file() == "tests/assets/waveshare.bmp"


def test_get_current_file():
    manager = get_backend_manager()
    assert manager.get_current_file() == "tests/assets/waveshare.bmp"


def test_get_filename_if_exists_ok():
    manager = get_backend_manager()
    assert (
        manager.get_filename_if_exists("photo_convert_filename")
        == "tests/assets/waveshare.bmp"
    )


def test_get_filename_if_exists_nok():
    manager = get_backend_manager()
    assert manager.get_filename_if_exists("pid_file") == ""


def test_get_filename_modification_time_if_exists_ok():
    manager = get_backend_manager()
    assert (
        manager.get_filename_modification_time_if_exists("photo_convert_filename") > 0
    )


def test_get_filename_modification_time_if_exists_nok():
    manager = get_backend_manager()
    assert manager.get_filename_modification_time_if_exists("pid_file") == 0
    remove_file("log.test")


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
