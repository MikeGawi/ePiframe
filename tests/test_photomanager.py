import pandas as pd
import pytest

from modules.photomanager import PhotoManager

source_label = "source_label"
mime_header = "mime_header"
source = "source"
mime_type = "mime_type"


@pytest.fixture
def photos() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "media": f"media{number}",
                source_label: source,
                mime_header: mime_type,
                0: f"photo{number}",
            }
            for number in range(1, 4)
        ]
    )


def test_get_number_of_photos(photos):
    assert PhotoManager.get_num_of_photos(photos) == 3


def test_get_photo(photos):
    photo = PhotoManager.get_photo_by_index(photos, 1)
    assert photo.values.tolist() == ["media2", "source", "mime_type", "photo2"]


def test_get_photo_attribute(photos):
    photo = PhotoManager.get_photo_by_index(photos, 1)
    assert PhotoManager.get_photo_attribute(photo, "media") == "media2"


def test_get_photos_attribute(photos):
    assert PhotoManager.get_photos_attribute(photos, "media").values.tolist() == [
        "media1",
        "media2",
        "media3",
    ]


def test_reset_index(photos):
    reversed_photos = photos.iloc[::-1]
    assert reversed_photos.index.tolist() == [2, 1, 0]
    assert PhotoManager.reset_index(reversed_photos).index.tolist() == [0, 1, 2]


def test_append_photos(photos):
    data = [
        {
            "media": "media4",
            source_label: source,
            mime_header: mime_type,
            0: "photo4",
        },
    ]
    merged = PhotoManager().append_photos(photos, pd.DataFrame(data))
    assert sorted([str(item) for item in merged.columns.tolist()]) == [
        "0",
        "media",
        "mime_header",
        "source_label",
    ]
    assert merged.values.tolist() == [
        ["media1", "source", "mime_type", "photo1"],
        ["media2", "source", "mime_type", "photo2"],
        ["media3", "source", "mime_type", "photo3"],
        ["media4", "source", "mime_type", "photo4"],
    ]
    assert PhotoManager.get_num_of_photos(merged) == 4
    assert merged.index.tolist() == [0, 1, 2, 3]


def test_append_photos_to_none(photos):
    merged = PhotoManager().append_photos(None, photos)
    assert merged.values.tolist() == photos.values.tolist()
