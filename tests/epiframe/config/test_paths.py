import importlib
from collections.abc import Iterator
from pathlib import Path

import pytest

from epiframe.config import paths


@pytest.fixture
def reload_paths(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reload the module after the test, so the other tests see the defaults."""
    yield
    monkeypatch.undo()
    importlib.reload(paths)


def test_default_config_file_is_package_data() -> None:
    default = Path(paths.CONFIG_FILE_DEFAULT)
    assert default.is_file()
    assert default.parent == Path(paths.__file__).parent


@pytest.mark.usefixtures("reload_paths")
@pytest.mark.parametrize("value", [None, ""])
def test_legacy_layout_without_variables(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    for variable in (
        paths.CONFIG_DIR_ENV,
        paths.DATA_DIR_ENV,
        paths.LIBRARY_DIR_ENV,
        paths.PLUGINS_DIR_ENV,
    ):
        if value is None:
            monkeypatch.delenv(variable, raising=False)
        else:
            monkeypatch.setenv(variable, value)
    importlib.reload(paths)

    assert paths.CONFIG_FILE == "config.cfg"
    assert paths.USERS_DB_FILE == "misc/users.db"
    # lib/ of the ePiframe directory, wherever the process runs
    assert str(Path(__file__).resolve().parents[3] / "lib") == paths.LIBRARY_DIR


@pytest.mark.usefixtures("reload_paths")
def test_directories_from_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, "/etc/epiframe")
    monkeypatch.setenv(paths.DATA_DIR_ENV, "/var/lib/epiframe")
    monkeypatch.setenv(paths.LIBRARY_DIR_ENV, "/opt/epiframe/lib")
    monkeypatch.setenv(paths.PLUGINS_DIR_ENV, "/var/lib/epiframe/plugins")
    importlib.reload(paths)

    assert paths.CONFIG_FILE == "/etc/epiframe/config.cfg"
    assert paths.USERS_DB_FILE == "/var/lib/epiframe/users.db"
    assert paths.LIBRARY_DIR == "/opt/epiframe/lib"
    assert paths.PLUGINS_DIR == "/var/lib/epiframe/plugins"
