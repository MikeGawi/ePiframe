import logging
import signal
import socket
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import closing
from functools import partial
from pathlib import Path
from types import FrameType
from typing import Any
from unittest.mock import MagicMock, create_autospec

import pytest
import requests

from epiframe.bot.telegram import TelegramBot
from epiframe.config import paths
from epiframe.core.logs import get_logger, setup_logging
from epiframe.display.hdmi import HdmiPower
from epiframe.plugins.base import Plugin
from epiframe.service import daemon
from epiframe.service.daemon import (
    BOT_START,
    PARTS,
    STARTED,
    STOPPED,
    WEB_START,
    Parts,
    Service,
    handle_signals,
    main,
    parser,
)
from epiframe.service.frame import Frame, Trigger
from epiframe.service.refresh import Refresher
from tests.epiframe.service.conftest import WORKING, write_config

TOKEN = "1:abc"  # noqa: S105 (fake)
# FILE entries that exist on every machine (verification of a full config)
MACHINE_INDEPENDENT = {"convert_bin_path": __file__, "fbi_bin_path": __file__}

MakeService = Callable[..., Service]


@pytest.fixture(autouse=True)
def info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="epiframe")


@pytest.fixture
def refresher() -> MagicMock:
    mock: MagicMock = create_autospec(Refresher, instance=True)
    return mock


@pytest.fixture
def make_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    plugins: MagicMock,
    refresher: MagicMock,
) -> Iterator[MakeService]:
    monkeypatch.chdir(tmp_path)  # relative paths of the default config
    monkeypatch.setattr(paths, "USERS_DB_FILE", str(tmp_path / "users.db"))
    monkeypatch.setattr(paths, "SECRET_KEY_FILE", str(tmp_path / "secret.key"))
    plugins.return_value.with_hook.return_value = []
    services: list[Service] = []

    def make(parts: Parts = PARTS[None], **entries: str) -> Service:
        config = tmp_path / "config.cfg"
        write_config(config, **(WORKING | MACHINE_INDEPENDENT | entries))
        factory = partial(
            Frame,
            root=paths.EPIFRAME_DIR,
            plugins_dir=tmp_path / "plugins",
            hdmi=create_autospec(HdmiPower, instance=True),
        )
        service = Service(parts, config, refresher=refresher, frame_factory=factory)
        services.append(service)
        return service

    yield make
    for service in services:  # no threads left behind by a failed test
        service.stop()
        service.scheduler.stop()


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_until(condition: Callable[[], object], timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.02)


def messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records]


# ------------------------------------------------------------------ the parts


def test_parts() -> None:
    assert PARTS[None] == Parts(schedule=True, web=True, telegram=True)
    assert PARTS["web"] == Parts(schedule=False, web=True, telegram=False)
    assert PARTS["telegram"] == Parts(schedule=False, web=False, telegram=True)


def test_init(make_service: MakeService, tmp_path: Path) -> None:
    service = make_service(PARTS["web"])

    assert service.frame.config_file == tmp_path / "config.cfg"
    assert service.scheduler.frame is service.frame
    assert service.scheduler.scheduled is False


def test_default_config_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "CONFIG_FILE", str(tmp_path / "config.cfg"))
    frames: list[tuple[Any, ...]] = []

    def factory(*arguments: Any) -> MagicMock:
        frames.append(arguments)
        return MagicMock()

    service = Service(frame_factory=factory)

    assert frames == [(service.trigger, str(tmp_path / "config.cfg"))]
    assert isinstance(service.scheduler.start_refresh, type(Refresher().start))


def test_frame_triggers_go_to_the_scheduler(make_service: MakeService) -> None:
    service = make_service()

    service.frame.redisplay()

    assert service.scheduler.wait(0) == (False, Trigger.REDISPLAY)


# --------------------------------------------------------------- run and stop


def test_run_serves_the_webui_until_stopped(
    make_service: MakeService,
    refresher: MagicMock,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    port = free_port()
    service = make_service(web_host="127.0.0.1", web_port=str(port), use_web="1")
    runner = threading.Thread(target=service.run)
    runner.start()
    try:
        wait_until(lambda: WEB_START in messages(caplog))
        answer = requests.get(f"http://127.0.0.1:{port}/api/action=next", timeout=10)
        wait_until(lambda: refresher.start.called)
    finally:
        service.stop()
        runner.join(timeout=30)

    assert not runner.is_alive()
    assert answer.json() == {"status": "OK"}
    refresher.start.assert_called_once_with(())
    assert messages(caplog)[0] == STARTED
    assert messages(caplog)[-1] == STOPPED
    assert [thread.name for thread in service.threads] == [
        "scheduler",
        "stats",
        "web",
        "telegram",
    ]
    assert not any(thread.is_alive() for thread in service.threads)
    # the first statistics sample is written when the service stops
    with closing(sqlite3.connect(tmp_path / "stats.db")) as connection:
        assert connection.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] > 0


def test_only_the_bot(make_service: MakeService) -> None:
    service = make_service(PARTS["telegram"])

    service.start()
    service.shutdown()

    assert [thread.name for thread in service.threads] == ["scheduler", "telegram"]


