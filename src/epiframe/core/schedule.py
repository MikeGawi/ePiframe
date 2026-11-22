"""Weekly working hours of the frame (``start_times`` / ``stop_times`` settings).

Both settings have one ``HH:MM`` value per day, Monday first. ``-`` as a start
time means the frame does not start that day; ``-`` as a stop time means it keeps
working until the next start (overnight).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

NO_TIME = "-"
TIME_FORMAT = "%H:%M"
DELIMITER = ","
DAYS = 7


def parse_time(value: str) -> time | None:
    """Parse ``HH:MM`` (``None`` for ``-``); raise ``ValueError`` otherwise."""
    value = value.strip()
    if value == NO_TIME:
        return None
    return datetime.strptime(value, TIME_FORMAT).time()


def _parse_week(values: Sequence[str]) -> tuple[time | None, ...]:
    if len(values) != DAYS:
        raise ValueError(f"{DAYS} values (one per day) are needed, got {len(values)}!")
    return tuple(parse_time(value) for value in values)


@dataclass(frozen=True)
class WeeklySchedule:
    """Start and stop time of each day of the week (Monday first)."""

    starts: tuple[time | None, ...]
    stops: tuple[time | None, ...]

    @classmethod
    def from_strings(
        cls, starts: Sequence[str], stops: Sequence[str]
    ) -> "WeeklySchedule":
        return cls(_parse_week(starts), _parse_week(stops))

    def validate(self) -> None:
        """Raise ``ValueError`` if a day stops before it starts."""
        for start, stop in zip(self.starts, self.stops, strict=True):
            if start and stop and start > stop:
                raise ValueError(
                    "Configuration start_times times are older than stop_times!"
                )

    def is_active(self, now: datetime | None = None) -> bool:
        """Return whether the frame should work at ``now`` (local time)."""
        now = now or datetime.now()
        day = now.weekday()
        start = self.starts[day]
        if start is None:
            return False
        if now.time() < start:
            # still working since yesterday when it had no stop time
            return self.stops[day - 1] is None
        stop = self.stops[day]
        return stop is None or now.time() < stop

    def next_start(self, now: datetime | None = None) -> datetime:
        """Return the first start after ``now`` as an aware local time.

        Raise ``ValueError`` when no day has a start time.
        """
        now = now or datetime.now()
        for offset in range(DAYS + 1):
            candidate = self._start_on(now.date() + timedelta(days=offset))
            if candidate and candidate > now:
                return candidate.astimezone()
        raise ValueError("No start time is set for any day!")

    def _start_on(self, day: date) -> datetime | None:
        start = self.starts[day.weekday()]
        return datetime.combine(day, start) if start else None


def verify(values: list[str]) -> None:
    """Config check of the ``[start_times, stop_times]`` values."""
    WeeklySchedule.from_strings(
        values[0].split(DELIMITER), values[1].split(DELIMITER)
    ).validate()
