import dataclasses
from collections.abc import Iterator
from datetime import datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import requests_mock
from google.auth.transport.requests import AuthorizedSession

from epiframe.photos.index import PhotoIndex
from epiframe.photos.model import Photo
from epiframe.photos.selection import Selection
from epiframe.sources import drive
from epiframe.sources.drive import (
    API_URL,
    DRIVE_SOURCE,
    FOLDER_KEY,
    FOLDER_TYPE,
    FULL_SCAN_KEY,
    PAGE_TOKEN_KEY,
    SCOPES,
    SETTINGS_KEY,
    Change,
    ChangePage,
    DriveClient,
    DriveError,
    DriveFile,
    DriveSource,
    folder_id,
    folder_ids,
)
from tests.helpers.fake_drive import (
    ROOT,
    TAKEN,
    FakeDrive,
    folder,
    http_error,
    photo,
)
from tests.helpers.service_account import ACCOUNT, write_key

NOW = datetime(2026, 11, 22, 12)
EXTENSIONS = ["jpg", "png", "cr2"]


@pytest.fixture
def fake() -> FakeDrive:
    fake = FakeDrive()
    fake.files[ROOT] = DriveFile(ROOT, "Photos", FOLDER_TYPE)
    fake.add(
        photo("b", name="b.jpg"),
        photo("a", name="a.JPG", mime_type="application/octet-stream"),
        DriveFile("notes", "notes.txt", "text/plain", (ROOT,)),
        DriveFile("video", "movie.mp4", "video/mp4", (ROOT,)),
        folder("2024"),
        photo("x", "2024", name="x.png", mime_type="image/png"),
        folder("deep", "2024"),
        photo("z", "deep", name="z.cr2", mime_type="image/x-canon-cr2"),
    )
    return fake


@pytest.fixture
def source(fake: FakeDrive) -> DriveSource:
    return DriveSource(fake, [ROOT], True, EXTENSIONS)


@pytest.fixture
def index(tmp_path: Path) -> Iterator[PhotoIndex]:
    with PhotoIndex(tmp_path / "photos.db") as photo_index:
        yield photo_index


def ids(index: PhotoIndex) -> list[str]:
    """Photo ids in the index's natural order."""
    result: list[str] = []
    current = index.next_photo(Selection())
    while current and current.id not in result:
        result.append(current.id)
        current = index.next_photo(Selection(), after=current)
    return result


# ---------------------------------------------------------------- folder id


