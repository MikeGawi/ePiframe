"""What every display offers to the rest of ePiframe."""

from enum import StrEnum
from pathlib import Path
from typing import Protocol


class Capability(StrEnum):
    """Refresh modes a display supports."""

    FULL = "full"  # standard full refresh (every display)
    FAST_FULL = "fast_full"  # shorter flashing full refresh
    PARTIAL = "partial"  # refresh of a window only
    GRAY4 = "gray4"  # 4 gray levels


class DisplayError(Exception):
    """A display can't be loaded or doesn't accept the photo."""


class Display(Protocol):
    """A display that shows the converted photo."""

    @property
    def capabilities(self) -> frozenset[Capability]: ...

    def show(self, path: Path | str) -> None:
        """Show the image file at ``path``."""

    def show_partial(self, path: Path | str, previous: Path | str) -> None:
        """Show the image file at ``path`` with a partial refresh (only with
        :attr:`Capability.PARTIAL`); ``previous`` is the image shown now."""
