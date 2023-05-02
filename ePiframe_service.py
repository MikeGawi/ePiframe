#!/usr/bin/env python3

import sys
import time
import sched
import os
import signal
import subprocess
from threading import Thread
from misc.daemon import Daemon
from misc.constants import Constants
import modules.backendmanager as backend
from modules.telebotmanager import TelebotManager
from modules.webuimanager import WebUIManager
from modules.statsmanager import StatsManager


class Service(Daemon):
    __config_path = os.path.dirname(os.path.realpath(__file__))
    __script = [
        sys.executable,
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "ePiframe.py"),
    ]

    __telebot: TelebotManager = None
    __web_man: WebUIManager = None
    __stats_man: StatsManager = None
    __telebot_thread: Thread = None
    __web_thread: Thread = None
    __stats_thread: Thread = None
    __event: sched.Event = None
    __plugin_threads = []
    __backend: backend.BackendManager = None
    __scheduler: sched.scheduler = None

    __SERVICE_LOG_IND = "--------ePiframe Service: "
    __SERVICE_LOG_STARTED = __SERVICE_LOG_IND + "STARTED"
    __SERVICE_TRIGGER = __SERVICE_LOG_IND + "Activity triggered"
    __SERVICE_LOG_STARTING = __SERVICE_LOG_IND + "Starting ePiframe script"
    __SERVICE_LOG_SLEEPING = __SERVICE_LOG_IND + "Off hours - sleeping"
    __SERVICE_LOG_MULT = __SERVICE_LOG_IND + "Interval multiplication for current photo"
    __SERVICE_LOG_NEXT = __SERVICE_LOG_IND + "Next update scheduled at {}"

    __SERVICE_WEB_START = __SERVICE_LOG_IND + "Starting ePiframe WebUI server"
    __SERVICE_TGBOT_START = __SERVICE_LOG_IND + "Starting Telegram Bot"

    __INITIAL_EVENT_TIME = 10
    __WAIT_EVENT_TIME = 60

    __EVENT_PRIORITY = 1
    __NUMBER_OF_NOTIF = 0

    __ERROR_TELE_BOT = "Error configuring Telegram Bot! {}"
    __ERROR_WEB = "Error configuring WebUI! {}"
    __ERROR_STATS = "Error getting statistics! {}"

    __WEB_ARG = "web"
    __TGBOT_ARG = "telegram"

    def run(self, args=None):
        self.__backend = backend.BackendManager(self.restart, self.__config_path)
        self.__backend.log(self.__SERVICE_LOG_STARTED, silent=True)

        self.__scheduler = sched.scheduler(time.time, time.sleep)
        self.__event = self.__scheduler.enter(
            self.__INITIAL_EVENT_TIME, self.__EVENT_PRIORITY, self.task
        )
        self.__run_telebot(args)
        self.__run_web_threads(args)
        self.__run_plugins()
        self.__run_scheduler(args)

        while True:
            time.sleep(self.__WAIT_EVENT_TIME)

    def __run_telebot(self, args):
        if not args or (args and args == self.__TGBOT_ARG):
            self.__telebot_thread = Thread(target=self.telebot_thread)
            self.__telebot_thread.start()

    def __run_web_threads(self, args):
        if not args or (args and args == self.__WEB_ARG):
            self.__stats_thread = Thread(target=self.stats_thread)
            self.__stats_thread.start()
            self.__web_thread = Thread(target=self.web_thread)
            self.__web_thread.start()

    def __run_plugins(self):
        for plug in self.__backend.get_plugins().plugin_service_thread():
            thread = Thread(
                target=plug.add_service_thread,
                args=(
                    self,
                    self.__backend,
                ),
            )
            self.__plugin_threads.append(thread)
            thread.start()

    def __run_scheduler(self, args):
        if not args:
            self.__scheduler.run()

    def stats_thread(self):
        self.__stats_man = StatsManager(self.__backend)
        while True:
            self.__backend.refresh()
            if self.__backend.is_web_enabled() and self.__backend.stats_enabled():
                try:
                    self.__stats_man.feed_stats()
                except Exception as exception:
                    self.__backend.log(
                        self.__ERROR_STATS.format(exception), silent=True
                    )
                    pass

            time.sleep(Constants.STATS_STEP)

    def web_thread(self):
        while True:
            self.__backend.refresh()
            if self.__backend.is_web_enabled():
                try:
                    self.__backend.log(self.__SERVICE_WEB_START, silent=True)
                    self.__web_man = WebUIManager(self.__backend)
                    self.__web_man.start()
                except Exception as exception:
                    self.__backend.log(self.__ERROR_WEB.format(exception), silent=True)
                    pass

            time.sleep(self.__WAIT_EVENT_TIME)

    def telebot_thread(self):
        while True:
            self.__backend.refresh()
            if self.__backend.is_telebot_enabled():
                try:
                    self.__backend.log(self.__SERVICE_TGBOT_START, silent=True)
                    self.__telebot = TelebotManager(self.__backend)
                    self.__telebot.start()
                except Exception as e:
                    self.__backend.log(self.__ERROR_TELE_BOT.format(e), silent=True)
                    pass

            time.sleep(self.__WAIT_EVENT_TIME)

    def restart(self, params=None):
        self.__backend.log(self.__SERVICE_TRIGGER, silent=True)
        if self.__scheduler and self.__event:
            self.__scheduler.cancel(self.__event)
        self.task(params)

    def task(self, params=None):
        self.__backend.refresh()
        interval: int = -1
        sleep = False

        if self.__backend.is_interval_mult_enabled():
            interval = self.__control_interval(interval)

        if interval < 0 or params:
            sleep = self.__work(params, sleep)

        frame_time = (
            self.__backend.get_slide_interval() if not sleep else self.__WAIT_EVENT_TIME
        )
        self.__backend.update_time()
        self.__log_next(sleep)
        self.__event = self.__scheduler.enter(
            frame_time, self.__EVENT_PRIORITY, self.task
        )

    def __log_next(self, sleep):
        if not sleep:
            self.__backend.log(
                self.__SERVICE_LOG_NEXT.format(self.__backend.next_time()), silent=True
            )

    def __work(self, params, sleep):
        if self.__backend.should_i_work_now() or (
            params and self.__backend.triggers_enabled()
        ):
            self.__do_work(params)
        else:
            sleep = self.__no_work(sleep)
        return sleep

    def __do_work(self, params):
        self.__NUMBER_OF_NOTIF = 0
        self.__backend.log(self.__SERVICE_LOG_STARTING, silent=True)
        self.__backend.display_power_config(True)
        par = params if params != self.__backend.get_empty_params() else str()
        args = (self.__script + par.split()) if par else self.__script
        subprocess.Popen(args)

    def __no_work(self, sleep):
        self.__backend.display_power_config(False)
        if self.__NUMBER_OF_NOTIF == 0:
            self.__backend.log(self.__SERVICE_LOG_SLEEPING, silent=True)
        self.__NUMBER_OF_NOTIF = (self.__NUMBER_OF_NOTIF + 1) % 10
        sleep = True
        return sleep

    def __control_interval(self, interval):
        try:
            interval = self.__backend.get_interval()
        except Exception:
            pass
        if interval > 0:
            interval -= 1
            self.__backend.save_interval(interval)
            self.__backend.log(self.__SERVICE_LOG_MULT, silent=True)
        else:
            self.__backend.remove_interval()
            interval = -1
        return interval


