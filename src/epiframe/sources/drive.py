"""Google Drive source: photos in a Drive folder shared with a service account.

The frame signs in as a Google Cloud service account (a JSON key file, no
browser consent and no expiring user token) with read-only access. The user
shares the photo folder with the service account's e-mail address.

Only metadata is synchronized into the photo index; the file itself is
downloaded when its photo is picked. Synchronization is incremental: after a
full listing, the Drive Changes API reports what changed since the stored page
token (one request when nothing changed, even for a huge library). The folders
of the tree are kept in the photo index (``source_state``) to tell whether a
changed file belongs to the source.

A full listing is done on the first run, when the source settings change, when
a folder is added to or removed from the tree (its content wouldn't be reported
as changes), and once every ``FULL_SCAN_INTERVAL`` as a safety net.

The id of a Drive photo is its file id; its time is the time the photo was taken
(EXIF, ``imageMediaMetadata.time``) or, without it, the file modification time.
"""

import re
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

from epiframe.core.media_types import TYPE_TO_EXTENSION
from epiframe.core.network import download_file
from epiframe.photos.index import PhotoIndex
from epiframe.photos.model import Photo

DRIVE_SOURCE = "Drive"
FULL_SCAN_INTERVAL = timedelta(days=7)

SCOPES = ("https://www.googleapis.com/auth/drive.readonly",)
API_URL = "https://www.googleapis.com/drive/v3"
FOLDER_TYPE = "application/vnd.google-apps.folder"
TIMEOUT = 60
PAGE_SIZE = 1000
# folders listed with one query ("'a' in parents or 'b' in parents ...")
FOLDERS_PER_QUERY = 50
FILE_FIELDS = "id,name,mimeType,parents,trashed,modifiedTime,imageMediaMetadata(time)"
DOWNLOAD_FIELDS = "name,mimeType,description"
EXIF_TIME_FORMAT = "%Y:%m:%d %H:%M:%S"
# shared drives are supported too
SHARED_DRIVES = {"supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}

# source_state keys: one per folder of the tree, the settings, the last full
# listing and the Changes API page token
FOLDER_KEY = "folder:"
SETTINGS_KEY = "scan:settings"
FULL_SCAN_KEY = "scan:full"
PAGE_TOKEN_KEY = "changes:token"  # noqa: S105 (not a password)

ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{10,}")
# folder links: .../drive/folders/<id>, .../drive/u/0/folders/<id>, ...?id=<id>
LINK_PATTERN = re.compile(r"/folders/([^/?#]+)|[?&]id=([^&#]+)")


def folder_id(value: str) -> str:
    """Return the folder id of a Drive folder id or link; raise ``ValueError``."""
    value = value.strip()
    match = LINK_PATTERN.search(value)
    candidate = (match.group(1) or match.group(2)) if match else value
    if not ID_PATTERN.fullmatch(candidate):
        raise ValueError("Not a Google Drive folder ID or link!")
    return candidate


class DriveError(Exception):
    """The Drive folder can't be used (missing, not shared, not a folder)."""


@dataclass(frozen=True)
class DriveFile:
    """Metadata of a Drive file (``FILE_FIELDS``)."""

    id: str
    name: str
    mime_type: str
    parents: tuple[str, ...] = ()
    trashed: bool = False
    modified: str = ""
    taken: str = ""

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DriveFile":
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            mime_type=data.get("mimeType", ""),
            parents=tuple(data.get("parents", ())),
            trashed=data.get("trashed", False),
            modified=data.get("modifiedTime", ""),
            taken=data.get("imageMediaMetadata", {}).get("time", ""),
        )

    @property
    def is_folder(self) -> bool:
        return self.mime_type == FOLDER_TYPE

    @property
    def extension(self) -> str:
        return self.name.rpartition(".")[2].lower() if "." in self.name else ""

    def created(self) -> datetime:
        """Time the photo was taken (EXIF), else the modification time."""
        try:
            return datetime.strptime(self.taken, EXIF_TIME_FORMAT)
        except ValueError:  # missing or invalid, e.g. "0000:00:00 00:00:00"
            return datetime.fromisoformat(self.modified)


@dataclass(frozen=True)
class Change:
    """A changed file; ``file`` is ``None`` when it was removed or access was lost."""

    file_id: str
    file: DriveFile | None


@dataclass(frozen=True)
class ChangePage:
    changes: list[Change]
    token: str  # page token to continue from


class Drive(Protocol):
    """The Drive API calls used by the source (``DriveClient``)."""

    def file(self, file_id: str, fields: str) -> dict[str, Any]: ...

    def children(self, folder_ids: Sequence[str]) -> Iterator[DriveFile]: ...

    def start_page_token(self) -> str: ...

    def changes(self, token: str) -> Iterator[ChangePage]: ...

    def download(self, file_id: str, destination: Path) -> Path: ...