@pytest.mark.parametrize(
    "value",
    [
        "1AbC-dEf_123456789",
        " 1AbC-dEf_123456789 ",
        "https://drive.google.com/drive/folders/1AbC-dEf_123456789",
        "https://drive.google.com/drive/folders/1AbC-dEf_123456789?usp=sharing",
        "https://drive.google.com/drive/u/0/folders/1AbC-dEf_123456789#x",
        "https://drive.google.com/open?id=1AbC-dEf_123456789&authuser=0",
    ],
)
def test_folder_id(value: str) -> None:
    assert folder_id(value) == "1AbC-dEf_123456789"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "short",
        "with space 123456",
        "https://drive.google.com/drive/folders/",
        "https://drive.google.com/drive/folders/bad'quote123456",
        "id' or name contains 'x",
    ],
)
def test_folder_id_invalid(value: str) -> None:
    with pytest.raises(ValueError, match="Not a Google Drive folder ID or link"):
        folder_id(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1AbC-dEf_123456789", ["1AbC-dEf_123456789"]),
        (
            "1AbC-dEf_123456789, https://drive.google.com/drive/folders/2XyZ_987654321,",
            ["1AbC-dEf_123456789", "2XyZ_987654321"],
        ),
        ("1AbC-dEf_123456789,1AbC-dEf_123456789", ["1AbC-dEf_123456789"]),
    ],
)
def test_folder_ids(value: str, expected: list[str]) -> None:
    assert folder_ids(value) == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (" , ", "No Google Drive folder ID or link"),
        ("1AbC-dEf_123456789,bad", "Not a Google Drive folder ID or link: 'bad'"),
    ],
)
def test_folder_ids_invalid(value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        folder_ids(value)


# ---------------------------------------------------------------- drive file


def test_drive_file_from_json() -> None:
    file = DriveFile.from_json(
        {
            "id": "f1",
            "name": "Holiday.JPEG",
            "mimeType": "image/jpeg",
            "parents": ["p1"],
            "trashed": True,
            "modifiedTime": "2024-05-02T08:00:00.000Z",
            "imageMediaMetadata": {"time": TAKEN},
        }
    )

    assert file == DriveFile(
        "f1",
        "Holiday.JPEG",
        "image/jpeg",
        ("p1",),
        True,
        "2024-05-02T08:00:00.000Z",
        TAKEN,
    )
    assert file.extension == "jpeg"
    assert not file.is_folder
    assert file.created() == datetime(2024, 5, 1, 10)


def test_drive_file_defaults() -> None:
    file = DriveFile.from_json({"id": "f1"})

    assert file == DriveFile("f1", "", "")
    assert file.extension == ""


@pytest.mark.parametrize("taken", ["", "0000:00:00 00:00:00", "garbage"])
def test_drive_file_created_falls_back_to_modified(taken: str) -> None:
    file = DriveFile("f1", "a.jpg", "image/jpeg", modified="2024-05-02T08:00:00Z")

    created = dataclasses.replace(file, taken=taken).created()

    assert created == datetime.fromisoformat("2024-05-02T08:00:00+00:00")
    assert Photo("f1", DRIVE_SOURCE, created).created == (
        created.astimezone().replace(tzinfo=None)
    )


# -------------------------------------------------------------------- client


@pytest.fixture
def http() -> Iterator[requests_mock.Mocker]:
    with requests_mock.Mocker() as mocker:
        yield mocker


@pytest.fixture
def client() -> DriveClient:
    return DriveClient(requests.Session(), "frame@example.com")


def query(request: Any) -> dict[str, str]:
    """Query parameters of a recorded request (case preserved)."""
    return {
        key: values[0] for key, values in parse_qs(urlparse(request.url).query).items()
    }


def test_client_file(http: requests_mock.Mocker, client: DriveClient) -> None:
    http.get(f"{API_URL}/files/f1", json={"name": "a.jpg"})

    assert client.file("f1", "name") == {"name": "a.jpg"}
    assert query(http.last_request) == {"fields": "name", "supportsAllDrives": "true"}
    assert http.request_history[0].timeout == drive.TIMEOUT


def test_client_error(http: requests_mock.Mocker, client: DriveClient) -> None:
    http.get(f"{API_URL}/files/f1", status_code=HTTPStatus.NOT_FOUND)

    with pytest.raises(requests.HTTPError) as error:
        client.file("f1", "name")
    assert error.value.response is not None
    assert error.value.response.status_code == HTTPStatus.NOT_FOUND


def test_client_children(http: requests_mock.Mocker, client: DriveClient) -> None:
    http.get(
        f"{API_URL}/files",
        [
            {"json": {"files": [{"id": "a"}, {"id": "b"}], "nextPageToken": "next"}},
            {"json": {"files": [{"id": "c"}]}},
            {"json": {}},
        ],
    )

    files = list(client.children(["p1", "p2"]))
    empty = list(client.children(["p3"]))

    assert [file.id for file in files] == ["a", "b", "c"]
    assert empty == []
    first, second, _ = (query(request) for request in http.request_history)
    assert first == {
        "q": "('p1' in parents or 'p2' in parents) and trashed = false",
        "fields": f"nextPageToken,files({drive.FILE_FIELDS})",
        "orderBy": "name",
        "pageSize": "1000",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    assert second == first | {"pageToken": "next"}


def test_client_start_page_token(
    http: requests_mock.Mocker, client: DriveClient
) -> None:
    http.get(f"{API_URL}/changes/startPageToken", json={"startPageToken": "42"})

    assert client.start_page_token() == "42"


def test_client_changes(http: requests_mock.Mocker, client: DriveClient) -> None:
    http.get(
        f"{API_URL}/changes",
        [
            {
                "json": {
                    "changes": [
                        {"changeType": "file", "fileId": "a", "file": {"id": "a"}},
                        {"changeType": "file", "fileId": "b", "removed": True},
                        {"changeType": "drive", "driveId": "d"},
                    ],
                    "nextPageToken": "11",
                }
            },
            {
                "json": {
                    "changes": [{"fileId": "c", "removed": False}],
                    "newStartPageToken": "12",
                }
            },
        ],
    )

    pages = list(client.changes("10"))

    assert pages == [
        ChangePage([Change("a", DriveFile("a", "", "")), Change("b", None)], "11"),
        ChangePage([Change("c", None)], "12"),
    ]
    assert [query(request)["pageToken"] for request in http.request_history] == [
        "10",
        "11",
    ]
    assert query(http.request_history[0])["includeItemsFromAllDrives"] == "true"


def test_client_download(
    http: requests_mock.Mocker, client: DriveClient, tmp_path: Path
) -> None:
    http.get(f"{API_URL}/files/f1?alt=media&supportsAllDrives=true", content=b"jpeg")

    path = client.download("f1", tmp_path / "photo.jpg")

    assert path == tmp_path / "photo.jpg"
    assert path.read_bytes() == b"jpeg"


def test_client_from_key_file(tmp_path: Path) -> None:
    key_file = write_key(tmp_path / "drive_key.json")

    client = DriveClient.from_key_file(str(key_file))

    assert client.account == ACCOUNT
    assert isinstance(client.session, AuthorizedSession)
    assert tuple(client.session.credentials.scopes) == SCOPES


def test_client_from_missing_key_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        DriveClient.from_key_file(str(tmp_path / "missing.json"))


# -------------------------------------------------------------------- source


def test_settings(fake: FakeDrive) -> None:
    source = DriveSource(fake, [ROOT, "second", ROOT], False, ["JPG", "png"])

    assert source.roots == (ROOT, "second")
    assert source.settings == f"{ROOT},second|0|jpg,png"


def test_photos_recursive(source: DriveSource) -> None:
    folders: set[str] = set()

    photos = list(source.photos(folders))

    assert photos == [
        Photo("a", DRIVE_SOURCE, datetime(2024, 5, 1, 10)),
        Photo("b", DRIVE_SOURCE, datetime(2024, 5, 1, 10)),
        Photo("x", DRIVE_SOURCE, datetime(2024, 5, 1, 10)),
        Photo("z", DRIVE_SOURCE, datetime(2024, 5, 1, 10)),
    ]
    assert folders == {ROOT, "2024", "deep"}


def test_photos_not_recursive(fake: FakeDrive) -> None:
    folders: set[str] = set()

    photos = DriveSource(fake, [ROOT], False, EXTENSIONS).photos(folders)

    assert [photo.id for photo in photos] == ["a", "b"]
    assert folders == {ROOT}


@pytest.fixture
def two_roots(fake: FakeDrive) -> DriveSource:
    fake.files["second"] = DriveFile("second", "Second", FOLDER_TYPE)
    fake.add(
        photo("s1", "second"),
        folder("sub", "second"),
        photo("s2", "sub"),
        folder("nested", "deep"),  # a configured folder inside the first tree
        photo("n1", "nested"),
    )
    return DriveSource(fake, [ROOT, "second", "nested"], True, EXTENSIONS)


def test_photos_of_several_folders(fake: FakeDrive, two_roots: DriveSource) -> None:
    folders: set[str] = set()

    photos = list(two_roots.photos(folders))

    assert [photo.id for photo in photos] == ["a", "b", "n1", "s1", "s2", "x", "z"]
    assert folders == {ROOT, "second", "nested", "2024", "deep", "sub"}
    assert fake.queries[0] == [ROOT, "second", "nested"]


def test_sync_several_folders(
    fake: FakeDrive, two_roots: DriveSource, index: PhotoIndex
) -> None:
    two_roots.sync(index, NOW)
    fake.add(photo("s3", "sub"))
    fake.add(DriveFile("second", "Renamed", FOLDER_TYPE))
    fake.remove("s1")

    result = two_roots.sync(index, NOW + timedelta(hours=1))

    assert result == drive.SyncResult(changes=3, photos=7, full=False)
    assert "s3" in ids(index)
    assert "s1" not in ids(index)


def test_check_folders_reports_the_failing_folder(
    fake: FakeDrive, two_roots: DriveSource
) -> None:
    del fake.files["second"]

    with pytest.raises(DriveError, match="folder second not found"):
        two_roots.check_folders()


def test_photos_lists_folders_in_batches(
    fake: FakeDrive, source: DriveSource, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drive, "FOLDERS_PER_QUERY", 2)
    fake.add(folder("f1"), folder("f2"), folder("f3"))
    # a folder found twice (two parents) and a cycle are listed once
    fake.add(folder("loop", "f1", "f2"), folder(ROOT, "loop"))

    list(source.photos(set()))

    assert fake.queries == [[ROOT], ["2024", "f1"], ["f2", "f3"], ["deep", "loop"]]


def test_check_folders(source: DriveSource) -> None:
    source.check_folders()


def test_check_folders_not_shared(fake: FakeDrive, source: DriveSource) -> None:
    del fake.files[ROOT]

    with pytest.raises(DriveError, match="not found or not shared"):
        source.check_folders()


@pytest.mark.parametrize(
    "error",
    [http_error(HTTPStatus.FORBIDDEN), requests.HTTPError("no response")],
)
def test_check_folders_other_errors(
    source: DriveSource, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fail(file_id: str, fields: str) -> dict[str, Any]:
        raise error

    monkeypatch.setattr(source.drive, "file", fail)

    with pytest.raises(requests.HTTPError) as raised:
        source.check_folders()
    assert raised.value is error


@pytest.mark.parametrize(
    "root",
    [
        DriveFile(ROOT, "photo.jpg", "image/jpeg"),
        DriveFile(ROOT, "Photos", FOLDER_TYPE, trashed=True),
    ],
)
def test_check_folders_not_a_folder(
    fake: FakeDrive, source: DriveSource, root: DriveFile
) -> None:
    fake.files[ROOT] = root

    with pytest.raises(DriveError, match="is not a folder"):
        source.check_folders()


# --------------------------------------------------------------------- sync


def test_first_sync_is_a_full_listing(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex
) -> None:
    result = source.sync(index, NOW)

    assert result == drive.SyncResult(changes=0, photos=4, full=True)
    assert ids(index) == ["a", "b", "x", "z"]
    assert index.source_state(DRIVE_SOURCE) == {
        FOLDER_KEY + ROOT: "",
        FOLDER_KEY + "2024": "",
        FOLDER_KEY + "deep": "",
        SETTINGS_KEY: source.settings,
        FULL_SCAN_KEY: NOW.isoformat(),
        PAGE_TOKEN_KEY: str(len(fake.log)),
    }


def test_sync_without_changes(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex
) -> None:
    source.sync(index, NOW)
    fake.queries.clear()

    result = source.sync(index, NOW + timedelta(hours=1))

    assert result == drive.SyncResult(changes=0, photos=4, full=False)
    assert fake.queries == []
    assert ids(index) == ["a", "b", "x", "z"]


def test_sync_applies_changes(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex
) -> None:
    source.sync(index, NOW)
    fake.queries.clear()
    fake.add(photo("new", "deep", taken="2025:01:01 08:00:00"))
    fake.add(photo("x", "2024", name="x.png", taken="2023:01:01 00:00:00"))
    fake.remove("b")
    fake.add(photo("a", trashed=True))
    fake.add(photo("z", "elsewhere"))  # moved out of the tree
    fake.add(photo("notes", mime_type="text/plain"))  # renamed to notes.jpg
    fake.add(photo("foreign", "other-folder"))  # not in the tree
    fake.add(folder("deep", "2024", name="Deep"))  # renamed folder
    fake.add(folder("other", "other-folder"))  # folder outside the tree

    result = source.sync(index, NOW + timedelta(hours=1))

    assert result == drive.SyncResult(changes=9, photos=3, full=False)
    assert fake.queries == []
    assert ids(index) == ["x", "new", "notes"]
    assert index.next_photo(Selection(), after=None) == Photo(
        "x", DRIVE_SOURCE, datetime(2023, 1, 1)
    )
    assert index.source_state(DRIVE_SOURCE)[PAGE_TOKEN_KEY] == str(len(fake.log))


def test_sync_change_of_a_photo_that_is_no_photo_anymore(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex
) -> None:
    source.sync(index, NOW)
    fake.add(photo("b", name="b.txt", mime_type="text/plain"))

    source.sync(index, NOW + timedelta(hours=1))

    assert ids(index) == ["a", "x", "z"]


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda fake: fake.add(folder("new")), id="folder added"),
        pytest.param(lambda fake: fake.remove("2024"), id="folder removed"),
        pytest.param(
            lambda fake: fake.add(folder("2024", "elsewhere")), id="folder moved out"
        ),
        pytest.param(
            lambda fake: fake.add(folder("2024", trashed=True)), id="folder trashed"
        ),
    ],
)
def test_sync_tree_change_needs_a_full_listing(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex, change: Any
) -> None:
    source.sync(index, NOW)
    fake.add(photo("c"))
    change(fake)
    fake.add(photo("new", "new"))
    fake.queries.clear()

    result = source.sync(index, NOW + timedelta(hours=1))

    assert result.full
    assert result.changes == 1  # "c", before the folder change
    assert fake.queries[0] == [ROOT]
    assert index.source_state(DRIVE_SOURCE)[PAGE_TOKEN_KEY] == str(len(fake.log))
    assert set(ids(index)) == {photo.id for photo in source.photos(set())}


