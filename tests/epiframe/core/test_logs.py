import gzip
import logging
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from epiframe.core import logs
from epiframe.core.logs import (
    GzipTimedRotatingFileHandler,
    StdoutHandler,
    format_duration,
    get_logger,
    setup_logging,
)

LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} : (?P<message>.*)$")


def _messages(text: str) -> list[str]:
    matches = [LINE.match(line) for line in text.splitlines()]
    return [match["message"] if match else "" for match in matches]


@pytest.fixture(autouse=True)
def clean_logger() -> Iterator[None]:
    yield
    setup_logging(console=False)
    logger = get_logger()
    assert logger.handlers == []
    logger.setLevel(logging.NOTSET)


def test_get_logger() -> None:
    assert get_logger().name == "epiframe"
    assert get_logger("service").name == "epiframe.service"
    assert get_logger("service").parent is get_logger()


def test_console_only(capsys: pytest.CaptureFixture[str]) -> None:
    logger = setup_logging()
    get_logger("child").info("Hello")
    assert _messages(capsys.readouterr().out) == ["Hello"]
    assert logger.level == logging.INFO
    assert [type(handler) for handler in logger.handlers] == [StdoutHandler]


def test_console_follows_stdout_redirect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    setup_logging()
    redirected = tmp_path / "out.txt"
    with redirected.open("w") as stream:
        monkeypatch.setattr(sys, "stdout", stream)
        get_logger().info("Redirected")
    assert "Redirected" in redirected.read_text()


def test_file_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log_file = tmp_path / "logs" / "nested" / "ePiframe.log"
    setup_logging(log_file, console=False)
    get_logger().info("To file")
    get_logger().error("Fail!")
    assert capsys.readouterr().out == ""
    assert _messages(log_file.read_text()) == ["To file", "Fail!"]


@pytest.mark.parametrize("log_file", [None, ""])
def test_no_file(log_file: str | None) -> None:
    logger = setup_logging(log_file, console=False)
    assert logger.handlers == []


def test_console_only_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(logs.CONSOLE_ONLY_ENV, "1")
    log_file = tmp_path / "ePiframe.log"

    logger = setup_logging(log_file)
    get_logger().info("Console only")

    assert [type(handler) for handler in logger.handlers] == [StdoutHandler]
    assert not log_file.exists()
    assert _messages(capsys.readouterr().out) == ["Console only"]


def test_log_line_is_kept_as_it_is(tmp_path: Path) -> None:
    log_file = tmp_path / "ePiframe.log"
    setup_logging(log_file, console=False)

    logs.log_line(get_logger("service"), "2026-11-25 12:00:00 : From 100% child")
    logs.log_line(get_logger(), "Traceback (most recent call last):")
    get_logger().info("Own")

    lines = log_file.read_text().splitlines()
    assert lines[:2] == [
        "2026-11-25 12:00:00 : From 100% child",
        "Traceback (most recent call last):",
    ]
    assert _messages(lines[2]) == ["Own"]


def test_setup_again_replaces_own_handlers_only(tmp_path: Path) -> None:
    logger = get_logger()
    foreign = logging.NullHandler()
    logger.addHandler(foreign)
    try:
        setup_logging()
        setup_logging(tmp_path / "ePiframe.log")
        own = [handler for handler in logger.handlers if handler is not foreign]
        assert [type(handler) for handler in own] == [
            StdoutHandler,
            GzipTimedRotatingFileHandler,
        ]
        assert foreign in logger.handlers
    finally:
        logger.removeHandler(foreign)


def test_rotation_is_daily_gzip(tmp_path: Path) -> None:
    handler = GzipTimedRotatingFileHandler(tmp_path / "ePiframe.log")
    try:
        assert handler.when == "MIDNIGHT"
        assert handler.backupCount == logs.BACKUP_COUNT
        assert handler.namer is not None
        assert handler.namer("ePiframe.log.2026-11-21") == "ePiframe.log.2026-11-21.gz"
    finally:
        handler.close()


def test_rollover_gzips_old_file(tmp_path: Path) -> None:
    log_file = tmp_path / "ePiframe.log"
    setup_logging(log_file, console=False)
    get_logger().info("Old line")
    handler = next(
        handler
        for handler in get_logger().handlers
        if isinstance(handler, GzipTimedRotatingFileHandler)
    )
    handler.doRollover()
    get_logger().info("New line")

    (rotated,) = tmp_path.glob("ePiframe.log.*.gz")
    with gzip.open(rotated, "rt") as file:
        assert "Old line" in file.read()
    assert "Old line" not in log_file.read_text()
    assert "New line" in log_file.read_text()


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00:00"),
        (0.4, "00:00:00"),
        (59.6, "00:01:00"),
        (3661, "01:01:01"),
        (90000, "25:00:00"),
    ],
)
def test_format_duration(seconds: float, expected: str) -> None:
    assert format_duration(seconds) == expected
