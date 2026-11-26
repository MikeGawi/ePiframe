"""The one owner of the display at a time.

The service shows every photo: the update it starts (``epiframe prepare``) only
prepares the converted photo, so stopping a hanging update can't interrupt an
SPI transfer any more and leave the panel garbled and awake. Manual commands
(``epiframe``, ``epiframe test-display``, ``epiframe redisplay``) show photos
themselves. :class:`DisplayController` serializes all of them with an exclusive
``flock`` on :data:`epiframe.config.paths.DISPLAY_LOCK_FILE`: two processes (or
two threads of the service) never drive the panel at the same time.

With ``fast_refresh`` every ``full_refresh_every``-th photo uses the standard
full refresh (it clears the ghosting the fast ones leave).

Status icons (:mod:`epiframe.display.icons`): the service turns them on and off
(:meth:`DisplayController.change_icons`); a change is shown with a partial
refresh of the last shown photo (kept as ``display_frame.png`` next to the
state file; ``display_shown.png`` is the image on the panel now). Every
``max_partial_refreshes``-th change uses a full refresh instead. A new photo
ends the busy icon and the error; the other icons are drawn on it before its
full refresh (also on displays without the partial refresh).

The state (refresh counters, icons) is kept in
:data:`epiframe.config.paths.DISPLAY_STATE_FILE`, so it is shared by the
processes and survives restarts.
"""

import fcntl
import json
import os
import shutil
import time
from collections.abc import Callable, Collection, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from epiframe.config import paths
from epiframe.config.property import ValueSource
from epiframe.core.files import write_text_atomic
from epiframe.core.logs import get_logger
from epiframe.display.base import Capability, Display, DisplayError
from epiframe.display.factory import create_display
from epiframe.display.icons import Icon, IconSettings, draw_icons
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
FRAME_FILE = "display_frame.png"  # the last photo, without icons
SHOWN_FILE = "display_shown.png"  # the image on the panel
NEXT_FILE = "display_next.png"  # the image of the last partial refresh
# a new photo ends these (the update is over and didn't fail)
ENDED_BY_PHOTO = frozenset({Icon.BUSY, Icon.ERROR})


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


@dataclass
class DisplayState:
    """What the controller remembers between refreshes."""

    fast_refreshes: int = 0  # since the last standard full refresh
    partial_refreshes: int = 0  # since the last full refresh
    icons: frozenset[Icon] = frozenset()  # turned on (shown if enabled)
    shown: frozenset[Icon] = frozenset()  # on the panel

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DisplayState":
        return cls(
            fast_refreshes=_count(data.get("fast_refreshes")),
            partial_refreshes=_count(data.get("partial_refreshes")),
            icons=_icons(data.get("icons")),
            shown=_icons(data.get("shown")),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "fast_refreshes": self.fast_refreshes,
            "partial_refreshes": self.partial_refreshes,
            "icons": sorted(self.icons),
            "shown": sorted(self.shown),
        }


def _count(value: object) -> int:
    return value if isinstance(value, int) and value > 0 else 0


def _icons(value: object) -> frozenset[Icon]:
    if not isinstance(value, list):
        return frozenset()
    return frozenset(Icon(item) for item in value if item in Icon.__members__.values())