def index_folders(index: PhotoIndex) -> set[str]:
    return {
        key.removeprefix(FOLDER_KEY)
        for key in index.source_state(DRIVE_SOURCE)
        if key.startswith(FOLDER_KEY)
    }


def test_sync_removed_folder_state(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex
) -> None:
    source.sync(index, NOW)
    fake.remove("deep")
    fake.remove("z")

    source.sync(index, NOW + timedelta(hours=1))

    assert index_folders(index) == {ROOT, "2024"}
    assert ids(index) == ["a", "b", "x"]


def test_sync_subfolder_change_when_not_recursive(
    fake: FakeDrive, index: PhotoIndex
) -> None:
    source = DriveSource(fake, [ROOT], False, EXTENSIONS)
    source.sync(index, NOW)
    fake.add(folder("new"))
    fake.add(photo("c"))

    result = source.sync(index, NOW + timedelta(hours=1))

    assert result == drive.SyncResult(changes=2, photos=3, full=False)


def test_sync_root_renamed(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex
) -> None:
    source.sync(index, NOW)
    fake.add(DriveFile(ROOT, "Renamed", FOLDER_TYPE))

    assert not source.sync(index, NOW + timedelta(hours=1)).full


def test_sync_full_listing_after_the_interval(
    source: DriveSource, index: PhotoIndex
) -> None:
    source.sync(index, NOW)
    later = NOW + drive.FULL_SCAN_INTERVAL

    assert not source.sync(index, later - timedelta(seconds=1)).full
    assert source.sync(index, later).full
    assert index.source_state(DRIVE_SOURCE)[FULL_SCAN_KEY] == later.isoformat()


