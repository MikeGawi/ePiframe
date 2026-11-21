"""File system helpers."""

import os


def last_modified(path: str | os.PathLike[str]) -> float | None:
    """Return the modification time of ``path``, or ``None`` if it can't be read."""
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None