class StateFile:
    """The display state in the file ``path`` (broken or missing: a new state)."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def read(self) -> DisplayState:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return DisplayState()  # no file yet, or broken: start again
        return (
            DisplayState.from_json(data) if isinstance(data, dict) else DisplayState()
        )

    def save(self, state: DisplayState) -> None:
        try:
            write_text_atomic(self.path, json.dumps(state.to_json()))
        except OSError as error:  # e.g. a read-only data folder: nothing breaks
            log.warning(f"Can't save the display state {self.path}: {error}")


def fast_now(config: ValueSource, fast_count: int) -> bool:
    """Whether this refresh is a fast one (every ``full_refresh_every``-th is not)."""
    if not bool(config.getint("fast_refresh")):
        return False
    return fast_count + 1 < config.getint("full_refresh_every")


class DisplayController:
    """Shows photos and status icons on the display of the configuration that
    ``settings`` returns (read every time: the service reloads it when it
    changes)."""

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

    @property
    def state(self) -> StateFile:
        return StateFile(self.state_file or paths.DISPLAY_STATE_FILE)

    def _file(self, name: str) -> Path:
        return self.state.path.with_name(name)

    def show(self, file: Path) -> None:
        """Show the image ``file``; raise ``DisplayError`` (no SPI, display busy)
        or the error of the display driver."""
        config = self.settings()
        self._check_spi(config)
        log.info("Sending to display...")
        with display_lock(self.lock_file or paths.DISPLAY_LOCK_FILE):
            self._refresh(config, file)

    def change_icons(
        self, on: Collection[Icon] = (), off: Collection[Icon] = ()
    ) -> None:
        """Turn the status icons ``on`` and ``off``; show the change (if the
        icons are enabled and the display has the partial refresh)."""
        config = self.settings()
        icons = IconSettings.from_config(config)
        if not icons.enabled:
            return  # no icons wanted: the state isn't even read
        self._check_spi(config)
        with display_lock(self.lock_file or paths.DISPLAY_LOCK_FILE):
            state = self.state.read()
            state.icons = (state.icons | frozenset(on)) - frozenset(off)
            wanted = state.icons & icons.enabled
            if wanted != state.shown:
                self._show_icons(config, icons, state, wanted)
            self.state.save(state)

    def _check_spi(self, config: ValueSource) -> None:
        if not DisplayType.is_hdmi(config.get("display_type")) and not self.spi_check():
            raise DisplayError(NO_SPI)

    # ----------------------------------------------------------- full refresh

    def _refresh(self, config: ValueSource, file: Path) -> None:
        state = self.state.read()
        state.icons -= ENDED_BY_PHOTO
        icons = IconSettings.from_config(config)
        fast = fast_now(config, state.fast_refreshes)
        display = self.factory(config, fast)
        wanted = state.icons & icons.enabled
        display.show(self._with_icons(file, icons, wanted))
        # a display without the fast refresh did a standard one
        fast = fast and Capability.FAST_FULL in display.capabilities
        state.fast_refreshes = state.fast_refreshes + 1 if fast else 0
        state.partial_refreshes = 0
        state.shown = wanted
        self.state.save(state)

    def _with_icons(
        self, file: Path, icons: IconSettings, wanted: frozenset[Icon]
    ) -> Path:
        """The image to show: ``file``, or its copy with the ``wanted`` icons.

        With icons enabled the photo is kept for the later partial refreshes;
        without, the old copies are removed (they would be out of date).
        """
        frame, shown = self._file(FRAME_FILE), self._file(SHOWN_FILE)
        if not icons.enabled:
            for path in (frame, shown):
                path.unlink(missing_ok=True)
            return file
        with Image.open(file) as source:
            source.load()
        source.save(frame)
        draw_icons(source, wanted, icons).save(shown)
        return shown

    # -------------------------------------------------------- partial refresh

    def _show_icons(
        self,
        config: ValueSource,
        icons: IconSettings,
        state: DisplayState,
        wanted: frozenset[Icon],
    ) -> None:
        frame, shown, following = (
            self._file(name) for name in (FRAME_FILE, SHOWN_FILE, NEXT_FILE)
        )
        if not frame.exists():
            return  # no photo shown with icons enabled yet: the next one has them
        display = self.factory(config, False)
        if Capability.PARTIAL not in display.capabilities:
            return  # the icons come with the next photo
        with Image.open(frame) as photo:
            draw_icons(photo, wanted, icons).save(following)
        try:
            self._update(display, config, state, following, shown)
        except BaseException:
            with suppress(OSError):
                following.unlink()
            raise
        # a copy: the display may still read the file (HDMI: fbi starts detached)
        shutil.copyfile(following, shown)
        state.shown = wanted

    @staticmethod
    def _update(
        display: Display,
        config: ValueSource,
        state: DisplayState,
        following: Path,
        shown: Path,
    ) -> None:
        if state.partial_refreshes >= config.getint("max_partial_refreshes"):
            display.show(following)  # clears the ghosting of the partial ones
            state.partial_refreshes = state.fast_refreshes = 0
        else:
            display.show_partial(following, shown)
            state.partial_refreshes += 1
