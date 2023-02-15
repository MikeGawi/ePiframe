import pytest
from modules.albummanager import AlbumManager

header = "header_name"
albums = [{header: "Album1"}, {header: "Album2"}, {header: "Album3"}]
names = "Album1,Album2"


def test_get_albums():
    album = AlbumManager(albums, names, header)
    assert sorted(album.get_albums().values.tolist()) == sorted(
        [[name] for name in names.split(",")]
    )


def test_get_albums_wrong_header():
    with pytest.raises(KeyError):
        AlbumManager(albums, names, "wrong_header")


def test_get_albums_all():
    album = AlbumManager(albums, "", header)
    assert sorted(album.get_albums().values.tolist()) == sorted(
        [["".join(album.values())] for album in albums]
    )


def test_get_albums_wrong():
    album = AlbumManager(albums, "wrong_album", header)
    assert album.get_albums().empty


def test_get_albums_empty():
    with pytest.raises(KeyError):
        AlbumManager([], names, header)


def test_append_empty():
    album = AlbumManager(albums, names, header)
    album.append_data([])
    assert album.get_data().empty


def test_append():
    album = AlbumManager(albums, names, header)
    album.append_data(albums)
    assert sorted(album.get_data().values.tolist()) == sorted(
        [["".join(album.values())] for album in albums]
    )


def test_append_twice():
    album = AlbumManager(albums, names, header)
    album.append_data(albums)
    additional = [{header: "Album4"}]
    album.append_data(additional)
    assert sorted(album.get_data().values.tolist()) == sorted(
        [["".join(album.values())] for album in albums + additional]
    )
