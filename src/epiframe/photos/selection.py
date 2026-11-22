"""Which photos are shown and in which order (``Filtering`` settings)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from epiframe.photos.model import local_time

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LEGACY_DATE_FORMAT = "%Y.%m.%d %H:%M:%S"


class Sorting(StrEnum):
    """Order of the photos (``sorting`` setting)."""

    NONE = "none"  # order in which the photos were found
    ASC = "asc"  # oldest first
    DESC = "desc"  # newest first

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]


@dataclass(frozen=True)
class Selection:
    """Photos created strictly between ``after`` and ``before`` (both optional).

    ``limit`` keeps only the first photos in the order they were found (applied
    before sorting, as in 1.x).
    """

    after: datetime | None = None
    before: datetime | None = None
    limit: int | None = None
    sorting: Sorting = Sorting.NONE

    def __post_init__(self) -> None:
        for name in ("after", "before"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, local_time(value))

    @classmethod
    def from_config(
        cls, photos_from: str, photos_to: str, no_photos: str, sorting: str
    ) -> "Selection":
        """Build the selection from the (validated) configuration values."""
        return cls(
            after=parse_date(photos_from),
            before=parse_date(photos_to),
            limit=int(no_photos) if no_photos else None,
            sorting=Sorting(sorting),
        )


def parse_date(value: str) -> datetime | None:
    """Parse a ``photos_from`` / ``photos_to`` value (empty = no limit)."""
    return datetime.strptime(value, DATE_FORMAT) if value else None


def verify_date(value: str) -> None:
    """Config check: raise ``ValueError`` if ``value`` is not a valid date."""
    parse_date(value)


def verify_range(values: list[str]) -> None:
    """Config check of ``[photos_from, photos_to]``."""
    after, before = (parse_date(value) for value in values)
    if after and before and after > before:
        raise ValueError("Configuration photos_from time is older than photos_to!")


def convert_legacy_date(value: str) -> str:
    """Convert a 1.x ``YYYY.MM.DD HH:MM:SS`` date to the current format."""
    try:
        datetime.strptime(value, LEGACY_DATE_FORMAT)
    except ValueError:
        return value
    return value.replace(".", "-")


def sorting_from_sort_desc(value: str) -> str:
    """Convert the 1.x ``sort_desc`` (0/1) entry to a ``sorting`` value."""
    return Sorting.DESC if int(value) else Sorting.NONE
