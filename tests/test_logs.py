import glob
import logging
import os
import re
import time
from logging.handlers import TimedRotatingFileHandler
from misc.logs import Logs
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import remove_file

filename = "test_log.log"


def test_show_log():
    message = "This is log message"
    with Capturing() as output:
        Logs.show_log(message)

    assert "".join(output)
    assert message in "".join(output)


def test_execution_time():
    start = Logs.start_time()
    time.sleep(1)
    end = Logs.end_time()

    assert start != end
    execution_time = Logs.execution_time(start, end)
    assert execution_time
    assert re.match("^ \\d{2}:\\d{2}:\\d{2}$", execution_time)


def test_logs():
    remove_file(filename)
    logger = Logs(filename)

    assert os.path.exists(filename)
    message = "This is log message"
    with Capturing() as output:
        logger.log(message, True)

    assert not "".join(output)
    with open(filename, "r") as file:
        assert message in file.readline()
    remove_file(filename)


def test_logs_silent():
    remove_file(filename)
    logger = Logs(filename)

    assert os.path.exists(filename)
    message = "This is log message"
    with Capturing() as output:
        logger.log(message)

    assert "".join(output)
    assert message in "".join(output)
    with open(filename, "r") as file:
        assert message in file.readline()
    remove_file(filename)


def test_empty_logs():
    remove_file(filename)
    logger = Logs("")

    assert not os.path.exists(filename)
    message = "This is log message"
    with Capturing() as output:
        logger.log(message)

    assert "".join(output)
    assert message in "".join(output)


def test_logs_rotation():
    remove_file(filename)

    handler = TimedRotatingFileHandler(filename, when="S", interval=1, backupCount=6)
    logger = Logs(filename)
    log = logging.getLogger("ePiframe")
    handler.rotator = log.handlers[0].rotator
    handler.namer = log.handlers[0].namer
    log.handlers[0] = handler

    message = "This is log message"
    logger.log(message)
    with open(filename, "r") as file:
        assert message in file.readline()

    time.sleep(2)

    new_message = "This is new log message"
    logger.log(new_message)
    with open(filename, "r") as file:
        assert new_message in file.readline()

    remove_file(filename)
    for file in glob.glob(f"{filename}.*.gz"):
        os.remove(file)
