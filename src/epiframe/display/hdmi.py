"""HDMI/Composite display: the photo is shown full screen by ``fbi`` on a console.

Power control of the screen (``control_display_power``) uses two mechanisms,
because none works everywhere:

- ``vcgencmd display_power`` — firmware graphics driver (Raspberry Pi OS up to
  Bullseye without KMS); under the KMS driver (default since Bookworm) it does
  nothing;
- framebuffer blanking (``/sys/class/graphics/fb0/blank``) — powers the monitor
  down (DPMS) through the DRM framebuffer emulation under KMS, as long as no
  desktop (X/Wayland) owns the screen.

Both are tried; failures are ignored (the screen just stays on). The state comes
from ``vcgencmd`` when it knows it, else it is the last state that was set.

The commands run without ``sudo``: the frame service runs as root. A manual run
(e.g. ``epiframe test-display``) needs ``sudo`` for ``fbi`` to take over
the console.
"""

import shutil
import subprocess
from pathlib import Path

from epiframe.core.logs import get_logger
from epiframe.display.base import Capability, DisplayError

log = get_logger("display")

VCGENCMD = "vcgencmd"
FRAMEBUFFER_BLANK = Path("/sys/class/graphics/fb0/blank")
UNBLANK = "0"
POWERDOWN = "4"  # FB_BLANK_POWERDOWN
COMMAND_TIMEOUT = 10


class HdmiDisplay:
    """Shows photos with ``fbi`` on virtual terminal ``tty``."""

    capabilities = frozenset({Capability.FULL})

    def __init__(self, viewer: str, tty: int):
        self._viewer = viewer
        self._tty = tty

    def show(self, path: Path | str) -> None:
        # the previous fbi keeps running (it shows the old photo), stop it first;
        # pkill matches the process name (at most 15 characters)
        stop = ["pkill", "-KILL", "-x", Path(self._viewer).name[:15]]
        command = [self._viewer, "-vt", str(self._tty), "-noverbose", "-a", str(path)]
        try:
            subprocess.run(  # noqa: S603 - fixed command, no shell
                stop,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=COMMAND_TIMEOUT,
            )
            subprocess.Popen(  # noqa: S603 - the viewer from the config, no shell
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # keeps showing after ePiframe exits
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise DisplayError(f"Can't start {self._viewer}: {error}") from error


class HdmiPower:
    """Turns the HDMI screen on and off."""

    def __init__(
        self,
        vcgencmd: str | None = None,
        blank: Path = FRAMEBUFFER_BLANK,
    ):
        self._vcgencmd = vcgencmd or shutil.which(VCGENCMD)
        self._blank = blank
        self._last: bool | None = None

    def set(self, on: bool) -> None:
        self._vcgencmd_run("1" if on else "0")
        try:
            self._blank.write_text(UNBLANK if on else POWERDOWN)
        except OSError as error:
            log.debug(f"Framebuffer blanking not available: {error}")
        self._last = on

    def state(self) -> bool | None:
        """Return whether the screen is on (``None`` when unknown)."""
        value = self._vcgencmd_run()
        if value in ("0", "1"):
            return value == "1"
        return self._last

    def _vcgencmd_run(self, *arguments: str) -> str | None:
        # vcgencmd display_power [0|1] prints "display_power=<state>"
        if self._vcgencmd is None:
            return None
        try:
            result = subprocess.run(  # noqa: S603 - fixed command, no shell
                [self._vcgencmd, "display_power", *arguments],
                capture_output=True,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            log.debug(f"vcgencmd failed: {error}")
            return None
        return result.stdout.strip().rpartition("=")[2]
