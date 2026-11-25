"""Commands working on single photo files: ``test-convert``, ``test-display``,
``redisplay`` and ``convert``."""

import shutil
import tempfile
from pathlib import Path

from epiframe.processing.imagemagick import ImageMagickError
from epiframe.update import UpdateError
from epiframe.update.fetch import Originals
from epiframe.update.pipeline import Pipeline

CONVERTED_SUFFIX = ".bmp"


def existing(file: Path) -> Path:
    if not file.is_file():
        raise UpdateError(f"No file: {file}!")
    return file


class FileCommands:
    """The commands for the frame of ``pipeline``."""

    def __init__(self, pipeline: Pipeline) -> None:
        self.pipeline = pipeline
        self.originals = Originals(pipeline.config, pipeline.magick)

    def test_convert(self, file: Path | None = None) -> None:
        """Convert ``file`` (default: the original photo) for the display; the
        file becomes the original photo."""
        source = existing(file) if file else self._newest_original()
        original = self.originals.copy(source)
        self.pipeline.convert(original, self.pipeline.target, None)

    def _newest_original(self) -> Path:
        newest = self.originals.newest()
        if newest is None:
            pattern = self.originals.directory / f"{self.originals.name}.*"
            raise UpdateError(f"No file: {pattern}!")
        return newest

    def test_display(self, file: Path | None = None) -> None:
        """Show ``file`` (default: the converted photo) on the display."""
        self.pipeline.show(existing(file or self.pipeline.target))

    def redisplay(self) -> None:
        """Convert and show the original photo again (e.g. a new one uploaded)."""
        self.test_convert()
        self.test_display()

    def convert(self, source: Path, destination: Path) -> Path:
        """Convert ``source`` to a BMP file ``destination`` (a folder: the file
        name of ``source``); return the converted file.

        ``source`` is left untouched (1.x auto-oriented it and let plugins edit it).
        """
        existing(source)
        try:
            self.pipeline.magick.image_format(str(source))
        except ImageMagickError as error:
            raise UpdateError(f"Unknown file {source} format! {error}") from error
        if destination.is_dir():
            destination /= source.name
        target = destination.with_suffix(CONVERTED_SUFFIX)
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory, source.name)
            shutil.copyfile(source, copy)
            self.pipeline.convert(copy, target, None, thumbnails=False)
        return target
