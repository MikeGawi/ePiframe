"""In-memory Google Drive for tests of the Drive source and its setup."""

from collections.abc import Iterator, Sequence
from http import HTTPStatus
from pathlib import Path
from typing import Any

import requests

from epiframe.sources.drive import FOLDER_TYPE, Change, ChangePage, DriveFile
from tests.helpers.service_account import ACCOUNT

ROOT = "root-folder-0001"
TAKEN = "2024:05:01 10:00:00"


def folder(file_id: str, *parents: str, **fields: Any) -> DriveFile:
    name = fields.pop("name", file_id)
    return DriveFile(file_id, name, FOLDER_TYPE, parents or (ROOT,), **fields)


def photo(file_id: str, parent: str = ROOT, name: str = "", **fields: Any) -> DriveFile:
    fields = {"mime_type": "image/jpeg", "taken": TAKEN} | fields
    return DriveFile(file_id, name or f"{file_id}.jpg", parents=(parent,), **fields)


def http_error(status: int, body: str = "") -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    response._content = body.encode()
    return requests.HTTPError(f"{status} error", response=response)


class FakeDrive:
    """In-memory Drive: files, a change log (token = position) and downloads."""

    def __init__(self) -> None:
        self.files: dict[str, DriveFile] = {}
        self.descriptions: dict[str, str] = {}
        self.log: list[Change] = []
        self.queries: list[list[str]] = []
        self.page_size = 2
        self.account = ACCOUNT
        self.failure: Exception | None = None  # of children()
        self.errors: dict[str, Exception] = {}  # of file(), by file id

    def add(self, *files: DriveFile) -> None:
        for file in files:
            self.files[file.id] = file
            self.log.append(Change(file.id, file))

    def remove(self, file_id: str) -> None:
        del self.files[file_id]
        self.log.append(Change(file_id, None))

    def file(self, file_id: str, fields: str) -> dict[str, Any]:
        if file_id in self.errors:
            raise self.errors[file_id]
        if file_id not in self.files:
            raise http_error(HTTPStatus.NOT_FOUND)
        file = self.files[file_id]
        return {
            "name": file.name,
            "mimeType": file.mime_type,
            "trashed": file.trashed,
            "description": self.descriptions.get(file_id, ""),
        }

    def children(self, folder_ids: Sequence[str]) -> Iterator[DriveFile]:
        self.queries.append(list(folder_ids))
        if self.failure:
            raise self.failure
        files = (
            file
            for file in self.files.values()
            if not file.trashed and set(file.parents) & set(folder_ids)
        )
        return iter(sorted(files, key=lambda file: file.name))

    def start_page_token(self) -> str:
        return str(len(self.log))

    def changes(self, token: str) -> Iterator[ChangePage]:
        start = int(token)
        while True:
            changes = self.log[start : start + self.page_size]
            start += len(changes)
            yield ChangePage(changes, str(start))
            if start >= len(self.log):
                return

    def download(self, file_id: str, destination: Path) -> Path:
        destination.write_bytes(file_id.encode())
        return destination
