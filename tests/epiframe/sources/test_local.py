import os
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from epiframe.photos.index import PhotoIndex
from epiframe.photos.selection import Selection
from epiframe.sources.local import (
    FOLDER_KEY,
    FULL_SCAN_KEY,
    LOCAL_SOURCE,
    SETTINGS_KEY,
    LocalSource,
    create_directory,
)

EXTENSIONS = ["jpg", "png"]
NOW = datetime(2026, 11, 22, 12)
MTIME = datetime(2024, 5, 1, 10).timestamp()


def touch(path: Path, mtime: float = MTIME) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    os.utime(path, (mtime, mtime))
    return path


def freeze(folder: Path, mtime_ns: int = 1_000_000_000) -> None:
    """Set the folder time back, as if nothing had changed in it."""
    os.utime(folder, ns=(mtime_ns, mtime_ns))


@pytest.fixture
def library(tmp_path: Path) -> Path:
    root = tmp_path / "photos"
    touch(root / "b.jpg")
    touch(root / "a.JPG")
    touch(root / "notes.txt")
    touch(root / ".hidden.jpg")
    touch(root / "2024" / "x.png")
    touch(root / ".cache" / "y.jpg")
    touch(root / "2023" / "deep" / "z.jpg")
    return root


@pytest.fixture
def index(tmp_path: Path) -> Iterator[PhotoIndex]:
    with PhotoIndex(tmp_path / "photos.db") as photo_index:
        yield photo_index


def ids(index: PhotoIndex) -> list[str]:
    """Photo ids in the index's natural order."""
    result = []
    photo = index.next_photo(Selection())
    while photo and photo.id not in result:
        result.append(photo.id)
        photo = index.next_photo(Selection(), after=photo)
    return [os.path.relpath(photo_id) for photo_id in result]


def test_create_directory(tmp_path: Path) -> None:
    folder = tmp_path / "new" / "photos"

    assert create_directory(str(folder)) == str(folder)
    assert folder.is_dir()
    assert create_directory(str(folder)) == str(folder)


def test_photos_recursive(library: Path) -> None:
    source = LocalSource(str(library) + "/", True, EXTENSIONS)

    photos = list(source.photos())

    assert [os.path.relpath(photo.id, library) for photo in photos] == [
        "a.JPG",
        "b.jpg",
        "2023/deep/z.jpg",
        "2024/x.png",
    ]
    assert all(photo.source == LOCAL_SOURCE for photo in photos)
    assert photos[0].created == datetime.fromtimestamp(MTIME)
    assert photos[0].id == f"{library}/a.JPG"


def test_photos_not_recursive(library: Path) -> None:
    source = LocalSource(str(library), False, EXTENSIONS)

    assert [Path(photo.id).name for photo in source.photos()] == ["a.JPG", "b.jpg"]


