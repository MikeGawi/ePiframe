"""The photo update: sync the sources, pick, fetch, convert and show a photo."""

from enum import Enum

from epiframe.config.property import ValueSource
from epiframe.core.interval import IntervalMultiplier
from epiframe.core.logs import get_logger
from epiframe.photos.index import PhotoIndex
from epiframe.photos.model import Photo
from epiframe.photos.selection import Selection
from epiframe.plugins.manager import PluginManager
from epiframe.processing.imagemagick import ImageMagick, ImageMagickError
from epiframe.sources.drive import DriveSource
from epiframe.update import UpdateError
from epiframe.update.fetch import Fetched, Fetcher, Originals
from epiframe.update.pipeline import Pipeline
from epiframe.update.sources import Sources, drive_source

ATTEMPTS = 3  # photos tried when a file can't be retrieved

log = get_logger("update")


class Mode(Enum):
    """What the update does with the photo."""

    SHOW = "show"  # mark it shown, show it
    TEST = "test"  # mark it shown, don't show it
    NO_SKIP = "no-skip"  # leave the index and the display time alone, don't show it


class PhotoUpdate:
    """One update of the configuration ``config``."""

    def __init__(
        self,
        config: ValueSource,
        plugins: PluginManager,
        pipeline: Pipeline,
        mode: Mode = Mode.SHOW,
    ) -> None:
        self.config = config
        self.mode = mode
        self.pipeline = pipeline
        self._drive: DriveSource | None = None
        self.sources = Sources(config, plugins, self.drive)
        self.originals = Originals(config, pipeline.magick)
        self.fetcher = Fetcher(self.originals, plugins, self.drive)

    @property
    def magick(self) -> ImageMagick:
        return self.pipeline.magick

    def drive(self) -> DriveSource:
        """The Google Drive source (created on first use)."""
        if self._drive is None:
            self._drive = drive_source(self.config)
        return self._drive

    def run(self) -> None:
        """Do the update; raise ``UpdateError`` when it stops."""
        log.info("Checking sources...")
        self.sources.check()
        log.info("OK!")
        with PhotoIndex(self.config.get("photo_db_file")) as index:
            self.sources.sync(index)
            selection = self._selection(index)
            photo, fetched = self._fetch(index, selection)
            self._multiplier(fetched)
            if self.mode is not Mode.NO_SKIP:
                index.mark_shown(photo, selection)  # the next update goes on from it
        self.pipeline.prepare(fetched.path, photo)
        if self.mode is Mode.SHOW:
            self.pipeline.show(self.pipeline.target)

    def _selection(self, index: PhotoIndex) -> Selection:
        total = index.count()
        log.info(f"Found {total} photos")
        if not total:
            raise UpdateError("No photos in sources!")
        log.info("Filtering photos...")
        try:
            selection = Selection.from_config(
                self.config.get("photos_from"),
                self.config.get("photos_to"),
                self.config.get("no_photos"),
                self.config.get("sorting"),
            )
        except ValueError as error:
            raise UpdateError(f"Error parsing configured filtering: {error}") from error
        filtered = index.count(selection)
        log.info(f"Filtered {filtered} photos")
        if not filtered:
            raise UpdateError("No photos after filtering!")
        return selection

    def _pick(
        self, index: PhotoIndex, selection: Selection, failed: Photo | None
    ) -> Photo:
        # after a failed photo the next one is picked as if it was shown
        if bool(self.config.getint("randomize")):
            photo = index.random_photo(selection, exclude=failed)
        else:
            photo = index.next_photo(selection, after=failed)
        if photo is None:  # the photos were counted before; removed meanwhile?
            raise UpdateError("No photos after filtering!")
        return photo

    def _fetch(self, index: PhotoIndex, selection: Selection) -> tuple[Photo, Fetched]:
        photo = None
        for attempt in range(ATTEMPTS):
            if attempt:
                log.info("Retrying with the new photo...")
            photo = self._pick(index, selection, photo)
            log.info(f"Photo to show:\n{photo}")
            self.originals.remove()
            log.info("Getting next photo...")
            try:
                fetched = self.fetcher.fetch(photo)
            except Exception as error:
                log.error(f"Fail! File was not retrieved! Error: {error}")
                continue
            log.info("Success!")
            return photo, fetched
        raise UpdateError(f"No photo retrieved in {ATTEMPTS} attempts!")

    def _multiplier(self, fetched: Fetched) -> None:
        """Store the display time multiplier from the photo's hot word."""
        if not bool(self.config.getint("interval_mult")) or self.mode is Mode.NO_SKIP:
            return
        multiplier = IntervalMultiplier(self.config.get("interval_mult_file"))
        multiplier.remove()
        multiplier.save_from_description(
            fetched.description or self._comment(fetched),
            self.config.get("interval_mult_hotword"),
            self.config.getint("interval_max_mult"),
        )

    def _comment(self, fetched: Fetched) -> str:
        try:
            return self.magick.comment(str(fetched.path))
        except ImageMagickError:
            return ""
