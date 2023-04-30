import os.path
from modules.intervalmanager import IntervalManager
from tests.helpers.helpers import remove_file

interval_filename = "test_interval.interval"
interval_test = 111
hot_word = "hot_word"
interval = f"{hot_word} {interval_test}"


def test_interval_manager_read_empty():
    remove_file(interval_filename)
    interval_manager = IntervalManager(interval_filename)

    assert interval_manager.read() == -1


def test_interval_manager_save():
    interval_manager = IntervalManager(interval_filename)
    interval_manager.save(interval_test)

    assert interval_manager.read() == interval_test


def test_interval_manager_save_interval_min():
    interval_manager = IntervalManager(interval_filename)
    interval_manager.save_interval(interval, hot_word, interval_test)
    assert interval_manager.read() == interval_test


def test_interval_manager_save_interval_max():
    interval_manager = IntervalManager(interval_filename)
    interval_manager.save_interval(interval, hot_word, interval_test - 10)
    assert interval_manager.read() == interval_test - 10


def test_interval_manager_remove():
    interval_manager = IntervalManager(interval_filename)
    interval_manager.remove()

    assert not os.path.exists(interval_filename)


def test_interval_manager_wrong_hot_word():
    interval_manager = IntervalManager(interval_filename)
    interval_manager.remove()
    interval_manager.save_interval(interval, "not_existing_hot_word", interval_test)

    interval_manager = IntervalManager(interval_filename)

    assert interval_manager.read() == -1
    assert not os.path.exists(interval_filename)
