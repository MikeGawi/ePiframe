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
from PIL import Image

from epiframe.config import paths
from epiframe.config.property import ValueSource
from epiframe.display.base import Capability, Display, DisplayError
from epiframe.display.controller import (
    FRAME_FILE,
    NO_SPI,
    SHOWN_FILE,
    DisplayController,
    DisplayState,
    StateFile,
    display_lock,
)
from epiframe.display.factory import create_display
from epiframe.display.icons import Icon, IconSettings, draw_icons
from epiframe.display.system import spi_enabled
from epiframe.processing.orientation import Orientation, Position

MakeController = Callable[..., DisplayController]


class Config:
    def __init__(self, display_type: str = "SPI", **values: str) -> None:
        self.values = {
            "display_type": display_type,
            "fast_refresh": "0",
            "full_refresh_every": "3",
            "busy_icon": "0",
            "offline_icon": "0",
            "error_icon": "0",
            "icons_position": "1",
            "icons_size": "16",
            "max_partial_refreshes": "3",
            "horizontal": "1",
            "turned": "0",
            "rotation": "90",
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
    assert json.loads((tmp_path / "default.json").read_text()) == {
        "fast_refreshes": 0,
        "partial_refreshes": 0,
        "icons": [],
        "shown": [],
    }


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
    assert StateFile(state_file).read().fast_refreshes == 1


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
    StateFile(state_file).save(DisplayState(fast_refreshes=2))  # another process

    make_controller(fast_refresh="1", full_refresh_every="3").show(Path("a.bmp"))

    assert fast_requests == [False]
    assert StateFile(state_file).read().fast_refreshes == 0


def test_display_without_fast_refresh_is_not_counted(
    make_controller: MakeController, display: MagicMock, state_file: Path
) -> None:
    display.capabilities = frozenset({Capability.FULL})

    make_controller(fast_refresh="1").show(Path("photo.bmp"))

    assert StateFile(state_file).read().fast_refreshes == 0


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
        '{"icons": "busy"}',
        '{"shown": [1]}',
    ],
)
def test_broken_state_file(tmp_path: Path, content: str) -> None:
    path = tmp_path / "display.json"
    path.write_text(content)

    assert StateFile(path).read() == DisplayState()


def test_unknown_icons_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "display.json"
    path.write_text('{"icons": ["busy", "clock"], "partial_refreshes": 2}')

    assert StateFile(path).read() == DisplayState(
        partial_refreshes=2, icons=frozenset({Icon.BUSY})
    )


