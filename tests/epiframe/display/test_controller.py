import fcntl
import json
import logging
import os
import re
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest

from epiframe.config import paths
from epiframe.config.property import ValueSource
from epiframe.display.base import Capability, Display, DisplayError
from epiframe.display.controller import (
    NO_SPI,
    DisplayController,
    RefreshCounter,
    display_lock,
)
from epiframe.display.factory import create_display
from epiframe.display.system import spi_enabled

MakeController = Callable[..., DisplayController]


class Config:
    def __init__(self, display_type: str = "SPI", **values: str) -> None:
        self.values = {
            "display_type": display_type,
            "fast_refresh": "0",
            "full_refresh_every": "3",
        } | values

    def get(self, name: str) -> str:
        return self.values[name]

    def getint(self, name: str) -> int:
        return int(self.values[name])


@pytest.fixture(autouse=True)
def info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="epiframe")


@pytest.fixture
def lock_file(tmp_path: Path) -> Path:
    return tmp_path / "data" / "display.lock"


@pytest.fixture
def state_file(tmp_path: Path) -> Path:
    return tmp_path / "data" / "display.json"


@pytest.fixture
def display() -> MagicMock:
    mock: MagicMock = create_autospec(Display, instance=True)
    mock.capabilities = frozenset({Capability.FULL, Capability.FAST_FULL})
    return mock


@pytest.fixture
def fast_requests() -> list[bool]:
    """The ``fast`` argument of every display created."""
    return []


@pytest.fixture
def make_controller(
    display: MagicMock, lock_file: Path, state_file: Path, fast_requests: list[bool]
) -> MakeController:
    def factory(settings: ValueSource, fast: bool) -> MagicMock:
        fast_requests.append(fast)
        return display

    def make(
        display_type: str = "SPI", *, spi: bool = True, **values: str
    ) -> DisplayController:
        config = Config(display_type, **values)
        return DisplayController(
            lambda: config,
            factory=factory,
            spi_check=lambda: spi,
            lock_file=lock_file,
            state_file=state_file,
        )

    return make


