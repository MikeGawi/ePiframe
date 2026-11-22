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


def test_create_files(tmp_path: Path) -> None:
    benchmark.create_files(tmp_path, 205)

    folders = sorted(path.name for path in tmp_path.iterdir())
    assert folders == ["00000", "00001", "00002"]
    assert len(list((tmp_path / "00002").iterdir())) == 5


def test_run_scan(tmp_path: Path) -> None:
    results = benchmark.run_scan(tmp_path / "scan.db", tmp_path / "files", 150)

    assert [name for name, _ in results] == [
        "create 150 files",
        "full scan",
        "incremental, no change",
        "incremental, 1 new file",
    ]


def test_main_with_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    benchmark.main(["--photos", "5", "--files", "10", "--files-dir", str(tmp_path)])

    output = capsys.readouterr().out
    assert f"10 files in {tmp_path}" in output
    assert "incremental, 1 new file" in output
    assert len(list((tmp_path / "00000").iterdir())) == 11


def test_main_with_temporary_files(capsys: pytest.CaptureFixture[str]) -> None:
    benchmark.main(["--photos", "5", "--files", "3"])

    assert "3 files in " in capsys.readouterr().out
