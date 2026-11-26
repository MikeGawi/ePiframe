import logging
import threading
from collections.abc import Callable, Sequence
from unittest.mock import MagicMock

import pytest

from epiframe.service import scheduler as scheduler_module
from epiframe.service.frame import Frame, Trigger, timestamp_text
from epiframe.service.scheduler import (
    IDLE_CHECK,
    MULTIPLIED,
    NO_NEXT,
    SLEEP_NOTICE_EVERY,
    SLEEPING,
    STARTING,
    TRIGGERED,
    PhotoScheduler,
)
from tests.epiframe.service.conftest import MakeFrame

HDMI = {"display_type": "HDMI", "control_display_power": "1"}


class Starts(list[tuple[str, ...]]):
    """Records the ``start_refresh`` calls; :attr:`event` is set on each."""

    def __init__(self) -> None:
        super().__init__()
        self.event = threading.Event()

    def __call__(self, arguments: Sequence[str]) -> None:
        self.append(tuple(arguments))
        self.event.set()


@pytest.fixture
def starts() -> Starts:
    return Starts()


@pytest.fixture(autouse=True)
def info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="epiframe")


MakeScheduler = Callable[..., PhotoScheduler]


@pytest.fixture
def make_scheduler(make_frame: MakeFrame, starts: Starts) -> MakeScheduler:
    def make(
        *, working: bool = True, scheduled: bool = True, **entries: str
    ) -> PhotoScheduler:
        frame = make_frame(**(HDMI | entries))
        frame.working = lambda now=None: working  # type: ignore[method-assign]
        return PhotoScheduler(frame, starts, scheduled=scheduled)

    return make


def hdmi(frame: Frame) -> MagicMock:
    power: MagicMock = frame.hdmi  # type: ignore[assignment]
    return power


def messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records]


def test_task_changes_the_photo(
    make_scheduler: MakeScheduler, starts: Starts, caplog: pytest.LogCaptureFixture
) -> None:
    scheduler = make_scheduler(slide_interval="300")

    assert scheduler.task() == 300

    assert starts == [("prepare",)]
    hdmi(scheduler.frame).set.assert_called_once_with(True)
    assert STARTING in messages(caplog)
    assert scheduler.frame.next_update is not None
    assert messages(caplog)[-1].endswith(timestamp_text(scheduler.frame.next_update))


def test_trigger_arguments(make_scheduler: MakeScheduler, starts: Starts) -> None:
    scheduler = make_scheduler()

    scheduler.task(Trigger.REDISPLAY)

    assert starts == [("prepare", "--again")]


def test_off_hours(
    make_scheduler: MakeScheduler, starts: Starts, caplog: pytest.LogCaptureFixture
) -> None:
    scheduler = make_scheduler(working=False)

    delays = [scheduler.task() for _ in range(SLEEP_NOTICE_EVERY + 1)]

    assert delays == [IDLE_CHECK] * (SLEEP_NOTICE_EVERY + 1)
    assert starts == []
    hdmi(scheduler.frame).set.assert_called_with(False)
    assert messages(caplog).count(SLEEPING) == 2  # first and 11th check
    assert "Next update" not in caplog.text


def test_sleep_notice_starts_again_after_work(
    make_scheduler: MakeScheduler, caplog: pytest.LogCaptureFixture
) -> None:
    scheduler = make_scheduler(working=False, allow_triggers="1")
    scheduler.task()
    scheduler.task(Trigger.NEXT_PHOTO)

    scheduler.task()

    assert messages(caplog).count(SLEEPING) == 2


@pytest.mark.parametrize(("allowed", "expected"), [("1", [("prepare",)]), ("0", [])])
def test_trigger_off_hours(
    make_scheduler: MakeScheduler,
    starts: Starts,
    allowed: str,
    expected: list[tuple[str, ...]],
) -> None:
    scheduler = make_scheduler(working=False, allow_triggers=allowed)

    scheduler.task(Trigger.NEXT_PHOTO)

    assert starts == expected


def test_trigger_without_working_hours(
    make_scheduler: MakeScheduler, starts: Starts, caplog: pytest.LogCaptureFixture
) -> None:
    never = ",".join(["-"] * 7)
    scheduler = make_scheduler(
        working=False, allow_triggers="1", start_times=never, stop_times=never
    )

    scheduler.task(Trigger.NEXT_PHOTO)

    assert starts == [("prepare",)]
    assert scheduler.frame.next_update is None
    assert messages(caplog)[-1] == NO_NEXT


