"""Locations of the configuration and data files.

The directories can be set with environment variables (the DEB package uses the
FHS layout: ``EPIFRAME_CONFIG_DIR=/etc/epiframe``,
``EPIFRAME_DATA_DIR=/var/lib/epiframe``). Without them the 1.x layout is used:
``config.cfg`` in the ePiframe directory and ``misc/users.db``. The values are
read once, on import, so the variables must be set before the process starts
(systemd ``Environment=``); child processes inherit them.

The default configuration file is part of the package.
"""

import os
from pathlib import Path

CONFIG_DIR_ENV = "EPIFRAME_CONFIG_DIR"
DATA_DIR_ENV = "EPIFRAME_DATA_DIR"

LEGACY_CONFIG_DIR = ""
LEGACY_DATA_DIR = "misc"


def _directory(variable: str, legacy: str) -> Path:
    # an empty variable counts as not set
    return Path(os.environ.get(variable) or legacy)


CONFIG_FILE = str(_directory(CONFIG_DIR_ENV, LEGACY_CONFIG_DIR) / "config.cfg")
CONFIG_FILE_DEFAULT = str(Path(__file__).with_name("config.default"))
USERS_DB_FILE = str(_directory(DATA_DIR_ENV, LEGACY_DATA_DIR) / "users.db")
