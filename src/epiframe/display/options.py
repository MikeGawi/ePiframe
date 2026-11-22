"""Display options selectable in the configuration."""

from enum import StrEnum


class _Option(StrEnum):
    @classmethod
    def values(cls) -> list[str]:
        """Return the plain string values, in declaration order."""
        return [member.value for member in cls]


class ColorMode(_Option):
    """Colors of the display (``display_color`` setting), in WebUI order."""

    BW = "BW"
    BWR = "BW+Red"
    BWY = "BW+Yellow"
    C4 = "4 colors"
    C7 = "7 colors"
    OTHER = "Other"


class Background(_Option):
    """Fill of the area not covered by the photo (``background_color`` setting)."""

    BLACK = "black"
    WHITE = "white"
    PHOTO = "photo"
    CROP = "crop"
