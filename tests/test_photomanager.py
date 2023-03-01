import pandas as pd
from modules.albummanager import AlbumManager
from modules.photomanager import PhotoManager
from tests.helpers.helpers import not_raises

header = "header_name"
media_header = "media_header"
photo_header = "photo_header"
mime_header = "mime_header"
source_label = "source_label"
mime_type = "mime_type"
source = "source"
albums = [
    {header: "Album1"},
    {header: "Album2"},
    {header: "Album3"},
]
names = "Album1"

photo_manager: PhotoManager
album: AlbumManager


def test_set_photos():
    global album
    album = AlbumManager(albums, names, header)
    assert sorted(album.get_albums().values.tolist()) == sorted(
        [[name] for name in names.split(",")]
    )

    data = [
        {
            "media": "media1",
            source_label: source,
            media_header: {mime_header: mime_type, photo_header: "photo1"},
        },
        {
            "media": "media2",
            source_label: source,
            media_header: {mime_header: mime_type, photo_header: "photo2"},
        },
        {
            "media": "media3",
            source_label: source,
            media_header: {mime_header: mime_type, photo_header: "photo3"},
        },
    ]

    album.append_data(data)

    global photo_manager
    photo_manager = PhotoManager()

    with not_raises(Exception):
        photo_manager.set_photos(
            album,
            media_header,
            photo_header,
            mime_header,
            mime_type,
            source_label,
            source,
        )


def test_get_photos():
    photos = photo_manager.get_photos()
    assert photos.values.tolist() == [
        ["media1", "source", "mime_type", "photo1"],
        ["media2", "source", "mime_type", "photo2"],
        ["media3", "source", "mime_type", "photo3"],
    ]

    assert photos.columns.tolist() == ["media", "source_label", "mime_header", 0]


def test_get_number_of_photos():
    assert photo_manager.get_num_of_photos(photo_manager.get_photos()) == 3


def test_get_album():
    assert photo_manager.get_album() == album


def test_get_photo():
    photo = photo_manager.get_photo_by_index(photo_manager.get_photos(), 1)
    assert photo.values.tolist() == ["media2", "source", "mime_type", "photo2"]


def test_get_photo_attribute():
    photo = photo_manager.get_photo_by_index(photo_manager.get_photos(), 1)
    assert photo_manager.get_photo_attribute(photo, "media") == "media2"


def test_get_photos_attribute():
    photos = photo_manager.get_photos()
    assert photo_manager.get_photos_attribute(photos, "media").values.tolist() == [
        "media1",
        "media2",
        "media3",
    ]


def test_append_photos():
    data = [
        {
            "media": "media4",
            source_label: source,
            mime_header: mime_type,
            0: "photo4",
        },
    ]
    photos = photo_manager.get_photos()
    assert photo_manager.get_num_of_photos(photos) == 3
    merged = photo_manager.append_photos(photos, pd.DataFrame(data))
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
    assert photo_manager.get_num_of_photos(merged) == 4
    assert merged.index.tolist() == [0, 1, 2, 3]