class DriveClient:
    """Drive API v3 over an (authorized) ``requests`` session."""

    def __init__(self, session: requests.Session, account: str = "") -> None:
        self.session = session
        self.account = account  # service account e-mail, to share the folder with

    @classmethod
    def from_key_file(cls, key_file: str) -> "DriveClient":
        """Client signed in with the service account key file (read-only scope)."""
        credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
            key_file, scopes=SCOPES
        )
        return cls(
            AuthorizedSession(credentials),  # type: ignore[no-untyped-call]
            credentials.service_account_email,
        )

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        response = self.session.get(f"{API_URL}/{path}", params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data

    def file(self, file_id: str, fields: str) -> dict[str, Any]:
        return self._get(
            f"files/{file_id}", {"fields": fields, "supportsAllDrives": "true"}
        )

    def children(self, folder_ids: Sequence[str]) -> Iterator[DriveFile]:
        """Files and folders (not trashed) directly in ``folder_ids``."""
        parents = " or ".join(f"'{folder}' in parents" for folder in folder_ids)
        params = SHARED_DRIVES | {
            "q": f"({parents}) and trashed = false",
            "fields": f"nextPageToken,files({FILE_FIELDS})",
            "orderBy": "name",
            "pageSize": str(PAGE_SIZE),
        }
        while True:
            data = self._get("files", params)
            yield from map(DriveFile.from_json, data.get("files", ()))
            if "nextPageToken" not in data:
                return
            params["pageToken"] = data["nextPageToken"]

    def start_page_token(self) -> str:
        data = self._get("changes/startPageToken", {"supportsAllDrives": "true"})
        return str(data["startPageToken"])

    def changes(self, token: str) -> Iterator[ChangePage]:
        """Changes since ``token``, page by page; the last page has the new token."""
        params = SHARED_DRIVES | {
            "fields": "nextPageToken,newStartPageToken,"
            f"changes(changeType,fileId,removed,file({FILE_FIELDS}))",
            "pageSize": str(PAGE_SIZE),
        }
        while token:
            data = self._get("changes", params | {"pageToken": token})
            token = data.get("nextPageToken", "")
            changes = [
                Change(change["fileId"], self._changed_file(change))
                for change in data.get("changes", ())
                if change.get("changeType", "file") == "file"
            ]
            yield ChangePage(changes, token or data["newStartPageToken"])

    @staticmethod
    def _changed_file(change: dict[str, Any]) -> DriveFile | None:
        if change.get("removed") or "file" not in change:
            return None
        return DriveFile.from_json(change["file"])

    def download(self, file_id: str, destination: Path) -> Path:
        query = urlencode({"alt": "media", "supportsAllDrives": "true"})
        return download_file(
            f"{API_URL}/files/{file_id}?{query}", destination, TIMEOUT, self.session
        )


@dataclass(frozen=True)
class SyncResult:
    changes: int  # changes read from the Changes API
    photos: int  # photos of the source after the synchronization
    full: bool


@dataclass(frozen=True)
class Download:
    path: Path
    description: str  # Drive file description (for the interval hot word)


class DriveSource:
    """Photos with a known image type or one of ``extensions`` in a Drive folder."""

    def __init__(
        self,
        drive: Drive,
        folder: str,
        recursive: bool,
        extensions: Collection[str],
        full_scan_interval: timedelta = FULL_SCAN_INTERVAL,
    ) -> None:
        self.drive = drive
        self.folder = folder
        self.recursive = recursive
        self.extensions = frozenset(extension.lower() for extension in extensions)
        self.full_scan_interval = full_scan_interval

    @property
    def settings(self) -> str:
        """Source settings; a change forces a full listing."""
        extensions = ",".join(sorted(self.extensions))
        return f"{self.folder}|{int(self.recursive)}|{extensions}"

    def _is_photo(self, file: DriveFile) -> bool:
        return file.mime_type in TYPE_TO_EXTENSION or file.extension in self.extensions

    # ----------------------------------------------------------------- listing

    def check_folder(self) -> None:
        """Raise ``DriveError`` if the configured folder can't be used."""
        data = self._folder_metadata()
        if data.get("mimeType") != FOLDER_TYPE or data.get("trashed"):
            raise DriveError(f"Google Drive item {self.folder} is not a folder!")

    def _folder_metadata(self) -> dict[str, Any]:
        try:
            return self.drive.file(self.folder, "mimeType,trashed")
        except requests.HTTPError as error:
            if error.response is None or error.response.status_code != 404:
                raise
            raise DriveError(
                f"Google Drive folder {self.folder} not found or not shared with"
                " the service account!"
            ) from error

    def photos(self, folders: set[str]) -> Iterator[Photo]:
        """All photos of the tree (a full listing), folder level by level.

        The ids of the listed folders are added to ``folders``.
        """
        level = [self.folder]
        while level:
            folders.update(level)
            subfolders: list[str] = []
            yield from self._photos(self._children(level), subfolders)
            # each folder once, in found order (a folder can have many parents)
            level = list(dict.fromkeys(f for f in subfolders if f not in folders))

    def _children(self, folders: list[str]) -> Iterator[DriveFile]:
        for start in range(0, len(folders), FOLDERS_PER_QUERY):
            yield from self.drive.children(folders[start : start + FOLDERS_PER_QUERY])

    def _photos(
        self, files: Iterator[DriveFile], subfolders: list[str]
    ) -> Iterator[Photo]:
        for file in files:
            if file.is_folder:
                if self.recursive:
                    subfolders.append(file.id)
            elif self._is_photo(file):
                yield Photo(file.id, DRIVE_SOURCE, file.created())

    # -------------------------------------------------------------------- index

    def sync(self, index: PhotoIndex, now: datetime | None = None) -> SyncResult:
        """Bring the photos of this source in ``index`` up to date.

        Everything is written in one transaction: when Drive can't be reached
        midway, the index keeps its previous content.
        """
        now = now or datetime.now()
        state = index.source_state(DRIVE_SOURCE)
        changes = 0
        full = self._needs_full_scan(state, now)
        with index.batch():
            if not full:
                changes, full = self._apply_changes(index, state)
            if full:
                self._full_scan(index, state, now)
        return SyncResult(changes, index.count_source(DRIVE_SOURCE), full)

    def _needs_full_scan(self, state: dict[str, str], now: datetime) -> bool:
        last = state.get(FULL_SCAN_KEY)
        return (
            state.get(SETTINGS_KEY) != self.settings
            or PAGE_TOKEN_KEY not in state
            or last is None
            or now - datetime.fromisoformat(last) >= self.full_scan_interval
        )

    def _full_scan(
        self, index: PhotoIndex, state: dict[str, str], now: datetime
    ) -> None:
        self.check_folder()
        # taken before the listing, so changes made during it are not missed
        token = self.drive.start_page_token()
        folders: set[str] = set()
        index.replace_source(DRIVE_SOURCE, self.photos(folders))
        stale = self._folders(state) - folders
        index.remove_source_state(DRIVE_SOURCE, (FOLDER_KEY + key for key in stale))
        index.set_source_state(
            DRIVE_SOURCE,
            dict.fromkeys((FOLDER_KEY + folder for folder in folders), "")
            | {
                SETTINGS_KEY: self.settings,
                FULL_SCAN_KEY: now.isoformat(),
                PAGE_TOKEN_KEY: token,
            },
        )

    def _apply_changes(
        self, index: PhotoIndex, state: dict[str, str]
    ) -> tuple[int, bool]:
        """Apply the changes since the stored token; ``True`` = full listing needed."""
        folders = self._folders(state)
        count = 0
        for page in self.drive.changes(state[PAGE_TOKEN_KEY]):
            for change in page.changes:
                if self._tree_changed(change, folders):
                    return count, True
                self._apply(index, change, folders)
                count += 1
            index.set_source_state(DRIVE_SOURCE, {PAGE_TOKEN_KEY: page.token})
        return count, False

    @staticmethod
    def _folders(state: dict[str, str]) -> set[str]:
        """Folders of the tree stored in the source state."""
        return {
            key.removeprefix(FOLDER_KEY) for key in state if key.startswith(FOLDER_KEY)
        }

    def _tree_changed(self, change: Change, folders: set[str]) -> bool:
        """A folder was added to or removed from the tree."""
        file = change.file
        if file is not None and not file.is_folder:
            return False
        return self._in_tree(file, folders) != (change.file_id in folders)

    def _in_tree(self, folder: DriveFile | None, folders: set[str]) -> bool:
        if folder is None or folder.trashed:
            return False
        return folder.id == self.folder or (
            self.recursive and not folders.isdisjoint(folder.parents)
        )

    def _apply(self, index: PhotoIndex, change: Change, folders: set[str]) -> None:
        file = change.file
        if file is not None and file.is_folder:
            return  # renamed or moved inside the tree
        if file is not None and self._wanted(file, folders):
            index.add_photos([Photo(file.id, DRIVE_SOURCE, file.created())])
        else:  # gone, trashed, moved out of the tree or not a photo anymore
            index.remove_photos(DRIVE_SOURCE, [change.file_id])

    def _wanted(self, file: DriveFile, folders: set[str]) -> bool:
        return (
            not file.trashed
            and self._is_photo(file)
            and not folders.isdisjoint(file.parents)
        )

    # ----------------------------------------------------------------- download

    def download(self, photo: Photo, directory: str, name: str) -> Download:
        """Download ``photo`` as ``<directory>/<name>.<extension>``."""
        data = self.drive.file(photo.id, DOWNLOAD_FIELDS)
        file = DriveFile.from_json({"id": photo.id} | data)
        extension = TYPE_TO_EXTENSION.get(file.mime_type) or file.extension
        path = self.drive.download(photo.id, Path(directory) / f"{name}.{extension}")
        return Download(path, data.get("description", ""))
