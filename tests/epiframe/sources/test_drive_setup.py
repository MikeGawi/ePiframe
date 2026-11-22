import json
import stat
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
import requests
from google.auth import exceptions as auth_exceptions

from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.sources.drive import FOLDER_TYPE, DriveFile
from epiframe.sources.drive_setup import (
    PRIVATE_KEY_START,
    SHARE_STEP,
    STEPS,
    FolderCheck,
    KeyFileError,
    ServiceAccountKey,
    SetupReport,
    check,
    explain,
    read_key,
    save_config,
    save_key,
)
from tests.helpers.fake_drive import ROOT, FakeDrive, folder, http_error, photo
from tests.helpers.service_account import ACCOUNT, write_key

KEY = ServiceAccountKey(ACCOUNT, "project")
DISABLED = json.dumps(
    {"error": {"code": 403, "errors": [{"reason": "accessNotConfigured"}]}}
)


def key_data(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": "service_account",
        "project_id": "project",
        "private_key": f"{PRIVATE_KEY_START}\nabc\n",
        "client_email": ACCOUNT,
    }
    return {
        name: value for name, value in (data | changes).items() if value is not None
    }


@pytest.fixture
def fake() -> FakeDrive:
    fake = FakeDrive()
    fake.files[ROOT] = DriveFile(ROOT, "Photos", FOLDER_TYPE)
    fake.files["second"] = DriveFile("second", "Second", FOLDER_TYPE)
    fake.add(
        photo("a"),
        photo("raw", name="raw.cr2", mime_type="application/octet-stream"),
        DriveFile("notes", "notes.txt", "text/plain", (ROOT,)),
        folder("2024"),
        photo("x", "2024"),
        photo("s", "second"),
    )
    return fake


def test_steps() -> None:
    assert [step.title for step in STEPS] == [
        "Create a Google Cloud project",
        "Enable the Google Drive API",
        "Create a service account",
        "Create a key",
    ]
    assert "{account}" in SHARE_STEP.text


# ---------------------------------------------------------------------- key


def test_parse_key() -> None:
    assert ServiceAccountKey.parse(json.dumps(key_data())) == KEY
    assert ServiceAccountKey.parse(json.dumps(key_data(project_id=None))) == (
        ServiceAccountKey(ACCOUNT, "")
    )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("not json", "not JSON"),
        ("[1, 2]", "not a JSON object"),
        (json.dumps({"installed": {"client_id": "x"}}), "OAuth client file"),
        (json.dumps({"web": {"client_id": "x"}}), "OAuth client file"),
        (json.dumps(key_data(type="authorized_user")), "not a Google service account"),
        (json.dumps(key_data(private_key=None)), "no private key"),
        (json.dumps(key_data(private_key="secret")), "no private key"),
        (json.dumps(key_data(client_email="")), "no service account e-mail"),
    ],
)
def test_parse_invalid_key(content: str, message: str) -> None:
    with pytest.raises(KeyFileError, match=message):
        ServiceAccountKey.parse(content)


def test_read_key(tmp_path: Path) -> None:
    path = write_key(tmp_path / "key.json")

    assert read_key(path) == ServiceAccountKey(ACCOUNT, "project")
    with pytest.raises(FileNotFoundError):
        read_key(tmp_path / "missing.json")


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_save_key(tmp_path: Path) -> None:
    path = tmp_path / "drive_key.json"
    content = json.dumps(key_data())

    assert save_key(content, path) == KEY

    assert path.read_text() == content
    assert mode(path) == 0o600
    assert not (tmp_path / "drive_key.json.back").exists()


def test_save_key_keeps_the_previous_key(tmp_path: Path) -> None:
    path = tmp_path / "drive_key.json"
    path.write_text("old key")
    path.chmod(0o666)

    save_key(json.dumps(key_data()), path)
    save_key(json.dumps(key_data()), path)  # the same key: no new backup

    backup = tmp_path / "drive_key.json.back"
    assert backup.read_text() == "old key"
    assert mode(backup) == 0o600
    assert mode(path) == 0o600


