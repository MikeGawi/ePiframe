"""Where things drawn on the converted photo land for the person looking at the frame.

The converted photo is stored the way the panel takes it: turned by 90/270
degrees for a vertical frame (``horizontal=0``, ``rotation``) and upside down for
a horizontal frame mounted upside down (``turned``). Overlays (the weather
stamp, the status icons) are drawn on the upright photo and turned back.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol, Self

from PIL import Image


class Settings(Protocol):
    def getint(self, name: str) -> int: ...


class Position(IntEnum):
    """Corner of an overlay (``position``, ``icons_position`` settings)."""

    TOP_LEFT = 0
    TOP_RIGHT = 1
    BOTTOM_LEFT = 2
    BOTTOM_RIGHT = 3

    @classmethod
    def values(cls) -> list[int]:
        return [member.value for member in cls]

    @property
    def right(self) -> bool:
        return self in (Position.TOP_RIGHT, Position.BOTTOM_RIGHT)

    @property
    def bottom(self) -> bool:
        return self in (Position.BOTTOM_LEFT, Position.BOTTOM_RIGHT)


@dataclass(frozen=True)
class Orientation:
    """How the frame hangs."""

    horizontal: bool = True
    turned: bool = False  # a horizontal frame mounted upside down
    rotation: int = 90  # of a vertical frame: 90 or 270

    @classmethod
    def from_config(cls, config: Settings) -> Self:
        horizontal = bool(config.getint("horizontal"))
        return cls(
            horizontal=horizontal,
            turned=horizontal and bool(config.getint("turned")),
            rotation=config.getint("rotation"),
        )

    def upright(self, image: Image.Image) -> Image.Image:
        """A copy of the stored ``image`` the way the viewer sees it."""
        return self._turn(image, back=False)

    def stored(self, image: Image.Image) -> Image.Image:
        """A copy of the upright ``image`` the way it is stored."""
        return self._turn(image, back=True)

    def _turn(self, image: Image.Image, back: bool) -> Image.Image:
        if self.horizontal:
            return (
                image.transpose(Image.Transpose.ROTATE_180)
                if self.turned
                else image.copy()
            )
        turn_left = (self.rotation == 90) != back
        return image.transpose(
            Image.Transpose.ROTATE_90 if turn_left else Image.Transpose.ROTATE_270
        )
