#!/usr/bin/env python3

import atexit
import glob
import os
import shutil
import signal
import sys
import time
from http import HTTPStatus
from typing import List

from epiframe.config import paths
from epiframe.core.interval import IntervalMultiplier
from epiframe.core.pidfile import PidFile, process_command
from epiframe.photos.index import PhotoIndex
from epiframe.photos.model import Photo
from epiframe.photos.selection import Selection
from epiframe.sources.drive import DRIVE_SOURCE, DriveClient, DriveSource, folder_ids
from epiframe.sources.drive_setup_console import ConsoleSetup
from epiframe.sources.local import LOCAL_SOURCE, LocalSource
from epiframe.core.logs import format_duration, get_logger, setup_logging
from epiframe.core.media_types import EXTENSIONS, MIME_PREFIX, TYPE_TO_EXTENSION
from modules.base.pluginbase import PluginBase
from epiframe.config.manager import ConfigManager
from epiframe.display.factory import create_display
from epiframe.display.options import DisplayType
from epiframe.display.system import spi_enabled
from epiframe.users.console import USERS_ACTIONS_TAG, UsersConsole
from epiframe.users.store import Users
from epiframe.weather.openweather import fetch_weather
from epiframe.weather.stamp import StampSettings, draw_stamp
from epiframe.processing.imagemagick import (
    ConvertSettings,
    ImageMagick,
    ImageMagickError,
    Thumbnails,
)
from modules.pluginsmanager import PluginsManager


# minimal needed Python version (keep in sync with requires-python in pyproject.toml)
MINIMAL_PYTHON_VERSION = (3, 11)

log = get_logger()


