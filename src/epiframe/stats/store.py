"""Samples of the metrics in SQLite, kept like an RRD (round-robin database).

Every sample is stored as it is (the raw tier) and averaged into longer periods
(the other tiers); each tier keeps only its time span, so the file does not grow
(about 100 000 rows for the default metrics). One table holds every tier, one row
per tier, time and metric, so new metrics need no schema change.

The averages are rolled up when samples are added: a period is averaged once it
is complete, from the tier before (10 minutes from the samples, hours from the
10 minutes, days from the hours). Periods start at multiples of their length in
Unix time, so the days are UTC days. Rows from the future (the clock was set
back, e.g. a Raspberry Pi without a real-time clock before its NTP sync) are
dropped, otherwise the averages would stop until that time.

A connection is opened per operation: the service adds samples from one thread
while the WebUI reads them from another. Every write is a transaction with an
fsync (about 38 KiB written to the SD card), so the samples are written in
batches (:mod:`epiframe.stats.recorder`).
"""

import sqlite3
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from epiframe.stats.metrics import SAMPLE_INTERVAL

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR

CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS metrics ("
    " step INTEGER NOT NULL,"  # the tier: seconds per point
    " time INTEGER NOT NULL,"  # Unix time of the sample / start of the period
    " name TEXT NOT NULL,"
    " value REAL NOT NULL,"
    " PRIMARY KEY (step, time, name)"
    ") WITHOUT ROWID"
)
ROLL_UP = (
    "INSERT INTO metrics (step, time, name, value)"
    " SELECT :step, time / :step * :step AS period, name, avg(value) FROM metrics"
    " WHERE step = :source AND time >= :start AND time < :end"
    " GROUP BY period, name"
    " ON CONFLICT (step, time, name) DO UPDATE SET value = excluded.value"
)


DELETE_OUTSIDE = "DELETE FROM metrics WHERE step = ? AND time NOT BETWEEN ? AND ?"


class Period(StrEnum):
    """The time spans the statistics are shown for."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


@dataclass(frozen=True)
class Tier:
    """``step`` seconds per point, kept for ``keep`` seconds."""

    period: Period
    step: int
    keep: int


TIERS = (
    Tier(Period.DAY, SAMPLE_INTERVAL, DAY),
    Tier(Period.WEEK, 10 * MINUTE, 7 * DAY),
    Tier(Period.MONTH, HOUR, 31 * DAY),
    Tier(Period.YEAR, DAY, 366 * DAY),
)


@dataclass
class Series:
    """Metrics in columns: ``values[name][i]`` was measured at ``times[i]``
    (``None`` if it was not)."""

    step: int
    times: list[int] = field(default_factory=list)
    values: dict[str, list[float | None]] = field(default_factory=dict)


def _now(now: float | None) -> int:
    return int(time.time() if now is None else now)


class MetricsStore:
    """The samples in the SQLite file ``path`` (created by the first :meth:`add`)."""

    def __init__(self, path: Path | str, tiers: Sequence[Tier] = TIERS):
        self.path = Path(path)
        self._tiers = tuple(tiers)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """A connection with one transaction (committed on success), then closed."""
        with closing(sqlite3.connect(self.path)) as db, db:
            yield db

    def add(self, sample: Mapping[str, float], now: float | None = None) -> None:
        """Store ``sample`` taken at ``now``, see :meth:`add_many`."""
        self.add_many([(_now(now), sample)])

    def add_many(self, samples: Sequence[tuple[float, Mapping[str, float]]]) -> None:
        """Store the ``(time, sample)`` pairs in one transaction, roll up and drop
        old rows."""
        if not samples:
            return
        moments = [int(moment) for moment, _ in samples]
        rows = _rows(self._tiers[0], samples)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(CREATE_TABLE)
            for tier in self._tiers:
                _keep(db, tier, 0, min(moments))
            db.executemany("INSERT OR REPLACE INTO metrics VALUES (?, ?, ?, ?)", rows)
            self._maintain(db, max(moments))

    def _maintain(self, db: sqlite3.Connection, now: int) -> None:
        # roll up before dropping old rows: after a long stop the samples of the
        # last period are older than the raw tier keeps them
        for source, tier in zip(self._tiers, self._tiers[1:], strict=False):
            self._roll_up(db, source, tier, now)
        for tier in self._tiers:
            _keep(db, tier, now - tier.keep, now)

    @staticmethod
    def _roll_up(db: sqlite3.Connection, source: Tier, tier: Tier, now: int) -> None:
        """Average the complete periods of ``tier`` not averaged yet."""
        (last,) = db.execute(
            "SELECT max(time) FROM metrics WHERE step = ?", (tier.step,)
        ).fetchone()
        start = 0 if last is None else last + tier.step
        end = now // tier.step * tier.step  # the current period is not complete
        if start < end:
            parameters = {"step": tier.step, "source": source.step}
            db.execute(ROLL_UP, {**parameters, "start": start, "end": end})

    def tier(self, period: Period) -> Tier:
        return next(tier for tier in self._tiers if tier.period == period)

    def series(
        self, period: Period, names: Sequence[str], now: float | None = None
    ) -> Series:
        """The metrics ``names`` over the last ``period``."""
        tier = self.tier(period)
        series = Series(tier.step, values={name: [] for name in names})
        if not names or not self.path.exists():
            return series
        query = (
            "SELECT time, name, value FROM metrics WHERE step = ? AND time >= ?"  # noqa: S608 - only placeholders
            f" AND name IN ({', '.join('?' * len(names))}) ORDER BY time"
        )
        with self._connect() as db:
            db.execute(CREATE_TABLE)
            rows = db.execute(query, (tier.step, _now(now) - tier.keep, *names))
            for moment, name, value in rows:
                _put(series, moment, name, value)
        return series


def _rows(
    raw: Tier, samples: Sequence[tuple[float, Mapping[str, float]]]
) -> list[tuple[int, int, str, float]]:
    return [
        (raw.step, int(moment), name, value)
        for moment, sample in samples
        for name, value in sample.items()
    ]


def _keep(db: sqlite3.Connection, tier: Tier, start: int, end: int) -> None:
    """Delete the rows of ``tier`` from before ``start`` and after ``end``."""
    db.execute(DELETE_OUTSIDE, (tier.step, start, end))


def _put(series: Series, moment: int, name: str, value: float) -> None:
    if not series.times or series.times[-1] != moment:
        series.times.append(moment)
        for column in series.values.values():
            column.append(None)
    series.values[name][-1] = value
