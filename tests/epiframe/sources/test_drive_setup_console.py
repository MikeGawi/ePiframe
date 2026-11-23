import json
import stat
from pathlib import Path

import pytest

from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.sources import drive_setup_console
from epiframe.sources.drive import FOLDER_TYPE, Drive, DriveFile
from epiframe.sources.drive_setup import STEPS
from epiframe.sources.drive_setup_console import ConsoleSetup
from tests.helpers.console import Answer, Console
from tests.helpers.fake_drive import ROOT, FakeDrive, folder, photo
from tests.helpers.service_account import ACCOUNT, write_key

LINK = f"https://drive.google.com/drive/folders/{ROOT}?usp=sharing"


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigManager:
    monkeypatch.chdir(tmp_path)
    return ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)


@pytest.fixture
def fake() -> FakeDrive:
    fake = FakeDrive()
    fake.files[ROOT] = DriveFile(ROOT, "Photos", FOLDER_TYPE)
    fake.add(photo("a"), photo("b"), folder("2024"))
    return fake


@pytest.fixture
def downloaded(tmp_path: Path) -> Path:
    (tmp_path / "Downloads").mkdir()
    return write_key(tmp_path / "Downloads" / "project-123.json")


def run(
    config: ConfigManager, fake: FakeDrive, *answers: Answer
) -> tuple[int, Console]:
    console = Console(*answers)
    connected: list[str] = []

    def connect(key_file: str) -> Drive:
        connected.append(key_file)
        return fake

    code = ConsoleSetup(config, console.ask, console.say, connect).run()
    assert set(connected) <= {"drive_key.json"}
    return code, console


def saved(tmp_path: Path) -> ConfigManager:
    return ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)


def test_setup(
    config: ConfigManager, fake: FakeDrive, downloaded: Path, tmp_path: Path
) -> None:
    code, console = run(config, fake, "n", str(downloaded), LINK)

    assert code == 0
    key = tmp_path / "drive_key.json"
    assert key.read_text() == downloaded.read_text()
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    result = saved(tmp_path)
    assert result.get("use_drive") == "1"
    assert result.get("drive_folders") == ROOT
    assert result.get("drive_key_file") == "drive_key.json"
    assert f"Key of {ACCOUNT} saved to drive_key.json" in console.output
    assert f"share each photo folder with {ACCOUNT} as Viewer" in console.output
    assert (
        f"[OK] Photos ({ROOT}): 2 photos and 1 subfolders directly in it"
        in console.output
    )
    assert "Google Drive source enabled" in console.output


def test_setup_shows_the_steps(
    config: ConfigManager, fake: FakeDrive, downloaded: Path
) -> None:
    code, console = run(config, fake, "", "", "", "", "", str(downloaded), ROOT)

    assert code == 0
    for number, step in enumerate(STEPS, 1):
        assert f"\n{number}. {step.title}\n   {step.text}" in console.lines
        if step.link:
            assert f"   {step.link}" in console.lines
    assert f"\n{len(STEPS) + 1}. Share the photo folders" in console.output
    assert console.prompts.count("   Press Enter when done...") == len(STEPS)


def test_setup_with_the_existing_key(
    config: ConfigManager, fake: FakeDrive, tmp_path: Path
) -> None:
    write_key(tmp_path / "drive_key.json")

    code, console = run(config, fake, "n", "", "", f" {ROOT} ")

    assert code == 0
    assert f"Use the key in drive_key.json ({ACCOUNT})? [Y/n] " in console.prompts
    assert "Error: No Google Drive folder ID or link!" in console.lines


def test_setup_replaces_the_existing_key(
    config: ConfigManager, fake: FakeDrive, downloaded: Path, tmp_path: Path
) -> None:
    write_key(tmp_path / "drive_key.json", "old@project.iam.gserviceaccount.com")

    code, _ = run(config, fake, "n", "no", str(downloaded), ROOT)

    assert code == 0
    assert (tmp_path / "drive_key.json").read_text() == downloaded.read_text()
    assert (tmp_path / "drive_key.json.back").exists()