def control():
    if len(sys.argv) >= 2 and "--help" not in [arg.lower() for arg in sys.argv]:
        process_command()
        sys.exit(0)
    else:
        print_help()


def process_command():
    if "start" == sys.argv[1]:
        start()
    elif "stop" == sys.argv[1]:
        daemon.stop()
    elif "restart" == sys.argv[1]:
        daemon.restart()
    else:
        print("Unknown command")
        sys.exit(2)


def print_help():
    print("ePiframe daemon service")
    print("usage: %s start|stop|restart [service]" % sys.argv[0])
    print("	service  	start only particular service (i.e. web or telegram)")
    print("			services must be enabled in configuration!")
    print(
        "for web: any port number below 5000 needs root privileges to be possible to assign (use sudo "
        "./ePiframe_service.py ... "
    )
    print("")
    print("")
    print("Use --debug at the end for debugger info")
    sys.exit(2)


def start():
    process = subprocess.Popen(["ps", "-efa"], stdout=subprocess.PIPE)
    process.wait()
    out, error = process.communicate()
    if out:
        process_lines(out)
    daemon.start(
        check(),
        "--debug" in [arg.lower() for arg in sys.argv],
    )


def check():
    return (
        "web"
        if "web" in [arg.lower() for arg in sys.argv]
        else "telegram"
        if "telegram" in [arg.lower() for arg in sys.argv]
        else str()
    )


def process_lines(out):
    for line in out.splitlines():
        if str(os.path.basename(__file__)) in str(line):
            kill_pid(line)


def kill_pid(line):
    pid = int(line.split()[1])
    if not pid == os.getpid():
        os.kill(pid, signal.SIGKILL)


if __name__ == "__main__":
    daemon = Service(
        "/tmp/ePiframe-service.pid", os.path.dirname(os.path.realpath(__file__))
    )

    control()