def test_relative_ids(library: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(library.parent)

    photos = list(LocalSource("photos/", False, EXTENSIONS).photos())

    assert [photo.id for photo in photos] == ["photos/a.JPG", "photos/b.jpg"]


def test_missing_folder(tmp_path: Path) -> None:
    assert list(LocalSource(str(tmp_path / "missing"), True, EXTENSIONS).photos()) == []


def test_unreadable_folder_is_skipped(library: Path) -> None:
    locked = library / "2024"
    locked.chmod(0)
    try:
        if os.access(locked, os.R_OK):  # pragma: no cover (running as root)
            pytest.skip("permissions are not enforced")
        names = [
            Path(p.id).name
            for p in LocalSource(str(library), True, EXTENSIONS).photos()
        ]
    finally:
        locked.chmod(0o755)

    assert names == ["a.JPG", "b.jpg", "z.jpg"]


def test_symlink_loops_are_followed_once(library: Path) -> None:
    (library / "2024" / "loop").symlink_to(library)
    (library / "link").symlink_to(library / "2023")

    names = [
        Path(p.id).name for p in LocalSource(str(library), True, EXTENSIONS).photos()
    ]

    assert sorted(names) == ["a.JPG", "b.jpg", "x.png", "z.jpg"]


def test_vanished_file_is_skipped(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = LocalSource(str(library), False, EXTENSIONS)
    folder = next(source.folders())
    (library / "a.JPG").unlink()

    photos = list(source._photos(folder))

    assert [Path(photo.id).name for photo in photos] == ["b.jpg"]


def test_first_sync_is_a_full_scan(library: Path, index: PhotoIndex) -> None:
    result = LocalSource(str(library), True, EXTENSIONS).sync(index, NOW)

    assert result.full is True
    assert (result.folders, result.scanned, result.photos) == (4, 4, 4)
    state = index.source_state(LOCAL_SOURCE)
    assert state[FULL_SCAN_KEY] == NOW.isoformat()
    assert state[SETTINGS_KEY] == f"{library}|1|jpg,png"
    assert sum(key.startswith(FOLDER_KEY) for key in state) == 4


def test_unchanged_folders_are_not_read(library: Path, index: PhotoIndex) -> None:
    source = LocalSource(str(library), True, EXTENSIONS)
    source.sync(index, NOW)

    result = source.sync(index, NOW + timedelta(hours=1))

    assert result.full is False
    assert (result.folders, result.scanned, result.photos) == (4, 0, 4)


def test_changed_folder_is_read(library: Path, index: PhotoIndex) -> None:
    source = LocalSource(str(library), True, EXTENSIONS)
    source.sync(index, NOW)
    before = ids(index)

    touch(library / "2024" / "new.jpg")
    (library / "2023" / "deep" / "z.jpg").unlink()
    result = source.sync(index, NOW + timedelta(hours=1))

    assert (result.scanned, result.photos) == (2, 4)
    # new photos are appended, the others keep their place
    assert ids(index) == [
        *[photo_id for photo_id in before if not photo_id.endswith("z.jpg")],
        os.path.relpath(library / "2024" / "new.jpg"),
    ]


def test_file_changes_in_unchanged_folder_wait_for_full_scan(
    library: Path, index: PhotoIndex
) -> None:
    source = LocalSource(str(library), False, EXTENSIONS)
    source.sync(index, NOW)
    freeze(library)
    source.sync(index, NOW)  # folder time stored after the freeze

    touch(library / "c.jpg")
    freeze(library)  # e.g. a file system that doesn't update folder times
    assert source.sync(index, NOW + timedelta(hours=1)).photos == 2

    result = source.sync(index, NOW + timedelta(days=1))
    assert result.full is True
    assert result.photos == 3


def test_removed_folder(library: Path, index: PhotoIndex) -> None:
    source = LocalSource(str(library), True, EXTENSIONS)
    source.sync(index, NOW)

    for path in sorted((library / "2023").rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    (library / "2023").rmdir()
    result = source.sync(index, NOW + timedelta(hours=1))

    assert (result.folders, result.photos) == (2, 3)  # 2023 and 2023/deep are gone
    assert not any("2023" in key for key in index.source_state(LOCAL_SOURCE))
    assert "z.jpg" not in " ".join(ids(index))


def test_settings_change_forces_full_scan(library: Path, index: PhotoIndex) -> None:
    LocalSource(str(library), True, EXTENSIONS).sync(index, NOW)

    result = LocalSource(str(library), False, EXTENSIONS).sync(
        index, NOW + timedelta(hours=1)
    )

    assert result.full is True
    assert (result.folders, result.photos) == (1, 2)
    folders = [
        key for key in index.source_state(LOCAL_SOURCE) if key.startswith(FOLDER_KEY)
    ]
    assert folders == [FOLDER_KEY + str(library)]


def test_full_scan_keeps_places_and_drops_unknown_photos(
    library: Path, index: PhotoIndex
) -> None:
    # e.g. photos indexed by 3.6 (no folder state) from an old local_path
    old = LocalSource(str(library / "2024"), False, EXTENSIONS)
    index.replace_source(LOCAL_SOURCE, old.photos())
    index.replace_source(
        LOCAL_SOURCE,
        [*old.photos(), *LocalSource(str(library), False, EXTENSIONS).photos()],
    )

    LocalSource(str(library), False, EXTENSIONS).sync(index, NOW)

    assert [Path(photo_id).name for photo_id in ids(index)] == ["a.JPG", "b.jpg"]


def test_failed_sync_writes_nothing(
    library: Path, index: PhotoIndex, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = LocalSource(str(library), True, EXTENSIONS)
    source.sync(index, NOW)
    touch(library / "2024" / "new.jpg")

    def broken(*arguments: object) -> None:
        raise OSError("SD card error")

    monkeypatch.setattr(index, "remove_source_state", broken)
    with pytest.raises(OSError, match="SD card error"):
        source.sync(index, NOW + timedelta(hours=1))

    assert index.count_source(LOCAL_SOURCE) == 4