def test_multiplier_keeps_the_photo(
    make_scheduler: MakeScheduler, starts: Starts, caplog: pytest.LogCaptureFixture
) -> None:
    scheduler = make_scheduler(interval_mult="1", slide_interval="300")
    scheduler.frame.multiplier.save(3)  # the photo stays 3 intervals

    assert scheduler.task() == 300
    assert scheduler.task() == 300
    assert scheduler.task() == 300

    assert starts == [("prepare",)]  # after two more intervals
    assert messages(caplog).count(MULTIPLIED) == 2
    assert scheduler.frame.multiplier.read() == 0
    assert not scheduler.frame.multiplier.path.exists()


def test_multiplier_disabled(make_scheduler: MakeScheduler, starts: Starts) -> None:
    scheduler = make_scheduler(interval_mult="0")
    scheduler.frame.multiplier.save(2)

    scheduler.task()

    assert starts == [("prepare",)]
    assert scheduler.frame.multiplier.read() == 2


def test_trigger_skips_the_multiplier(
    make_scheduler: MakeScheduler, starts: Starts
) -> None:
    scheduler = make_scheduler(interval_mult="1")
    scheduler.frame.multiplier.save(2)

    scheduler.task(Trigger.NEXT_PHOTO)

    assert starts == [("prepare",)]


def test_safe_task_logs_errors(
    make_scheduler: MakeScheduler, caplog: pytest.LogCaptureFixture
) -> None:
    scheduler = make_scheduler()
    scheduler.frame.refresh = MagicMock(side_effect=ValueError("broken"))  # type: ignore[method-assign]

    assert scheduler.safe_task() == IDLE_CHECK

    assert "Error changing the photo: broken" in caplog.text


def test_wait_times_out(make_scheduler: MakeScheduler) -> None:
    assert make_scheduler().wait(0) == (False, None)


def test_trigger_wakes_the_wait(
    make_scheduler: MakeScheduler, caplog: pytest.LogCaptureFixture
) -> None:
    scheduler = make_scheduler()

    scheduler.trigger(Trigger.REDISPLAY)

    assert TRIGGERED in messages(caplog)
    assert scheduler.wait(None) == (False, Trigger.REDISPLAY)
    assert scheduler.wait(0) == (False, None)  # taken once


def run_in_thread(scheduler: PhotoScheduler) -> threading.Thread:
    thread = threading.Thread(target=scheduler.run)
    thread.start()
    return thread


def stop(scheduler: PhotoScheduler, thread: threading.Thread) -> None:
    scheduler.stop()
    thread.join(timeout=10)
    assert not thread.is_alive()


def test_run_starts_after_the_initial_delay(
    make_scheduler: MakeScheduler, starts: Starts, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduler_module, "INITIAL_DELAY", 0)
    scheduler = make_scheduler()

    thread = run_in_thread(scheduler)
    assert starts.event.wait(10)
    stop(scheduler, thread)

    assert starts == [("prepare",)]


def test_run_unscheduled_waits_for_triggers(
    make_scheduler: MakeScheduler, starts: Starts, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduler_module, "INITIAL_DELAY", 0)
    scheduler = make_scheduler(scheduled=False)

    thread = run_in_thread(scheduler)
    assert not starts.event.wait(0.2)
    scheduler.trigger(Trigger.NEXT_PHOTO)
    assert starts.event.wait(10)
    stop(scheduler, thread)

    assert starts == [("prepare",)]


def test_stop_before_run(make_scheduler: MakeScheduler, starts: Starts) -> None:
    scheduler = make_scheduler()
    scheduler.stop()

    scheduler.run()

    assert starts == []


def test_trigger_during_an_update_runs_after_it(make_frame: MakeFrame) -> None:
    frame = make_frame(**HDMI)
    frame.working = lambda now=None: False  # type: ignore[method-assign]
    running = threading.Event()
    finish = threading.Event()
    calls: list[tuple[str, ...]] = []

    def update(arguments: Sequence[str]) -> None:
        calls.append(tuple(arguments))
        running.set()
        assert finish.wait(10)  # the update runs (the scheduler waits for it)

    scheduler = PhotoScheduler(frame, update, scheduled=False)
    thread = run_in_thread(scheduler)
    scheduler.trigger(Trigger.NEXT_PHOTO)
    assert running.wait(10)
    running.clear()
    scheduler.trigger(Trigger.REDISPLAY)  # queued, the running one goes on
    scheduler.trigger(Trigger.REDISPLAY)

    assert calls == [("prepare",)]
    finish.set()
    assert running.wait(10)
    stop(scheduler, thread)

    # the queued requests ran right after it, once
    assert calls == [("prepare",), ("prepare", "--again")]
