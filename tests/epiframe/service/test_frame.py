import os
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest

from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.config.property import ConfigError
from epiframe.core import system
from epiframe.display.hdmi import HdmiPower
from epiframe.plugins.manager import PluginManager
from epiframe.service import frame as frame_module
from epiframe.service.frame import (
    NEVER,
    Frame,
    Trigger,
    next_update_text,
    timestamp_text,
)

# a Wednesday
NOON = datetime(2026, 11, 25, 12, 0).astimezone()
WORKING = {"start_times": ",".join(["8:00"] * 7), "stop_times": ",".join(["20:00"] * 7)}

TOKEN = "1:abc"  # noqa: S105 (fake)

MakeFrame = Callable[..., Frame]


@pytest.fixture
def plugins(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    manager: MagicMock = create_autospec(PluginManager)
    monkeypatch.setattr(frame_module, "PluginManager", manager)
    return manager


@pytest.fixture
def triggers() -> list[Trigger]:
    return []


@pytest.fixture
def make_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    plugins: MagicMock,
    triggers: list[Trigger],
) -> MakeFrame:
    monkeypatch.chdir(tmp_path)  # relative paths of the default config

    def make(**entries: str) -> Frame:
        write_config(tmp_path / "config.cfg", **(WORKING | entries))
        return Frame(
            triggers.append,
            tmp_path / "config.cfg",
            tmp_path,
            plugins_dir=tmp_path / "plugins",
            hdmi=create_autospec(HdmiPower, instance=True),
        )

    return make


@pytest.fixture
def frame(make_frame: MakeFrame) -> Frame:
    return make_frame()


def write_config(path: Path, **entries: str) -> None:
    config = ConfigManager(path, paths.CONFIG_FILE_DEFAULT)
    for name, value in entries.items():
        config.set(name, value)
    config.save()


# ------------------------------------------------------------------ helpers


def test_trigger_arguments() -> None:
    assert Trigger.NEXT_PHOTO.arguments == ()
    assert Trigger.REDISPLAY.arguments == ("--test-convert", "--test-display")
    assert all(Trigger)  # members are true: the service checks "if trigger"


def test_timestamp_text() -> None:
    assert timestamp_text(datetime(2026, 11, 25, 7, 5, 3, 999)) == (
        "2026-11-25 at 07:05:03"
    )


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(minutes=5), "at 12:05:00\nin 5 mins 0 secs"),
        (timedelta(seconds=59.9), "at 12:00:59\nin 0 mins 59 secs"),
        (timedelta(hours=1, seconds=5), "at 13:00:05\nin 1 hours 0 mins 5 secs"),
        (
            timedelta(days=1, seconds=5),
            "2026-11-26 at 12:00:05\nin 1 days 0 hours 0 mins 5 secs",
        ),
        (
            timedelta(days=2, hours=3, minutes=4, seconds=5),
            "2026-11-27 at 15:04:05\nin 2 days 3 hours 4 mins 5 secs",
        ),
        (timedelta(hours=13), "2026-11-26 at 01:00:00\nin 13 hours 0 mins 0 secs"),
        (-timedelta(minutes=1), "at 11:59:00\nin 0 mins 0 secs"),
    ],
)
def test_next_update_text(delta: timedelta, expected: str) -> None:
    assert next_update_text(NOON + delta, NOON) == expected


def test_next_update_text_never() -> None:
    assert next_update_text(None, NOON) == NEVER


# ------------------------------------------------------------- configuration


def test_init(make_frame: MakeFrame, tmp_path: Path, plugins: MagicMock) -> None:
    (tmp_path / "time").write_text("3")  # left by the previous run

    frame = make_frame()

    assert not (tmp_path / "time").exists()
    assert frame.config_file == tmp_path / "config.cfg"
    assert frame.root == tmp_path
    assert frame.plugins is plugins.return_value
    plugins.assert_called_once_with(tmp_path / "plugins", frame.config)
    assert frame.next_update is not None


def test_init_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plugins: MagicMock
) -> None:
    monkeypatch.chdir(tmp_path)  # the default config file is relative to it

    frame = Frame(lambda trigger: None)

    assert frame.config_file == Path(paths.CONFIG_FILE)
    assert frame.root == paths.EPIFRAME_DIR
    assert isinstance(frame.hdmi, HdmiPower)
    plugins.assert_called_once_with(Path(paths.PLUGINS_DIR), frame.config)


