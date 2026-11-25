"""The ePiframe service (``ePiframe_service.py``).

It runs in the foreground (systemd ``Type=simple``, or a terminal for tests) and
stops cleanly on SIGTERM or Ctrl+C. Its threads:

- the photo scheduler (:mod:`epiframe.service.scheduler`), which runs
  ``ePiframe.py`` for every photo change (:mod:`epiframe.service.refresh`);
- the WebUI / REST API server and the statistics recorder;
- the Telegram bot;
- the service threads of the plugins (``Plugin.service_thread``).

The WebUI, statistics and bot threads check the configuration every minute: they
start once enabled, and a failed start (e.g. the port is taken) is tried again a
minute later. ``ePiframe_service.py web`` / ``telegram`` runs only the WebUI or
the bot (photo changes then only on request).

1.x was a forking daemon with a fixed ``/tmp`` PID file that killed every other
``ePiframe_service.py`` process on the machine when it started.
"""

import argparse
import signal
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

from epiframe.bot.telegram import TelegramBot
from epiframe.config import paths
from epiframe.config.property import ConfigError
from epiframe.core.logs import get_logger, setup_logging
from epiframe.plugins.base import Plugin
from epiframe.service.frame import Frame, Trigger
from epiframe.service.refresh import Refresher
from epiframe.service.scheduler import PREFIX, PhotoScheduler
from epiframe.stats.metrics import SAMPLE_INTERVAL, Sampler
from epiframe.stats.recorder import Recorder
from epiframe.stats.store import MetricsStore
from epiframe.web.app import WebUI

RETRY = 60  # seconds between the checks / start attempts of the WebUI and the bot
WEB_POLL = 0.5  # seconds: how fast the WebUI server notices the stop
STOP_TIMEOUT = 10  # seconds to wait for the threads when stopping

STARTED = PREFIX + "STARTED"
STOPPED = PREFIX + "STOPPED"
WEB_START = PREFIX + "Starting ePiframe WebUI server"
BOT_START = PREFIX + "Starting Telegram Bot"

log = get_logger("service")

FrameFactory = Callable[..., Frame]


@dataclass(frozen=True)
class Parts:
    """What the service runs."""

    schedule: bool = True  # photo changes by the schedule
    web: bool = True  # WebUI, REST API and statistics
    telegram: bool = True


PARTS = {
    None: Parts(),
    "web": Parts(schedule=False, telegram=False),
    "telegram": Parts(schedule=False, web=False),
}


