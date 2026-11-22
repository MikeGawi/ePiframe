"""File system helpers."""

import os
import shutil
import tempfile
from pathlib import Path


def last_modified(path: str | os.PathLike[str]) -> float | None:
    """Return the modification time of ``path``, or ``None`` if it can't be read."""
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None


def write_text_atomic(path: str | os.PathLike[str], text: str) -> None:
    """Replace the content of ``path`` with ``text`` atomically.

    The text goes to a temporary file next to ``path`` that is renamed over it, so
    a power cut never leaves a truncated file. The mode of an existing file is kept.
    """
    target = Path(path)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(handle, "w") as file:
            file.write(text)
        if target.exists():
            shutil.copymode(target, temporary)
        os.replace(temporary, target)
    except BaseException:
        os.remove(temporary)
        raise
