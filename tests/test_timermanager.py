from datetime import datetime, timedelta
import pytest
from tests.helpers.helpers import not_raises
from modules.timermanager import TimerManager


def test_get_time_ok():
    with not_raises(Exception):
        TimerManager.get_time_from_string("01:59")


def test_get_time_nok():
    with pytest.raises(Exception):
        TimerManager.get_time_from_string("01:59:11")


def test_verify_times_ok():
    start_times = "5:30,5:30,5:30,5:30,5:30,5:30,5:30"
    stop_times = "23:30,23:30,23:30,23:30,23:30,23:30,23:30"

    with not_raises(Exception):
        TimerManager.verify([start_times, stop_times])


def test_verify_times_nok():
    start_times = "5:30,5:30,5:30,5:30,5:30,5:30,5:30"
    stop_times = "23:30,23:30,23:30,23:30,23:30,23:30,23:30"

    with pytest.raises(Exception) as exception:
        TimerManager.verify([stop_times, start_times])
        assert (
            str(exception)
            == "Configuration start_times times are older than stop_times!"
        )


def test_should_i_work_ok():
    now = datetime.now()
    ago = now - timedelta(minutes=10)
    future = now + timedelta(minutes=10)
    start_times = [ago.strftime("%H:%M")] * 7
    stop_times = [future.strftime("%H:%M")] * 7
    timer_manager = TimerManager(start_times, stop_times)
    assert timer_manager.should_i_work_now() is True


def test_should_i_work_nok():
    now = datetime.now()
    ago = now - timedelta(minutes=10)
    future = now + timedelta(minutes=10)
    start_times = [ago.strftime("%H:%M")] * 7
    stop_times = [future.strftime("%H:%M")] * 7
    timer_manager = TimerManager(stop_times, start_times)
    assert timer_manager.should_i_work_now() is False


def test_should_i_work_mark():
    times = ["-"] * 7
    timer_manager = TimerManager(times, times)
    assert timer_manager.should_i_work_now() is False


def test_when_i_work_ok():
    now = datetime.now()
    next_time = now + timedelta(minutes=10)
    future = now + timedelta(minutes=20)
    start_times = [next_time.strftime("%H:%M")] * 7
    stop_times = [future.strftime("%H:%M")] * 7
    timer_manager = TimerManager(start_times, stop_times)
    work_next = timer_manager.when_i_work_next()
    assert work_next.strftime("%H:%M") == next_time.strftime("%H:%M")
    assert work_next.day == next_time.day
    assert work_next.year == next_time.year
    assert work_next.month == next_time.month
    assert work_next.hour == next_time.hour
    assert work_next.minute == next_time.minute


def test_when_i_work_nok():
    times = ["-"] * 7
    timer_manager = TimerManager(times, times)
    with pytest.raises(Exception) as exception:
        timer_manager.when_i_work_next()
        assert str(exception) == "OverflowError: date value out of range"


def test_when_i_work_mark():
    now = datetime.now()
    day_of_week = now.weekday()
    next_time = now + timedelta(minutes=10)
    start_times = ["-"] * 7
    stop_times = ["-"] * 7
    start_times[day_of_week + 2] = next_time.strftime("%H:%M")
    timer_manager = TimerManager(start_times, stop_times)
    work_next = timer_manager.when_i_work_next()
    assert work_next.strftime("%H:%M") == next_time.strftime("%H:%M")
    assert (work_next.replace(tzinfo=None) - next_time.replace(tzinfo=None)).days == 2
