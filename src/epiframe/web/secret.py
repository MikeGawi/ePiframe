"""The secret key of the WebUI sessions, random for every installation.

1.x used the same hard-coded key on every frame, so anybody could forge a
session cookie and skip the login. The key is created on the first start and
kept in the data directory (readable by the owner only).
"""

import os
import secrets
from pathlib import Path

from epiframe.core.files import write_text_atomic

KEY_BYTES = 32


def secret_key(path: str | os.PathLike[str]) -> str:
    """The key stored in ``path``, a new one if the file is missing or empty."""
    file = Path(path)
    if file.exists() and (key := file.read_text().strip()):
        return key
    key = secrets.token_hex(KEY_BYTES)
    file.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(file, key + "\n")  # a new file gets mode 0600
    return key
