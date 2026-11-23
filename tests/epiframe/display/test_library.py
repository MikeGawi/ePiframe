import sys
from pathlib import Path

import pytest

from epiframe.config import paths
from epiframe.display.base import DisplayError
from epiframe.display.library import load_driver


def test_load_driver_from_library_folder(library: Path) -> None:
    module = load_driver("waveshare_epd", "epdfake", library)

    assert module.__name__ == "waveshare_epd.epdfake"
    assert sys.path[-1] == str(library)


def test_library_folder_added_once(library: Path) -> None:
    load_driver("waveshare_epd", "epdfake", library)
    load_driver("inky", "what", library)

    assert sys.path.count(str(library)) == 1


def test_default_library_folder(library: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "LIBRARY_DIR", str(library))

    assert load_driver("inky", "phat").__name__ == "inky.phat"


@pytest.mark.usefixtures("library")
def test_missing_driver(library: Path) -> None:
    with pytest.raises(DisplayError, match=r"waveshare_epd\.epd_missing .*lib\)"):
        load_driver("waveshare_epd", "epd_missing", library)


@pytest.mark.parametrize("name", ["", "..os", "epd7in5_V2.x", "a/b"])
def test_invalid_name(name: str, library: Path) -> None:
    with pytest.raises(DisplayError, match="Invalid display name"):
        load_driver("waveshare_epd", name, library)
