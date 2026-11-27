"""Locations of the configuration and data files.

The directories can be set with environment variables (the DEB package uses the
FHS layout: ``EPIFRAME_CONFIG_DIR=/etc/epiframe``,
``EPIFRAME_DATA_DIR=/var/lib/epiframe``,
``EPIFRAME_PLUGINS_DIR=/var/lib/epiframe/plugins``, see ``packaging/deb``).
Without them the 1.x layout is used: ``config.cfg`` in the ePiframe directory,
``misc/users.db`` and ``misc/secret.key`` (the WebUI session key),
``misc/display.lock`` (taken by whoever drives the display) and
``misc/display.json`` (refresh counter), see :mod:`epiframe.display.controller`.
The display libraries (Waveshare ``waveshare_epd``, Pimoroni ``inky``) are looked
up in ``EPIFRAME_LIBRARY_DIR``, by default in ``lib`` of the ePiframe directory,
the plugins in ``EPIFRAME_PLUGINS_DIR`` (default ``plugins`` there). The values
are read once, on import, so the variables must be set before the process starts
(systemd ``Environment=``); child processes inherit them.

The ``epiframe`` command of install.sh and of the DEB package runs ePiframe in
the frame folder and sets ``EPIFRAME_CALLER_DIR`` to the folder it was started
in: :func:`caller_path` resolves the file names given on the command line (or
typed in a console dialog) against it.

The default configuration file is part of the package.
"""

import os
from pathlib import Path

CONFIG_DIR_ENV = "EPIFRAME_CONFIG_DIR"
DATA_DIR_ENV = "EPIFRAME_DATA_DIR"
LIBRARY_DIR_ENV = "EPIFRAME_LIBRARY_DIR"
PLUGINS_DIR_ENV = "EPIFRAME_PLUGINS_DIR"
CALLER_DIR_ENV = "EPIFRAME_CALLER_DIR"

LEGACY_CONFIG_DIR = ""
LEGACY_DATA_DIR = "misc"
# src/epiframe/config/paths.py -> the ePiframe directory (source checkout)
EPIFRAME_DIR = Path(__file__).resolve().parents[3]
LEGACY_LIBRARY_DIR = str(EPIFRAME_DIR / "lib")
LEGACY_PLUGINS_DIR = str(EPIFRAME_DIR / "plugins")


def _directory(variable: str, legacy: str) -> Path:
    # an empty variable counts as not set
    return Path(os.environ.get(variable) or legacy)


CONFIG_FILE = str(_directory(CONFIG_DIR_ENV, LEGACY_CONFIG_DIR) / "config.cfg")
CONFIG_FILE_DEFAULT = str(Path(__file__).with_name("config.default"))
USERS_DB_FILE = str(_directory(DATA_DIR_ENV, LEGACY_DATA_DIR) / "users.db")
SECRET_KEY_FILE = str(_directory(DATA_DIR_ENV, LEGACY_DATA_DIR) / "secret.key")
DISPLAY_LOCK_FILE = str(_directory(DATA_DIR_ENV, LEGACY_DATA_DIR) / "display.lock")
DISPLAY_STATE_FILE = str(_directory(DATA_DIR_ENV, LEGACY_DATA_DIR) / "display.json")
LIBRARY_DIR = str(_directory(LIBRARY_DIR_ENV, LEGACY_LIBRARY_DIR))
PLUGINS_DIR = str(_directory(PLUGINS_DIR_ENV, LEGACY_PLUGINS_DIR))


def caller_path(path: str | Path) -> Path:
    """A file given by the user: relative to the folder the command started in."""
    path = Path(path).expanduser()
    caller = os.environ.get(CALLER_DIR_ENV)
    return Path(caller) / path if caller and not path.is_absolute() else path
