import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from epiframe.photos.index import SCHEMA_VERSION, PhotoIndex, check_sqlite_version
from epiframe.photos.model import Photo
from epiframe.photos.selection import Selection, Sorting

START = datetime(2024, 1, 1, 12)


def photo(name: str, day: int, source: str = "Local") -> Photo:
    return Photo(name, source, START + timedelta(days=day))


# found in this order; created on different days
PHOTOS = [photo("c.jpg", 2), photo("a.jpg", 0), photo("d.jpg", 3), photo("b.jpg", 1)]


@pytest.fixture
def index(tmp_path: Path) -> Iterator[PhotoIndex]:
    with PhotoIndex(tmp_path / "photos.db") as photo_index:
        photo_index.replace_source("Local", PHOTOS)
        yield photo_index


def names(photos: list[Photo | None]) -> list[str]:
    return [item.id if item else "-" for item in photos]


def sequence(index: PhotoIndex, selection: Selection, count: int) -> list[str]:
    shown = []
    for _ in range(count):
        current = index.next_photo(selection)
        assert current is not None
        index.mark_shown(current, selection)
        shown.append(current)
    return names(list(shown))


def test_schema_and_reopen(tmp_path: Path) -> None:
    path = tmp_path / "photos.db"
    with PhotoIndex(path) as index:
        index.replace_source("Local", PHOTOS)
    with PhotoIndex(str(path)) as index:
        assert index.count() == 4
    # the connection's own context manager commits but doesn't close it
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)


def test_empty_index(tmp_path: Path) -> None:
    with PhotoIndex(tmp_path / "photos.db") as index:
        assert index.count() == 0
        assert index.next_photo(Selection()) is None
        assert index.random_photo(Selection()) is None
        assert index.last_shown() is None


def test_replace_source_updates_and_removes(index: PhotoIndex) -> None:
    changed = photo("a.jpg", 10)

    count = index.replace_source("Local", [changed, photo("e.jpg", 4), PHOTOS[0]])

    assert count == 3
    assert index.count() == 3
    # existing photos keep their place, new ones are appended
    assert sequence(index, Selection(), 3) == ["c.jpg", "a.jpg", "e.jpg"]
    assert index.last_shown() == photo("e.jpg", 4)
    # newest first: after the oldest (c.jpg) it starts over with a.jpg
    assert index.next_photo(Selection(sorting=Sorting.DESC), after=PHOTOS[0]) == changed


def test_replace_source_rejects_other_sources(index: PhotoIndex) -> None:
    with pytest.raises(ValueError, match=r"'x\.jpg' is not from source 'Local'"):
        index.replace_source("Local", [photo("e.jpg", 4), photo("x.jpg", 0, "Plugin")])

    # nothing was changed
    assert index.count() == 4


def test_sources_are_separate(index: PhotoIndex) -> None:
    index.replace_source("Plugin", [photo("a.jpg", 5, "Plugin")])

    assert index.count() == 5
    assert index.count_source("Local") == 4
    assert index.count_source("Plugin") == 1

    index.keep_sources(["Plugin"])
    assert index.count() == 1
    index.keep_sources([])
    assert index.count() == 0


@pytest.mark.parametrize(
    ("sorting", "expected"),
    [
        (Sorting.NONE, ["c.jpg", "a.jpg", "d.jpg", "b.jpg", "c.jpg"]),
        (Sorting.ASC, ["a.jpg", "b.jpg", "c.jpg", "d.jpg", "a.jpg"]),
        (Sorting.DESC, ["d.jpg", "c.jpg", "b.jpg", "a.jpg", "d.jpg"]),
    ],
)
def test_sequential_order_wraps(
    index: PhotoIndex, sorting: Sorting, expected: list[str]
) -> None:
    assert sequence(index, Selection(sorting=sorting), 5) == expected


def test_selection_filters_and_limit(index: PhotoIndex) -> None:
    between = Selection(after=START, before=START + timedelta(days=3))

    assert index.count(between) == 2  # strict: a.jpg (day 0) and d.jpg (day 3) out
    assert sequence(index, between, 3) == ["c.jpg", "b.jpg", "c.jpg"]
    # the limit takes the first photos in found order, then sorts them
    limited = Selection(limit=2, sorting=Sorting.ASC)
    assert index.count(limited) == 2
    assert sequence(index, limited, 2) == ["a.jpg", "c.jpg"]


def test_next_after_given_photo(index: PhotoIndex) -> None:
    # retry after a photo that couldn't be loaded
    assert index.next_photo(Selection(), after=PHOTOS[1]) == PHOTOS[2]


def test_next_after_removed_photo_continues_from_its_place(index: PhotoIndex) -> None:
    index.mark_shown(PHOTOS[1], Selection())  # a.jpg (2nd in found order)
    index.replace_source("Local", [p for p in PHOTOS if p.id != "a.jpg"])

    assert index.next_photo(Selection()) == PHOTOS[2]
    assert index.next_photo(Selection(sorting=Sorting.ASC)) == photo("b.jpg", 1)
    # a.jpg was the oldest: newest first starts over
    assert index.next_photo(Selection(sorting=Sorting.DESC)) == photo("d.jpg", 3)
    assert index.last_shown() == PHOTOS[1]


@pytest.mark.parametrize("sorting", list(Sorting))
def test_next_after_unknown_photo(index: PhotoIndex, sorting: Sorting) -> None:
    unknown = photo("x.jpg", 1, "Plugin")  # same time as b.jpg
    expected = {Sorting.NONE: "c.jpg", Sorting.ASC: "b.jpg", Sorting.DESC: "b.jpg"}

    result = index.next_photo(Selection(sorting=sorting), after=unknown)

    assert result is not None
    assert result.id == expected[sorting]