def test_webui_start_is_retried(
    make_service: MakeService,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[float] = []
    monkeypatch.setattr(daemon, "RETRY", 0.01)
    service = make_service(PARTS["web"], use_web="1")

    def fail() -> None:
        attempts.append(time.monotonic())
        raise OSError("Address already in use")

    monkeypatch.setattr(service, "serve_web", fail)
    service.start()
    wait_until(lambda: len(attempts) >= 2)
    service.shutdown()

    assert "Error configuring WebUI! Address already in use" in caplog.text


def test_webui_disabled(
    make_service: MakeService, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = make_service(use_web="0")
    monkeypatch.setattr(daemon, "WebUI", MagicMock(side_effect=AssertionError))

    service.serve_web()  # returns at once


def test_bot(
    make_service: MakeService,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = create_autospec(TelegramBot)
    monkeypatch.setattr(daemon, "TelegramBot", bot)
    service = make_service(PARTS["telegram"], use_telebot="1", token=TOKEN)

    service.start()
    wait_until(lambda: bot.return_value.start.called)
    service.shutdown()

    bot.assert_called_once_with(service.frame)
    bot.return_value.stop.assert_called_once_with()
    assert BOT_START in messages(caplog)


def test_bot_not_started_after_the_stop(
    make_service: MakeService, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = create_autospec(TelegramBot)
    monkeypatch.setattr(daemon, "TelegramBot", bot)
    service = make_service(use_telebot="1", token=TOKEN)
    service.stop()

    service.run_bot()

    bot.return_value.start.assert_not_called()


def test_bot_disabled(
    make_service: MakeService, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = make_service(use_telebot="0")
    monkeypatch.setattr(daemon, "TelegramBot", MagicMock(side_effect=AssertionError))

    service.run_bot()


def test_no_stats_when_disabled(make_service: MakeService, tmp_path: Path) -> None:
    service = make_service(use_web="1", show_stats="0")
    service.stop()

    service.record_stats()

    assert not (tmp_path / "stats.db").exists()


def test_stats_errors_are_logged(
    make_service: MakeService,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = make_service(use_web="1", show_stats="1")
    monkeypatch.setattr(
        service.frame, "refresh", MagicMock(side_effect=OSError("disk"))
    )
    monkeypatch.setattr(service.stopping, "wait", lambda timeout: service.stop())

    service.record_stats()

    assert "Error getting statistics! disk" in caplog.text


def plugin(body: Callable[[Frame, threading.Event], object]) -> MagicMock:
    mock: MagicMock = create_autospec(Plugin, instance=True)
    mock.name = "Clock"
    mock.folder = "clock"
    mock.service_thread.side_effect = body
    return mock


def test_plugin_threads(
    make_service: MakeService, plugins: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    seen: list[Frame] = []

    def wait_for_stop(frame: Frame, stop: threading.Event) -> None:
        seen.append(frame)
        stop.wait()

    def broken(frame: Frame, stop: threading.Event) -> None:
        raise RuntimeError("no clock")

    plugins.return_value.with_hook.return_value = [
        plugin(wait_for_stop),
        plugin(broken),
    ]
    service = make_service(PARTS["web"])

    service.start()
    wait_until(lambda: "no clock" in caplog.text)
    service.shutdown()

    plugins.return_value.with_hook.assert_called_with("service_thread")
    assert seen == [service.frame]
    assert "Service thread of plugin Clock failed: RuntimeError('no clock')" in (
        caplog.text
    )
    assert [thread.name for thread in service.threads][-2:] == [
        "plugin clock",
        "plugin clock",
    ]
    assert not any(thread.is_alive() for thread in service.threads)


def test_stuck_thread_is_reported(
    make_service: MakeService,
    plugins: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    release = threading.Event()
    plugins.return_value.with_hook.return_value = [
        plugin(lambda frame, stop: release.wait())
    ]
    monkeypatch.setattr(daemon, "STOP_TIMEOUT", 0)
    service = make_service(PARTS["telegram"])

    service.start()
    service.shutdown()
    release.set()

    warning = caplog.records[-2].getMessage()
    assert warning.startswith("Threads still running when stopping: ")
    assert warning.endswith("plugin clock")


# --------------------------------------------------------------------- command


def test_parser() -> None:
    assert parser().parse_args([]).part is None
    assert parser().parse_args(["web"]).part == "web"
    with pytest.raises(SystemExit):
        parser().parse_args(["start"])


def test_handle_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    handlers: dict[int, Callable[[int, FrameType | None], None]] = {}
    monkeypatch.setattr(
        signal, "signal", lambda number, handler: handlers.update({number: handler})
    )
    service = MagicMock()

    handle_signals(service)
    handlers[signal.SIGTERM](signal.SIGTERM, None)

    assert set(handlers) == {signal.SIGTERM, signal.SIGINT}
    service.stop.assert_called_once_with()


@pytest.fixture
def clean_logger() -> Iterator[None]:
    yield
    setup_logging(console=False)
    get_logger().setLevel(logging.NOTSET)


@pytest.mark.usefixtures("clean_logger")
def test_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    service = MagicMock()
    service.frame.config.get.return_value = str(tmp_path / "logs" / "service.log")
    created: list[Parts] = []

    def make(parts: Parts) -> MagicMock:
        created.append(parts)
        return service

    monkeypatch.setattr(daemon, "Service", make)
    monkeypatch.setattr(daemon, "handle_signals", lambda served: served.handled())

    assert main(["telegram"]) == 0

    assert created == [PARTS["telegram"]]
    service.frame.config.get.assert_called_with("log_files")
    service.handled.assert_called_once_with()
    service.run.assert_called_once_with()
    get_logger("service").info("To the file")
    assert "To the file" in (tmp_path / "logs" / "service.log").read_text()


@pytest.mark.usefixtures("clean_logger")
def test_main_with_a_broken_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.cfg"
    config.write_text("not an ini file")
    monkeypatch.setattr(paths, "CONFIG_FILE", str(config))

    assert main([]) == 1

    assert f"Error loading {config} configuration file!" in capsys.readouterr().out