def test_setup_keeps_the_current_folders(
    config: ConfigManager, fake: FakeDrive, downloaded: Path, tmp_path: Path
) -> None:
    config.set("drive_folders", ROOT)

    code, console = run(config, fake, "n", str(downloaded), "")

    assert code == 0
    assert f"\nFolder links or IDs, comma separated [{ROOT}]: " in console.prompts
    assert saved(tmp_path).get("drive_folders") == ROOT


def test_setup_with_a_pasted_key(
    config: ConfigManager, fake: FakeDrive, downloaded: Path, tmp_path: Path
) -> None:
    lines = json.dumps(json.loads(downloaded.read_text()), indent=2).splitlines()

    code, _ = run(config, fake, "n", *lines, ROOT)

    assert code == 0
    assert json.loads((tmp_path / "drive_key.json").read_text()) == json.loads(
        downloaded.read_text()
    )


def test_setup_key_errors(
    config: ConfigManager,
    fake: FakeDrive,
    downloaded: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(drive_setup_console, "MAX_PASTED_LINES", 3)

    code, console = run(
        config,
        fake,
        "maybe",  # not an answer: asked again
        "n",
        str(tmp_path / "missing.json"),
        '{"installed": {}}',
        "{",
        '"a": 1,',
        '"b": 2,',  # 3 lines, still no JSON: given up
        str(downloaded),
        ROOT,
    )

    assert code == 0
    errors = [line for line in console.lines if line.startswith("Error: ")]
    assert len(errors) == 3
    assert "No such file or directory" in errors[0]
    assert "OAuth client file" in errors[1]
    assert errors[2] == "Error: The key file is not JSON!"
    assert console.prompts.count("") == 2


def test_setup_check_again(
    config: ConfigManager, fake: FakeDrive, downloaded: Path
) -> None:
    root = fake.files.pop(ROOT)

    def share() -> str:
        fake.files[ROOT] = root
        return ""

    code, console = run(config, fake, "n", str(downloaded), ROOT, share)

    assert code == 0
    assert f"  [!!] {ROOT}: Not found or not shared" in console.output
    assert console.output.count("Checking the access...") == 2


def test_setup_not_saved(
    config: ConfigManager, fake: FakeDrive, downloaded: Path, tmp_path: Path
) -> None:
    del fake.files[ROOT]
    before = (tmp_path / "config.cfg").read_text()

    code, console = run(config, fake, "n", str(downloaded), ROOT, "n", "")

    assert code == 1
    assert "Settings not saved." in console.lines
    assert (tmp_path / "config.cfg").read_text() == before


def test_setup_saved_anyway(
    config: ConfigManager, fake: FakeDrive, downloaded: Path, tmp_path: Path
) -> None:
    fake.failure = ConnectionError("offline")

    code, console = run(config, fake, "n", str(downloaded), ROOT, "n", "y")

    assert code == 0
    assert "  [!!] offline" in console.lines
    assert saved(tmp_path).get("use_drive") == "1"


def test_setup_connection_failure(
    config: ConfigManager, downloaded: Path, tmp_path: Path
) -> None:
    console = Console("n", str(downloaded), ROOT, "n", "n")

    def connect(key_file: str) -> Drive:
        raise ValueError("Could not deserialize key data")

    code = ConsoleSetup(config, console.ask, console.say, connect).run()

    assert code == 1
    assert "  [!!] Could not deserialize key data" in console.lines


@pytest.mark.parametrize("stop", [KeyboardInterrupt(), EOFError()])
def test_setup_stopped(
    config: ConfigManager, fake: FakeDrive, stop: BaseException
) -> None:
    code, console = run(config, fake, "n", stop)

    assert code == 1
    assert console.lines[-1] == "\nSetup stopped, settings not saved."
