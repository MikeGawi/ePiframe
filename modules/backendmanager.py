import glob
import os
from datetime import datetime, timedelta

import modules.configmanager as configuration_manager
import modules.intervalmanager as interval_manager
import modules.pidmanager as pid_manager
import modules.pluginsmanager as plugins_manager
import modules.timermanager as timer_manager
from misc.constants import Constants
from misc.logs import Logs
from misc.tools import Tools
from modules.displaymanager import DisplayManager
from modules.weathermanager import WeatherManager


class BackendManager:

    __REBOOT_OS_CMD = "sudo reboot"
    __POWER_OFF_OS_CMD = "sudo poweroff"
    __RESTART_OS_CMD = "sudo systemctl restart ePiframe.service"
    __SERVICE_RUN_CMD = (
        "systemctl is-active --quiet ePiframe.service && echo Running 2> /dev/null"
    )
    __UPTIME_CMD = "uptime --pretty 2> /dev/null"
    __LOAD_CMD = 'awk \'{print $1" "$2" "$3}\' /proc/loadavg 2> /dev/null'
    __MEM_CMD = (
        "awk '/MemAvailable/{free=$2} /MemTotal/{total=$2} END{print int(100-(free*100)/total)}' /proc/meminfo "
        "2> /dev/null "
    )
    __TEMP_CMD = "vcgencmd measure_temp 2> /dev/null"
    __NEXT_TIME_FORMAT = "in {d} days {h} hours {m} mins {s} secs"

    __ERROR_CONF_FILE = "Error loading {} configuration file! {}"

    __IDLE_STATE = "Idle"
    __BUSY_STATE = "Busy"
    __NOT_RUNNING = "Not running!"
    __NOTHING = "-"

    __REFRESH_PARAMS = "--test-convert --test-display"
    __EMPTY_PARAMS = "NOPARAMS"

    __next_time: datetime

    def __init__(self, event, path: str):
        self.__event = event
        self.__path = path
        self.__last_date = None
        self.__load_config()
        self.__interval = interval_manager.IntervalManager(
            self.__config.get("interval_mult_file")
        )
        self.__timer = timer_manager.TimerManager(
            self.__config.get("start_times").split(","),
            self.__config.get("stop_times").split(","),
        )
        self.remove_interval()
        self.update_time()
        self.__logging = Logs(self.__config.get("log_files"))
        self.__plugins = plugins_manager.PluginsManager(
            self.__path,
            pid_manager.PIDManager(self.__config.get("pid_file")),
            self.__logging,
            self.__config,
        )

    def get_last_date(self, file: str) -> float:
        return Tools.get_last_date(os.path.join(self.__path, file))

    def get_path(self) -> str:
        return self.__path

    def get_plugins(self) -> plugins_manager:
        return self.__plugins

    def __load_config(self):
        try:
            self.__config = configuration_manager.ConfigManager(
                os.path.join(self.__path, Constants.CONFIG_FILE),
                os.path.join(self.__path, Constants.CONFIG_FILE_DEFAULT),
            )
            self.__last_date = self.get_last_date(Constants.CONFIG_FILE)
        except Exception as exception:
            raise Exception(
                self.__ERROR_CONF_FILE.format(Constants.CONFIG_FILE, exception)
            )

    def log(self, text: str, silent: bool):
        self.__logging.log(text, silent)

    def refresh(self):
        date = self.get_last_date(Constants.CONFIG_FILE)

        if not date or not self.__last_date or date != self.__last_date:
            self.__load_config()
            self.__interval = interval_manager.IntervalManager(
                self.__config.get("interval_mult_file")
            )
            self.__timer = timer_manager.TimerManager(
                self.__config.get("start_times").split(","),
                self.__config.get("stop_times").split(","),
            )

    def get_config(self) -> configuration_manager:
        return self.__config

    def next_time(self) -> str:
        next_update = datetime.now(datetime.now().astimezone().tzinfo) + timedelta(
            seconds=self.__config.getint("slide_interval")
        )
        return next_update.isoformat().replace("T", " at ").split(".")[0]

    def update_time(self):
        value = self.get_slide_interval()
        multiplication = 1

        try:
            multiplication = self.get_interval() or 1
            if multiplication <= 0:
                multiplication = 1
        except Exception:
            pass

        if self.should_i_work_now():
            self.__next_time = datetime.now(
                datetime.now().astimezone().tzinfo
            ) + timedelta(seconds=(value * multiplication))
        else:
            self.__next_time = self.__timer.when_i_work_next()

    def should_i_work_now(self) -> bool:
        return self.__timer.should_i_work_now()

    def get_update_time_formatted(self, formatted: bool = False):
        return_value = (
            self.__next_time.isoformat().replace("T", " at ").split(".")[0]
            if formatted
            else self.__next_time
        )

        if formatted and datetime.now().date() == self.__next_time.date():
            return_value = (
                "at " + self.__next_time.isoformat().split("T")[1].split(".")[0]
            )
        return return_value

    def fire_event(self, args=None):
        self.remove_interval()
        self.__event(args)

    def next_photo(self):
        self.fire_event(self.__EMPTY_PARAMS)

    def get_empty_params(self) -> str:
        return self.__EMPTY_PARAMS

    def refresh_frame(self):
        self.fire_event(self.__REFRESH_PARAMS)

    @staticmethod
    def get_period(delta: timedelta, pattern: str):
        d = {"d": delta.days if delta.days > 0 else 0}
        d["h"], rem = divmod(delta.seconds, 3600)
        d["m"], d["s"] = divmod(rem, 60)
        return pattern.format(**d)

    def remove_interval(self):
        self.__interval.remove()

    def get_token(self) -> str:
        return self.__config.get("token")

    def get_interval(self) -> int:
        return self.__interval.read()

    def is_metric(self) -> bool:
        return WeatherManager.is_metric(self.__config.get("units"))

    def save_interval(self, number: int):
        self.__interval.save(number)

    def get_max_interval(self) -> int:
        return self.__config.getint("interval_max_mult")

    def is_interval_mult_enabled(self) -> bool:
        return bool(self.__config.getint("interval_mult"))

    def triggers_enabled(self) -> bool:
        return bool(self.__config.getint("allow_triggers"))

    def pid_file_exists(self) -> bool:
        return os.path.exists(self.__config.get("pid_file"))

    def get_download_file(self) -> str:
        return os.path.join(
            self.__config.get("photo_convert_path"),
            self.__config.get("photo_download_name"),
        )

    def get_chat_id(self) -> str:
        return self.__config.get("chat_id")

    def get_original_file(self) -> str:
        return_value = None
        files = glob.glob(
            "{}.*".format(
                os.path.join(
                    self.__config.get("photo_convert_path"),
                    self.__config.get("photo_download_name"),
                )
            )
        )
        if files:
            return_value = max(files, key=os.path.getctime)
        return return_value

    def get_current_file(self) -> str:
        return_value = None
        path = os.path.join(
            self.__config.get("photo_convert_path"),
            self.__config.get("photo_convert_filename"),
        )
        if os.path.exists(path):
            return_value = path
        return return_value

    def get_filename_if_exists(self, filename: str) -> str:
        return (
            os.path.join(
                self.__config.get("photo_convert_path"), self.__config.get(filename)
            )
            if os.path.exists(
                os.path.join(
                    self.__config.get("photo_convert_path"), self.__config.get(filename)
                )
            )
            else str()
        )

    def get_filename_modification_time_if_exists(self, filename: str) -> float:
        file = (
            os.path.join(
                self.__config.get("photo_convert_path"), self.__config.get(filename)
            )
            if os.path.exists(
                os.path.join(
                    self.__config.get("photo_convert_path"), self.__config.get(filename)
                )
            )
            else str()
        )
        return os.stat(file).st_mtime if file else 0

    def get_slide_interval(self) -> int:
        return self.__config.getint("slide_interval")

    def is_telebot_enabled(self) -> bool:
        return bool(self.__config.getint("use_telebot"))

    def is_web_enabled(self) -> bool:
        return bool(self.__config.getint("use_web"))

    def stats_enabled(self) -> bool:
        return bool(self.__config.getint("show_stats"))

    def get_state(self) -> str:
        return self.__BUSY_STATE if self.pid_file_exists() else self.__IDLE_STATE

    def get_service_state(self) -> str:
        return os.popen(self.__SERVICE_RUN_CMD).read().strip() or self.__NOT_RUNNING

    def get_uptime(self) -> str:
        return os.popen(self.__UPTIME_CMD).read().strip() or self.__NOTHING

    def get_load(self) -> str:
        return os.popen(self.__LOAD_CMD).read().strip() or self.__NOTHING

    def get_mem(self) -> str:
        return os.popen(self.__MEM_CMD).read().strip() or self.__NOTHING

    def get_temp(self) -> str:
        result = (
            os.popen(self.__TEMP_CMD)
            .read()
            .strip()
            .replace("temp=", "")
            .replace("'C", "")
            or self.__NOTHING
        )

        if result:
            if self.is_metric():
                result += "\N{DEGREE SIGN}C"
            else:
                result = self.calc_to_f(result) + "\N{DEGREE SIGN}F"

        return result

    @classmethod
    def calc_to_f(cls, temp) -> str:
        result = cls.__NOTHING
        try:
            result = str(round(float(temp) * 1.8 + 32, 1))
        except Exception:
            pass

        return result

    def get_next_time(self) -> str:
        time = self.get_update_time_formatted(True)
        delta = self.get_update_time_formatted() - datetime.now(
            datetime.now().astimezone().tzinfo
        )
        period = self.get_period(delta, self.__NEXT_TIME_FORMAT)

        if delta.days <= 0:
            periods = period.split(" ")
            del periods[1]
            del periods[1]
            if divmod(delta.seconds, 3600)[0] == 0:
                del periods[1]
                del periods[1]
            period = " ".join(periods)

        return f"{time}\n{period}"

    def reboot(self):
        os.system(self.__REBOOT_OS_CMD)

    def restart(self):
        os.system(self.__RESTART_OS_CMD)

    def power_off(self):
        os.system(self.__POWER_OFF_OS_CMD)

    @staticmethod
    def start_system_command(cmd) -> str:
        return os.popen(cmd).read()

    @staticmethod
    def get_display_power() -> str:
        return DisplayManager.get_display_power()

    @staticmethod
    def display_power(on_off: bool):
        DisplayManager.control_display_power(on_off)

    def display_power_config(self, on_off: bool):
        if DisplayManager.is_hdmi(
            self.__config.get("display_type")
        ) and self.__config.getint("control_display_power"):
            self.display_power(on_off)
