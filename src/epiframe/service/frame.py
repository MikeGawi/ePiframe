"""The frame as the service, the WebUI and the Telegram bot see it.

:class:`Frame` (was the 1.x ``BackendManager``) holds the configuration (reloaded
when the file changes), the working hours and the display time multiplier, knows
when the photo changes next and where the photo files are, and passes photo
change requests (:class:`Trigger`) to the service, which runs an update
(``epiframe``).
The service's threads share one frame.
"""

import glob
import os
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from epiframe.config import manager as config_manager
from epiframe.config import paths
from epiframe.config.property import ConfigError
from epiframe.core import system
from epiframe.core.files import last_modified
from epiframe.core.interval import IntervalMultiplier
from epiframe.core.schedule import DELIMITER, WeeklySchedule
from epiframe.display.hdmi import HdmiPower
from epiframe.display.options import DisplayType
from epiframe.plugins.manager import PluginManager
from epiframe.weather.openweather import Units

BUSY = "Busy"
IDLE = "Idle"
NEVER = "never (no start time is set in start_times)"


class Trigger(Enum):
    """A photo change asked for from outside the schedule (WebUI, bot, API)."""

    NEXT_PHOTO = ()
    REDISPLAY = ("redisplay",)  # the downloaded photo again

    @property
    def arguments(self) -> tuple[str, ...]:
        """``epiframe`` arguments that do it."""
        return tuple(self.value)


TriggerHandler = Callable[[Trigger], None]


def _now() -> datetime:
    return datetime.now().astimezone()


def _local(moment: datetime) -> datetime:
    """``moment`` as a naive local time (what :class:`WeeklySchedule` uses)."""
    return moment.astimezone().replace(tzinfo=None)