def test_state_file_that_cant_be_saved(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    StateFile(tmp_path / "missing" / "display.json").save(DisplayState())

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


# ---------------------------------------------------------------- status icons

ICONS_ON = {"busy_icon": "1", "offline_icon": "1", "error_icon": "1"}
SETTINGS = IconSettings(frozenset(Icon), Position.TOP_RIGHT, 16, Orientation())


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    path = tmp_path / "photo.bmp"
    Image.new("1", (120, 60), 1).save(path)
    return path


@pytest.fixture
def partial_display(display: MagicMock) -> MagicMock:
    display.capabilities = frozenset({Capability.FULL, Capability.PARTIAL})
    return display


def image_of(path: Path) -> list[int]:
    with Image.open(path) as image:
        return list(image.convert("1").tobytes())


def expected(photo: Path, icons: set[Icon]) -> list[int]:
    with Image.open(photo) as image:
        return list(draw_icons(image, icons, SETTINGS).convert("1").tobytes())


def test_photo_with_icons(
    make_controller: MakeController,
    display: MagicMock,
    photo: Path,
    state_file: Path,
) -> None:
    state_file.parent.mkdir()
    StateFile(state_file).save(DisplayState(icons=frozenset(Icon)))

    make_controller(**ICONS_ON).show(photo)

    shown = state_file.with_name(SHOWN_FILE)
    display.show.assert_called_once_with(shown)
    # a new photo ends the busy icon and the error; offline stays
    assert image_of(shown) == expected(photo, {Icon.OFFLINE})
    assert image_of(state_file.with_name(FRAME_FILE)) == image_of(photo)
    state = StateFile(state_file).read()
    assert state.icons == state.shown == {Icon.OFFLINE}


def test_photo_without_icons_removes_the_old_copies(
    make_controller: MakeController,
    display: MagicMock,
    photo: Path,
    state_file: Path,
) -> None:
    make_controller(**ICONS_ON).show(photo)

    make_controller().show(photo)

    display.show.assert_called_with(photo)
    assert not state_file.with_name(FRAME_FILE).exists()
    assert not state_file.with_name(SHOWN_FILE).exists()


def test_icons_disabled(
    make_controller: MakeController, display: MagicMock, state_file: Path
) -> None:
    make_controller(spi=False).change_icons(on=[Icon.BUSY])

    assert not state_file.exists()
    display.show_partial.assert_not_called()


def test_icons_need_spi(make_controller: MakeController) -> None:
    with pytest.raises(DisplayError, match=re.escape(NO_SPI)):
        make_controller(spi=False, **ICONS_ON).change_icons(on=[Icon.BUSY])


def test_icon_with_partial_refresh(
    make_controller: MakeController,
    partial_display: MagicMock,
    photo: Path,
    state_file: Path,
    fast_requests: list[bool],
) -> None:
    controller = make_controller(**ICONS_ON)
    controller.show(photo)
    shown = state_file.with_name(SHOWN_FILE)
    before = image_of(shown)
    new_images: list[list[int]] = []
    old_images: list[list[int]] = []

    def show_partial(new: Path, old: Path) -> None:
        new_images.append(image_of(new))
        old_images.append(image_of(old))

    partial_display.show_partial.side_effect = show_partial

    controller.change_icons(on=[Icon.BUSY])

    assert new_images == [expected(photo, {Icon.BUSY})]
    assert old_images == [before]
    assert image_of(shown) == expected(photo, {Icon.BUSY})
    assert fast_requests == [False, False]
    state = StateFile(state_file).read()
    assert state.shown == state.icons == {Icon.BUSY}
    assert state.partial_refreshes == 1
    # kept: HDMI's fbi reads it after it starts
    assert image_of(state_file.with_name("display_next.png")) == expected(
        photo, {Icon.BUSY}
    )


def test_busy_becomes_error(
    make_controller: MakeController,
    partial_display: MagicMock,
    photo: Path,
    state_file: Path,
) -> None:
    controller = make_controller(**ICONS_ON)
    controller.show(photo)
    controller.change_icons(on=[Icon.BUSY])

    controller.change_icons(on=[Icon.ERROR], off=[Icon.BUSY])

    assert partial_display.show_partial.call_count == 2
    shown = state_file.with_name(SHOWN_FILE)
    assert image_of(shown) == expected(photo, {Icon.ERROR})


def test_no_change_no_refresh(
    make_controller: MakeController, partial_display: MagicMock, photo: Path
) -> None:
    controller = make_controller(**ICONS_ON)
    controller.show(photo)

    controller.change_icons(off=[Icon.ERROR])  # not shown anyway

    partial_display.show_partial.assert_not_called()


def test_icon_not_enabled_is_remembered(
    make_controller: MakeController,
    partial_display: MagicMock,
    photo: Path,
    state_file: Path,
) -> None:
    controller = make_controller(busy_icon="1")
    controller.show(photo)

    controller.change_icons(on=[Icon.OFFLINE])

    partial_display.show_partial.assert_not_called()
    state = StateFile(state_file).read()
    assert state.icons == {Icon.OFFLINE}
    assert state.shown == set()


def test_no_photo_shown_yet(
    make_controller: MakeController, partial_display: MagicMock, state_file: Path
) -> None:
    make_controller(**ICONS_ON).change_icons(on=[Icon.OFFLINE])

    partial_display.show_partial.assert_not_called()
    assert StateFile(state_file).read().icons == {Icon.OFFLINE}


def test_display_without_partial_refresh_gets_icons_with_the_photo(
    make_controller: MakeController,
    display: MagicMock,
    photo: Path,
    state_file: Path,
) -> None:
    controller = make_controller(**ICONS_ON)
    controller.show(photo)

    controller.change_icons(on=[Icon.OFFLINE])
    display.show_partial.assert_not_called()
    controller.show(photo)

    assert image_of(state_file.with_name(SHOWN_FILE)) == expected(photo, {Icon.OFFLINE})


def test_full_refresh_after_max_partial_refreshes(
    make_controller: MakeController,
    partial_display: MagicMock,
    photo: Path,
    state_file: Path,
) -> None:
    controller = make_controller(max_partial_refreshes="2", **ICONS_ON)
    controller.show(photo)

    for _ in range(3):
        controller.change_icons(on=[Icon.OFFLINE])
        controller.change_icons(off=[Icon.OFFLINE])

    # partial, partial, full, partial, partial, full
    assert partial_display.show_partial.call_count == 4
    assert partial_display.show.call_count == 1 + 2
    assert StateFile(state_file).read().partial_refreshes == 0


def test_failed_partial_refresh(
    make_controller: MakeController,
    partial_display: MagicMock,
    photo: Path,
    state_file: Path,
) -> None:
    controller = make_controller(**ICONS_ON)
    controller.show(photo)
    before = image_of(state_file.with_name(SHOWN_FILE))
    partial_display.show_partial.side_effect = OSError("SPI transfer failed")

    with pytest.raises(OSError, match="SPI transfer failed"):
        controller.change_icons(on=[Icon.BUSY])

    assert image_of(state_file.with_name(SHOWN_FILE)) == before
    assert not state_file.with_name("display_next.png").exists()
    assert StateFile(state_file).read().shown == set()
