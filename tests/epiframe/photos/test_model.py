from datetime import UTC, datetime, timedelta, timezone

import pytest

from epiframe.photos.model import Photo, local_time


def test_naive_time_drops_microseconds() -> None:
    assert local_time(datetime(2024, 5, 1, 10, 0, 0, 999)) == datetime(2024, 5, 1, 10)


def test_aware_time_becomes_local(monkeypatch: pytest.MonkeyPatch) -> None:
    aware = datetime(2024, 5, 1, 10, tzinfo=timezone(timedelta(hours=2)))

    result = local_time(aware)

    assert result.tzinfo is None
    assert result == aware.astimezone().replace(tzinfo=None)


def test_photo_normalizes_created() -> None:
    photo = Photo("a.jpg", "Local", datetime(2024, 5, 1, 8, tzinfo=UTC))

    assert photo.created.tzinfo is None
    assert photo == Photo("a.jpg", "Local", photo.created)
