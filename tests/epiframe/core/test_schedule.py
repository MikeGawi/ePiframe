from datetime import datetime, time, timedelta

import pytest

from epiframe.core.schedule import WeeklySchedule, parse_time, verify

# 2026-11-23 is a Monday
MONDAY = datetime(2026, 11, 23)


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """Local time on the given weekday (0 = Monday) of the test week."""
    return MONDAY + timedelta(days=day, hours=hour, minutes=minute)


def week(*values: str) -> list[str]:
    """Seven values: the given ones from Monday on, the rest repeat the last one."""
    return [*values, *[values[-1]] * (7 - len(values))]


def schedule(starts: list[str], stops: list[str]) -> WeeklySchedule:
    return WeeklySchedule.from_strings(starts, stops)


def test_parse_time() -> None:
    assert parse_time("5:30") == time(5, 30)
    assert parse_time(" 23:59 ") == time(23, 59)
    assert parse_time("-") is None
    for invalid in ("01:59:11", "24:00", "x", ""):
        with pytest.raises(ValueError, match=r"does not match format|unconverted"):
            parse_time(invalid)


def test_from_strings_needs_seven_days() -> None:
    with pytest.raises(ValueError, match="7 values"):
        schedule(["5:30"] * 6, ["23:30"] * 7)


def test_validate() -> None:
    schedule(week("5:30", "-"), week("23:30", "-")).validate()
    schedule(week("5:30"), week("-")).validate()
    with pytest.raises(ValueError, match="start_times times are older than stop_times"):
        schedule(week("23:30"), week("5:30")).validate()


def test_verify_config_values() -> None:
    verify(["5:30,5:30,5:30,5:30,5:30,5:30,5:30", "23:30," * 6 + "23:30"])
    with pytest.raises(ValueError, match="older than stop_times"):
        verify(["23:30," * 6 + "23:30", "5:30,5:30,5:30,5:30,5:30,5:30,5:30"])
    with pytest.raises(ValueError, match="7 values"):
        verify(["5:30", "23:30"])


DAILY = schedule(week("8:00"), week("22:00"))


@pytest.mark.parametrize(
    ("now", "active"),
    [
        (at(0, 7, 59), False),
        (at(0, 8), True),
        (at(0, 12), True),
        (at(0, 22), False),
        (at(6, 23), False),
    ],
)
def test_is_active_daily(now: datetime, active: bool) -> None:
    assert DAILY.is_active(now) is active


def test_is_active_day_off() -> None:
    days_off = schedule(week("8:00", "-"), week("22:00", "-"))

    assert days_off.is_active(at(0, 12)) is True
    assert days_off.is_active(at(1, 12)) is False


def test_is_active_overnight() -> None:
    # Friday has no stop time: the frame works until Saturday's start
    overnight = schedule(week("8:00"), ["22:00"] * 4 + ["-", "22:00", "22:00"])

    assert overnight.is_active(at(4, 23)) is True  # Friday night
    assert overnight.is_active(at(5, 3)) is True  # Saturday before start
    assert overnight.is_active(at(5, 23)) is False  # Saturday after stop
    # 1.x looked at the day before yesterday here (Thursday stops at 22:00)
    assert overnight.is_active(at(6, 3)) is False  # Sunday before start


def test_is_active_sunday_night_into_monday() -> None:
    overnight = schedule(week("8:00"), ["22:00"] * 6 + ["-"])

    assert overnight.is_active(at(7, 3)) is True  # next Monday, 3:00


def test_is_active_uses_current_time() -> None:
    always = schedule(week("0:00"), week("-"))

    assert always.is_active() is True


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (at(0, 6), at(0, 8)),  # later today
        (at(0, 23), at(1, 8)),  # tomorrow
        (at(6, 23), at(7, 8)),  # over the week boundary
    ],
)
def test_next_start_daily(now: datetime, expected: datetime) -> None:
    result = DAILY.next_start(now)

    assert result.tzinfo is not None
    assert result.replace(tzinfo=None) == expected


def test_next_start_uses_the_start_of_that_day() -> None:
    # 1.x took today's start time for tomorrow
    varied = schedule(
        ["8:00", "10:30", "8:00", "8:00", "8:00", "8:00", "8:00"], week("22:00")
    )

    assert varied.next_start(at(0, 23)).replace(tzinfo=None) == at(1, 10, 30)


def test_next_start_skips_days_off() -> None:
    only_wednesday = schedule(["-", "-", "9:15", "-", "-", "-", "-"], week("-"))

    assert only_wednesday.next_start(at(0, 12)).replace(tzinfo=None) == at(2, 9, 15)
    # passed this week: next week
    assert only_wednesday.next_start(at(2, 10)).replace(tzinfo=None) == at(9, 9, 15)


def test_next_start_without_start_times() -> None:
    never = schedule(week("-"), week("-"))

    with pytest.raises(ValueError, match="No start time"):
        never.next_start(at(0, 12))
    assert never.is_active(at(0, 12)) is False


def test_next_start_uses_current_time() -> None:
    assert DAILY.next_start() > datetime.now().astimezone()
