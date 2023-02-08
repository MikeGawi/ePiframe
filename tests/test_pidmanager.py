import os.path
import sys
import pytest
from modules.pidmanager import PIDManager
from tests.helpers.helpers import remove_file

pid_filename = "test_pid.pid"


def test_pid_manager_init():
    remove_file(pid_filename)
    pid_manager = PIDManager(path=pid_filename)
    pytest.pid = pid_manager.get_pid()

    assert pytest.pid
    pid_manager.remove()


def test_pid_manager_read_empty():
    pid_manager = PIDManager(path=pid_filename)
    pid = pid_manager.read()

    assert pid == 0


def test_pid_manager_save():
    pid_manager = PIDManager(path=pid_filename)
    pid = pid_manager.get_pid()

    assert pytest.pid == pid

    pid_manager.save()
    with open(pid_filename, "r") as file:
        pid = file.readline()

    assert pytest.pid == int(pid)


def test_pid_manager_read():
    pid_manager = PIDManager(path=pid_filename)
    pid = pid_manager.read()

    assert pytest.pid == pid


def test_pid_manager_remove():
    pid_manager = PIDManager(path=pid_filename)
    pid_manager.remove()

    assert not os.path.exists(pid_filename)


def test_pid_manager_get_name():
    name = PIDManager.get_pid_name(pytest.pid)

    assert name.decode() == f"{sys.executable} {sys.argv[0]}\n"
