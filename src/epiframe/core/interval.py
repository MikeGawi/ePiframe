"""Display time multiplier of the current photo (``interval_mult_file`` setting).

A photo whose description contains the hot word and a number (e.g. ``hotword 3``)
stays on the frame that many slide intervals; the Telegram bot can extend the
time too. The service decrements the stored value after each interval.
"""

import os
from pathlib import Path

from epiframe.core.files import write_text_atomic

NO_MULTIPLIER = 0


class IntervalMultiplier:
    """Multiplier stored in the file at ``path``; no file means no multiplier."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def read(self) -> int:
        """Return the stored multiplier, ``NO_MULTIPLIER`` if there is no valid one."""
        try:
            return int(self.path.read_text().strip())
        except (OSError, ValueError):
            return NO_MULTIPLIER

    def save(self, multiplier: int) -> None:
        """Store ``multiplier``; values <= 1 (no extra time) remove the file."""
        if multiplier <= 1:
            self.remove()
        else:
            write_text_atomic(self.path, str(multiplier))

    def remove(self) -> None:
        self.path.unlink(missing_ok=True)

    def save_from_description(
        self, description: str, hot_word: str, max_multiplier: int
    ) -> None:
        """Store the multiplier from a photo description like ``"<hot word> 3"``.

        Nothing is stored when the hot word is missing or the rest of the
        description is not a number; the value is capped at ``max_multiplier``.
        """
        text = description.lower()
        word = hot_word.lower()
        if word not in text:
            return
        try:
            multiplier = int(text.replace(word, "").strip())
        except ValueError:
            return
        self.save(min(multiplier, max_multiplier))
