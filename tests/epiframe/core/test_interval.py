from pathlib import Path

import pytest

from epiframe.core.interval import NO_MULTIPLIER, IntervalMultiplier


@pytest.fixture
def multiplier(tmp_path: Path) -> IntervalMultiplier:
    return IntervalMultiplier(tmp_path / "time")


def test_read_missing(multiplier: IntervalMultiplier) -> None:
    assert multiplier.read() == NO_MULTIPLIER == 0


def test_read_corrupted(multiplier: IntervalMultiplier) -> None:
    multiplier.path.write_text("x")

    assert multiplier.read() == NO_MULTIPLIER


def test_save_and_read(multiplier: IntervalMultiplier) -> None:
    multiplier.save(5)

    assert multiplier.path.read_text() == "5"
    assert IntervalMultiplier(str(multiplier.path)).read() == 5


@pytest.mark.parametrize("value", [1, 0, -3])
def test_save_without_extra_time_removes(
    multiplier: IntervalMultiplier, value: int
) -> None:
    multiplier.save(5)
    multiplier.save(value)

    assert not multiplier.path.exists()


def test_remove_missing(multiplier: IntervalMultiplier) -> None:
    multiplier.remove()

    assert not multiplier.path.exists()


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("hotword 3", 3),
        ("3 HotWord", 3),
        ("hotword 30", 10),
        ("hotword", NO_MULTIPLIER),
        ("hotword three", NO_MULTIPLIER),
        ("holiday 3", NO_MULTIPLIER),
        ("", NO_MULTIPLIER),
    ],
)
def test_save_from_description(
    multiplier: IntervalMultiplier, description: str, expected: int
) -> None:
    multiplier.save_from_description(description, "HOTWORD", 10)

    assert multiplier.read() == expected
