import os
import sys

import pytest

from modules.pidmanager import PIDManager


@pytest.fixture
def pid_path(tmp_path):
    return str(tmp_path / "test_pid.pid")


def test_pid_manager_init(pid_path):
    pid_manager = PIDManager(path=pid_path)

    assert pid_manager.get_pid() == os.getpid()
    assert not os.path.exists(pid_path)


def test_pid_manager_read_empty(pid_path):
    pid_manager = PIDManager(path=pid_path)

    assert pid_manager.read() == 0


def test_pid_manager_save(pid_path):
    pid_manager = PIDManager(path=pid_path)
    pid_manager.save()

    with open(pid_path) as file:
        assert int(file.readline()) == os.getpid()


def test_pid_manager_read(pid_path):
    PIDManager(path=pid_path).save()

    assert PIDManager(path=pid_path).read() == os.getpid()


def test_pid_manager_read_corrupted(pid_path):
    with open(pid_path, "w") as file:
        file.write("not a pid")

    with pytest.raises(ValueError):
        PIDManager(path=pid_path).read()


def test_pid_manager_remove(pid_path):
    pid_manager = PIDManager(path=pid_path)
    pid_manager.save()
    pid_manager.remove()

    assert not os.path.exists(pid_path)


def test_pid_manager_remove_missing(pid_path):
    PIDManager(path=pid_path).remove()

    assert not os.path.exists(pid_path)


def test_pid_manager_get_name():
    name = PIDManager.get_pid_name(os.getpid()).decode()

    # the interpreter may be started with a relative path, so compare only the binary name
    assert os.path.basename(name.split()[0]) == os.path.basename(sys.executable)
