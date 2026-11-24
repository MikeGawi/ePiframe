"""Loading of the vendor display drivers (Waveshare, Pimoroni)."""

import importlib
import sys
from pathlib import Path
from types import ModuleType

from epiframe.config import paths
from epiframe.display.base import DisplayError


def load_driver(
    package: str, name: str, directory: Path | str | None = None
) -> ModuleType:
    """Import ``<package>.<name>`` (e.g. ``waveshare_epd.epd7in5_V2``).

    The vendor libraries are copied by the installer into ``directory`` (default
    ``paths.LIBRARY_DIR``); installed packages of the same name are found too.
    """
    if not name.isidentifier():
        raise DisplayError(f"Invalid display name {name!r}!")
    folder = str(directory if directory is not None else paths.LIBRARY_DIR)
    if folder not in sys.path:
        sys.path.append(folder)
    try:
        return importlib.import_module(f"{package}.{name}")
    except ImportError as error:
        raise DisplayError(
            f"Can't load the display driver {package}.{name} (library folder"
            f" {folder}): {error}"
        ) from error