class EPiframe:
    def __init__(self):
        self.check_python_version()
        print("ePiframe - e-Paper Raspberry Pi Photo Frame")

        self.show_help()
        start_time = time.monotonic()
        setup_logging()
        self.config = self.load_config()

        setup_logging(self.config.get("log_files"))
        self.start_drive_setup()
        log.info("Verifying configuration...")
        self.verify_config()

        self.pid_manager = PidFile(self.config.get("pid_file"))
        self.plugins_manager = PluginsManager(
            os.path.dirname(os.path.realpath(__file__)),
            self.pid_manager,
            self.config,
        )
        self.verify_plugin_configs()
        log.info("OK!")
        self.check_config()

        self.start_user_management()
        self.check_system()
        self.save_pid()

        if (
            not self.check_arguments("--test-display")
            and not self.check_arguments("--test-convert")
            and not self.check_arguments("--convert")
            and not self.check_arguments("--users")
        ):
            self.process_flow()

        self.process_test_convert()
        self.process_convert_command()
        self.process_test_display()

        log.info(f"Done in {format_duration(time.monotonic() - start_time)}")

    def process_flow(self):
        log.info("Checking sources...")
        self.check_all_sources()
        log.info("OK!")
        with PhotoIndex(self.config.get("photo_db_file")) as photo_index:
            self.photo_index = photo_index
            self.update_index()

            total_number = photo_index.count()
            log.info(f"Found {total_number} photos")
            self.exit_if_no_photos(total_number)

            log.info("Filtering photos...")
            self.selection = self.get_selection()
            filter_number = photo_index.count(self.selection)
            log.info(f"Filtered {filter_number} photos")
            self.exit_if_no_photos_after_filtering(filter_number)
            self.show_next_photo()

    def show_next_photo(self):
        photo = None
        for count in reversed(range(3)):
            photo = self.pick_photo(photo)
            log.info(f"Photo to show:\n{photo}")
            self.remove_old_files()

            log.info("Getting next photo...")
            filename, returned_value = self.get_next_photo(photo)

            if os.path.exists(filename) and returned_value == HTTPStatus.OK:
                self.process_file(filename, photo)
                break

            log.error(f"Fail! File was not retrieved! Error: {str(returned_value)}")
            if count > 0:
                log.info("Retrying with the new photo...")

    def pick_photo(self, failed: Photo | None) -> Photo:
        # after a failed photo the next one is picked as if it was shown
        if bool(self.config.getint("randomize")):
            return self.photo_index.random_photo(self.selection, exclude=failed)
        return self.photo_index.next_photo(self.selection, after=failed)

    def get_next_photo(self, photo) -> tuple:
        self.photo_description = None
        if photo.source == DRIVE_SOURCE:
            return self.download_drive_photo(photo)
        returned_value = HTTPStatus.OK
        plugin_with_source = self.get_plugin_with_source(photo)
        filename = self.get_filename(photo, plugin_with_source, returned_value)
        return filename, returned_value

    def download_drive_photo(self, photo: Photo) -> tuple:
        try:
            download = self.get_drive_source().download(
                photo,
                self.config.get("photo_convert_path"),
                self.config.get("photo_download_name"),
            )
        except Exception as exception:
            return "", str(exception)
        # the Drive description holds the interval hot word
        self.photo_description = download.description
        return str(download.path), HTTPStatus.OK

    def get_drive_source(self) -> DriveSource:
        if not self.drive_source:
            self.drive_source = DriveSource(
                DriveClient.from_key_file(self.config.get("drive_key_file")),
                folder_ids(self.config.get("drive_folders")),
                bool(self.config.getint("drive_subfolders")),
                EXTENSIONS,
            )
        return self.drive_source

    def get_filename(
        self, photo: Photo, plugin_with_source: PluginBase, returned_value
    ) -> str:
        if plugin_with_source and self.plugins_manager.plugin_source_get_file(
            plugin_with_source
        ):
            filename = plugin_with_source.add_photo_source_get_file(
                photo,
                self.config.get("photo_convert_path"),
                self.config.get("photo_download_name"),
            )
        else:
            source_file = photo.id
            error, image_type = self.get_image_format(source_file)

            filename = (
                self.config.get("photo_download_name")
                + "."
                + str(source_file).rsplit(".")[-1].lower()
            )
            self.get_source(error, image_type, returned_value, filename)
            filename = os.path.join(self.config.get("photo_convert_path"), filename)
            self.copy_file(source_file, filename)
        return filename

    def get_plugin_with_source(self, photo: Photo) -> PluginBase:
        return next(
            (
                plugin
                for plugin in self.plugins_manager.get_plugin_source()
                if plugin.SOURCE == photo.source
            ),
            None,
        )

    def remove_old_files(self):
        for old_file in glob.glob(
            os.path.join(
                self.config.get("photo_convert_path"),
                self.config.get("photo_download_name"),
            )
            + ".*"
        ):
            os.remove(old_file)

    def exit_if_no_photos_after_filtering(self, filter_number: int):
        if filter_number == 0:
            log.info("No photos after filtering!")
            sys.exit(1)

    def get_selection(self) -> Selection:
        try:
            return Selection.from_config(
                self.config.get("photos_from"),
                self.config.get("photos_to"),
                self.config.get("no_photos"),
                self.config.get("sorting"),
            )
        except Exception as exception:
            log.error(f"Error parsing configured filtering: {exception}")
            raise

    def exit_if_no_photos(self, total_number: int):
        if total_number == 0:
            log.info("No photos in sources!")
            sys.exit(1)

    def update_index(self):
        sources = []
        if bool(self.config.getint("use_local")):
            self.update_local_source()
            sources.append(LOCAL_SOURCE)
        if bool(self.config.getint("use_drive")):
            self.update_drive_source()
            sources.append(DRIVE_SOURCE)
        for plugin in self.plugins_manager.plugin_source():
            self.update_plugin_source(plugin)
            sources.append(plugin.SOURCE)
        # photos of disabled sources are not shown anymore
        self.photo_index.keep_sources(sources)

    def process_test_convert(self):
        if self.check_arguments("--test-convert"):
            self.test_convert()

    def process_convert_command(self):
        if self.check_arguments("--convert"):
            self.convert_command()

    def process_test_display(self):
        if self.check_arguments("--test-display"):
            self.test_display()

    def check_all_sources(self):
        if (
            not bool(self.config.getint("use_local"))
            and not bool(self.config.getint("use_drive"))
            and not self.plugins_manager.plugin_source()
        ):
            log.info("No photo sources picked! Check the configuration!")
            raise Exception("No photo sources picked! Check the configuration!")

    def update_local_source(self):
        log.info("Getting data from local source...")
        result = LocalSource(
            self.config.get("local_path"),
            bool(self.config.getint("local_subfolders")),
            EXTENSIONS,
        ).sync(self.photo_index)
        scan = "full scan" if result.full else "incremental scan"
        log.info(
            f"Success! {result.photos} photos, {result.scanned} of {result.folders} "
            f"folders read ({scan})"
        )

    def update_drive_source(self):
        try:
            source = self.get_drive_source()
            log.info(
                f"Getting data from Google Drive source (as {source.drive.account})..."
            )
            result = source.sync(self.photo_index)
        except Exception as exception:
            # e.g. no network: the photos found before are still shown
            log.error(f"Error getting data from Google Drive source: {exception}")
            return
        scan = "full listing" if result.full else f"{result.changes} changes"
        log.info(f"Success! {result.photos} photos ({scan})")

    def update_plugin_source(self, plugin: PluginBase):
        try:
            log.info(f"Getting data from plugin '{plugin.name}' source...")
            self.photo_index.replace_source(plugin.SOURCE, plugin.add_photo_source())
            log.info("Success!")
        except Exception as exception:
            log.error(f"Error: {exception}")
            raise

    def process_file(
        self,
        filename: str,
        photo: Photo,
    ):
        log.info("Success!")
        self.interval_multiplication(filename, photo)
        self.save_index(photo)
        if bool(self.config.getint("convert")):
            self.convert_file(filename, photo)
        else:
            log.info(
                "Conversion disabled in config by 'config' flag! Make sure your photos are pre-converted!"
            )

    def save_index(self, photo: Photo):
        # remember the photo for the next run
        try:
            if not self.check_arguments("--no-skip"):
                self.photo_index.mark_shown(photo, self.selection)
        except Exception as exception:
            log.error(
                "Error saving photo index {}: {}".format(
                    self.config.get("photo_db_file"), exception
                )
            )
            raise

    def save_pid(self):
        try:
            last_pid = self.pid_manager.read()
            if last_pid:
                self.stop_previous_run(last_pid)
                self.pid_manager.remove()

            self.pid_manager.write()
            atexit.register(self.pid_manager.remove)
        except Exception as exception:
            log.error(f"Error! {exception}")
            raise

    def check_system(self):
        if not self.check_multiple_arguments(
            ["--test", "--test-convert", "--convert", "--no-skip"]
        ) and not DisplayType.is_hdmi(self.config.get("display_type")):
            self.process_check_system()

    def process_check_system(self):
        try:
            if not spi_enabled():
                raise Exception("SPI is disabled on system!")
        except Exception as exception:
            log.error(
                f"Error on checking system configuration - SPI is not enabled! {exception}"
            )
            raise

    def start_user_management(self):
        if self.check_arguments("--users"):
            log.info(USERS_ACTIONS_TAG + "Starting users management module...")
            try:
                users = Users(paths.USERS_DB_FILE)
                log.info(USERS_ACTIONS_TAG + "Success!")
            except Exception as exception:
                log.error(USERS_ACTIONS_TAG + f"Fail! {exception}")
                raise
            sys.exit(UsersConsole(users).run())

    def start_drive_setup(self):
        # before the verification: an unfinished Drive setup must not block it
        if self.check_arguments("--setup-drive"):
            sys.exit(ConsoleSetup(self.config).run())

    def check_config(self):
        if self.check_arguments("--check-config"):
            sys.exit(0)

    def show_help(self):
        if self.check_arguments("--help"):
            print("Command line options:")
            print("--check-config		checks configuration file")
            print("--test			runs the whole chain: gets and converts the photo")
            print("			without sending it to the display")
            print(
                "--test-display [file]	displays the photo file on attached display"
            )
            print("			with current ePiframe configuration")
            print("--test-convert [file]	converts the photo file to configured")
            print(
                "			photo_convert_filename with current ePiframe configuration"
            )
            print("--convert [source_file] [target_file_or_loc]")
            print("                        converts the [source_file] photo file to")
            print(
                "                        [target_file_or_loc] (if location - the filename is the same)"
            )
            print("--no-skip		like --test but is not skipping to another photo")
            print("--users			manage users")
            print(
                "--setup-drive		set up the Google Drive source (service account)"
            )
            print("--help			this help")

            sys.exit(0)

    @staticmethod
    def check_multiple_arguments(names: List[str]) -> bool:
        return_value = False
        for name in names:
            return_value = return_value or EPiframe.check_arguments(name)
        return return_value

    @staticmethod
    def check_arguments(name: str) -> bool:
        return name in [argument.lower() for argument in sys.argv]

    def verify_plugin_configs(self):
        if len(self.plugins_manager.get_enabled()) > 0:
            log.info("Verifying plugins configuration...")

            for plugin in self.plugins_manager.get_enabled():
                try:
                    plugin.config.verify()
                except Warning as warning:
                    log.warning(
                        f"Warning verifying configuration file for '{plugin.name}' plugin! {warning}"
                    )
                    pass
                except Exception as exception:
                    log.error(
                        f"Error verifying configuration file for '{plugin.name}' plugin! {exception}"
                    )
                    raise

    def warn_obsolete_config(self):
        obsolete = self.config.get_obsolete()
        if obsolete:
            log.warning(
                f"Warning! Obsolete configuration entries removed: {', '.join(obsolete)}"
            )

    def verify_config(self):
        self.warn_obsolete_config()
        try:
            self.config.verify()
        except Warning as warning:
            log.warning(f"Warning verifying configuration file! {warning}")
            pass
        except Exception as exception:
            log.error(f"Error verifying configuration file! {exception}")
            raise

    @staticmethod
    def load_config() -> ConfigManager:
        try:
            return ConfigManager(paths.CONFIG_FILE, paths.CONFIG_FILE_DEFAULT)
        except Exception as exception:
            log.error(
                f"Error loading {paths.CONFIG_FILE} configuration file! {exception}"
            )
            raise

    @staticmethod
    def check_python_version():
        if sys.version_info < MINIMAL_PYTHON_VERSION:
            version = ".".join(map(str, MINIMAL_PYTHON_VERSION))
            raise Exception(f"Must be using Python {version} or newer!")

    @staticmethod
    def stop_previous_run(pid: int):
        # a previous update that still runs (hangs) is killed; 1.x compared str with
        # bytes here, so it never did
        command = process_command(pid)
        if pid != os.getpid() and command and os.path.basename(__file__) in command:
            log.warning(f"Warning! Stopping previous ePiframe run (PID {pid})")
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def interval_multiplication(self, filename: str, photo):
        if bool(self.config.getint("interval_mult")):
            # if photo comment contains hot word then multiply interval by its value and photo will
            # be displayed longer
            self.interval_manager = IntervalMultiplier(
                self.config.get("interval_mult_file")
            )
            if not self.check_arguments("--no-skip"):
                self.interval_manager.remove()
            self.process_interval(filename, photo)

    def process_interval(self, filename, photo):
        try:
            if not self.check_arguments("--no-skip"):
                comment = self.photo_description
                if not comment:
                    comment = self.magick().comment(filename)
                self.interval_manager.save_from_description(
                    comment,
                    self.config.get("interval_mult_hotword"),
                    self.config.getint("interval_max_mult"),
                )
        except Exception:
            pass

    def convert_file(
        self,
        filename: str,
        photo,
    ):
        target_filename = os.path.join(
            self.config.get("photo_convert_path"),
            self.config.get("photo_convert_filename"),
        )
        if self.convert(
            filename,
            target_filename,
            photo,
        ):
            if not self.check_arguments("--test") and not self.check_arguments(
                "--no-skip"
            ):
                self.send_to_display(target_filename)
        else:
            log.error("Fail!")

    def send_to_display(self, target_filename: str):
        log.info("Sending to display...")
        try:
            create_display(self.config).show(target_filename)
        except Exception as exception:
            log.error(f"Error sending photo to display: {exception}")
            raise

    def test_convert(self):
        filename = os.path.join(
            self.config.get("photo_convert_path"),
            self.config.get("photo_download_name"),
        )
        target_filename = os.path.join(
            self.config.get("photo_convert_path"),
            self.config.get("photo_convert_filename"),
        )
        file = self.get_next_file()
        returned_value = None
        if file:
            filename = file
        else:
            files = glob.glob(f"{filename}.*")
            if not files:
                raise Exception(f"No file: {filename}.*!")
            file = max(files, key=os.path.getctime)
            filename = file
        self.check_file_exist(filename)
        error, image_type = self.get_image_format(filename)
        source = (
            self.config.get("photo_download_name")
            + "."
            + str(filename).rsplit(".")[-1].lower()
        )
        returned_value, source = self.get_source(
            error, image_type, returned_value, source
        )

        self.copy_file(filename, source)
        self.process_convert(returned_value, source, target_filename)

    def convert_command(self):
        files = list(self.get_files())
        if not files or len(files) != 2:
            raise Exception("Files not specified!")

        source, target = files
        self.check_file_exist(source)
        error, _ = self.get_image_format(source)

        if error:
            raise Exception(f"Unknown file {source} format ! - {error}")

        if os.path.isdir(target):
            target = os.path.join(target, source.split(os.sep)[-1])

        self.process_convert(
            None, source, "".join(target.rsplit(".")[:-1]) + ".bmp", thumbs=False
        )

    def magick(self) -> ImageMagick:
        return ImageMagick(self.config.get("convert_bin_path"))

    def get_image_format(self, file: str) -> tuple:
        # (error, format name) as in 1.x
        try:
            return "", self.magick().image_format(file)
        except ImageMagickError as error:
            return str(error), ""

    def get_source(
        self, error: str, image_type, returned_value, source: str
    ) -> (str, str):
        if not error and image_type:
            try:
                source = (
                    self.config.get("photo_download_name")
                    + "."
                    + TYPE_TO_EXTENSION[MIME_PREFIX + image_type.lower()]
                )
            except Exception as exception:
                returned_value = str(exception)
        return returned_value, source

    @staticmethod
    def check_file_exist(filename: str):
        if not os.path.exists(filename):
            raise Exception(f"No file: {filename}!")

    def process_convert(
        self, returned_value, source: str, target_filename: str, thumbs: bool = True
    ):
        if not os.path.exists(source):
            log.error(f"Fail! File was not retrieved! : {str(returned_value)}")
        else:
            if not self.convert(source, target_filename, None, thumbs):
                log.error("Fail!")

    def test_display(self):
        target_filename = os.path.join(
            self.config.get("photo_convert_path"),
            self.config.get("photo_convert_filename"),
        )
        file = self.get_next_file()
        if file:
            target_filename = file
        if not os.path.exists(target_filename):
            raise Exception(f"No file: {target_filename}!")
        self.send_to_display(target_filename)

    @staticmethod
    def get_next_file():
        return next(
            EPiframe.get_files(),
            "",
        )

    @staticmethod
    def get_files():
        return (element for element in sys.argv[1:] if "--" not in element)

    def convert(self, filename: str, target_filename: str, photo, thumbs: bool = True):
        return_value = False

        self.auto_orient(filename)

        filename_pre = (
            os.path.join(
                os.path.split(filename)[0], "pre_" + os.path.split(filename)[1]
            )
            if thumbs
            else filename
        )

        if thumbs:
            self.copy_file(filename, filename_pre)
        self.plugins_preprocess(photo, filename_pre)

        if self.convert_photo(filename_pre, target_filename, thumbs):
            self.plugins_postprocess(photo, target_filename)
            self.process_show_weather(target_filename)
            return_value = True
        return return_value

    def convert_photo(self, source: str, target: str, thumbs: bool) -> bool:
        log.info("Processing the photo...")
        try:
            self.magick().convert(
                source,
                target,
                ConvertSettings.from_config(
                    self.config,
                    DisplayType.is_hdmi(self.config.get("display_type")),
                ),
                Thumbnails.from_config(self.config) if thumbs else None,
            )
        except ImageMagickError as error:
            log.error(f"Fail! {error}")
            return False
        log.info("Success!")
        return True

    def auto_orient(self, filename):
        if bool(self.config.getint("auto_orientation")):
            log.info("Auto-orientate the photo...")
            try:
                turned = self.magick().auto_orient(filename)
            except ImageMagickError as error:
                # the conversion reports the broken photo too (1.x crashed here)
                log.error(f"Fail! {error}")
                return
            log.info("Success!" if turned else "Success! Already upright")

    @staticmethod
    def copy_file(src, target):
        try:
            shutil.copy(src, target)
        except Exception:
            pass

    def plugins_preprocess(
        self,
        photo,
        filename_pre: str,
    ):
        for plugin in self.plugins_manager.plugin_preprocess():
            try:
                log.info(f"Preprocessing photo by plugin '{plugin.name}'...")
                plugin.preprocess_photo(
                    filename_pre,
                    bool(self.config.getint("horizontal")),
                    self.magick(),
                    photo,
                )
                log.info("Success!")
            except Exception as exception:
                log.error(f"Error: {exception}")
                raise

    def plugins_postprocess(
        self,
        photo,
        targetFilename: str,
    ):
        for plugin in self.plugins_manager.plugin_postprocess():
            try:
                log.info(f"Postprocessing photo by plugin '{plugin.name}'...")
                plugin.postprocess_photo(
                    targetFilename,
                    self.config.getint("image_width"),
                    self.config.getint("image_height"),
                    bool(self.config.getint("horizontal")),
                    self.magick(),
                    photo,
                )
                log.info("Success!")
            except Exception as exception:
                log.error(f"Error: {exception}")
                raise

    def process_show_weather(self, target_filename: str):
        if bool(self.config.getint("show_weather")):
            self.show_weather(target_filename)

    def show_weather(self, target_filename: str):
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
                target_filename,
                weather,
                self.config.get("units"),
                StampSettings.from_config(self.config),
            )
            log.info("Success!")
        except Exception as exception:
            log.error(f"Fail! {exception}")

    config = None
    photo_index = None
    drive_source = None
    photo_description = None
    selection = None
    plugins_manager = None
    pid_manager = None
    interval_manager = None


if __name__ == "__main__":
    EPiframe()
