"""Gets the file of the photo to show (the "original" photo).

The original is stored in ``photo_convert_path`` as ``photo_download_name``
with the extension of its format (the WebUI and the bot offer it for download).
"""

import glob
import shutil
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from epiframe.config.property import ValueSource
from epiframe.core.media_types import MIME_PREFIX, TYPE_TO_EXTENSION
from epiframe.photos.model import Photo
from epiframe.plugins.manager import PluginManager
from epiframe.processing.imagemagick import ImageMagick, ImageMagickError
from epiframe.sources.drive import DRIVE_SOURCE, DriveSource


@dataclass(frozen=True)
class Fetched:
    """The original photo file and its description (Drive; holds the hot word)."""

    path: Path
    description: str = ""


def extension(magick: ImageMagick, file: Path) -> str:
    """The extension of the file's format, its own one if the format is unknown.

    1.x always kept the file's own extension.
    """
    try:
        image_format = magick.image_format(str(file))
    except ImageMagickError:
        image_format = ""
    mime_type = MIME_PREFIX + image_format.lower()
    return TYPE_TO_EXTENSION.get(mime_type) or file.suffix.lstrip(".").lower()


class Originals:
    """The original photo files of the configuration."""

    def __init__(self, config: ValueSource, magick: ImageMagick) -> None:
        self.config = config
        self.magick = magick

    @property
    def directory(self) -> Path:
        return Path(self.config.get("photo_convert_path"))

    @property
    def name(self) -> str:
        return self.config.get("photo_download_name")

    def files(self) -> list[Path]:
        """The original photo files (one, unless a format changed)."""
        pattern = glob.escape(str(self.directory / self.name)) + ".*"
        return [Path(name) for name in glob.glob(pattern)]

    def newest(self) -> Path | None:
        """The newest original photo file (e.g. the uploaded one)."""
        return max(self.files(), key=lambda path: path.stat().st_ctime, default=None)

    def remove(self) -> None:
        for path in self.files():
            path.unlink(missing_ok=True)

    def copy(self, file: Path) -> Path:
        """Copy ``file`` to the original photo file (if it isn't that file)."""
        target = self.directory / f"{self.name}.{extension(self.magick, file)}"
        with suppress(shutil.SameFileError):
            shutil.copyfile(file, target)
        return target


class Fetcher:
    """Gets the file of a photo from its source into the original photo file."""

    def __init__(
        self,
        originals: Originals,
        plugins: PluginManager,
        drive: Callable[[], DriveSource],
    ) -> None:
        self.originals = originals
        self.plugins = plugins
        self.drive = drive

    def fetch(self, photo: Photo) -> Fetched:
        """Get the file of ``photo``; raise any error of the source."""
        fetched = self._fetch(photo)
        if not fetched.path.is_file():
            raise FileNotFoundError(f"No file {fetched.path}")
        return fetched

    def _fetch(self, photo: Photo) -> Fetched:
        directory, name = self.originals.directory, self.originals.name
        if photo.source == DRIVE_SOURCE:
            download = self.drive().download(photo, str(directory), name)
            return Fetched(download.path, download.description)
        plugin = self.plugins.source_of(photo)
        if plugin is not None and plugin.implements("fetch_photo"):
            return Fetched(plugin.fetch_photo(photo, directory, name))
        # local photos (also of plugins without fetch_photo): the id is the path
        return Fetched(self.originals.copy(Path(photo.id)))
