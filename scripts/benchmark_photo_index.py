#!/usr/bin/env python3
"""Benchmark the SQLite photo index with a synthetic library.

Run it on the target device (Raspberry Pi Zero) with the project environment::

    uv run python scripts/benchmark_photo_index.py --photos 300000

It prints the time of each operation of a frame refresh. The database is
created in a temporary directory unless ``--database`` is given.
"""

import argparse
import random
import resource
import tempfile
import time
from collections.abc import Callable, Iterator, Sequence
from datetime import datetime, timedelta
from pathlib import Path

from epiframe.photos.index import PhotoIndex
from epiframe.photos.model import Photo
from epiframe.photos.selection import Selection, Sorting

SOURCE = "Local"
START = datetime(2000, 1, 1)
YEARS = 25


def synthetic_photos(count: int, seed: int = 0) -> Iterator[Photo]:
    """``count`` photos with random creation times spread over ``YEARS`` years."""
    generator = random.Random(seed)  # noqa: S311 (test data, not security)
    span = int(timedelta(days=365 * YEARS).total_seconds())
    for number in range(count):
        created = START + timedelta(seconds=generator.randrange(span))
        yield Photo(f"/photos/{number // 1000:04}/{number:07}.jpg", SOURCE, created)


def measure(name: str, operation: Callable[[], object]) -> tuple[str, float]:
    started = time.perf_counter()
    operation()
    return name, time.perf_counter() - started


def operations(index: PhotoIndex, count: int) -> list[tuple[str, Callable[[], object]]]:
    middle = START + timedelta(days=365 * YEARS // 2)
    filtered = Selection(after=middle, before=middle + timedelta(days=365))
    ascending = Selection(sorting=Sorting.ASC)
    first = next(synthetic_photos(1))
    return [
        ("initial sync", lambda: index.replace_source(SOURCE, synthetic_photos(count))),
        (
            "sync, no changes",
            lambda: index.replace_source(SOURCE, synthetic_photos(count)),
        ),
        ("count all", index.count),
        ("count, 1 year filter", lambda: index.count(filtered)),
        ("next, found order", lambda: index.next_photo(Selection(), after=first)),
        ("next, oldest first", lambda: index.next_photo(ascending, after=first)),
        ("next, 1 year filter", lambda: index.next_photo(filtered)),
        ("random pick", lambda: index.random_photo(Selection())),
        ("random pick, filter", lambda: index.random_photo(filtered)),
        ("mark shown", lambda: index.mark_shown(first, Selection())),
    ]


def run(database: Path, count: int) -> list[tuple[str, float]]:
    with PhotoIndex(database) as index:
        return [
            measure(name, operation) for name, operation in operations(index, count)
        ]


def report(results: Sequence[tuple[str, float]], database: Path) -> str:
    lines = [f"{name:<24}{seconds * 1000:>12.1f} ms" for name, seconds in results]
    size = database.stat().st_size / 1024 / 1024
    memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    lines.append(f"{'database size':<24}{size:>12.1f} MB")
    lines.append(f"{'max memory (RSS)':<24}{memory:>12.1f} MB")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--photos", type=int, default=300_000)
    parser.add_argument("--database", type=Path, help="default: a temporary file")
    arguments = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as directory:
        database = arguments.database or Path(directory) / "photos.db"
        print(f"{arguments.photos} photos, database {database}")
        print(report(run(database, arguments.photos), database))


if __name__ == "__main__":  # pragma: no cover
    main()
