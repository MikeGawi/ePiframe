"""SQLite index of the photos of all sources (replaces the 1.x pandas list).

The index lives on disk, so memory use doesn't grow with the library (hundreds
of thousands of photos on a Raspberry Pi Zero). Each refresh synchronizes the
sources into it; choosing the next photo is a query.

The natural order of the photos is the order in which they were first found
(the ``rowid``): new photos are appended, existing ones keep their place.

The ``state`` table remembers the last shown photo, so the next run continues
after it (sequential mode) or doesn't repeat it (random mode). In random mode
every photo is shown once before the cycle starts again (the ``shown`` flag).
"""

import os
import sqlite3
from collections.abc import Collection, Iterable, Iterator
from datetime import datetime
from types import TracebackType
from typing import Self

from epiframe.photos.model import Photo
from epiframe.photos.selection import Selection, Sorting

SCHEMA_VERSION = 1
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    source TEXT NOT NULL,
    id TEXT NOT NULL,
    created TEXT NOT NULL,
    shown INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source, id)
);
CREATE INDEX IF NOT EXISTS photos_created ON photos (created);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# photos of the source being synchronized, in found order
INCOMING = """
CREATE TEMP TABLE IF NOT EXISTS incoming (
    id TEXT NOT NULL UNIQUE,
    created TEXT NOT NULL
);
DELETE FROM incoming;
"""

# candidates: the selected photos with their order key (rowid); a limit is
# applied in the natural order, before sorting (1.x behaviour). Only the needed
# conditions are added, so the date filter can use the "created" index.
SELECT_CANDIDATES = "SELECT rowid AS position, source, id, created, shown FROM photos"
AFTER = "created > :after"
BEFORE = "created < :before"
LIMIT = " ORDER BY rowid LIMIT :limit"

# order of each sorting and the matching "comes after" condition (row values)
ORDER = {
    Sorting.NONE: ("position", "position > :last_position"),
    Sorting.ASC: (
        "created, position",
        "(created, position) > (:last_created, :last_position)",
    ),
    Sorting.DESC: (
        "created DESC, position DESC",
        "(created, position) < (:last_created, :last_position)",
    ),
}

COLUMNS = "source, id, created"
MAX_ROWID = 2**63 - 1


def _format(value: datetime | None) -> str | None:
    return value.strftime(TIME_FORMAT) if value else None


def _photo(row: tuple[str, str, str]) -> Photo:
    source, photo_id, created = row
    return Photo(photo_id, source, datetime.strptime(created, TIME_FORMAT))


def _rows(source: str, photos: Iterable[Photo]) -> Iterator[tuple[str, str | None]]:
    for photo in photos:
        if photo.source != source:
            raise ValueError(f"Photo {photo.id!r} is not from source {source!r}!")
        yield photo.id, _format(photo.created)


