import datetime
import pandas as pd
import pytest
from modules.filteringmanager import FilteringManager
from tests.helpers.helpers import not_raises

date_header = "date_header"
photo_header = "photo"


def test_get_sorting():
    sorting = FilteringManager.get_sorting()
    assert sorting == ["none", "asc", "desc"]


def test_verify_sorting_ok():
    sorting = FilteringManager.get_sorting()
    with not_raises(Exception):
        FilteringManager.verify_sorting(sorting[0])


def test_verify_sorting_nok():
    with pytest.raises(Exception) as exception:
        FilteringManager.verify_sorting("non_existing_sorting")
    assert (
        str(exception.value)
        == f"Configuration sorting should be one of {FilteringManager.get_sorting()}"
    )


def test_get_descending():
    descending = FilteringManager.get_descending(True)
    assert descending == "desc"


def test_get_none():
    none = FilteringManager.get_descending(False)
    assert none == "none"


def test_verify_ok():
    with not_raises(Exception):
        FilteringManager.verify(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def test_verify_nok():
    with pytest.raises(Exception):
        FilteringManager.verify(datetime.datetime.now().isoformat())


def test_convert_ok():
    now = datetime.datetime.now()
    new = now.strftime("%Y-%m-%d %H:%M:%S")
    old = now.strftime("%Y.%m.%d %H:%M:%S")

    assert FilteringManager.convert(old) == new


def test_convert_no_change():
    new = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    assert FilteringManager.convert(new) == new


def test_verify_times_ok():
    past = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with not_raises(Exception):
        FilteringManager.verify_times([past, now])


def test_verify_times_nok():
    past = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with pytest.raises(Exception) as exception:
        FilteringManager.verify_times([now, past])
    assert (
        str(exception.value)
        == "Configuration photos_from time is older than photos_to!"
    )


def test_sort_none():
    photos_pd = create_photos_dataframe()
    sorted_photos = FilteringManager.sort(
        photos_pd, photo_header, photos_pd[photo_header], "none"
    )

    assert [photos[0] for photos in sorted_photos.values.tolist()] == [
        "Photo1",
        "Photo2",
        "Photo3",
    ]


def test_sort_asc():
    photos_pd = create_photos_dataframe()
    sorted_photos = FilteringManager.sort(
        photos_pd, date_header, photos_pd[date_header], "asc"
    )

    assert [photos[0] for photos in sorted_photos.values.tolist()] == [
        "Photo2",
        "Photo1",
        "Photo3",
    ]


def test_sort_desc():
    photos_pd = create_photos_dataframe()
    sorted_photos = FilteringManager.sort(
        photos_pd, date_header, photos_pd[date_header], "desc"
    )

    assert [photos[0] for photos in sorted_photos.values.tolist()] == [
        "Photo3",
        "Photo1",
        "Photo2",
    ]


def test_get_by_number():
    photos_pd = create_photos_dataframe()
    filtered_photos = FilteringManager.filter_by_number(photos_pd, 2)

    assert [photos[0] for photos in filtered_photos.values.tolist()] == [
        "Photo1",
        "Photo2",
    ]


def test_get_by_number_too_much():
    photos_pd = create_photos_dataframe()
    filtered_photos = FilteringManager.filter_by_number(photos_pd, 5)

    assert [photos[0] for photos in filtered_photos.values.tolist()] == [
        "Photo1",
        "Photo2",
        "Photo3",
    ]


def test_get_by_number_negative():
    photos_pd = create_photos_dataframe()
    filtered_photos = FilteringManager.filter_by_number(photos_pd, -1)

    assert [photos[0] for photos in filtered_photos.values.tolist()] == [
        "Photo1",
        "Photo2",
        "Photo3",
    ]


def test_get_from():
    now = datetime.datetime.now()
    photos_pd = create_photos_dataframe(now)
    filtered_photos = FilteringManager.filter_by_from_date(
        photos_pd, now.strftime("%Y-%m-%d %H:%M:%S"), date_header
    )

    assert [photos[0] for photos in filtered_photos.values.tolist()] == [
        "Photo3",
    ]


def test_get_to():
    now = datetime.datetime.now()
    photos_pd = create_photos_dataframe(now)
    filtered_photos = FilteringManager.filter_by_to_date(
        photos_pd, now.strftime("%Y-%m-%d %H:%M:%S"), date_header
    )

    assert [photos[0] for photos in filtered_photos.values.tolist()] == [
        "Photo2",
    ]


def create_photos_dataframe(time: datetime.datetime = None):
    time_format = "%Y-%m-%d %H:%M:%S"
    time_now = time if time else datetime.datetime.now()
    now = time_now.strftime(time_format)
    past = (time_now - datetime.timedelta(hours=1)).strftime(time_format)
    future = (time_now + datetime.timedelta(hours=1)).strftime(time_format)
    photos = [
        {photo_header: "Photo1", date_header: now},
        {photo_header: "Photo2", date_header: past},
        {photo_header: "Photo3", date_header: future},
    ]
    return pd.DataFrame(photos)
