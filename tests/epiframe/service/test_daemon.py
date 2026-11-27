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
from unittest.mock import MagicMock, call, create_autospec

import pytest
import requests

from epiframe.bot.telegram import TelegramBot
from epiframe.config import paths
from epiframe.core.logs import get_logger, setup_logging
from epiframe.display.controller import DisplayController
from epiframe.display.hdmi import HdmiPower
from epiframe.display.icons import Icon
from epiframe.plugins.base import Plugin
from epiframe.service import daemon
from epiframe.service.daemon import (
    BOT_START,
    NETWORK_URL,
    OFFLINE,
    ONLINE,
    PARTS,
    STARTED,
    STOPPED,
    WEB_START,
    Parts,
    Service,
    handle_signals,
    run,
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
def display() -> MagicMock:
    mock: MagicMock = create_autospec(DisplayController, instance=True)
    return mock


@pytest.fixture
def make_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    plugins: MagicMock,
    refresher: MagicMock,
    display: MagicMock,
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
        service = Service(
            parts,
            config,
            refresher=refresher,
            display=display,
            frame_factory=factory,
        )
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


def listening(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


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
    assert isinstance(service.refresher, Refresher)
    assert isinstance(service.display, DisplayController)
    assert service.display.settings() is service.frame.config
    assert service.scheduler.start_refresh == service.start_update


def test_frame_triggers_go_to_the_scheduler(make_service: MakeService) -> None:
    service = make_service()

    service.frame.redisplay()

    assert service.scheduler.wait(0) == (False, Trigger.REDISPLAY)


# -------------------------------------------------------------- photo change


def test_start_update(
    make_service: MakeService, refresher: MagicMock, display: MagicMock, tmp_path: Path
) -> None:
    service = make_service(slide_interval="600")
    refresher.run.return_value = 0
    (tmp_path / "photo.bmp").write_bytes(b"BM")

    service.start_update(("prepare", "--again"))

    # a hanging update is stopped after the slide interval
    refresher.run.assert_called_once_with(("prepare", "--again"), 600)
    display.change_icons.assert_called_once_with((Icon.BUSY,), ())
    display.show.assert_called_once_with(Path("photo.bmp"))


def test_prepared_photo_is_shown(
    make_service: MakeService, display: MagicMock, tmp_path: Path
) -> None:
    service = make_service()
    (tmp_path / "photo.bmp").write_bytes(b"BM")

    service.updated(0)

    display.show.assert_called_once_with(Path("photo.bmp"))


def test_failed_update_shows_nothing(
    make_service: MakeService, display: MagicMock, tmp_path: Path
) -> None:
    service = make_service()
    (tmp_path / "photo.bmp").write_bytes(b"BM")  # the previous photo

    service.updated(1)
    service.updated(None)  # not started

    display.show.assert_not_called()
    # the busy icon becomes the error icon
    assert display.change_icons.call_args_list == [
        call((Icon.ERROR,), (Icon.BUSY,)),
        call((Icon.ERROR,), (Icon.BUSY,)),
    ]


def test_no_prepared_photo(
    make_service: MakeService, display: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    make_service().updated(0)

    display.show.assert_not_called()
    display.change_icons.assert_called_once_with((Icon.ERROR,), (Icon.BUSY,))
    assert messages(caplog) == ["Error sending photo to display: no converted photo!"]


def test_display_error_doesnt_end_the_service(
    make_service: MakeService,
    display: MagicMock,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = make_service()
    (tmp_path / "photo.bmp").write_bytes(b"BM")
    display.show.side_effect = OSError("GPIO busy")
    display.change_icons.side_effect = OSError("GPIO still busy")

    service.updated(0)

    display.change_icons.assert_called_once_with((Icon.ERROR,), (Icon.BUSY,))
    assert messages(caplog) == [
        "Error sending photo to display: GPIO busy",
        "Error showing the status icons: GPIO still busy",
    ]


# ------------------------------------------------------------------- network


@pytest.fixture
def connection(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    """Results of the next internet checks (``None``: connected)."""
    results: list[str | None] = []

    def check(url: str, timeout: float) -> str | None:
        assert url == NETWORK_URL
        return results.pop(0)

    monkeypatch.setattr(daemon, "check_internet", check)
    return results


def test_offline_icon_follows_the_connection(
    make_service: MakeService,
    display: MagicMock,
    connection: list[str | None],
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = make_service(offline_icon="1")
    connection.extend([None, None, "timed out", "timed out", None])

    for _ in range(5):
        service.check_network()

    # only the changes (the first check: the icon state is unknown)
    assert display.change_icons.call_args_list == [
        call((), (Icon.OFFLINE,)),
        call((Icon.OFFLINE,), ()),
        call((), (Icon.OFFLINE,)),
    ]
    assert messages(caplog) == [ONLINE, f"{OFFLINE} timed out", ONLINE]


def test_no_check_without_the_offline_icon(
    make_service: MakeService, display: MagicMock, connection: list[str | None]
) -> None:
    service = make_service(offline_icon="0")
    service.online = False

    service.check_network()  # no result in connection: not called

    assert online(service) is None  # checked again once enabled
    display.change_icons.assert_not_called()


def online(service: Service) -> bool | None:
    return service.online


def test_network_check_error_is_logged(
    make_service: MakeService,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = make_service()

    def broken() -> None:
        service.stop()
        raise ValueError("broken config")

    monkeypatch.setattr(service, "check_network", broken)
    service.watch_network()

    assert messages(caplog) == ["Error checking the internet connection! broken config"]


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
        # WEB_START is logged before the server binds its socket: wait for the port
        wait_until(lambda: listening(port))
        answer = requests.get(f"http://127.0.0.1:{port}/api/action=next", timeout=10)
        wait_until(lambda: refresher.run.called)
    finally:
        service.stop()
        runner.join(timeout=30)

    assert not runner.is_alive()
    assert answer.json() == {"status": "OK"}
    refresher.run.assert_called_once_with(("prepare",), service.frame.slide_interval)
    refresher.stop.assert_called_once_with()  # at the stop
    assert messages(caplog)[0] == STARTED
    assert WEB_START in messages(caplog)
    assert messages(caplog)[-1] == STOPPED
    assert [thread.name for thread in service.threads] == [
        "scheduler",
        "stats",
        "web",
        "telegram",
        "network",
    ]
    assert not any(thread.is_alive() for thread in service.threads)
    # the first statistics sample is written when the service stops
    with closing(sqlite3.connect(tmp_path / "stats.db")) as connection:
        assert connection.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] > 0


def test_only_the_bot(make_service: MakeService) -> None:
    service = make_service(PARTS["telegram"])

    service.start()
    service.shutdown()

    assert [thread.name for thread in service.threads] == [
        "scheduler",
        "telegram",
        "network",
    ]


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
def test_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    service = MagicMock()
    service.frame.config.get.return_value = str(tmp_path / "logs" / "service.log")
    created: list[Parts] = []

    def make(parts: Parts) -> MagicMock:
        created.append(parts)
        return service

    monkeypatch.setattr(daemon, "Service", make)
    monkeypatch.setattr(daemon, "handle_signals", lambda served: served.handled())

    assert run("telegram") == 0

    assert created == [PARTS["telegram"]]
    service.frame.config.get.assert_called_with("log_files")
    service.handled.assert_called_once_with()
    service.run.assert_called_once_with()
    get_logger("service").info("To the file")
    assert "To the file" in (tmp_path / "logs" / "service.log").read_text()


@pytest.mark.usefixtures("clean_logger")
def test_run_with_a_broken_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.cfg"
    config.write_text("not an ini file")
    monkeypatch.setattr(paths, "CONFIG_FILE", str(config))

    assert run() == 1

    assert f"Error loading {config} configuration file!" in capsys.readouterr().out
