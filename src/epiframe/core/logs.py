"""Logging setup on top of the standard :mod:`logging` module.

All ePiframe loggers live under the ``epiframe`` logger (:func:`get_logger`). An entry
point calls :func:`setup_logging` once it knows the log file, then modules just log::

    log = get_logger("service")
    log.info("Started")

Lines keep the 1.x format ``YYYY-mm-dd HH:MM:SS : message`` (WebUI log view, REST
``get_log``) on the console and in the file. The file rotates at midnight and the old
files are gzipped (``<file>.<date>.gz``, 6 kept).
"""

import gzip
import logging
import os
import shutil
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import TextIO

LOGGER_NAME = "epiframe"
LINE_FORMAT = "%(asctime)s : %(message)s"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
BACKUP_COUNT = 6

_OWN_HANDLER = "_epiframe_handler"


class StdoutHandler(logging.StreamHandler[TextIO]):
    """Console handler writing to the *current* ``sys.stdout``.

    ``sys.stdout`` is looked up on every record, so redirecting it later (pytest
    capture, ``contextlib.redirect_stdout``) works.
    """

    def __init__(self) -> None:
        super().__init__(sys.stdout)

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


class GzipTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Rotate the log file at midnight and gzip the rotated file."""

    def __init__(self, filename: str | os.PathLike[str]) -> None:
        super().__init__(
            filename, when="midnight", interval=1, backupCount=BACKUP_COUNT
        )
        self.namer = self.gzip_name
        self.rotator = self.gzip_rotate

    @staticmethod
    def gzip_name(name: str) -> str:
        return name + ".gz"

    @staticmethod
    def gzip_rotate(source: str, destination: str) -> None:
        with open(source, "rb") as source_file, gzip.open(destination, "wb") as target:
            shutil.copyfileobj(source_file, target)
        os.remove(source)


def get_logger(name: str = "") -> logging.Logger:
    """Return the ``epiframe`` logger, or its ``epiframe.<name>`` child."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


def _remove_own_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, _OWN_HANDLER, False):
            logger.removeHandler(handler)
            handler.close()


def _add_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    handler.setFormatter(logging.Formatter(LINE_FORMAT, TIME_FORMAT))
    setattr(handler, _OWN_HANDLER, True)
    logger.addHandler(handler)


def setup_logging(
    log_file: str | os.PathLike[str] | None = None, *, console: bool = True
) -> logging.Logger:
    """Configure the ``epiframe`` logger and return it.

    Logs to ``log_file`` (parent directories are created; empty or ``None`` means no
    file) and, if ``console`` is set, to stdout. Calling it again replaces the
    handlers set up before, so it is safe to call first without a file and again
    once the configuration is loaded.
    """
    logger = get_logger()
    logger.setLevel(logging.INFO)
    _remove_own_handlers(logger)
    if console:
        _add_handler(logger, StdoutHandler())
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        _add_handler(logger, GzipTimedRotatingFileHandler(log_file))
    return logger


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as ``HH:MM:SS`` (hours may exceed 24)."""
    minutes, secs = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
