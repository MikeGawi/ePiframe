from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from epiframe.core.interval import IntervalMultiplier
from epiframe.photos.index import PhotoIndex
from epiframe.photos.model import Photo
from epiframe.photos.selection import Selection
from epiframe.processing.imagemagick import ImageMagickError
from epiframe.sources.drive import DRIVE_SOURCE, DriveSource
from epiframe.update import UpdateError
from epiframe.update import flow as flow_module
from epiframe.update.flow import ATTEMPTS, Mode, PhotoUpdate
from epiframe.update.pipeline import Pipeline
from epiframe.update.sources import NO_SOURCES
from tests.epiframe.update.conftest import add_photo
from tests.helpers.fake_drive import FakeDrive, photo

MakeUpdate = Callable[..., PhotoUpdate]


@pytest.fixture
def make_update(
    make_pipeline: Callable[..., Pipeline], plugins: MagicMock
) -> MakeUpdate:
    def make(mode: Mode = Mode.SHOW, **entries: str) -> PhotoUpdate:
        pipeline = make_pipeline(**entries)
        return PhotoUpdate(pipeline.config, plugins, pipeline, mode)

    return make


@pytest.fixture
def photos(tmp_path: Path) -> list[Path]:
    return [
        add_photo(tmp_path / "photos", "b.jpg", 1_700_000_000),
        add_photo(tmp_path / "photos", "a.jpg", 1_600_000_000),
    ]


def shown(tmp_path: Path) -> list[str]:
    with PhotoIndex(tmp_path / "photos.db") as index:
        last = index.last_shown()
    return [Path(last.id).name] if last else []


@pytest.mark.usefixtures("photos")
def test_update_shows_the_next_photo(
    make_update: MakeUpdate,
    display: MagicMock,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    update = make_update(sorting="asc")

    update.run()

    assert shown(tmp_path) == ["a.jpg"]
    display.show.assert_called_once_with(Path("photo.bmp"))
    assert Path("origphoto.jpg").exists()
    for message in ("Checking sources...", "Found 2 photos", "Filtered 2 photos"):
        assert message in caplog.messages

    make_update(sorting="asc").run()

    assert shown(tmp_path) == ["b.jpg"]


@pytest.mark.usefixtures("photos")
def test_test_mode_doesnt_show(
    make_update: MakeUpdate, display: MagicMock, tmp_path: Path
) -> None:
    make_update(Mode.TEST, sorting="asc").run()

    assert shown(tmp_path) == ["a.jpg"]
    assert Path("photo.bmp").exists()
    display.show.assert_not_called()


@pytest.mark.usefixtures("photos")
def test_no_skip_mode_keeps_the_photo(
    make_update: MakeUpdate, display: MagicMock, tmp_path: Path, magick: MagicMock
) -> None:
    magick.comment.return_value = "Frame 3"

    make_update(Mode.NO_SKIP).run()

    assert shown(tmp_path) == []
    assert not Path("time").exists()  # no multiplier
    display.show.assert_not_called()


@pytest.mark.usefixtures("photos")
def test_random_order(make_update: MakeUpdate, tmp_path: Path) -> None:
    make_update(randomize="1").run()
    first = shown(tmp_path)
    make_update(randomize="1").run()

    assert sorted(first + shown(tmp_path)) == ["a.jpg", "b.jpg"]


def test_no_sources(make_update: MakeUpdate) -> None:
    with pytest.raises(UpdateError, match=NO_SOURCES):
        make_update(use_local="0").run()


def test_no_photos(make_update: MakeUpdate) -> None:
    with pytest.raises(UpdateError, match="No photos in sources!"):
        make_update().run()


@pytest.mark.usefixtures("photos")
def test_no_photos_after_filtering(make_update: MakeUpdate) -> None:
    with pytest.raises(UpdateError, match="No photos after filtering!"):
        make_update(photos_from="2030-01-01 00:00:00").run()


@pytest.mark.usefixtures("photos")
def test_broken_filtering(make_update: MakeUpdate) -> None:
    update = make_update(sorting="sideways")  # not verified

    with pytest.raises(UpdateError, match="Error parsing configured filtering"):
        update.run()


def test_photo_removed_meanwhile(make_update: MakeUpdate) -> None:
    index: MagicMock = MagicMock(spec=PhotoIndex)
    index.next_photo.return_value = None

    with pytest.raises(UpdateError, match="No photos after filtering!"):
        make_update()._pick(index, Selection(), None)


def test_failed_photo_is_skipped(
    make_update: MakeUpdate,
    photos: list[Path],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    update = make_update(sorting="asc")
    with PhotoIndex(tmp_path / "photos.db") as index:
        update.sources.sync(index)
    photos[1].unlink()  # a.jpg is in the index, but gone: b.jpg is shown
    update.sources.sync = lambda index: None  # type: ignore[method-assign]

    update.run()

    assert shown(tmp_path) == ["b.jpg"]
    assert "Retrying with the new photo..." in caplog.messages
    assert any("File was not retrieved" in message for message in caplog.messages)


@pytest.mark.usefixtures("photos")
def test_no_photo_retrieved(
    make_update: MakeUpdate, monkeypatch: pytest.MonkeyPatch, display: MagicMock
) -> None:
    update = make_update()
    monkeypatch.setattr(
        update.fetcher, "fetch", MagicMock(side_effect=OSError("disk error"))
    )

    with pytest.raises(UpdateError, match=f"No photo retrieved in {ATTEMPTS}"):
        update.run()

    assert update.fetcher.fetch.call_count == ATTEMPTS  # type: ignore[attr-defined]
    display.show.assert_not_called()


# ---------------------------------------------------------------- multiplier


@pytest.mark.usefixtures("photos")
def test_multiplier_from_comment(make_update: MakeUpdate, magick: MagicMock) -> None:
    magick.comment.return_value = "Frame 3"

    make_update(Mode.TEST).run()

    assert IntervalMultiplier("time").read() == 3
    magick.comment.assert_called_once_with("origphoto.jpg")


@pytest.mark.usefixtures("photos")
def test_old_multiplier_is_removed(make_update: MakeUpdate, magick: MagicMock) -> None:
    IntervalMultiplier("time").save(4)
    magick.comment.side_effect = ImageMagickError("no comment")

    make_update(Mode.TEST).run()

    assert IntervalMultiplier("time").read() == 0


@pytest.mark.usefixtures("photos")
def test_multiplier_disabled(make_update: MakeUpdate, magick: MagicMock) -> None:
    IntervalMultiplier("time").save(4)

    make_update(Mode.TEST, interval_mult="0").run()

    assert IntervalMultiplier("time").read() == 4
    magick.comment.assert_not_called()


def test_drive_photo(
    make_update: MakeUpdate, magick: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    drive = FakeDrive()
    drive.files["p1"] = photo("p1")
    drive.descriptions["p1"] = "Frame 2"
    created: list[object] = []

    def drive_source(config: object) -> DriveSource:
        created.append(config)
        return DriveSource(drive, ["root"], True, ["jpg"])

    monkeypatch.setattr(flow_module, "drive_source", drive_source)
    update = make_update(Mode.TEST, use_local="0", use_drive="1")
    update.sources.sync = lambda index: None  # type: ignore[method-assign]
    with PhotoIndex("photos.db") as index:
        index.add_photos([Photo("p1", DRIVE_SOURCE, datetime(2024, 5, 1))])

    update.run()

    assert Path("origphoto.jpg").read_bytes() == b"p1"
    assert IntervalMultiplier("time").read() == 2  # the Drive description
    magick.comment.assert_not_called()
    assert update.drive() is update.drive()
    assert len(created) == 1