def timestamp_text(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d at %H:%M:%S")


def _period_text(delta: timedelta) -> str:
    hours, rest = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    parts = [f"{delta.days} days"] if delta.days else []
    if delta.days or hours:
        parts.append(f"{hours} hours")
    return " ".join(["in", *parts, f"{minutes} mins {seconds} secs"])


def next_update_text(when: datetime | None, now: datetime) -> str:
    """``at 12:00:00`` (another day: ``2026-11-25 at 12:00:00``) and, on a second
    line, ``in 1 hours 5 mins 0 secs`` (as 1.x)."""
    if when is None:
        return NEVER
    same_day = _local(when).date() == _local(now).date()
    time = when.strftime("at %H:%M:%S") if same_day else timestamp_text(when)
    return f"{time}\n{_period_text(max(when - now, timedelta()))}"


class Frame:
    """The frame with the configuration in ``config_file``.

    ``on_trigger`` is called with every photo change request; ``root`` is the
    ePiframe directory (WebUI templates and static files).
    """

    def __init__(
        self,
        on_trigger: TriggerHandler,
        config_file: str | os.PathLike[str] = paths.CONFIG_FILE,
        root: str | os.PathLike[str] = paths.EPIFRAME_DIR,
        *,
        plugins_dir: str | os.PathLike[str] = paths.PLUGINS_DIR,
        hdmi: HdmiPower | None = None,
    ) -> None:
        self.on_trigger = on_trigger
        self.config_file = Path(config_file)
        self.root = Path(root)
        self.hdmi = hdmi or HdmiPower()
        self._refresh_lock = threading.Lock()  # the service's threads refresh
        self._load()
        # a multiplier left by the previous run belongs to a photo shown long ago
        self.multiplier.remove()
        self.next_update: datetime | None = None
        self.schedule_next()
        self.plugins = PluginManager(Path(plugins_dir), self.config)

    # ------------------------------------------------------------ configuration

    def _load(self) -> None:
        self._config_time = last_modified(self.config_file)
        try:
            self.config = config_manager.ConfigManager(
                self.config_file, paths.CONFIG_FILE_DEFAULT
            )
        except Exception as error:
            raise ConfigError(
                f"Error loading {self.config_file} configuration file! {error}"
            ) from error
        self.multiplier = IntervalMultiplier(self.config.get("interval_mult_file"))
        self.schedule = WeeklySchedule.from_strings(
            self.config.get("start_times").split(DELIMITER),
            self.config.get("stop_times").split(DELIMITER),
        )

    def refresh(self) -> None:
        """Reload the configuration if the file changed (or can't be checked)."""
        with self._refresh_lock:
            modified = last_modified(self.config_file)
            if modified is None or modified != self._config_time:
                self._load()

    def _enabled(self, name: str) -> bool:
        return bool(self.config.getint(name))

    @property
    def slide_interval(self) -> int:
        """Seconds between photo changes."""
        return self.config.getint("slide_interval")

    @property
    def metric(self) -> bool:
        return Units.is_metric(self.config.get("units"))

    @property
    def token(self) -> str:
        return self.config.get("token")

    @property
    def chat_id(self) -> str:
        return self.config.get("chat_id")

    @property
    def interval_enabled(self) -> bool:
        return self._enabled("interval_mult")

    @property
    def max_interval(self) -> int:
        return self.config.getint("interval_max_mult")

    @property
    def triggers_enabled(self) -> bool:
        """Whether triggers change the photo during off hours too."""
        return self._enabled("allow_triggers")

    @property
    def web_enabled(self) -> bool:
        return self._enabled("use_web")

    @property
    def telegram_enabled(self) -> bool:
        return self._enabled("use_telebot")

    @property
    def stats_enabled(self) -> bool:
        return self._enabled("show_stats")

    @property
    def stats_file(self) -> Path:
        """The statistics database (``epiframe.stats.store``)."""
        return Path(self.config.get("stats_db_file"))

    # ------------------------------------------------------------- photo change

    @property
    def busy(self) -> bool:
        """Whether an update is changing the photo now (its PID file exists)."""
        return Path(self.config.get("pid_file")).exists()

    @property
    def state(self) -> str:
        return BUSY if self.busy else IDLE

    def working(self, now: datetime | None = None) -> bool:
        """Whether ``now`` is within the working hours."""
        return self.schedule.is_active(_local(now or _now()))

    def schedule_next(self, now: datetime | None = None) -> None:
        """Set :attr:`next_update`: a slide interval (times the multiplier) from
        ``now``, or the next start out of the working hours."""
        now = now or _now()
        if self.working(now):
            seconds = self.slide_interval * max(self.multiplier.read(), 1)
            self.next_update = now + timedelta(seconds=seconds)
            return
        try:
            self.next_update = self.schedule.next_start(_local(now))
        except ValueError:
            self.next_update = None

    def next_update_text(self, now: datetime | None = None) -> str:
        return next_update_text(self.next_update, now or _now())

    def next_photo(self) -> None:
        self._trigger(Trigger.NEXT_PHOTO)

    def redisplay(self) -> None:
        """Convert and show the downloaded photo again (e.g. a new one uploaded)."""
        self._trigger(Trigger.REDISPLAY)

    def _trigger(self, trigger: Trigger) -> None:
        self.multiplier.remove()
        self.on_trigger(trigger)

    # -------------------------------------------------------------------- files

    def path(self, name: str) -> Path:
        """The file named by the ``name`` setting in ``photo_convert_path``."""
        return Path(self.config.get("photo_convert_path"), self.config.get(name))

    def file(self, name: str) -> Path | None:
        """:meth:`path` if the file exists."""
        path = self.path(name)
        return path if path.is_file() else None

    def modified(self, name: str) -> float:
        """Modification time of :meth:`path`, ``0`` if there is no file."""
        return last_modified(self.path(name)) or 0

    def download_file(self, extension: str) -> Path:
        """Where the original photo with ``extension`` is saved."""
        return Path(f"{self.path('photo_download_name')}.{extension}")

    def original_file(self) -> Path | None:
        """The original (downloaded or uploaded) photo, the newest if many."""
        pattern = glob.escape(str(self.path("photo_download_name"))) + ".*"
        files = [Path(name) for name in glob.glob(pattern)]
        return max(files, key=lambda path: path.stat().st_ctime, default=None)

    def current_file(self) -> Path | None:
        """The converted photo on the display."""
        return self.file("photo_convert_filename")

    # ----------------------------------------------------------- system, screen

    def reboot(self) -> None:
        system.reboot()

    def power_off(self) -> None:
        system.power_off()

    def restart(self) -> None:
        """Restart the ePiframe service."""
        system.restart_service()

    def power_display(self, on: bool) -> None:
        """Turn the HDMI screen on/off by the schedule (``control_display_power``)."""
        if DisplayType.is_hdmi(self.config.get("display_type")) and self._enabled(
            "control_display_power"
        ):
            self.hdmi.set(on)
