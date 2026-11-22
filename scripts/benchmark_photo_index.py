#!/usr/bin/env python3
"""Benchmark the SQLite photo index with a synthetic library.

Run it on the target device (Raspberry Pi Zero) with the project environment::

    uv run python scripts/benchmark_photo_index.py --photos 300000

It prints the time of each operation of a frame refresh. The database is
created in a temporary directory unless ``--database`` is given.

``--files N`` also benchmarks the local source scan: it creates N empty photo
files (100 per folder) in ``--files-dir`` (default: a temporary directory) and
times a full scan, an incremental scan without changes and one with a new file::

    uv run python scripts/benchmark_photo_index.py --photos 0 --files 300000 \\
        --files-dir ~/bench-photos
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
from epiframe.sources.local import LocalSource

SOURCE = "Local"
START = datetime(2000, 1, 1)
YEARS = 25
FILES_PER_FOLDER = 100


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


def create_files(directory: Path, count: int) -> None:
    """``count`` empty ``.jpg`` files, ``FILES_PER_FOLDER`` per folder."""
    for number in range(count):
        folder = directory / f"{number // FILES_PER_FOLDER:05}"
        if number % FILES_PER_FOLDER == 0:
            folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{number:07}.jpg").touch()


def run_scan(database: Path, directory: Path, count: int) -> list[tuple[str, float]]:
    """Time the local source scans of ``count`` files in ``directory``."""
    results = [measure(f"create {count} files", lambda: create_files(directory, count))]
    source = LocalSource(str(directory), True, ["jpg"])
    with PhotoIndex(database) as index:
        results.append(measure("full scan", lambda: source.sync(index)))
        results.append(measure("incremental, no change", lambda: source.sync(index)))
        (directory / "00000" / "new.jpg").touch()
        results.append(measure("incremental, 1 new file", lambda: source.sync(index)))
    return results


def scan_report(count: int, files_dir: Path | None, directory: Path) -> str:
    files_dir = files_dir or directory / "files"
    database = directory / "scan.db"
    results = run_scan(database, files_dir, count)
    return f"{count} files in {files_dir}\n{report(results, database)}"


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
    parser.add_argument("--files", type=int, default=0, help="local scan benchmark")
    parser.add_argument("--files-dir", type=Path, help="default: a temporary folder")
    arguments = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as directory:
        database = arguments.database or Path(directory) / "photos.db"
        print(f"{arguments.photos} photos, database {database}")
        print(report(run(database, arguments.photos), database))
        if arguments.files:
            print(scan_report(arguments.files, arguments.files_dir, Path(directory)))


if __name__ == "__main__":  # pragma: no cover
    main()