def test_mark_shown_of_unknown_photo(index: PhotoIndex) -> None:
    unknown = photo("x.jpg", 1, "Plugin")

    index.mark_shown(unknown, Selection())

    assert index.last_shown() == unknown
    assert index.next_photo(Selection()) == PHOTOS[0]


def test_random_cycle_shows_every_photo_once(index: PhotoIndex) -> None:
    selection = Selection()
    shown = []
    for _ in range(12):
        current = index.random_photo(selection)
        assert current is not None
        index.mark_shown(current, selection)
        shown.append(current.id)

    for cycle in range(3):
        assert sorted(shown[cycle * 4 : cycle * 4 + 4]) == sorted(p.id for p in PHOTOS)
    # the last photo of a cycle is not the first of the next one
    assert shown[3] != shown[4]
    assert shown[7] != shown[8]


def test_random_excludes_given_photo(index: PhotoIndex) -> None:
    picks = Counter(
        index.random_photo(Selection(), exclude=PHOTOS[0]) for _ in range(40)
    )

    assert PHOTOS[0] not in picks


def test_random_with_one_photo(tmp_path: Path) -> None:
    with PhotoIndex(tmp_path / "photos.db") as index:
        index.replace_source("Local", [PHOTOS[0]])
        for _ in range(3):
            assert index.random_photo(Selection()) == PHOTOS[0]
            index.mark_shown(PHOTOS[0], Selection())


def test_random_respects_selection(index: PhotoIndex) -> None:
    only_b = Selection(after=START, before=START + timedelta(days=2))

    assert {index.random_photo(only_b) for _ in range(10)} == {photo("b.jpg", 1)}


def test_new_cycle_only_resets_the_selection(index: PhotoIndex) -> None:
    index.mark_shown(PHOTOS[0], Selection())  # c.jpg shown, outside the selection below
    only_b = Selection(after=START, before=START + timedelta(days=2))

    index.mark_shown(photo("b.jpg", 1), only_b)  # last unshown of the selection
    index.mark_shown(photo("b.jpg", 1), only_b)  # starts a new cycle of the selection

    # c.jpg is still shown: random picks among the other photos first
    picks = {
        index.random_photo(Selection(), exclude=photo("b.jpg", 1)) for _ in range(30)
    }
    assert picks == {PHOTOS[1], PHOTOS[2]}


def test_add_photos_appends_and_updates(index: PhotoIndex) -> None:
    index.add_photos([photo("e.jpg", 4), photo("a.jpg", 9)])

    assert index.count() == 5
    assert index.next_photo(Selection(), after=PHOTOS[-1]) == photo("e.jpg", 4)
    # newest first: after the oldest (b.jpg) it starts over with the updated a.jpg
    newest = index.next_photo(Selection(sorting=Sorting.DESC), after=PHOTOS[3])
    assert newest == photo("a.jpg", 9)


def test_remove_photos(index: PhotoIndex) -> None:
    index.remove_photos("Local", ["a.jpg", "missing.jpg"])
    index.remove_photos("Plugin", ["b.jpg"])

    assert index.count() == 3
    assert index.child_ids("Local", "a") == set()


def test_child_ids(tmp_path: Path) -> None:
    with PhotoIndex(tmp_path / "photos.db") as index:
        index.add_photos(
            [
                photo("photos/a.jpg", 0),
                photo("photos/b.jpg", 0),
                photo("photos/sub/c.jpg", 0),
                photo("photos0/d.jpg", 0),
                photo("photos/e.jpg", 0, "Plugin"),
            ]
        )

        assert index.child_ids("Local", "photos/") == {"photos/a.jpg", "photos/b.jpg"}
        assert index.child_ids("Local", "photos/sub/") == {"photos/sub/c.jpg"}
        assert index.child_ids("Local", "other/") == set()


def test_source_state(index: PhotoIndex) -> None:
    assert index.source_state("Local") == {}

    index.set_source_state("Local", {"a": "1", "b": "2"})
    index.set_source_state("Local", {"a": "3"})
    index.set_source_state("Plugin", {"a": "x"})
    index.remove_source_state("Local", ["b", "missing"])

    assert index.source_state("Local") == {"a": "3"}
    assert index.source_state("Plugin") == {"a": "x"}

    index.keep_sources(["Local"])
    assert index.source_state("Plugin") == {}


def test_batch_is_one_transaction(index: PhotoIndex) -> None:
    def failing_batch() -> None:
        with index.batch():
            index.add_photos([photo("e.jpg", 4)])
            index.replace_source("Plugin", [photo("p.jpg", 0, "Plugin")])
            index.set_source_state("Local", {"a": "1"})
            raise RuntimeError

    with pytest.raises(RuntimeError):
        failing_batch()

    assert index.count() == 4
    assert index.source_state("Local") == {}

    with index.batch():
        index.add_photos([photo("e.jpg", 4)])
        index.set_source_state("Local", {"a": "1"})

    assert index.count() == 5
    assert index.source_state("Local") == {"a": "1"}


def test_sqlite_version_check() -> None:
    check_sqlite_version()
    check_sqlite_version((3, 35, 0))
    with pytest.raises(
        RuntimeError, match=r"SQLite 3\.35\.0 or newer .* found 3\.27\.2"
    ):
        check_sqlite_version((3, 27, 2))
