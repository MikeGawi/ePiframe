import stat
from pathlib import Path

from epiframe.web.secret import KEY_BYTES, secret_key


def test_new_key_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "data" / "secret.key"

    key = secret_key(path)

    assert len(key) == 2 * KEY_BYTES
    assert secret_key(path) == key
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_every_installation_has_its_own_key(tmp_path: Path) -> None:
    assert secret_key(tmp_path / "a.key") != secret_key(tmp_path / "b.key")


def test_empty_file_gets_a_key(tmp_path: Path) -> None:
    path = tmp_path / "secret.key"
    path.write_text("\n")

    assert secret_key(path) == path.read_text().strip() != ""


def test_existing_key(tmp_path: Path) -> None:
    path = tmp_path / "secret.key"
    path.write_text("my-key\n")

    assert secret_key(path) == "my-key"
