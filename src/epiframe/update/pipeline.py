"""Converts the original photo for the display and shows it.

The conversion: auto-orientation of the original, plugins' ``preprocess_photo``
(on a copy), ImageMagick, plugins' ``postprocess_photo`` and the weather stamp.
The photo is shown through the :class:`~epiframe.display.controller.DisplayController`
(manual commands; the service shows the photos of its updates itself).
"""

import shutil
from pathlib import Path

from epiframe.config.property import ValueSource
from epiframe.core.logs import get_logger
from epiframe.display.controller import DisplayController
from epiframe.display.options import DisplayType
from epiframe.photos.model import Photo
from epiframe.plugins.base import PhotoFile
from epiframe.plugins.manager import PluginManager
from epiframe.processing.imagemagick import (
    ConvertSettings,
    ImageMagick,
    ImageMagickError,
    Thumbnails,
)
from epiframe.update import UpdateError
from epiframe.weather.openweather import fetch_weather
from epiframe.weather.stamp import StampSettings, draw_stamp

WORK_PREFIX = "pre_"  # the copy of the original edited by the plugins

log = get_logger("update")


class Pipeline:
    """Conversion and display of the configuration."""

    def __init__(
        self,
        config: ValueSource,
        plugins: PluginManager,
        magick: ImageMagick,
        display: DisplayController | None = None,
    ) -> None:
        self.config = config
        self.plugins = plugins
        self.magick = magick
        self.display = display or DisplayController(lambda: self.config)

    @property
    def target(self) -> Path:
        """The converted photo (``photo_convert_filename``)."""
        return Path(
            self.config.get("photo_convert_path"),
            self.config.get("photo_convert_filename"),
        )

    @property
    def hdmi(self) -> bool:
        return DisplayType.is_hdmi(self.config.get("display_type"))

    # -------------------------------------------------------------- the update

    def prepare(self, original: Path, photo: Photo) -> None:
        """Make :attr:`target` from the fetched ``original`` photo."""
        if bool(self.config.getint("convert")):
            self.convert(original, self.target, photo)
            return
        # 1.x logged this and never showed the photo
        log.info(
            "Conversion disabled by the 'convert' setting: the photo is shown as is"
        )
        shutil.copyfile(original, self.target)

    # -------------------------------------------------------------- conversion

    def convert(
        self, source: Path, target: Path, photo: Photo | None, thumbnails: bool = True
    ) -> None:
        """Convert ``source`` to ``target``; raise ``UpdateError`` on failure."""
        self._auto_orient(source)
        work = source.with_name(WORK_PREFIX + source.name)
        shutil.copyfile(source, work)
        try:
            self._plugins("preprocess_photo", work, photo)
            self._convert(work, target, thumbnails)
        finally:
            work.unlink(missing_ok=True)
        self._plugins("postprocess_photo", target, photo)
        if bool(self.config.getint("show_weather")):
            self._weather(target)

    def _auto_orient(self, file: Path) -> None:
        if not bool(self.config.getint("auto_orientation")):
            return
        log.info("Auto-orientate the photo...")
        try:
            turned = self.magick.auto_orient(str(file))
        except ImageMagickError as error:
            # the conversion reports the broken photo too (1.x crashed here)
            log.error(f"Fail! {error}")
            return
        log.info("Success!" if turned else "Success! Already upright")

    def _convert(self, source: Path, target: Path, thumbnails: bool) -> None:
        log.info("Processing the photo...")
        try:
            self.magick.convert(
                str(source),
                str(target),
                ConvertSettings.from_config(self.config, self.hdmi),
                Thumbnails.from_config(self.config) if thumbnails else None,
            )
        except ImageMagickError as error:
            raise UpdateError(f"Fail! {error}") from error
        log.info("Success!")

    def _photo_file(self, path: Path, photo: Photo | None) -> PhotoFile:
        return PhotoFile(
            path=path,
            photo=photo,
            width=self.config.getint("image_width"),
            height=self.config.getint("image_height"),
            horizontal=bool(self.config.getint("horizontal")),
            rotation=self.config.getint("rotation"),
            image_magick=self.magick,
        )

    def _plugins(self, hook: str, path: Path, photo: Photo | None) -> None:
        verb = "Preprocessing" if hook == "preprocess_photo" else "Postprocessing"
        for plugin in self.plugins.with_hook(hook):
            log.info(f"{verb} photo by plugin '{plugin.name}'...")
            getattr(plugin, hook)(self._photo_file(path, photo))
            log.info("Success!")

    def _weather(self, target: Path) -> None:
        # the stamp is optional: any failure is logged, the photo is shown anyway
        log.info("Getting weather data...")
        try:
            weather = fetch_weather(
                self.config.get("apikey"),
                self.config.get("lat"),
                self.config.get("lon"),
                self.config.get("units"),
            )
            log.info("Success!")
            log.info("Putting weather stamp...")
            draw_stamp(
                str(target),
                weather,
                self.config.get("units"),
                StampSettings.from_config(self.config),
            )
            log.info("Success!")
        except Exception as error:
            log.error(f"Fail! {error}")

    # ----------------------------------------------------------------- display

    def show(self, file: Path) -> None:
        """Send ``file`` to the display; raise ``UpdateError`` on failure."""
        try:
            self.display.show(file)
        except Exception as error:
            raise UpdateError(f"Error sending photo to display: {error}") from error
