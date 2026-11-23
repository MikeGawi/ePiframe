from pathlib import Path

import pytest

from scripts import benchmark_photo_index as benchmark


def test_synthetic_photos_are_deterministic() -> None:
    photos = list(benchmark.synthetic_photos(3))

    assert photos == list(benchmark.synthetic_photos(3))
    assert [photo.id for photo in photos] == [
        "/photos/0000/0000000.jpg",
        "/photos/0000/0000001.jpg",
        "/photos/0000/0000002.jpg",
    ]
    assert all(photo.source == benchmark.SOURCE for photo in photos)


def test_run_measures_all_operations(tmp_path: Path) -> None:
    results = benchmark.run(tmp_path / "photos.db", 50)

    assert [name for name, _ in results][:2] == ["initial sync", "sync, no changes"]
    assert len(results) == 10
    assert all(seconds >= 0 for _, seconds in results)


def test_main(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database = tmp_path / "bench.db"

    benchmark.main(["--photos", "20", "--database", str(database)])

    output = capsys.readouterr().out
    assert output.startswith(f"20 photos, database {database}\n")
    assert "random pick" in output
    assert "database size" in output
    assert "max memory (RSS)" in output


def test_main_with_temporary_database(capsys: pytest.CaptureFixture[str]) -> None:
    benchmark.main(["--photos", "5"])

    assert "5 photos, database " in capsys.readouterr().out
