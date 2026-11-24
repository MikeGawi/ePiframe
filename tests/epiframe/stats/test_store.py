import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from epiframe.stats.store import (
    DAY,
    HOUR,
    MINUTE,
    TIERS,
    MetricsStore,
    Period,
    Series,
    Tier,
)

# the start of a UTC day: every period starts here
T0 = 1_700_000_000 // DAY * DAY


@pytest.fixture
def store(tmp_path: Path) -> MetricsStore:
    return MetricsStore(tmp_path / "data" / "stats.db")


def rows(store: MetricsStore) -> list[tuple[int, int, str, float]]:
    with closing(sqlite3.connect(store.path)) as db:
        return db.execute("SELECT * FROM metrics ORDER BY step, time, name").fetchall()


def test_samples(store: MetricsStore) -> None:
    store.add({"a": 1, "b": 2}, now=T0)
    store.add({"a": 3}, now=T0 + 10)
    store.add({"b": 4.5}, now=T0 + 20.9)

    series = store.series(Period.DAY, ["b", "a"], now=T0 + 30)

    assert series == Series(
        step=10,
        times=[T0, T0 + 10, T0 + 20],
        values={"b": [2, None, 4.5], "a": [1, 3, None]},
    )


def test_unknown_names_are_empty(store: MetricsStore) -> None:
    store.add({"a": 1}, now=T0)

    series = store.series(Period.DAY, ["a", "other"], now=T0)

    assert series.values == {"a": [1], "other": [None]}


def test_sample_at_the_same_time_replaces(store: MetricsStore) -> None:
    store.add({"a": 1}, now=T0)
    store.add({"a": 2}, now=T0)

    assert store.series(Period.DAY, ["a"], now=T0).values == {"a": [2]}


def test_current_time(store: MetricsStore) -> None:
    store.add({"a": 1})

    assert store.series(Period.DAY, ["a"]).values == {"a": [1]}


def test_no_file_yet(store: MetricsStore) -> None:
    series = store.series(Period.WEEK, ["a"], now=T0)

    assert series == Series(step=10 * MINUTE, times=[], values={"a": []})
    assert not store.path.exists()


def test_no_names(store: MetricsStore) -> None:
    store.add({"a": 1}, now=T0)

    assert store.series(Period.DAY, [], now=T0) == Series(step=10)


def test_complete_periods_are_averaged(store: MetricsStore) -> None:
    store.add({"a": 1}, now=T0)
    store.add({"a": 3}, now=T0 + 5 * MINUTE)
    # the period T0 + 10 minutes is not complete
    store.add({"a": 10}, now=T0 + 10 * MINUTE)

    series = store.series(Period.WEEK, ["a"], now=T0 + 10 * MINUTE)

    assert series == Series(step=10 * MINUTE, times=[T0], values={"a": [2]})


def test_periods_are_averaged_once(store: MetricsStore) -> None:
    store.add({"a": 1}, now=T0)
    store.add({"a": 3}, now=T0 + 10 * MINUTE)
    week = rows(store)
    # a sample of the averaged period that came late (clock) is not averaged again
    store.add({"a": 100}, now=T0 + 1)
    store.add({"a": 5}, now=T0 + 10 * MINUTE + 10)

    assert [row for row in rows(store) if row[0] != 10] == [
        row for row in week if row[0] != 10
    ]


def test_tiers_roll_up(store: MetricsStore) -> None:
    store.add({"a": 1}, now=T0)
    store.add({"a": 3}, now=T0 + HOUR)
    store.add({"a": 5}, now=T0 + DAY)

    month = store.series(Period.MONTH, ["a"], now=T0 + DAY)
    year = store.series(Period.YEAR, ["a"], now=T0 + DAY)

    assert month == Series(step=HOUR, times=[T0, T0 + HOUR], values={"a": [1, 3]})
    assert year == Series(step=DAY, times=[T0], values={"a": [2]})


def test_rolled_up_after_a_long_stop(store: MetricsStore) -> None:
    store.add({"a": 4}, now=T0)
    # the service was stopped for 3 days: the samples are averaged, then dropped
    store.add({"a": 1}, now=T0 + 3 * DAY)

    assert store.series(Period.WEEK, ["a"], now=T0 + 3 * DAY).values == {"a": [4]}
    assert store.series(Period.DAY, ["a"], now=T0 + 3 * DAY).values == {"a": [1]}


def test_old_rows_are_dropped(store: MetricsStore) -> None:
    store.add({"a": 1}, now=T0)
    store.add({"a": 2}, now=T0 + DAY)
    store.add({"a": 3}, now=T0 + DAY + 10)

    # T0 is a day old at T0 + DAY (kept), older at T0 + DAY + 10 (dropped)
    assert [row for row in rows(store) if row[0] == 10] == [
        (10, T0 + DAY, "a", 2),
        (10, T0 + DAY + 10, "a", 3),
    ]


def test_every_tier_keeps_its_span(store: MetricsStore) -> None:
    for day in range(400):
        store.add({"a": day}, now=T0 + day * DAY)

    now = T0 + 399 * DAY
    for tier in TIERS:
        times = store.series(tier.period, ["a"], now=now).times
        assert times
        assert min(times) >= now - tier.keep


def test_rows_from_the_future_are_dropped(store: MetricsStore) -> None:
    # the clock was a day ahead, then set back
    store.add({"a": 1}, now=T0 + DAY)
    store.add({"a": 1}, now=T0 + DAY + 10 * MINUTE)
    store.add({"a": 2}, now=T0)
    store.add({"a": 4}, now=T0 + 10 * MINUTE)

    day = store.series(Period.DAY, ["a"], now=T0 + 10 * MINUTE)
    week = store.series(Period.WEEK, ["a"], now=T0 + 10 * MINUTE)

    assert day.times == [T0, T0 + 10 * MINUTE]
    # averaging goes on (it would wait until T0 + DAY otherwise)
    assert week == Series(step=10 * MINUTE, times=[T0], values={"a": [2]})


def test_custom_tiers(tmp_path: Path) -> None:
    store = MetricsStore(
        tmp_path / "stats.db",
        [Tier(Period.DAY, 1, 100), Tier(Period.YEAR, 10, 1000)],
    )
    for second in range(20):
        store.add({"a": second}, now=T0 + second)

    year = store.series(Period.YEAR, ["a"], now=T0 + 19)

    assert year == Series(step=10, times=[T0], values={"a": [4.5]})
    assert store.tier(Period.YEAR) == Tier(Period.YEAR, 10, 1000)


def test_default_tiers() -> None:
    assert [(tier.period, tier.step, tier.keep) for tier in TIERS] == [
        (Period.DAY, 10, DAY),
        (Period.WEEK, 10 * MINUTE, 7 * DAY),
        (Period.MONTH, HOUR, 31 * DAY),
        (Period.YEAR, DAY, 366 * DAY),
    ]


def test_add_many(store: MetricsStore) -> None:
    store.add_many([(T0, {"a": 1}), (T0 + 10.5, {"a": 3, "b": 4})])

    assert store.series(Period.DAY, ["a", "b"], now=T0 + 10) == Series(
        step=10, times=[T0, T0 + 10], values={"a": [1, 3], "b": [None, 4]}
    )


def test_add_many_rolls_up_to_the_last_sample(store: MetricsStore) -> None:
    store.add_many([(T0, {"a": 1}), (T0 + 10 * MINUTE, {"a": 2})])

    assert store.series(Period.WEEK, ["a"], now=T0 + 10 * MINUTE).values == {"a": [1]}


def test_add_nothing(store: MetricsStore) -> None:
    store.add_many([])

    assert not store.path.exists()
