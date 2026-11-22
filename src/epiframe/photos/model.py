"""A photo known to the index."""

from dataclasses import dataclass
from datetime import datetime


def local_time(value: datetime) -> datetime:
    """Return ``value`` as naive local time, whole seconds.

    Photos are compared by their wall-clock time (like EXIF dates); aware values
    are converted to the local time zone first.
    """
    if value.tzinfo is not None:
        value = value.astimezone().replace(tzinfo=None)
    return value.replace(microsecond=0)


@dataclass(frozen=True)
class Photo:
    """A photo of a source.

    ``id`` is unique within ``source`` (the file path for local photos, the file id
    for remote ones); ``source`` is ``"Local"`` or a plugin's ``SOURCE``.
    """

    id: str
    source: str
    created: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "created", local_time(self.created))
