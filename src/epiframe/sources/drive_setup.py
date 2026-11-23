"""Google Drive source setup: the steps, the key file and a check of the access.

Shared by the console setup (``ePiframe.py --setup-drive``), the WebUI wizard
and the installer. Replaces the 1.x ``activate.py`` (Google Photos OAuth); a
service account needs no consent screen and no token, only a key file and the
photo folders shared with its e-mail address.
"""

import json
import os
import shutil
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

import requests
from google.auth import exceptions as auth_exceptions

from epiframe.config.base import ConfigBase
from epiframe.core.files import write_text_atomic
from epiframe.core.media_types import EXTENSIONS
from epiframe.sources.drive import FOLDER_TYPE, Drive, is_photo

ENABLE_API_URL = "https://console.cloud.google.com/apis/library/drive.googleapis.com"
KEY_MODE = 0o600
# split, so the detect-private-key hook does not take this line for a key
PRIVATE_KEY_START = "-----BEGIN " + "PRIVATE KEY-----"
# a 403 answer with one of these: the Drive API is disabled in the project
API_DISABLED = ("accessNotConfigured", "SERVICE_DISABLED")
# errors raised before an answer from Google
CONNECTION_ERRORS = (
    auth_exceptions.TransportError,
    requests.ConnectionError,
    requests.Timeout,
)


@dataclass(frozen=True)
class Step:
    title: str
    text: str
    link: str = ""


STEPS = (
    Step(
        "Create a Google Cloud project",
        "Sign in to the Google Cloud console with any Google account and create a"
        " project, e.g. named ePiframe (no billing is needed). Then select it in the"
        " project picker at the top.",
        "https://console.cloud.google.com/projectcreate",
    ),
    Step(
        "Enable the Google Drive API",
        "With the ePiframe project selected, click Enable.",
        ENABLE_API_URL,
    ),
    Step(
        "Create a service account",
        "Click Create service account, name it e.g. epiframe and click Create and"
        " continue. Skip the roles (none are needed) and click Done.",
        "https://console.cloud.google.com/iam-admin/serviceaccounts",
    ),
    Step(
        "Create a key",
        "Open the service account, go to Keys, Add key, Create new key, choose JSON"
        " and click Create: the key file is downloaded. Keep it private, anyone with"
        " it can read the folders shared with the account. If creating keys is"
        " blocked, the account belongs to a Google Workspace organization that"
        " forbids it: use a personal Google account.",
    ),
)

SHARE_STEP = Step(
    "Share the photo folders",
    "In Google Drive share each photo folder with {account} as Viewer (untick"
    " Notify people). Then copy the folder link (Share, Copy link).",
    "https://drive.google.com/",
)


class KeyFileError(ValueError):
    """The content is not a Google service account key."""


@dataclass(frozen=True)
class ServiceAccountKey:
    account: str  # client_email: the folders are shared with it
    project: str

    @classmethod
    def parse(cls, content: str) -> Self:
        """Validate a service account key (JSON); raise ``KeyFileError``."""
        data = cls._load(content)
        cls._check_type(data)
        if not str(data.get("private_key", "")).startswith(PRIVATE_KEY_START):
            raise KeyFileError("The key file has no private key!")
        if not data.get("client_email"):
            raise KeyFileError("The key file has no service account e-mail!")
        return cls(data["client_email"], data.get("project_id", ""))

    @staticmethod
    def _load(content: str) -> dict[str, Any]:
        try:
            data = json.loads(content)
        except ValueError:
            raise KeyFileError("The key file is not JSON!") from None
        if not isinstance(data, dict):
            raise KeyFileError("The key file is not a JSON object!")
        return data

    @staticmethod
    def _check_type(data: dict[str, Any]) -> None:
        if "installed" in data or "web" in data:
            raise KeyFileError(
                "This is an OAuth client file (like the 1.x credentials.json), not a"
                " service account key!"
            )
        if data.get("type") != "service_account":
            raise KeyFileError("This is not a Google service account key file!")


def read_key(path: str | os.PathLike[str]) -> ServiceAccountKey:
    """The key stored at ``path``; raises ``OSError`` or ``KeyFileError``."""
    return ServiceAccountKey.parse(Path(path).read_text())