@contextmanager
def held(path: Path) -> Iterator[int]:
    """The lock held by another open file (as another process would)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDONLY | os.O_CREAT)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield descriptor
    finally:
        os.close(descriptor)


def test_defaults() -> None:
    config = Config()
    controller = DisplayController(lambda: config)

    assert controller.settings() is config
    assert controller.factory is create_display
    assert controller.spi_check is spi_enabled
    assert controller.lock_file is None
    assert controller.state_file is None


def test_show(
    make_controller: MakeController,
    display: MagicMock,
    lock_file: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    make_controller().show(Path("photo.bmp"))

    display.show.assert_called_once_with(Path("photo.bmp"))
    assert caplog.messages == ["Sending to display..."]
    assert lock_file.exists()  # its folder is created


def test_show_holds_the_lock(
    make_controller: MakeController, display: MagicMock, lock_file: Path
) -> None:
    def show(file: Path) -> None:
        descriptor = os.open(lock_file, os.O_RDONLY)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(descriptor)

    display.show.side_effect = show

    make_controller().show(Path("photo.bmp"))

    display.show.assert_called_once()


def test_epaper_needs_spi(make_controller: MakeController, display: MagicMock) -> None:
    with pytest.raises(DisplayError, match=re.escape(NO_SPI)):
        make_controller(spi=False).show(Path("photo.bmp"))

    display.show.assert_not_called()


def test_hdmi_needs_no_spi(make_controller: MakeController, display: MagicMock) -> None:
    make_controller("HDMI", spi=False).show(Path("photo.bmp"))

    display.show.assert_called_once_with(Path("photo.bmp"))


def test_default_files(
    display: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths, "DISPLAY_LOCK_FILE", str(tmp_path / "default.lock"))
    monkeypatch.setattr(paths, "DISPLAY_STATE_FILE", str(tmp_path / "default.json"))
    config = Config()
    controller = DisplayController(
        lambda: config, factory=lambda settings, fast: display, spi_check=lambda: True
    )
    controller.show(Path("photo.bmp"))

    assert (tmp_path / "default.lock").exists()
    assert json.loads((tmp_path / "default.json").read_text()) == {"fast_refreshes": 0}


# -------------------------------------------------------------- fast refresh


def test_fast_refresh_off(
    make_controller: MakeController, fast_requests: list[bool]
) -> None:
    controller = make_controller()

    for _ in range(4):
        controller.show(Path("photo.bmp"))

    assert fast_requests == [False] * 4


def test_every_nth_refresh_is_a_full_one(
    make_controller: MakeController, fast_requests: list[bool], state_file: Path
) -> None:
    controller = make_controller(fast_refresh="1", full_refresh_every="3")

    for _ in range(7):
        controller.show(Path("photo.bmp"))

    assert fast_requests == [True, True, False, True, True, False, True]
    assert RefreshCounter(state_file).read() == 1


def test_always_full_refresh(
    make_controller: MakeController, fast_requests: list[bool]
) -> None:
    controller = make_controller(fast_refresh="1", full_refresh_every="1")

    controller.show(Path("photo.bmp"))
    controller.show(Path("photo.bmp"))

    assert fast_requests == [False, False]


def test_counter_survives_restarts(
    make_controller: MakeController, fast_requests: list[bool], state_file: Path
) -> None:
    state_file.parent.mkdir()
    RefreshCounter(state_file).save(2)  # e.g. by another process

    make_controller(fast_refresh="1", full_refresh_every="3").show(Path("a.bmp"))

    assert fast_requests == [False]
    assert RefreshCounter(state_file).read() == 0


def test_display_without_fast_refresh_is_not_counted(
    make_controller: MakeController, display: MagicMock, state_file: Path
) -> None:
    display.capabilities = frozenset({Capability.FULL})

    make_controller(fast_refresh="1").show(Path("photo.bmp"))

    assert RefreshCounter(state_file).read() == 0


def test_failed_refresh_is_not_counted(
    make_controller: MakeController, display: MagicMock, state_file: Path
) -> None:
    display.show.side_effect = OSError("SPI transfer failed")

    with pytest.raises(OSError, match="SPI transfer failed"):
        make_controller(fast_refresh="1").show(Path("photo.bmp"))
    assert not state_file.exists()


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json",
        "[]",
        '{"other": 1}',
        '{"fast_refreshes": "2"}',
        '{"fast_refreshes": -1}',
    ],
)
def test_broken_state_file(tmp_path: Path, content: str) -> None:
    path = tmp_path / "display.json"
    path.write_text(content)

    assert RefreshCounter(path).read() == 0


def test_state_file_that_cant_be_saved(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    RefreshCounter(tmp_path / "missing" / "display.json").save(1)

    assert caplog.messages[0].startswith("Can't save the display state ")


def test_driver_error_releases_the_lock(
    make_controller: MakeController, display: MagicMock, lock_file: Path
) -> None:
    display.show.side_effect = OSError("SPI transfer failed")

    with pytest.raises(OSError, match="SPI transfer failed"):
        make_controller().show(Path("photo.bmp"))
    with display_lock(lock_file, timeout=0):
        pass


# ---------------------------------------------------------------------- lock


def test_lock_is_released(lock_file: Path) -> None:
    with display_lock(lock_file):
        pass
    with display_lock(lock_file, timeout=0):
        pass


def test_busy_lock(lock_file: Path, caplog: pytest.LogCaptureFixture) -> None:
    with (
        held(lock_file),
        pytest.raises(DisplayError, match=r"still busy after 0\.05 seconds"),
        display_lock(lock_file, timeout=0.05, poll=0.01),
    ):
        pass  # pragma: no cover - never entered

    assert caplog.messages == [
        "Waiting for the display (another refresh is running)..."
    ]


def test_lock_waits_for_the_other_refresh(
    lock_file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    taken = threading.Event()
    release = threading.Event()

    def other() -> None:
        with held(lock_file):
            taken.set()
            release.wait(10)

    thread = threading.Thread(target=other)
    thread.start()
    assert taken.wait(10)
    threading.Timer(0.1, release.set).start()

    with display_lock(lock_file, timeout=10, poll=0.01):
        assert release.is_set()
    thread.join(10)

    # logged once, however many attempts
    assert caplog.messages == [
        "Waiting for the display (another refresh is running)..."
    ]


def test_lock_file_without_write_access(lock_file: Path) -> None:
    lock_file.parent.mkdir()
    lock_file.touch(mode=0o444)
    lock_file.chmod(0o444)

    with display_lock(lock_file, timeout=0):
        pass
