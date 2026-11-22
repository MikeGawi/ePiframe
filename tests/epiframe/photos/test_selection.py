from datetime import UTC, datetime

import pytest

from epiframe.photos.selection import (
    Selection,
    Sorting,
    convert_legacy_date,
    parse_date,
    sorting_from_sort_desc,
    verify_date,
    verify_range,
)


def test_sorting_values() -> None:
    assert Sorting.values() == ["none", "asc", "desc"]


def test_defaults() -> None:
    selection = Selection()

    assert (selection.after, selection.before, selection.limit) == (None, None, None)
    assert selection.sorting == Sorting.NONE


def test_dates_are_local_times() -> None:
    selection = Selection(after=datetime(2024, 1, 1, tzinfo=UTC))

    assert selection.after is not None
    assert selection.after.tzinfo is None


def test_from_config() -> None:
    selection = Selection.from_config("2020-01-02 03:04:05", "", "10", "desc")

    assert selection == Selection(
        after=datetime(2020, 1, 2, 3, 4, 5), limit=10, sorting=Sorting.DESC
    )
    assert Selection.from_config("", "", "", "none") == Selection()


def test_parse_and_verify_date() -> None:
    assert parse_date("") is None
    assert parse_date("2020-01-02 03:04:05") == datetime(2020, 1, 2, 3, 4, 5)
    verify_date("2020-01-02 03:04:05")
    with pytest.raises(ValueError, match="does not match format"):
        verify_date("2020.01.02 03:04:05")


def test_verify_range() -> None:
    verify_range(["2020-01-01 00:00:00", "2021-01-01 00:00:00"])
    verify_range(["2020-01-01 00:00:00", ""])
    verify_range(["", ""])
    with pytest.raises(ValueError, match="photos_from time is older than photos_to"):
        verify_range(["2021-01-01 00:00:00", "2020-01-01 00:00:00"])


def test_convert_legacy_date() -> None:
    assert convert_legacy_date("2020.01.02 03:04:05") == "2020-01-02 03:04:05"
    assert convert_legacy_date("2020-01-02 03:04:05") == "2020-01-02 03:04:05"
    assert convert_legacy_date("") == ""


def test_sorting_from_sort_desc() -> None:
    assert sorting_from_sort_desc("1") == "desc"
    assert sorting_from_sort_desc("0") == "none"
