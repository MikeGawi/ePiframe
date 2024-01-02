#!/usr/bin/env python3

import atexit
import glob
import os
import shutil
import signal
import sys
from datetime import datetime
import pandas
import starlette.status
from pandas import DataFrame
from requests import HTTPError

from misc.connection import Connection
from misc.constants import Constants
from misc.logs import Logs
from misc.tools import Tools
from modules.albummanager import AlbumManager
from modules.base.pluginbase import PluginBase
from modules.configmanager import ConfigManager
from modules.convertmanager import ConvertManager
from modules.databasemanager import DatabaseManager
from modules.displaymanager import DisplayManager
from modules.filteringmanager import FilteringManager
from modules.indexmanager import IndexManager
from modules.intervalmanager import IntervalManager
from modules.localsourcemanager import LocalSourceManager
from modules.oauthmanager import OAuthManager
from modules.photomanager import PhotoManager
from modules.pidmanager import PIDManager
from modules.pluginsmanager import PluginsManager
from modules.randommanager import RandomManager
from modules.usersmanager import UsersManager
from modules.weathermanager import WeatherManager
from modules.weatherstampmanager import WeatherStampManager


class EPiframe:
    def __init__(self):
        self.check_python_version()
        print("ePiframe - e-Paper Raspberry Pi Photo Frame")

        self.show_help()
        start_time = Logs.start_time()
        self.config = self.load_config()

        self.logging = Logs(self.config.get("log_files"))
        self.logging.log("Verifying configuration...")
        self.verify_config()

        self.photo_manager = PhotoManager()
        self.pid_manager = PIDManager(self.config.get("pid_file"))
        self.plugins_manager = PluginsManager(
            os.path.dirname(os.path.realpath(__file__)),
            self.pid_manager,
            self.logging,
            self.config,
        )
        self.verify_plugin_configs()
        self.logging.log("OK!")
        self.check_config()

        self.start_user_management()
        self.check_system()
        self.save_pid()

        if (
            not self.check_arguments("--test-display")
            and not self.check_arguments("--test-convert")
            and not self.check_arguments("--users")
        ):
            self.process_flow()

        self.process_test_convert()
        self.process_test_display()

        end_time = Logs.end_time()
        self.logging.log(f"Done in{Logs.execution_time(start_time, end_time)}")

    def process_flow(self):
        self.logging.log("Checking sources...")
        self.check_all_sources()
        self.logging.log("OK!")
        photos = self.get_from_sources()

        total_number = self.get_total_count(photos)
        self.logging.log(f"Found {total_number} photos")
        self.exit_if_no_photos(total_number)

        self.logging.log("Reading last photo index file...")
        self.read_index()
        self.logging.log("Success!")

        self.logging.log("Filtering photos...")
        photos = self.filter_photos_by_from_date(photos)
        photos = self.filter_photos_by_to_date(photos)
        photos = self.filter_photos_by_number(photos)

        self.logging.log("and sorting ...")
        photos = self.sort_photos(photos)
        photos = self.photo_manager.reset_index(photos)
        photos = self.process_plugins_manipulate_list(photos)

        filter_number = self.photo_manager.get_num_of_photos(photos)
        self.logging.log(f"Filtered {filter_number} photos")
        self.exit_if_no_photos_after_filtering(filter_number)

        count = 3
        while count > 0:
            self.get_random_photo(filter_number, photos)
            photo = self.photo_manager.get_photo_by_index(
                photos, self.index_manager.get_index()
            )
            self.logging.log(f"Photo to show:\n{photo}")

            self.index_manager.set_id(self.get_photo_id(photo))
            self.remove_old_files()

            self.logging.log("Getting next photo...")
            filename, returned_value = self.get_next_photo(photo)

            count -= 1
            if os.path.exists(filename) and returned_value == Constants.OK_STATUS_ERRORCODE:
                self.process_file(
                    filename,
                    photo,
                )
                break

            self.logging.log(
                f"Fail! File was not retrieved! Error: {str(returned_value)}"
            )
            if count > 0:
                self.logging.log("Retrying with the new photo...")

    def get_photo_id(self, photo):
        return self.photo_manager.get_photo_attribute(
            photo, Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER
        )

    def get_next_photo(self, photo) -> tuple:
        returned_value = None
        if photo[Constants.PHOTOS_SOURCE_LABEL] == Constants.GOOGLE_PHOTOS_SOURCE:
            filename = self.get_photo(photo)
            returned_value = self.try_download_file(
                self.get_download_url(photo), self.get_photo_id(photo), filename
            )
        else:
            plugin_with_source = self.get_plugin_with_source(photo)
            filename = self.get_filename(photo, plugin_with_source, returned_value)
        return filename, returned_value

    def get_filename(
        self, photo, plugin_with_source: PluginBase, returned_value
    ) -> str:
        if plugin_with_source and self.plugins_manager.plugin_source_get_file(
            plugin_with_source
        ):
            filename = plugin_with_source.add_photo_source_get_file(
                photo,
                self.config.get("photo_convert_path"),
                self.config.get("photo_download_name"),
                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                Constants.PHOTOS_SOURCE_LABEL,
                self.photo_manager,
            )
        else:
            source_file = photo[Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER]
            error, image_type = ConvertManager().get_image_format(
                self.config.get("convert_bin_path"),
                source_file,
                Constants.FIRST_FRAME_GIF,
            )

            filename = (
                self.config.get("photo_download_name")
                + "."
                + str(source_file).rsplit(".")[-1].lower()
            )
            self.get_source(error, image_type, returned_value, filename)
            filename = os.path.join(self.config.get("photo_convert_path"), filename)
            self.copy_file(source_file, filename)
        return filename

    def get_plugin_with_source(self, photo) -> PluginBase:
        return next(
            (
                plugin
                for plugin in self.plugins_manager.get_plugin_source()
                if plugin.SOURCE == photo[Constants.PHOTOS_SOURCE_LABEL]
            ),
            None,
        )

    def try_download_file(self, download_url: str, photo_id: str, filename: str) -> str:
        returned_value = self.download_or_retry(download_url, filename, photo_id)

        if returned_value != Constants.OK_STATUS_ERRORCODE:
            self.logging.log(f"Fail! Server error: {str(returned_value)}")
        return returned_value

    def download_or_retry(self, download_url, filename, photo_id):
        returned_value = None
        count = 2
        while not returned_value:
            try:
                returned_value = Connection.download_file(
                    download_url,
                    self.config.get("photo_convert_path"),
                    filename,
                    Constants.OK_STATUS_ERRORCODE,
                    Constants.CHECK_CONNECTION_TIMEOUT,
                )
            except HTTPError as exception:
                if self.is_403_exception(exception) and count:
                    download_url = self.get_download_url(
                        self.auth_manager.get_item(photo_id)
                    )
                    self.logging.log("Photo download URL expired! - Refreshing URL in Google Photos...")
                    count -= 1
                    continue
                returned_value = str(exception)
        return returned_value

    @staticmethod
    def is_403_exception(exception):
        return (
            hasattr(exception, "response")
            and exception.response.status_code == starlette.status.HTTP_403_FORBIDDEN
        )

    def get_download_url(self, photo) -> str:
        return (
            self.photo_manager.get_photo_attribute(
                photo,
                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_BASEURL_HEADER,
            )
            + Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_GET_DETAILS
        )

    def get_photo(self, photo) -> str:
        return (
            self.config.get("photo_download_name")
            + "."
            + Constants.TYPE_TO_EXTENSION[
                self.photo_manager.get_photo_attribute(
                    photo,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER,
                )
            ]
        )

    def get_random_photo(self, filter_number: int, photos):
        if not bool(self.config.getint("randomize")):
            # find previous photo
            photo_id = next(
                iter(
                    photos[
                        self.photo_manager.get_photos_attribute(
                            photos,
                            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                        )
                        == self.index_manager.get_id()
                    ].index
                ),
                Constants.NOMATCH_INDICATOR_STRING,
            )

            if photo_id != Constants.NOMATCH_INDICATOR_STRING:
                self.index_manager.set_index(photo_id + 1)
            else:
                self.index_manager.set_index(self.index_manager.get_index() + 1)

            # don't go above the number of photos
            self.index_manager.check_index(filter_number)
        else:
            # get random photo
            self.random_manager = RandomManager(
                self.config.get("photo_list_file"),
                photos,
                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
            )
            self.index_manager.set_index(
                self.random_manager.get_random(
                    self.index_manager.get_id(),
                    self.check_arguments("--no-skip"),
                )
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
            self.logging.log("No photos after filtering!")
            sys.exit(1)

    def process_plugins_manipulate_list(self, photos):
        for plugin in self.plugins_manager.plugin_photos_list():
            try:
                self.logging.log(f"Changing photo list by plugin '{plugin.name}'...")
                photos = plugin.change_photos_list(
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                    Constants.PHOTOS_SOURCE_LABEL,
                    photos,
                    self.photo_manager,
                    self.index_manager,
                    FilteringManager(),
                )
                self.logging.log("Success!")
            except Exception as exception:
                self.logging.log(f"Error: {exception}")
                raise
        return photos

    def sort_photos(self, photos):
        return FilteringManager.sort(
            photos,
            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
            photos[Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER],
            self.config.get("sorting"),
        )

    def filter_photos_by_number(self, photos):
        if self.config.get("no_photos"):
            try:
                photos = FilteringManager.filter_by_number(
                    photos, self.config.getint("no_photos")
                )
            except Exception as exception:
                self.logging.log(
                    f"Error parsing configured time no_photos: {exception}"
                )
                raise
        return photos

    def filter_photos_by_to_date(self, photos):
        if self.config.get("photos_to"):
            try:
                photos = FilteringManager.filter_by_to_date(
                    photos,
                    self.config.get("photos_to"),
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                )
            except Exception as exception:
                self.logging.log(
                    f"Error parsing configured time photos_to: {exception}"
                )
                raise
        return photos

    def filter_photos_by_from_date(self, photos):
        if self.config.get("photos_from"):
            try:
                photos = FilteringManager.filter_by_from_date(
                    photos,
                    self.config.get("photos_from"),
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                )
            except Exception as exception:
                self.logging.log(
                    f"Error parsing configured time photos_from: {exception}"
                )
                raise
        return photos

    def read_index(self):
        try:
            self.index_manager = IndexManager(self.config.get("photo_index_file"))
        except IOError as exception:
            self.logging.log(
                "Error opening file {}: {}".format(
                    self.config.get("photo_index_file"), exception
                )
            )
            raise

    def exit_if_no_photos(self, total_number: int):
        if total_number == 0:
            self.logging.log("No photos in albums!")
            sys.exit(1)

    def get_from_sources(self) -> DataFrame:
        photos: DataFrame = DataFrame()
        if bool(self.config.getint("use_google_photos")):
            photos = self.get_google_photos()
        photos = self.get_local_source(photos)
        photos = self.get_plugin_sources(photos)
        return photos

    @staticmethod
    def should_data_be_refreshed(filename: str) -> bool:
        if not os.path.exists(filename):
            return True

        mod_time = Tools.get_last_date(filename)
        if not mod_time:
            return True

        return datetime.now().date() > datetime.fromtimestamp(int(mod_time)).date()

    def read_stored_photos(self):
        photos = DataFrame()
        filename: str = self.config.get("photo_list_file") + ".pickle"
        should_refresh: bool = self.should_data_be_refreshed(filename)
        if (
            self.config.get("refresh_rate") == Constants.REFRESH_ONCE
            and not self.check_arguments("--refresh")
            and not should_refresh
        ):
            try:
                self.logging.log(
                    "Trying to read saved Google Photos data (according to refresh_rate setting set to "
                    "'once' a day)..."
                )
                photos = pandas.read_pickle(filename)
                self.logging.log("Success!")
            except Exception:
                pass

        return photos

    def get_google_photos(self) -> DataFrame:
        self.logging.log("Getting data from Google Photos source...")
        self.logging.log("Checking connection...")
        self.check_connection()
        self.logging.log("OK!")
        self.logging.log("Loading credentials...")
        self.create_auth_manager()
        self.logging.log("Success!")
        self.logging.log("Trying to build service with given credentials...")
        self.build_service()
        self.logging.log("Success!")

        photos = self.read_stored_photos()
        if not photos.empty:
            return photos

        self.logging.log("Getting all albums...")
        self.get_albums_data()
        self.logging.log("Success!")
        self.logging.log("Getting desired album(s)...")
        self.album_manager = AlbumManager(
            self.auth_manager.get_response(),
            self.config.get("album_names"),
            Constants.GOOGLE_PHOTOS_ALBUMS_TITLE_HEADER,
        )
        return self.get_albums()

    def process_test_convert(self):
        if self.check_arguments("--test-convert"):
            self.test_convert()

    def process_test_display(self):
        if self.check_arguments("--test-display"):
            self.test_display()

    def get_total_count(self, photos):
        total_number = (
            self.photo_manager.get_num_of_photos(photos) if photos is not None else 0
        )
        return total_number

    def get_albums_data(self):
        try:
            self.auth_manager.get(
                Constants.GOOGLE_PHOTOS_PAGESIZE,
                bool(Constants.GOOGLE_PHOTOS_EXCLUDENONAPPCREATEDDATA),
                Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER,
                Constants.GOOGLE_PHOTOS_ALBUMS_RESPONSE,
            )
        except Exception as exception:
            error = str(exception)
            self.logging.log(f"Fail! {error}")
            raise Exception(f"Fail! {error}")

    def build_service(self):
        try:
            self.auth_manager.build_service(
                Constants.SERVICE_NAME, Constants.SERVICE_VERSION
            )
        except Exception as exception:
            error = str(exception)
            self.logging.log(f"Fail! {error}")
            raise

    def create_auth_manager(self):
        try:
            self.auth_manager = OAuthManager()
            self.auth_manager.manage_pickle(
                self.config.get("pickle_file"),
                self.config.get("cred_file"),
                Constants.SCOPES,
            )
        except Exception as exception:
            self.logging.log(f"Error! {exception}")
            raise

    def check_connection(self):
        connection = Connection.check_internet(
            Constants.SCOPES[0], Constants.CHECK_CONNECTION_TIMEOUT
        )
        if connection:
            self.logging.log(f"Error! {connection} - No connection to the Internet")
            if not bool(self.config.getint("use_local")):
                raise Exception(f"Error! {connection} - No connection to the Internet")
            else:
                self.logging.log("Continuing with local source...")

    def check_all_sources(self):
        if not bool(self.config.getint("use_google_photos")) and not bool(
            self.config.getint("use_local")
        ):
            self.logging.log("No photo sources picked! Check the configuration!")
            raise Exception("No photo sources picked! Check the configuration!")

    def get_albums(self) -> DataFrame:
        if self.album_manager.get_albums().empty:
            self.logging.log(
                "Fail! Can't find album {}".format(self.config.get("album_names"))
            )
            raise Exception(
                "Fail! Can't find album {}".format(self.config.get("album_names"))
            )

        self.logging.log("Success!")
        self.logging.log("Fetching albums data...")
        try:
            for (index, album_id,) in self.album_manager.get_albums()[
                Constants.GOOGLE_PHOTOS_ALBUMS_ID_HEADER
            ].iteritems():
                items = self.auth_manager.get_items(
                    Constants.GOOGLE_PHOTOS_ALBUMS_ALBUMID_HEADER,
                    album_id,
                    Constants.GOOGLE_PHOTOS_ALBUMS_MEDIAITEMS_HEADER,
                    Constants.GOOGLE_PHOTOS_PAGESIZE,
                    Constants.GOOGLE_PHOTOS_PAGESIZE_HEADER,
                    Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_HEADER,
                    Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER,
                )
                self.album_manager.append_data(items)
        except Exception as exception:
            error = str(exception)
            self.logging.log(f"Fail! {error}")
            raise
        return self.get_google_source()

    def get_google_source(self) -> DataFrame:
        if self.album_manager.get_data().empty:
            self.logging.log("Fail! Couldn't retrieve albums!")
            raise
        photos: DataFrame = self.photo_manager.set_photos(
            self.album_manager,
            Constants.GOOGLE_PHOTOS_ALBUMS_MEDIAMETADATA_HEADER,
            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_HEADER,
            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER,
            Constants.IMAGE_MIMETYPE_STARTING_STRING,
            Constants.PHOTOS_SOURCE_LABEL,
            Constants.GOOGLE_PHOTOS_SOURCE,
        )
        self.logging.log("Success!")
        if not photos.empty:
            photos.to_pickle(self.config.get("photo_list_file") + ".pickle")
        return photos

    def get_local_source(self, photos: DataFrame) -> DataFrame:
        if bool(self.config.getint("use_local")):
            self.logging.log("Getting data from local source...")
            self.local_source_manager = LocalSourceManager(
                self.config.get("local_path"),
                bool(self.config.getint("local_subfolders")),
                Constants.EXTENSIONS,
            )
            local_photos = self.local_source_manager.get_local_photos(
                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                Constants.PHOTOS_SOURCE_LABEL,
                Constants.LOCAL_SOURCE,
            )
            photos = self.photo_manager.append_photos(photos, local_photos)
            self.logging.log("Success!")
        return photos

    def get_plugin_sources(self, photos: DataFrame) -> DataFrame:
        for plugin in self.plugins_manager.plugin_source():
            try:
                self.logging.log(f"Getting data from plugin '{plugin.name}' source...")
                plugin_photos = plugin.add_photo_source(
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                    Constants.PHOTOS_SOURCE_LABEL,
                    self.photo_manager,
                )
                photos = self.photo_manager.append_photos(photos, plugin_photos)
                self.logging.log("Success!")
            except Exception as exception:
                self.logging.log(f"Error: {exception}")
                raise
        return photos

    def process_file(
        self,
        filename: str,
        photo: str,
    ):
        self.logging.log("Success!")
        self.interval_multiplication(filename, photo)
        self.save_index()
        self.convert_file(filename, photo)

    def save_index(self):
        # save index of current photo for next run
        try:
            if not self.check_arguments("--no-skip"):
                self.index_manager.save()
        except IOError as exception:
            self.logging.log(
                "Error saving file {}: {}".format(
                    self.config.get("photo_index_file"), exception
                )
            )
            raise

    def save_pid(self):
        try:
            last_pid = self.pid_manager.read()
            if int(last_pid) > 0:
                try:
                    if os.path.basename(__file__) in self.pid_manager.get_pid_name(
                        last_pid
                    ):
                        os.kill(int(last_pid), signal.SIGKILL)
                except Exception:
                    pass
                self.pid_manager.remove()

            self.pid_manager.save()
            atexit.register(self.pid_manager.remove)
        except Exception as exception:
            self.logging.log(f"Error! {exception}")
            raise

    def check_system(self):
        if (
            not self.check_arguments("--test")
            and not self.check_arguments("--test-convert")
            and not self.check_arguments("--no-skip")
            and not DisplayManager.is_hdmi(self.config.get("display_type"))
        ):
            self.process_check_system()

    def process_check_system(self):
        try:
            if not self.config.check_system():
                raise Exception("SPI is disabled on system!")
        except Exception as exception:
            self.logging.log(
                f"Error on checking system configuration - SPI is not enabled! {exception}"
            )
            raise

    def start_user_management(self):
        if self.check_arguments("--users"):
            self.logging.log(
                Constants.USERS_ACTIONS_TAG + "Starting database management module..."
            )
            try:
                self.database_manager = DatabaseManager()
                self.logging.log(Constants.USERS_ACTIONS_TAG + "Success!")
            except Exception as exception:
                self.logging.log(Constants.USERS_ACTIONS_TAG + f"Fail! {exception}")
                raise

            self.logging.log(
                Constants.USERS_ACTIONS_TAG + "Starting users management module..."
            )
            try:
                self.users_manager = UsersManager(self.database_manager)
                self.logging.log(Constants.USERS_ACTIONS_TAG + "Success!")
            except Exception as exception:
                self.logging.log(Constants.USERS_ACTIONS_TAG + f"Fail! {exception}")
                raise

            self.users_manager.manage(self.logging)
            sys.exit(1)

    def check_config(self):
        if self.check_arguments("--check-config"):
            sys.exit(0)

    def show_help(self):
        if self.check_arguments("--help"):
            print("Command line options:")
            print("--check-config		checks configuration file")
            print("--test			tests credentials, pickle file and downloads photo")
            print("			without sending it to the display")
            print("--test-display [file]	displays the photo file on attached display")
            print("			with current ePiframe configuration")
            print("--test-convert [file]	converts the photo file to configured")
            print("			photo_convert_filename with current ePiframe configuration")
            print("--no-skip		like --test but is not skipping to another photo")
            print(
                "--refresh		force Google API data refresh even if refresh_rate flag is set to 'once'"
            )
            print("--users			manage users")
            print("--help			this help")

            sys.exit(0)

    @staticmethod
    def check_arguments(name: str) -> bool:
        return name in [argument.lower() for argument in sys.argv]

    def verify_plugin_configs(self):
        if len(self.plugins_manager.get_enabled()) > 0:
            self.logging.log("Verifying plugins configuration...")

            for plugin in self.plugins_manager.get_enabled():
                try:
                    plugin.config.verify()
                except Warning as warning:
                    self.logging.log(
                        f"Warning verifying configuration file for '{plugin.name}' plugin! {warning}"
                    )
                    pass
                except Exception as exception:
                    self.logging.log(
                        f"Error verifying configuration file for '{plugin.name}' plugin! {exception}"
                    )
                    raise

    def verify_config(self):
        try:
            self.config.verify()
        except Warning as warning:
            self.logging.log(f"Warning verifying configuration file! {warning}")
            pass
        except Exception as exception:
            self.logging.log(f"Error verifying configuration file! {exception}")
            raise

    @staticmethod
    def load_config() -> ConfigManager:
        try:
            return ConfigManager(Constants.CONFIG_FILE, Constants.CONFIG_FILE_DEFAULT)
        except Exception as exception:
            Logs.show_log(
                f"Error loading {Constants.CONFIG_FILE} configuration file! {exception}"
            )
            raise

    @staticmethod
    def check_python_version():
        if sys.version_info[0] < Constants.MINIMAL_PYTHON_VERSION:
            raise Exception(f"Must be using Python {Constants.MINIMAL_PYTHON_VERSION}!")

    def interval_multiplication(self, filename: str, photo):
        if bool(self.config.getint("interval_mult")):
            # if photo comment contains hot word then multiply interval by its value and photo will
            # be displayed longer
            self.interval_manager = IntervalManager(
                self.config.get("interval_mult_file")
            )
            if not self.check_arguments("--no-skip"):
                self.interval_manager.remove()
            self.process_interval(filename, photo)

    def process_interval(self, filename, photo):
        try:
            if not self.check_arguments("--no-skip"):
                if (
                    photo[Constants.PHOTOS_SOURCE_LABEL]
                    == Constants.GOOGLE_PHOTOS_SOURCE
                ):
                    comment = str(
                        self.photo_manager.get_photo_attribute(
                            photo,
                            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_DESCRIPTION_HEADER,
                        )
                    )
                else:
                    (error, comment,) = ConvertManager().get_image_comment(
                        self.config.get("convert_bin_path"), filename
                    )
                self.interval_manager.save_interval(
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
            self.logging.log("Fail!")

    def send_to_display(self, target_filename: str):
        self.logging.log("Sending to display...")
        display_manager = DisplayManager(self.config)
        try:
            display_manager.show_image(target_filename)
        except Exception as exception:
            self.logging.log(f"Error sending photo to display: {exception}")
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
        error, image_type = ConvertManager().get_image_format(
            self.config.get("convert_bin_path"), filename, Constants.FIRST_FRAME_GIF
        )
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

    def get_source(
        self, error: str, image_type, returned_value, source: str
    ) -> (str, str):
        if not error and image_type:
            try:
                source = (
                    self.config.get("photo_download_name")
                    + "."
                    + Constants.TYPE_TO_EXTENSION[
                        Constants.MIME_START + image_type.lower()
                    ]
                )
            except Exception as exception:
                returned_value = str(exception)
        return returned_value, source

    @staticmethod
    def check_file_exist(filename: str):
        if not os.path.exists(filename):
            raise Exception(f"No file: {filename}!")

    def process_convert(
        self,
        returned_value,
        source: str,
        target_filename: str,
    ):
        if not os.path.exists(source):
            self.logging.log(f"Fail! File was not retrieved! : {str(returned_value)}")
        else:
            import pandas as pandas_engine

            if not self.convert(
                source,
                target_filename,
                pandas_engine.DataFrame(),
            ):
                self.logging.log("Fail!")

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
        self.logging.log("Sending to display...")
        self.display_manager = DisplayManager(self.config)
        self.show_image(target_filename)

    @staticmethod
    def get_next_file():
        return next(
            (
                element
                for element in [argument.lower() for argument in sys.argv[1:]]
                if "--" not in element
            ),
            "",
        )

    def show_image(self, target_filename: str):
        try:
            self.display_manager.show_image(target_filename)
        except Exception as exception:
            self.logging.log(f"Error sending photo to display: {exception}")
            raise

    def convert(
        self,
        filename: str,
        target_filename: str,
        photo,
    ):
        return_value = False

        self.auto_orient(filename)
        filename_pre = os.path.join(
            os.path.split(filename)[0], "pre_" + os.path.split(filename)[1]
        )
        self.copy_file(filename, filename_pre)
        self.plugins_preprocess(photo, filename_pre)
        error, width, height = ConvertManager().get_image_size(
            self.config.get("convert_bin_path"), filename_pre, Constants.FIRST_FRAME_GIF
        )

        self.logging.log("Processing the photo...")
        if (
            error
            or ConvertManager().convert_image(
                width,
                height,
                filename_pre + Constants.FIRST_FRAME_GIF,
                target_filename,
                self.config,
                DisplayManager.is_hdmi(self.config.get("display_type")),
            )
            is not None
        ):
            self.logging.log(f"Fail! {str(error)}")
        else:
            self.logging.log("Success!")

            self.plugins_postprocess(photo, target_filename)
            self.process_show_weather(target_filename)
            return_value = True
        return return_value

    def auto_orient(self, filename):
        if bool(self.config.getint("auto_orientation")):
            self.logging.log("Auto-orientate the photo...")
            error = ConvertManager().orient_image(
                self.config.get("convert_bin_path"), filename, Constants.FIRST_FRAME_GIF
            )

            if error:
                self.logging.log(f"Fail! {str(error)}")
                raise
            self.logging.log("Success!")

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
                self.logging.log(f"Preprocessing photo by plugin '{plugin.name}'...")
                plugin.preprocess_photo(
                    filename_pre,
                    bool(self.config.getint("horizontal")),
                    ConvertManager(),
                    photo,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                    Constants.PHOTOS_SOURCE_LABEL,
                )
                self.logging.log("Success!")
            except Exception as exception:
                self.logging.log(f"Error: {exception}")
                raise

    def plugins_postprocess(
        self,
        photo,
        targetFilename: str,
    ):
        for plugin in self.plugins_manager.plugin_postprocess():
            try:
                self.logging.log(f"Postprocessing photo by plugin '{plugin.name}'...")
                plugin.postprocess_photo(
                    targetFilename,
                    self.config.getint("image_width"),
                    self.config.getint("image_height"),
                    bool(self.config.getint("horizontal")),
                    ConvertManager(),
                    photo,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                    Constants.PHOTOS_SOURCE_LABEL,
                )
                self.logging.log("Success!")
            except Exception as exception:
                self.logging.log(f"Error: {exception}")
                raise

    def process_show_weather(self, target_filename: str):
        if bool(self.config.getint("show_weather")):
            self.logging.log("Getting weather data...")
            self.weather_manager = WeatherManager(
                self.config.get("apikey"),
                self.config.get("units"),
                self.config.get("lat"),
                self.config.get("lon"),
            )

            try:
                self.weather_manager.send_request(
                    Constants.WEATHER_BASE_URL, Constants.CHECK_CONNECTION_TIMEOUT
                )
                if not self.weather_manager.get_data():
                    raise Exception("Couldn't retrieve weather data!")
                self.logging.log("Success!")
                self.logging.log("Putting weather stamp...")
                self.weather_stamp_manager = WeatherStampManager(
                    target_filename,
                    self.config.getint("image_width"),
                    self.config.getint("image_height"),
                    bool(self.config.getint("horizontal")),
                    self.config.getint("font"),
                    self.config.get("font_color"),
                    self.config.getint("position"),
                    self.config.getint("rotation"),
                )
                self.weather_stamp_manager.compose(
                    float(
                        self.weather_manager.get_temperature(
                            Constants.WEATHER_TEMP_MAINTAG, Constants.WEATHER_TEMP_TAG
                        )
                    ),
                    self.config.get("units"),
                    self.weather_manager.get_weather_icon(
                        Constants.WEATHER_ICON_MAINTAG,
                        Constants.WEATHER_ICON_POSITION,
                        Constants.WEATHER_ICON_TAG,
                    ),
                )
                self.logging.log("Success!")
            except Exception as exception:
                self.logging.log(f"Fail! {str(exception)}")

    config = None
    logging = None
    photo_manager = None
    plugins_manager = None
    pid_manager = None
    index_manager = None
    display_manager = None
    interval_manager = None
    auth_manager = None
    album_manager = None
    database_manager = None
    users_manager = None
    local_source_manager = None
    random_manager = None
    weather_manager = None
    weather_stamp_manager = None


if __name__ == "__main__":
    EPiframe()