class PhotoIndex:
    """Photo index stored in the SQLite database at ``path``."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._connection = sqlite3.connect(path)
        self._connection.executescript(SCHEMA)
        self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------ sources

    def replace_source(self, source: str, photos: Iterable[Photo]) -> int:
        """Make ``photos`` the content of ``source``; return their number.

        Photos already in the index keep their place and ``shown`` flag; photos of
        the source that are not in ``photos`` anymore are removed. Only changes
        are written (an unchanged library doesn't wear the SD card).
        """
        self._connection.executescript(INCOMING)
        with self._connection:
            self._connection.executemany(
                "INSERT OR REPLACE INTO incoming (id, created) VALUES (?, ?)",
                _rows(source, photos),
            )
            for statement in (
                "DELETE FROM photos WHERE source = :source"
                " AND id NOT IN (SELECT id FROM incoming)",
                "UPDATE photos SET created = incoming.created FROM incoming"
                " WHERE photos.source = :source AND photos.id = incoming.id"
                " AND photos.created != incoming.created",
                "INSERT INTO photos (source, id, created)"
                " SELECT :source, id, created FROM incoming WHERE true ORDER BY rowid"
                " ON CONFLICT (source, id) DO NOTHING",
            ):
                self._connection.execute(statement, {"source": source})
        self._connection.execute("DELETE FROM incoming")
        return self.count_source(source)

    def keep_sources(self, sources: Collection[str]) -> None:
        """Remove the photos of all sources except ``sources`` (disabled ones)."""
        marks = ", ".join("?" * len(sources))
        with self._connection:
            self._connection.execute(
                f"DELETE FROM photos WHERE source NOT IN ({marks})",
                tuple(sources),
            )

    def count_source(self, source: str) -> int:
        (count,) = self._connection.execute(
            "SELECT COUNT(*) FROM photos WHERE source = ?", (source,)
        ).fetchone()
        return int(count)

    # ---------------------------------------------------------------- selection

    @staticmethod
    def _parameters(selection: Selection) -> dict[str, object]:
        return {
            "after": _format(selection.after),
            "before": _format(selection.before),
            "limit": selection.limit,
        }

    @staticmethod
    def _candidates(selection: Selection) -> str:
        """``WITH candidates AS (...)`` clause of the selection."""
        conditions = [
            condition
            for condition, value in (
                (AFTER, selection.after),
                (BEFORE, selection.before),
            )
            if value is not None
        ]
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        limit = LIMIT if selection.limit is not None else ""
        return f"WITH candidates AS ({SELECT_CANDIDATES}{where}{limit})"

    def count(self, selection: Selection | None = None) -> int:
        """Number of photos (of the selection, or all)."""
        selection = selection or Selection()
        (count,) = self._connection.execute(
            f"{self._candidates(selection)} SELECT COUNT(*) FROM candidates",
            self._parameters(selection),
        ).fetchone()
        return int(count)

    def next_photo(
        self, selection: Selection, after: Photo | None = None
    ) -> Photo | None:
        """Return the photo that follows ``after`` (default: the last shown one).

        The order is the selection's sorting; after the last photo it starts over.
        A photo that is not in the index anymore is followed by the photo after
        its old place.
        """
        order, comes_after = ORDER[selection.sorting]
        position = self._position(after)
        if position["last_position"] is None:
            # unknown place: everything created at the same time comes after it
            position["last_position"] = (
                MAX_ROWID if selection.sorting == Sorting.DESC else -1
            )
        parameters = self._parameters(selection) | position
        query = f"{self._candidates(selection)} SELECT {COLUMNS} FROM candidates"
        row = (
            self._connection.execute(
                f"{query} WHERE {comes_after} ORDER BY {order} LIMIT 1", parameters
            ).fetchone()
            or self._connection.execute(
                f"{query} ORDER BY {order} LIMIT 1", parameters
            ).fetchone()
        )
        return _photo(row) if row else None

    def _position(self, photo: Photo | None) -> dict[str, object]:
        """Order key of ``photo`` (or of the last shown photo)."""
        if photo is not None:
            row = self._connection.execute(
                "SELECT created, rowid FROM photos WHERE source = ? AND id = ?",
                (photo.source, photo.id),
            ).fetchone()
            created, position = row or (_format(photo.created), None)
        else:
            created = self._state("last_created")
            position = self._state("last_position")
        return {"last_created": created, "last_position": position}

    def random_photo(
        self, selection: Selection, exclude: Photo | None = None
    ) -> Photo | None:
        """Return a random photo not shown in this cycle.

        ``exclude`` (default: the last shown photo) is not picked again unless it
        is the only one. When all photos were shown, any photo can be picked
        (``mark_shown`` then starts a new cycle).
        """
        excluded = exclude if exclude is not None else self.last_shown()
        for unshown_only in (True, False):
            for skip in (excluded, None):
                row = self._random_row(selection, unshown_only, skip)
                if row:
                    return _photo(row)
        return None

    def _random_row(
        self, selection: Selection, unshown_only: bool, skip: Photo | None
    ) -> tuple[str, str, str] | None:
        row: tuple[str, str, str] | None = self._connection.execute(
            f"{self._candidates(selection)} SELECT {COLUMNS} FROM candidates"
            " WHERE (:unshown_only = 0 OR shown = 0)"
            " AND NOT (source IS :skip_source AND id IS :skip_id)"
            " ORDER BY random() LIMIT 1",
            self._parameters(selection)
            | {
                "unshown_only": int(unshown_only),
                "skip_source": skip.source if skip else None,
                "skip_id": skip.id if skip else None,
            },
        ).fetchone()
        return row

    # -------------------------------------------------------------------- state

    def mark_shown(self, photo: Photo, selection: Selection) -> None:
        """Remember ``photo`` as the last shown one and flag it as shown.

        When no photo of the selection is unshown (``random_photo`` had to pick a
        shown one), a new random cycle starts: the flags of the selection are
        cleared first.
        """
        parameters = self._parameters(selection)
        candidates = self._candidates(selection)
        with self._connection:
            (unshown,) = self._connection.execute(
                f"{candidates} SELECT COUNT(*) FROM candidates WHERE shown = 0",
                parameters,
            ).fetchone()
            if not unshown:
                self._connection.execute(
                    f"{candidates} UPDATE photos SET shown = 0"
                    " WHERE rowid IN (SELECT position FROM candidates)",
                    parameters,
                )
            row = self._connection.execute(
                "UPDATE photos SET shown = 1 WHERE source = ? AND id = ?"
                " RETURNING created, rowid",
                (photo.source, photo.id),
            ).fetchone()
            created, position = row or (_format(photo.created), None)
            self._set_state(
                last_source=photo.source,
                last_id=photo.id,
                last_created=created,
                last_position=str(position) if position is not None else None,
            )

    def last_shown(self) -> Photo | None:
        """The photo remembered by ``mark_shown`` (it may be gone from the index)."""
        source, photo_id, created = (
            self._state(key) for key in ("last_source", "last_id", "last_created")
        )
        if source is None or photo_id is None or created is None:
            return None
        return _photo((source, photo_id, created))

    def _state(self, key: str) -> str | None:
        row = self._connection.execute(
            "SELECT value FROM state WHERE key = ?", (key,)
        ).fetchone()
        return str(row[0]) if row else None

    def _set_state(self, **values: str | None) -> None:
        for key, value in values.items():
            if value is None:
                self._connection.execute("DELETE FROM state WHERE key = ?", (key,))
            else:
                self._connection.execute(
                    "INSERT INTO state (key, value) VALUES (?, ?)"
                    " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )
