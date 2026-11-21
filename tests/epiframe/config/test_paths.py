from pathlib import Path

from epiframe.config import paths


def test_default_config_file_exists() -> None:
    assert Path(paths.CONFIG_FILE_DEFAULT).is_file()


def test_paths_are_relative() -> None:
    for path in (paths.CONFIG_FILE, paths.CONFIG_FILE_DEFAULT, paths.USERS_DB_FILE):
        assert not Path(path).is_absolute()
