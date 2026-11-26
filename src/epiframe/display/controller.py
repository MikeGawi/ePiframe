"""The one owner of the display at a time.

The service shows every photo: the update it starts (``epiframe prepare``) only
prepares the converted photo, so stopping a hanging update can't interrupt an
SPI transfer any more and leave the panel garbled and awake. Manual commands
(``epiframe``, ``epiframe test-display``, ``epiframe redisplay``) show photos
themselves. :class:`DisplayController` serializes all of them with an exclusive
``flock`` on :data:`epiframe.config.paths.DISPLAY_LOCK_FILE`: two processes (or
two threads of the service) never drive the panel at the same time.

With ``fast_refresh`` every ``full_refresh_every``-th photo uses the standard
full refresh (it clears the ghosting the fast ones leave); the number of fast
refreshes since the last standard one is kept in
:data:`epiframe.config.paths.DISPLAY_STATE_FILE`, so it counts across the
processes and restarts.
"""

import fcntl
import json
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from epiframe.config import paths
from epiframe.config.property import ValueSource
from epiframe.core.files import write_text_atomic
from epiframe.core.logs import get_logger
from epiframe.display.base import Capability, Display, DisplayError
from epiframe.display.factory import create_display
from epiframe.display.options import DisplayType
from epiframe.display.system import spi_enabled

# seconds: a refresh takes up to about a minute (large multicolor panels), a
# longer one hangs (e.g. a disconnected panel never stops being busy)
LOCK_TIMEOUT = 300
LOCK_POLL = 0.5  # seconds between the attempts to take the lock
NO_SPI = "SPI is not enabled! The e-Paper display needs it (raspi-config)."

log = get_logger("display")

Settings = Callable[[], ValueSource]
DisplayFactory = Callable[[ValueSource, bool], Display]
FAST_COUNT = "fast_refreshes"  # key in the state file


@contextmanager
def display_lock(
    path: str | os.PathLike[str],
    timeout: float = LOCK_TIMEOUT,
    poll: float = LOCK_POLL,
) -> Iterator[None]:
    """Hold the display lock file ``path``; raise ``DisplayError`` when it is
    not free within ``timeout`` seconds."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # read-only: users without write access to the file can still lock it
    descriptor = os.open(path, os.O_RDONLY | os.O_CREAT, 0o644)
    try:
        _acquire(descriptor, timeout, poll)
        yield
    finally:
        os.close(descriptor)  # releases the lock


def _acquire(descriptor: int, timeout: float, poll: float) -> None:
    deadline = time.monotonic() + timeout
    waiting = False
    while True:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise DisplayError(
                    f"The display is still busy after {timeout:g} seconds"
                    " (a refresh hangs?)!"
                ) from None
        if not waiting:
            log.info("Waiting for the display (another refresh is running)...")
            waiting = True
        time.sleep(poll)


class RefreshCounter:
    """The number of fast refreshes since the last standard one (file ``path``)."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def read(self) -> int:
        try:
            value = json.loads(self.path.read_text())[FAST_COUNT]
        except (OSError, ValueError, TypeError, KeyError):
            return 0  # no file yet, or broken: start counting again
        return value if isinstance(value, int) and value > 0 else 0

    def save(self, count: int) -> None:
        try:
            write_text_atomic(self.path, json.dumps({FAST_COUNT: count}))
        except OSError as error:  # e.g. a read-only data folder: nothing breaks
            log.warning(f"Can't save the display state {self.path}: {error}")


def fast_now(config: ValueSource, fast_count: int) -> bool:
    """Whether this refresh is a fast one (every ``full_refresh_every``-th is not)."""
    if not bool(config.getint("fast_refresh")):
        return False
    return fast_count + 1 < config.getint("full_refresh_every")


class DisplayController:
    """Shows photos on the display of the configuration that ``settings``
    returns (read for every photo: the service reloads it when it changes)."""

    def __init__(
        self,
        settings: Settings,
        *,
        factory: DisplayFactory = create_display,
        spi_check: Callable[[], bool] = spi_enabled,
        lock_file: str | os.PathLike[str] | None = None,
        state_file: str | os.PathLike[str] | None = None,
    ) -> None:
        self.settings = settings
        self.factory = factory
        self.spi_check = spi_check
        self.lock_file = lock_file
        self.state_file = state_file

    def show(self, file: Path) -> None:
        """Show the image ``file``; raise ``DisplayError`` (no SPI, display busy)
        or the error of the display driver."""
        config = self.settings()
        if not DisplayType.is_hdmi(config.get("display_type")) and not self.spi_check():
            raise DisplayError(NO_SPI)
        log.info("Sending to display...")
        with display_lock(self.lock_file or paths.DISPLAY_LOCK_FILE):
            self._refresh(config, file)

    def _refresh(self, config: ValueSource, file: Path) -> None:
        counter = RefreshCounter(self.state_file or paths.DISPLAY_STATE_FILE)
        count = counter.read()
        fast = fast_now(config, count)
        display = self.factory(config, fast)
        display.show(file)
        # a display without the fast refresh did a standard one
        fast = fast and Capability.FAST_FULL in display.capabilities
        counter.save(count + 1 if fast else 0)
