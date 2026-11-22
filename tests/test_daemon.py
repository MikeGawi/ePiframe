import os
import time
import pytest
from tests.helpers.helpers import remove_file

pid_filename = "tests/test_pid.pid"


def test_daemon_start():
    remove_file(pid_filename)
    os.popen(
        f"python {os.path.dirname(os.path.realpath(__file__))}/helpers/daemon_test.py start"
    )

    time.sleep(1)
    with open(pid_filename, "r") as file:
        file_pid = file.readline()

    assert file_pid
    pytest.pid = file_pid


def test_daemon_restart():
    os.popen(
        f"python {os.path.dirname(os.path.realpath(__file__))}/helpers/daemon_test.py restart"
    )

    time.sleep(1)
    with open(pid_filename, "r") as file:
        file_pid = file.readline()

    assert file_pid
    assert file_pid != pytest.pid


def test_daemon_stop():
    os.popen(
        f"python {os.path.dirname(os.path.realpath(__file__))}/helpers/daemon_test.py stop"
    )

    time.sleep(1)
    assert not os.path.exists(pid_filename)