def test_save_invalid_key(tmp_path: Path) -> None:
    path = tmp_path / "drive_key.json"
    path.write_text("old key")

    with pytest.raises(KeyFileError):
        save_key("{}", path)
    assert path.read_text() == "old key"


def test_save_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)

    save_config(config, "keys/drive.json", ["id1", "id2"])

    saved = ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)
    assert saved.get("use_drive") == "1"
    assert saved.get("drive_folders") == "id1,id2"
    assert saved.get("drive_key_file") == "keys/drive.json"


# ------------------------------------------------------------------ explain


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            auth_exceptions.RefreshError("invalid_grant"),  # type: ignore[no-untyped-call]
            "Google rejected the key of",
        ),
        (
            auth_exceptions.TransportError("dns"),  # type: ignore[no-untyped-call]
            "No connection to Google",
        ),
        (requests.ConnectionError("refused"), "No connection to Google"),
        (requests.ReadTimeout("slow"), "No connection to Google"),
        (
            http_error(HTTPStatus.FORBIDDEN, DISABLED),
            "Google Drive API is disabled in project project: enable it at "
            "https://console.cloud.google.com/apis/library/drive.googleapis.com"
            "?project=project",
        ),
        (http_error(HTTPStatus.FORBIDDEN, "SERVICE_DISABLED"), "API is disabled"),
        (http_error(HTTPStatus.FORBIDDEN, "rate limit"), "403 error"),
        (requests.HTTPError("no response"), "no response"),
        (ValueError("other"), "other"),
    ],
)
def test_explain(error: Exception, message: str) -> None:
    assert message in explain(error, KEY)


# -------------------------------------------------------------------- check


def test_report_ok() -> None:
    assert SetupReport(ACCOUNT).ok
    assert SetupReport(ACCOUNT, (FolderCheck("a"),)).ok
    assert not SetupReport(ACCOUNT, (FolderCheck("a", problem="x"),)).ok
    assert not SetupReport(ACCOUNT, problem="x").ok


def test_check(fake: FakeDrive) -> None:
    report = check(fake, [ROOT, "second"], KEY)

    assert report == SetupReport(
        ACCOUNT,
        (
            FolderCheck(ROOT, "Photos", photos=2, subfolders=1),
            FolderCheck("second", "Second", photos=1),
        ),
    )
    assert report.ok
    assert fake.queries == [[ROOT], ["second"]]


def test_check_folder_problems(fake: FakeDrive) -> None:
    fake.files["trashed"] = DriveFile("trashed", "Old", FOLDER_TYPE, trashed=True)

    report = check(fake, ["missing", "a", "trashed", ROOT], KEY)

    assert report.folders == (
        FolderCheck(
            "missing",
            problem=f"Not found or not shared: share it with {ACCOUNT} as Viewer.",
        ),
        FolderCheck("a", "a.jpg", problem="Not a folder (or in the trash)."),
        FolderCheck("trashed", "Old", problem="Not a folder (or in the trash)."),
        FolderCheck(ROOT, "Photos", photos=2, subfolders=1),
    )
    assert not report.problem
    assert not report.ok


def test_check_stops_on_a_general_problem(fake: FakeDrive) -> None:
    fake.errors["second"] = http_error(HTTPStatus.FORBIDDEN, DISABLED)

    report = check(fake, [ROOT, "second", "third"], KEY)

    assert report.folders == (FolderCheck(ROOT, "Photos", photos=2, subfolders=1),)
    assert "API is disabled" in report.problem
    assert not report.ok


def test_check_listing_failure(fake: FakeDrive) -> None:
    fake.failure = requests.ConnectionError("offline")

    report = check(fake, [ROOT], KEY)

    assert report.folders == ()
    assert report.problem.startswith("No connection to Google")
