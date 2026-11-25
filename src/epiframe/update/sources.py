"""Brings the photo index up to date with the enabled sources."""

from collections.abc import Callable

from epiframe.config.property import ValueSource
from epiframe.core.logs import get_logger
from epiframe.core.media_types import EXTENSIONS
from epiframe.photos.index import PhotoIndex
from epiframe.plugins.base import Plugin
from epiframe.plugins.manager import PluginManager
from epiframe.sources.drive import DRIVE_SOURCE, DriveClient, DriveSource, folder_ids
from epiframe.sources.local import LOCAL_SOURCE, LocalSource
from epiframe.update import UpdateError

NO_SOURCES = "No photo sources picked! Check the configuration!"

log = get_logger("update")


def drive_source(config: ValueSource) -> DriveSource:
    """The Google Drive source of the configuration."""
    return DriveSource(
        DriveClient.from_key_file(config.get("drive_key_file")),
        folder_ids(config.get("drive_folders")),
        bool(config.getint("drive_subfolders")),
        EXTENSIONS,
    )


class Sources:
    """The photo sources of ``config``: local folder, Google Drive, plugins.

    ``drive`` returns the Google Drive source (created once, it is also used to
    download the photo).
    """

    def __init__(
        self,
        config: ValueSource,
        plugins: PluginManager,
        drive: Callable[[], DriveSource],
    ) -> None:
        self.config = config
        self.plugins = plugins
        self.drive = drive

    @property
    def use_local(self) -> bool:
        return bool(self.config.getint("use_local"))

    @property
    def use_drive(self) -> bool:
        return bool(self.config.getint("use_drive"))

    def check(self) -> None:
        """Raise ``UpdateError`` if no source is enabled."""
        if not (self.use_local or self.use_drive or self.plugins.sources()):
            raise UpdateError(NO_SOURCES)

    def sync(self, index: PhotoIndex) -> None:
        """Update ``index``; photos of disabled sources are removed from it."""
        sources = []
        if self.use_local:
            self._sync_local(index)
            sources.append(LOCAL_SOURCE)
        if self.use_drive:
            self._sync_drive(index)
            sources.append(DRIVE_SOURCE)
        for plugin in self.plugins.sources():
            self._sync_plugin(index, plugin)
            sources.append(plugin.source)
        index.keep_sources(sources)

    def _sync_local(self, index: PhotoIndex) -> None:
        log.info("Getting data from local source...")
        result = LocalSource(
            self.config.get("local_path"),
            bool(self.config.getint("local_subfolders")),
            EXTENSIONS,
        ).sync(index)
        scan = "full scan" if result.full else "incremental scan"
        log.info(
            f"Success! {result.photos} photos, {result.scanned} of {result.folders} "
            f"folders read ({scan})"
        )

    def _sync_drive(self, index: PhotoIndex) -> None:
        try:
            source = self.drive()
            log.info(
                f"Getting data from Google Drive source (as {source.drive.account})..."
            )
            result = source.sync(index)
        except Exception as error:
            # e.g. no network: the photos found before are still shown
            log.error(f"Error getting data from Google Drive source: {error}")
            return
        scan = "full listing" if result.full else f"{result.changes} changes"
        log.info(f"Success! {result.photos} photos ({scan})")

    @staticmethod
    def _sync_plugin(index: PhotoIndex, plugin: Plugin) -> None:
        log.info(f"Getting data from plugin '{plugin.name}' source...")
        try:
            index.replace_source(plugin.source, plugin.source_photos())
        except Exception as error:
            raise UpdateError(
                f"Error getting data from plugin '{plugin.name}' source: {error!r}"
            ) from error
        log.info("Success!")