def test_config_error(tmp_path: Path, plugins: MagicMock) -> None:
    (tmp_path / "config.cfg").mkdir()

    with pytest.raises(ConfigError, match=r"Error loading .*config\.cfg configuration"):
        Frame(lambda trigger: None, tmp_path / "config.cfg", tmp_path)


def test_refresh_unchanged(frame: Frame) -> None:
    config = frame.config

    frame.refresh()

    assert frame.config is config


def test_refresh_changed(frame: Frame) -> None:
    config = frame.config
    write_config(frame.config_file, slide_interval="120")
    os.utime(frame.config_file, (0, 1))

    frame.refresh()

    assert frame.config is not config
    assert frame.slide_interval == 120


def test_refresh_missing_file(frame: Frame) -> None:
    config = frame.config
    frame.config_file.unlink()

    frame.refresh()

    assert frame.config is not config
    assert frame.config_file.exists()  # created from the default


def test_settings(make_frame: MakeFrame) -> None:
    frame = make_frame(
        slide_interval="300",
        units="imperial",
        token=TOKEN,
        chat_id="1,2",
        interval_mult="0",
        interval_max_mult="7",
        allow_triggers="0",
        use_web="0",
        use_telebot="1",
        show_stats="0",
        stats_db_file="data/stats.db",
    )

    assert frame.slide_interval == 300
    assert frame.metric is False
    assert frame.token == TOKEN
    assert frame.chat_id == "1,2"
    assert frame.interval_enabled is False
    assert frame.max_interval == 7
    assert frame.triggers_enabled is False
    assert frame.web_enabled is False
    assert frame.telegram_enabled is True
    assert frame.stats_enabled is False
    assert frame.stats_file == Path("data/stats.db")


def test_settings_other_values(make_frame: MakeFrame) -> None:
    frame = make_frame(units="metric", interval_mult="1", allow_triggers="1")

    assert frame.metric is True
    assert frame.interval_enabled is True
    assert frame.triggers_enabled is True


# -------------------------------------------------------------- photo change


def test_state_idle(frame: Frame) -> None:
    assert frame.busy is False
    assert frame.state == "Idle"


def test_state_busy(frame: Frame, tmp_path: Path) -> None:
    (tmp_path / "pid").write_text("123")

    assert frame.busy is True
    assert frame.state == "Busy"


def test_working(frame: Frame) -> None:
    assert frame.working(NOON) is True
    assert frame.working(NOON.replace(hour=21)) is False


def test_working_now(make_frame: MakeFrame) -> None:
    always = make_frame(start_times=",".join(["0:00"] * 7), stop_times="-,-,-,-,-,-,-")

    assert always.working() is True


def test_schedule_next(make_frame: MakeFrame) -> None:
    frame = make_frame(slide_interval="600")

    frame.schedule_next(NOON)

    assert frame.next_update == NOON + timedelta(minutes=10)


def test_schedule_next_multiplied(make_frame: MakeFrame, tmp_path: Path) -> None:
    frame = make_frame(slide_interval="600")
    (tmp_path / "time").write_text("3")

    frame.schedule_next(NOON)

    assert frame.next_update == NOON + timedelta(minutes=30)


def test_schedule_next_off_hours(frame: Frame) -> None:
    frame.schedule_next(NOON.replace(hour=21))

    assert frame.next_update == datetime(2026, 11, 26, 8, 0).astimezone()


def test_schedule_next_never(make_frame: MakeFrame) -> None:
    frame = make_frame(start_times="-,-,-,-,-,-,-")

    frame.schedule_next(NOON)

    assert frame.next_update is None
    assert frame.next_update_text(NOON) == NEVER


def test_schedule_next_now(make_frame: MakeFrame) -> None:
    always = make_frame(
        start_times=",".join(["0:00"] * 7),
        stop_times="-,-,-,-,-,-,-",
        slide_interval="60",
    )
    before = datetime.now().astimezone()

    always.schedule_next()

    assert always.next_update is not None
    assert before + timedelta(seconds=60) <= always.next_update
    assert always.next_update <= datetime.now().astimezone() + timedelta(seconds=60)


