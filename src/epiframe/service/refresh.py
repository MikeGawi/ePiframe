"""Runs an update (``epiframe prepare``, one photo change) for the service.

It runs as ``python -P -m epiframe`` (``-P``: the working directory is not on
the import path), so it doesn't depend on where ``ePiframe.py`` is. The update
logs to stdout only (:data:`epiframe.core.logs.CONSOLE_ONLY_ENV`);
its output, including tracebacks on stderr, is copied line by line to the
service's log, so a single process writes (and rotates) the log file.

:meth:`Refresher.run` waits for the update: the service runs one at a time and
shows the prepared photo after it. An update that hangs (e.g. a stalled
download) is stopped after a time limit (the slide interval, as in 1.x, where
the next run stopped it) — first with SIGINT, so it cleans up (PID file), then
with SIGKILL. The update never drives the display, so stopping it can't
interrupt a refresh.
"""

import os
import signal
import subprocess
import sys
import threading
from collections.abc import Sequence

from epiframe.core.logs import CONSOLE_ONLY_ENV, get_logger, log_line

MODULE = "epiframe"
STOP_GRACE = 10  # seconds after SIGINT until SIGKILL
OUTPUT_WAIT = 10  # seconds to wait for the last output lines

log = get_logger("service")


class Refresher:
    """Runs the update with ``python``."""

    def __init__(self, python: str = sys.executable, module: str = MODULE) -> None:
        self.python = python
        self.module = module
        self._process: subprocess.Popen[str] | None = None

    def command(self, arguments: Sequence[str]) -> list[str]:
        return [self.python, "-P", "-m", self.module, *arguments]

    def run(
        self, arguments: Sequence[str] = (), timeout: float | None = None
    ) -> int | None:
        """Run the update with ``arguments`` and wait for it (``timeout`` seconds
        at most: then it is stopped); return its exit code, ``None`` if it can't
        be started."""
        process = self._start(arguments)
        if process is None:
            return None
        output = threading.Thread(target=copy_output, args=(process,), daemon=True)
        output.start()
        try:
            code = self._wait(process, timeout)
        finally:
            self._process = None
        output.join(OUTPUT_WAIT)
        if code:
            log.warning(f"ePiframe update ended with exit code {code}")
        return code

    def stop(self) -> None:
        """Stop the running update (the service stops); safe from any thread."""
        process = self._process
        if process is not None and process.poll() is None:
            stop(process)

    def _start(self, arguments: Sequence[str]) -> subprocess.Popen[str] | None:
        try:
            self._process = subprocess.Popen(  # noqa: S603 - argument list, no shell
                self.command(arguments),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                env=os.environ | {CONSOLE_ONLY_ENV: "1", "PYTHONUNBUFFERED": "1"},
            )
        except OSError as error:
            log.error(f"Can't start the ePiframe update: {error}")
            return None
        return self._process

    @staticmethod
    def _wait(process: subprocess.Popen[str], timeout: float | None) -> int:
        try:
            return process.wait(timeout)
        except subprocess.TimeoutExpired:
            log.warning(
                f"ePiframe update still running after {timeout:g} seconds: stopping it"
            )
            return stop(process)


def stop(process: subprocess.Popen[str], grace: float = STOP_GRACE) -> int:
    """Stop ``process``: SIGINT (it cleans up), SIGKILL after ``grace`` seconds;
    return its exit code."""
    process.send_signal(signal.SIGINT)
    try:
        return process.wait(grace)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.wait()


def copy_output(process: subprocess.Popen[str]) -> None:
    """Log the lines of ``process`` until its output ends."""
    if process.stdout is not None:
        with process.stdout:
            for line in process.stdout:
                log_line(log, line.rstrip("\n"))
