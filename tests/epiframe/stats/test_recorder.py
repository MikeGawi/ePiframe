from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest

from epiframe.stats import recorder
from epiframe.stats.metrics import Sampler
from epiframe.stats.recorder import Recorder
from epiframe.stats.store import MetricsStore, Period

T0 = 1_700_000_000


@pytest.fixture
def sampler() -> MagicMock:
    sampler: MagicMock = create_autospec(Sampler, instance=True)
    sampler.sample.side_effect = [{"a": value} for value in range(10)]
    return sampler


def test_samples_are_written_in_batches(tmp_path: Path, sampler: Sampler) -> None:
    store = MetricsStore(tmp_path / "stats.db")
    stats = Recorder(store, sampler, batch=3)

    stats.record(now=T0)
    stats.record(now=T0 + 10)
    assert not store.path.exists()
    stats.record(now=T0 + 20)
    stats.record(now=T0 + 30)

    series = store.series(Period.DAY, ["a"], now=T0 + 30)
    assert series.times == [T0, T0 + 10, T0 + 20]
    assert series.values == {"a": [0, 1, 2]}


def test_flush(tmp_path: Path, sampler: Sampler) -> None:
    store = MetricsStore(tmp_path / "stats.db")
    stats = Recorder(store, sampler)

    stats.record()
    stats.flush()

    assert store.series(Period.DAY, ["a"]).values == {"a": [0]}


def test_failed_write_drops_the_batch(sampler: Sampler) -> None:
    store = create_autospec(MetricsStore, instance=True)
    store.add_many.side_effect = OSError("disk full")
    stats = Recorder(store, sampler, batch=1)

    with pytest.raises(OSError, match="disk full"):
        stats.record(now=T0)
    store.add_many.side_effect = None
    stats.record(now=T0 + 10)

    store.add_many.assert_called_with([(T0 + 10, {"a": 1})])


def test_default_batch_is_a_minute() -> None:
    assert recorder.BATCH == 6