class Service:
    """The service for the configuration in ``config_file``."""

    def __init__(
        self,
        parts: Parts = PARTS[None],
        config_file: str | Path | None = None,
        *,
        refresher: Refresher | None = None,
        frame_factory: FrameFactory = Frame,
    ) -> None:
        self.parts = parts
        self.stopping = threading.Event()
        self.frame = frame_factory(
            self.trigger, paths.CONFIG_FILE if config_file is None else config_file
        )
        self.scheduler = PhotoScheduler(
            self.frame, (refresher or Refresher()).start, scheduled=parts.schedule
        )
        self.threads: list[threading.Thread] = []
        self.bot: TelegramBot | None = None

    def trigger(self, trigger: Trigger) -> None:
        self.scheduler.trigger(trigger)

    # ----------------------------------------------------------- start / stop

    def run(self) -> None:
        """Start the threads and wait until :meth:`stop`."""
        self.start()
        self.stopping.wait()
        self.shutdown()

    def start(self) -> None:
        log.info(STARTED)
        self._spawn("scheduler", self.scheduler.run)
        if self.parts.web:
            self._spawn("stats", self.record_stats)
            self._spawn("web", lambda: self._repeat(self.serve_web, "WebUI"))
        if self.parts.telegram:
            self._spawn("telegram", lambda: self._repeat(self.run_bot, "Telegram Bot"))
        for plugin in self.frame.plugins.with_hook("service_thread"):
            self._spawn(f"plugin {plugin.folder}", self._plugin_target(plugin))

    def stop(self) -> None:
        """Ask the service to stop (safe in a signal handler)."""
        self.stopping.set()

    def shutdown(self) -> None:
        """Stop the threads; wait :data:`STOP_TIMEOUT` seconds at most."""
        self.stopping.set()
        self.scheduler.stop()
        if self.bot is not None:
            self.bot.stop()
        running = self._join()
        if running:
            log.warning(f"Threads still running when stopping: {', '.join(running)}")
        log.info(STOPPED)

    def _join(self) -> list[str]:
        """Wait for the threads; return the names of those still running."""
        deadline = time.monotonic() + STOP_TIMEOUT
        for thread in self.threads:
            thread.join(max(deadline - time.monotonic(), 0))
        return [thread.name for thread in self.threads if thread.is_alive()]

    def _spawn(self, name: str, target: Callable[[], None]) -> None:
        thread = threading.Thread(target=target, name=name, daemon=True)
        self.threads.append(thread)
        thread.start()

    def _repeat(self, body: Callable[[], None], what: str) -> None:
        """Run ``body`` every :data:`RETRY` seconds until the stop."""
        while not self.stopping.is_set():
            try:
                body()
            except Exception as error:
                log.error(f"Error configuring {what}! {error}")
            self.stopping.wait(RETRY)

    # ---------------------------------------------------------------- threads

    def serve_web(self) -> None:
        """Serve the WebUI (if enabled) until the stop."""
        self.frame.refresh()
        if not self.frame.web_enabled:
            return
        log.info(WEB_START)
        server = WebUI(self.frame).server()
        server.timeout = WEB_POLL
        try:
            while not self.stopping.is_set():
                server.handle_request()
        finally:
            server.server_close()

    def run_bot(self) -> None:
        """Run the Telegram bot (if enabled) until the stop."""
        self.frame.refresh()
        if not self.frame.telegram_enabled:
            return
        log.info(BOT_START)
        self.bot = TelegramBot(self.frame)
        if not self.stopping.is_set():
            self.bot.start()

    def record_stats(self) -> None:
        """Take a statistics sample every :data:`SAMPLE_INTERVAL` seconds (if the
        WebUI and the statistics are enabled); write the last ones at the stop."""
        store = MetricsStore(self.frame.stats_file)
        recorder = Recorder(store, Sampler(store.path.absolute().parent))
        while not self.stopping.is_set():
            self._safe_stats(lambda: self._sample(recorder))
            self.stopping.wait(SAMPLE_INTERVAL)
        self._safe_stats(recorder.flush)

    def _sample(self, recorder: Recorder) -> None:
        self.frame.refresh()
        if self.frame.web_enabled and self.frame.stats_enabled:
            recorder.record()

    @staticmethod
    def _safe_stats(action: Callable[[], None]) -> None:
        try:
            action()
        except Exception as error:
            log.error(f"Error getting statistics! {error}")

    def _plugin_target(self, plugin: Plugin) -> Callable[[], None]:
        def target() -> None:
            try:
                plugin.service_thread(self.frame, self.stopping)
            except Exception as error:
                log.error(f"Service thread of plugin {plugin.name} failed: {error!r}")

        return target


# --------------------------------------------------------------------- command


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ePiframe_service.py",
        description="The ePiframe service: photo changes, WebUI, Telegram bot. "
        "Runs in the foreground until Ctrl+C or SIGTERM; as a system service it is "
        "controlled with systemctl (start, stop, restart, status).",
    )
    parser.add_argument(
        "part",
        nargs="?",
        choices=[part for part in PARTS if part],
        help="run only the WebUI or the Telegram bot (it must be enabled in the "
        "configuration); photos then change only on request",
    )
    return parser


def handle_signals(service: Service) -> None:
    def stop(signal_number: int, frame: FrameType | None) -> None:
        service.stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)


def main(arguments: Sequence[str] | None = None) -> int:
    part = parser().parse_args(arguments).part
    setup_logging()  # the console until the log file is known
    try:
        service = Service(PARTS[part])
    except ConfigError as error:
        log.error(str(error))
        return 1
    # a terminal shows the log too; under systemd only the file gets it
    setup_logging(service.frame.config.get("log_files"), console=sys.stdout.isatty())
    handle_signals(service)
    service.run()
    return 0