def test_sync_full_listing_after_settings_change(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex
) -> None:
    source.sync(index, NOW)

    result = DriveSource(fake, [ROOT], False, EXTENSIONS).sync(index, NOW)

    assert result == drive.SyncResult(changes=0, photos=2, full=True)
    assert index_folders(index) == {ROOT}


def test_sync_without_token_is_a_full_listing(
    source: DriveSource, index: PhotoIndex
) -> None:
    source.sync(index, NOW)
    index.remove_source_state(DRIVE_SOURCE, [PAGE_TOKEN_KEY])

    assert source.sync(index, NOW + timedelta(hours=1)).full


def test_sync_keeps_photos_and_shown_flags(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex
) -> None:
    source.sync(index, NOW)
    index.mark_shown(Photo("b", DRIVE_SOURCE, datetime(2024, 5, 1, 10)), Selection())

    source.sync(index, NOW + timedelta(days=8))

    assert index.last_shown() == Photo("b", DRIVE_SOURCE, datetime(2024, 5, 1, 10))
    assert index.random_photo(Selection()) != index.last_shown()


def test_sync_failure_keeps_the_index(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex
) -> None:
    source.sync(index, NOW)
    state = index.source_state(DRIVE_SOURCE)
    fake.add(photo("c"))
    fake.add(folder("new"))  # needs a full listing, which fails
    fake.failure = requests.ConnectionError("offline")

    with pytest.raises(requests.ConnectionError):
        source.sync(index, NOW + timedelta(hours=1))

    assert ids(index) == ["a", "b", "x", "z"]
    assert index.source_state(DRIVE_SOURCE) == state


def test_sync_folder_not_shared(
    fake: FakeDrive, source: DriveSource, index: PhotoIndex
) -> None:
    del fake.files[ROOT]

    with pytest.raises(DriveError):
        source.sync(index, NOW)
    assert index.count() == 0


# ----------------------------------------------------------------- download


def test_download(fake: FakeDrive, source: DriveSource, tmp_path: Path) -> None:
    fake.descriptions["x"] = "hotword 3"

    download = source.download(Photo("x", DRIVE_SOURCE, NOW), str(tmp_path), "orig")

    assert download == drive.Download(tmp_path / "orig.png", "hotword 3")
    assert download.path.read_bytes() == b"x"


def test_download_unknown_type_uses_the_name(
    source: DriveSource, tmp_path: Path
) -> None:
    download = source.download(Photo("a", DRIVE_SOURCE, NOW), str(tmp_path), "orig")

    assert download == drive.Download(tmp_path / "orig.jpg", "")
