"""Runs ``ePiframe.py`` (one photo change) for the service.

The script logs to stdout only (:data:`epiframe.core.logs.CONSOLE_ONLY_ENV`);
its output, including tracebacks on stderr, is copied line by line to the
service's log, so a single process writes (and rotates) the log file.
"""

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from threading import Thread

from epiframe.config import paths
from epiframe.core.logs import CONSOLE_ONLY_ENV, get_logger, log_line

SCRIPT = paths.EPIFRAME_DIR / "ePiframe.py"

log = get_logger("service")


class Refresher:
    """Starts ``script`` with ``python``; :meth:`start` doesn't wait for it."""

    def __init__(self, script: Path = SCRIPT, python: str = sys.executable) -> None:
        self.script = script
        self.python = python

    def command(self, arguments: Sequence[str]) -> list[str]:
        return [self.python, str(self.script), *arguments]

    def start(self, arguments: Sequence[str] = ()) -> subprocess.Popen[str] | None:
        """Start the script with ``arguments``; ``None`` if it can't be started."""
        try:
            process = subprocess.Popen(  # noqa: S603 - argument list, no shell
                self.command(arguments),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                env=os.environ | {CONSOLE_ONLY_ENV: "1", "PYTHONUNBUFFERED": "1"},
            )
        except OSError as error:
            log.error(f"Can't start {self.script}: {error}")
            return None
        Thread(target=copy_output, args=(process,), daemon=True).start()
        return process


def copy_output(process: subprocess.Popen[str]) -> None:
    """Log the lines of ``process`` until it ends, then reap it."""
    if process.stdout is not None:
        with process.stdout:
            for line in process.stdout:
                log_line(log, line.rstrip("\n"))
    code = process.wait()
    if code:
        log.warning(f"ePiframe script ended with exit code {code}")