def save_key(content: str, path: str | os.PathLike[str]) -> ServiceAccountKey:
    """Validate ``content`` and store it at ``path``, readable only by the owner.

    A different existing key is kept as ``<path>.back``.
    """
    key = ServiceAccountKey.parse(content)
    target = Path(path)
    if target.exists() and target.read_text() != content:
        backup = target.with_name(target.name + ".back")
        shutil.copyfile(target, backup)
        os.chmod(backup, KEY_MODE)
    write_text_atomic(target, content)
    os.chmod(target, KEY_MODE)
    return key


def save_config(config: ConfigBase, key_file: str, folders: Sequence[str]) -> None:
    """Enable the Drive source with ``folders`` and ``key_file`` and save."""
    config.set("use_drive", "1")
    config.set("drive_folders", ",".join(folders))
    config.set("drive_key_file", key_file)
    config.save()


@dataclass(frozen=True)
class FolderCheck:
    folder: str
    name: str = ""
    photos: int = 0  # directly in the folder
    subfolders: int = 0
    problem: str = ""


@dataclass(frozen=True)
class SetupReport:
    account: str
    folders: tuple[FolderCheck, ...] = field(default=())
    problem: str = ""  # stops the whole check (key, API, network)

    @property
    def ok(self) -> bool:
        return not self.problem and not any(item.problem for item in self.folders)


def explain(error: Exception, key: ServiceAccountKey) -> str:
    """A hint for an error of the Drive access."""
    if isinstance(error, auth_exceptions.RefreshError):
        return (
            f"Google rejected the key of {key.account} ({error}). The key or the"
            " service account may have been deleted: create a new key."
        )
    if isinstance(error, CONNECTION_ERRORS):
        return f"No connection to Google, check the network ({error})."
    if isinstance(error, requests.HTTPError) and _api_disabled(error):
        return (
            f"The Google Drive API is disabled in project {key.project}: enable it at"
            f" {ENABLE_API_URL}?project={key.project} and try again in a few minutes."
        )
    return str(error)


def _api_disabled(error: requests.HTTPError) -> bool:
    text = error.response.text if error.response is not None else ""
    return any(marker in text for marker in API_DISABLED)


def _status(error: requests.HTTPError) -> int | None:
    return error.response.status_code if error.response is not None else None


def check(
    drive: Drive,
    folders: Sequence[str],
    key: ServiceAccountKey,
    extensions: Collection[str] = EXTENSIONS,
) -> SetupReport:
    """Check that every folder can be read and count what is directly in it."""
    results: list[FolderCheck] = []
    try:
        for folder in folders:
            results.append(_check_folder(drive, folder, key, extensions))
    except Exception as error:  # every failure is reported
        return SetupReport(key.account, tuple(results), explain(error, key))
    return SetupReport(key.account, tuple(results))


def _check_folder(
    drive: Drive, folder: str, key: ServiceAccountKey, extensions: Collection[str]
) -> FolderCheck:
    data = _folder_data(drive, folder)
    if data is None:
        return FolderCheck(
            folder,
            problem=f"Not found or not shared: share it with {key.account} as Viewer.",
        )
    name = data.get("name", "")
    if data.get("mimeType") != FOLDER_TYPE or data.get("trashed"):
        return FolderCheck(folder, name, problem="Not a folder (or in the trash).")
    return FolderCheck(folder, name, *_count(drive, folder, extensions))


def _folder_data(drive: Drive, folder: str) -> dict[str, Any] | None:
    """Metadata of ``folder``; ``None`` if it is not found (or not shared)."""
    try:
        return drive.file(folder, "name,mimeType,trashed")
    except requests.HTTPError as error:
        if _status(error) != 404:
            raise
        return None


def _count(drive: Drive, folder: str, extensions: Collection[str]) -> tuple[int, int]:
    """Photos and subfolders directly in ``folder``."""
    photos = subfolders = 0
    for file in drive.children([folder]):
        subfolders += file.is_folder
        photos += not file.is_folder and is_photo(file, extensions)
    return photos, subfolders
