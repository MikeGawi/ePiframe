#!/usr/bin/env python3
import os
import sys
import time

sys.path.append(f"{os.path.dirname(os.path.realpath(__file__))}/../../")
from misc.daemon import Daemon


class DaemonTest(Daemon):
    def run(self, args=None):
        time.sleep(10)


if __name__ == "__main__":
    daemon = DaemonTest(
        f"{os.path.dirname(os.path.realpath(__file__))}/../test_pid.pid",
        f"{os.path.dirname(os.path.realpath(__file__))}",
    )

    if "start" == sys.argv[1]:
        daemon.start()
    elif "stop" == sys.argv[1]:
        daemon.stop()
    elif "restart" == sys.argv[1]:
        daemon.restart()