def test_next_update_text_of_frame(make_frame: MakeFrame) -> None:
    frame = make_frame(slide_interval="600")
    frame.schedule_next(NOON)

    assert frame.next_update_text(NOON) == "at 12:10:00\nin 10 mins 0 secs"
    assert frame.next_update_text().startswith(("at ", "2026-11-25 at "))


@pytest.mark.parametrize(
    ("action", "trigger"),
    [("next_photo", Trigger.NEXT_PHOTO), ("redisplay", Trigger.REDISPLAY)],
)
def test_triggers(
    frame: Frame,
    triggers: list[Trigger],
    tmp_path: Path,
    action: str,
    trigger: Trigger,
) -> None:
    (tmp_path / "time").write_text("3")

    getattr(frame, action)()

    assert triggers == [trigger]
    assert not (tmp_path / "time").exists()


# --------------------------------------------------------------------- files


@pytest.fixture
def photos(make_frame: MakeFrame, tmp_path: Path) -> Frame:
    (tmp_path / "convert").mkdir()
    return make_frame(photo_convert_path=str(tmp_path / "convert"))


def test_path(photos: Frame, tmp_path: Path) -> None:
    assert photos.path("photo_convert_filename") == tmp_path / "convert" / "photo.bmp"


def test_file_and_modified(photos: Frame, tmp_path: Path) -> None:
    assert photos.file("thumb_photo_convert_filename") is None
    assert photos.modified("thumb_photo_convert_filename") == 0
    assert photos.current_file() is None

    thumbnail = tmp_path / "convert" / "photo_thumb.jpg"
    thumbnail.write_bytes(b"JPEG")
    os.utime(thumbnail, (5, 5))
    (tmp_path / "convert" / "photo.bmp").write_bytes(b"BMP")

    assert photos.file("thumb_photo_convert_filename") == thumbnail
    assert photos.modified("thumb_photo_convert_filename") == 5
    assert photos.current_file() == tmp_path / "convert" / "photo.bmp"


def test_file_directory_is_not_a_file(photos: Frame, tmp_path: Path) -> None:
    (tmp_path / "convert" / "photo.bmp").mkdir()

    assert photos.current_file() is None


def test_download_file(photos: Frame, tmp_path: Path) -> None:
    assert photos.download_file("png") == tmp_path / "convert" / "origphoto.png"


def test_original_file(photos: Frame, tmp_path: Path) -> None:
    folder = tmp_path / "convert"
    assert photos.original_file() is None

    (folder / "origphoto_thumb.jpg").write_bytes(b"thumbnail, not the original")
    (folder / "origphoto.jpg").write_bytes(b"old")
    time.sleep(0.01)
    (folder / "origphoto.png").write_bytes(b"new")

    assert photos.original_file() == folder / "origphoto.png"


def test_original_file_name_with_glob_characters(
    make_frame: MakeFrame, tmp_path: Path
) -> None:
    frame = make_frame(photo_download_name="[orig]")
    (tmp_path / "o.jpg").write_bytes(b"not it")
    (tmp_path / "[orig].jpg").write_bytes(b"it")

    assert frame.original_file() == Path("[orig].jpg")


# ------------------------------------------------------------ system, screen


@pytest.mark.parametrize(
    ("action", "function"),
    [("reboot", "reboot"), ("power_off", "power_off"), ("restart", "restart_service")],
)
def test_system_actions(
    frame: Frame, monkeypatch: pytest.MonkeyPatch, action: str, function: str
) -> None:
    called = MagicMock(return_value=True)
    monkeypatch.setattr(system, function, called)

    getattr(frame, action)()

    called.assert_called_once_with()


@pytest.mark.parametrize(
    ("display_type", "control", "calls"),
    [("SPI", "1", 0), ("HDMI", "0", 0), ("HDMI", "1", 1)],
)
def test_power_display(
    make_frame: MakeFrame, display_type: str, control: str, calls: int
) -> None:
    frame = make_frame(display_type=display_type, control_display_power=control)

    frame.power_display(False)

    hdmi: MagicMock = frame.hdmi  # type: ignore[assignment]
    assert hdmi.set.call_count == calls
    if calls:
        hdmi.set.assert_called_once_with(False)
