#!/usr/bin/env python3

import atexit
import glob
import os
import shutil
import signal
import sys
from misc.connection import Connection
from misc.constants import Constants
from misc.logs import Logs
from modules.albummanager import AlbumManager
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


def main():
    if sys.version_info[0] < Constants.MINIMAL_PYTHON_VERSION:
        raise Exception(f"Must be using Python {Constants.MINIMAL_PYTHON_VERSION}!")

    print("ePiframe - e-Paper Raspberry Pi Photo Frame")

    if "--help" in [argument.lower() for argument in sys.argv]:
        print("Command line options:")
        print("--check-config		checks configuration file")
        print("--test			tests credentials, pickle file and downloads photo")
        print("			without sending it to the display")
        print("--test-display [file]	displays the photo file on attached display")
        print("			with current ePiframe configuration")
        print("--test-convert [file]	converts the photo file to configured")
        print("			photo_convert_filename current ePiframe configuration")
        print("--no-skip		like --test but is not skipping to another photo")
        print("--users			manage users")
        print("--help			this help")
    else:
        start_time = Logs.start_time()

        try:
            config = ConfigManager(Constants.CONFIG_FILE, Constants.CONFIG_FILE_DEFAULT)
        except Exception as exception:
            Logs.show_log(
                f"Error loading {Constants.CONFIG_FILE} configuration file! {exception}"
            )
            raise

        logging = Logs(config.get("log_files"))
        logging.log("Verifying configuration...")

        try:
            config.verify()
        except Warning as warning:
            logging.log(f"Warning verifying configuration file! {warning}")
            pass
        except Exception as exception:
            logging.log(f"Error verifying configuration file! {exception}")
            raise

        pid_manager = PIDManager(config.get("pid_file"))

        plugins_manager = PluginsManager(
            os.path.dirname(os.path.realpath(__file__)), pid_manager, logging, config
        )

        if len(plugins_manager.get_enabled()) > 0:
            logging.log("Verifying plugins configuration...")

            for plugin in plugins_manager.get_enabled():
                try:
                    plugin.config.verify()
                except Warning as warning:
                    logging.log(
                        f"Warning verifying configuration file for '{plugin.name}' plugin! {warning}"
                    )
                    pass
                except Exception as exception:
                    logging.log(
                        f"Error verifying configuration file for '{plugin.name}' plugin! {exception}"
                    )
                    raise
        logging.log("OK!")

        if "--check-config" in [argument.lower() for argument in sys.argv]:
            exit()

        if "--users" in [argument.lower() for argument in sys.argv]:
            logging.log(
                Constants.USERS_ACTIONS_TAG + "Starting database management module..."
            )
            try:
                database_manager = DatabaseManager()
                logging.log(Constants.USERS_ACTIONS_TAG + "Success!")
            except Exception as exception:
                logging.log(Constants.USERS_ACTIONS_TAG + f"Fail! {exception}")
                raise

            logging.log(
                Constants.USERS_ACTIONS_TAG + "Starting users management module..."
            )
            try:
                users_manager = UsersManager(database_manager)
                logging.log(Constants.USERS_ACTIONS_TAG + "Success!")
            except Exception as exception:
                logging.log(Constants.USERS_ACTIONS_TAG + f"Fail! {exception}")
                raise

            users_manager.manage(logging)
            exit()

        if (
            "--test" not in [argument.lower() for argument in sys.argv]
            and "--test-convert" not in [argument.lower() for argument in sys.argv]
            and "--no-skip" not in [argument.lower() for argument in sys.argv]
            and not DisplayManager.is_hdmi(config.get("display_type"))
        ):
            try:
                if not config.check_system():
                    raise Exception("SPI is disabled on system!")
            except Exception as exception:
                logging.log(
                    f"Error on checking system configuration - SPI is not enabled! {exception}"
                )
                raise

        try:
            last_pid = pid_manager.read()
            if int(last_pid) > 0:
                try:
                    if os.path.basename(__file__) in pid_manager.get_pid_name(last_pid):
                        os.kill(int(last_pid), signal.SIGKILL)
                except Exception:
                    pass
                pid_manager.remove()

            pid_manager.save()
            atexit.register(pid_manager.remove)
        except Exception as exception:
            logging.log(f"Error! {exception}")
            raise

        if (
            "--test-display" not in [argument.lower() for argument in sys.argv]
            and "--test-convert" not in [argument.lower() for argument in sys.argv]
            and "--users" not in [argument.lower() for argument in sys.argv]
        ):

            logging.log("Checking sources...")

            if not bool(config.getint("use_google_photos")) and not bool(
                config.getint("use_local")
            ):
                logging.log("No photo sources picked! Check the configuration!")
                raise Exception("No photo sources picked! Check the configuration!")

            logging.log("OK!")
            photo_manager = PhotoManager()
            photos = None

            if bool(config.getint("use_google_photos")):
                logging.log("Getting data from Google Photos source...")
                logging.log("Checking connection...")

                connection = Connection.check_internet(
                    Constants.SCOPES[0], Constants.CHECK_CONNECTION_TIMEOUT
                )
                if connection:
                    logging.log(f"Error! {connection} - No connection to the Internet")
                    if not bool(config.getint("use_local")):
                        raise Exception(
                            f"Error! {connection} - No connection to the Internet"
                        )
                    else:
                        logging.log("Continuing with local source...")
                else:
                    logging.log("OK!")

                    logging.log("Loading credentials...")
                    try:
                        auth_manager = OAuthManager()
                        auth_manager.manage_pickle(
                            config.get("pickle_file"),
                            config.get("cred_file"),
                            Constants.SCOPES,
                        )
                    except Exception as exception:
                        logging.log(f"Error! {exception}")
                        raise
                    logging.log("Success!")

                    logging.log("Trying to build service with given credentials...")
                    error = None
                    try:
                        auth_manager.build_service(
                            Constants.SERVICE_NAME, Constants.SERVICE_VERSION
                        )
                    except Exception as exception:
                        error = str(exception)

                    if error:
                        logging.log(f"Fail! {error}")
                        raise
                    else:
                        logging.log("Success!")

                        logging.log("Getting all albums...")
                        try:
                            auth_manager.get(
                                Constants.GOOGLE_PHOTOS_PAGESIZE,
                                bool(Constants.GOOGLE_PHOTOS_EXCLUDENONAPPCREATEDDATA),
                                Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER,
                                Constants.GOOGLE_PHOTOS_ALBUMS_RESPONSE,
                            )
                        except Exception as exception:
                            error = str(exception)

                        if error:
                            logging.log(f"Fail! {error}")
                            raise Exception(f"Fail! {error}")
                        else:
                            logging.log("Success!")

                            logging.log("Getting desired album(s)...")
                            album = AlbumManager(
                                auth_manager.get_response(),
                                config.get("album_names"),
                                Constants.GOOGLE_PHOTOS_ALBUMS_TITLE_HEADER,
                            )

                            if album.get_albums().empty:
                                logging.log(
                                    "Fail! Can't find album {}".format(
                                        config.get("album_names")
                                    )
                                )
                                raise Exception(
                                    "Fail! Can't find album {}".format(
                                        config.get("album_names")
                                    )
                                )
                            else:
                                logging.log("Success!")

                                logging.log("Fetching albums data...")
                                error = None
                                try:
                                    for index, album_id in album.get_albums()[
                                        Constants.GOOGLE_PHOTOS_ALBUMS_ID_HEADER
                                    ].iteritems():
                                        items = auth_manager.get_items(
                                            Constants.GOOGLE_PHOTOS_ALBUMS_ALBUMID_HEADER,
                                            album_id,
                                            Constants.GOOGLE_PHOTOS_ALBUMS_MEDIAITEMS_HEADER,
                                            Constants.GOOGLE_PHOTOS_PAGESIZE,
                                            Constants.GOOGLE_PHOTOS_PAGESIZE_HEADER,
                                            Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_HEADER,
                                            Constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER,
                                        )
                                        album.append_data(items)
                                except Exception as exception:
                                    error = str(exception)

                                if error:
                                    logging.log(f"Fail! {error}")
                                    raise
                                elif album.get_data().empty:
                                    logging.log("Fail! Couldn't retrieve albums!")
                                    raise
                                else:
                                    photos = photo_manager.set_photos(
                                        album,
                                        Constants.GOOGLE_PHOTOS_ALBUMS_MEDIAMETADATA_HEADER,
                                        Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_HEADER,
                                        Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER,
                                        Constants.IMAGE_MIMETYPE_STARTING_STRING,
                                        Constants.PHOTOS_SOURCE_LABEL,
                                        Constants.GOOGLE_PHOTOS_SOURCE,
                                    )
                                    logging.log("Success!")

            if bool(config.getint("use_local")):
                logging.log("Getting data from local source...")
                local_source_manager = LocalSourceManager(
                    config.get("local_path"),
                    bool(config.getint("local_subfolders")),
                    Constants.EXTENSIONS,
                )
                local_photos = local_source_manager.get_local_photos(
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                    Constants.PHOTOS_SOURCE_LABEL,
                    Constants.LOCAL_SOURCE,
                )
                photos = photo_manager.append_photos(photos, local_photos)
                logging.log("Success!")

            for plugin in plugins_manager.plugin_source():
                try:
                    logging.log(f"Getting data from plugin '{plugin.name}' source...")
                    plugin_photos = plugin.add_photo_source(
                        Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                        Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                        Constants.PHOTOS_SOURCE_LABEL,
                        photo_manager,
                    )
                    photos = photo_manager.append_photos(photos, plugin_photos)
                    logging.log("Success!")
                except Exception as exception:
                    logging.log(f"Error: {exception}")
                    raise

            # get number of photos available from the album
            total_number = (
                photo_manager.get_num_of_photos(photos) if photos is not None else 0
            )
            logging.log(f"Found {total_number} photos")

            # exit if no photos
            if total_number == 0:
                logging.log("No photos in albums!")
            else:
                logging.log("Reading last photo index file...")

                # read index from file to change after each run
                try:
                    index_manager = IndexManager(config.get("photo_index_file"))
                except IOError as exception:
                    logging.log(
                        "Error opening file {}: {}".format(
                            config.get("photo_index_file"), exception
                        )
                    )
                    raise
                logging.log("Success!")

                logging.log("Filtering photos...")
                # filter photos by from date
                if config.get("photos_from"):
                    try:
                        photos = FilteringManager.filter_by_from_date(
                            photos,
                            config.get("photos_from"),
                            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                        )
                    except Exception as exception:
                        logging.log(
                            f"Error parsing configured time photos_from: {exception}"
                        )
                        raise

                # filter photos by to date
                if config.get("photos_to"):
                    try:
                        photos = FilteringManager.filter_by_to_date(
                            photos,
                            config.get("photos_to"),
                            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                        )
                    except Exception as exception:
                        logging.log(
                            f"Error parsing configured time photos_to: {exception}"
                        )
                        raise

                # filter photos by number
                if config.get("no_photos"):
                    try:
                        photos = FilteringManager.filter_by_number(
                            photos, config.getint("no_photos")
                        )
                    except Exception as exception:
                        logging.log(
                            f"Error parsing configured time no_photos: {exception}"
                        )
                        raise

                logging.log("and sorting ...")
                # photos sorting
                photos = FilteringManager.sort(
                    photos,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                    photos[Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER],
                    config.get("sorting"),
                )
                # update index
                photos = photo_manager.reset_index(photos)

                for plugin in plugins_manager.plugin_photos_list():
                    try:
                        logging.log(f"Changing photo list by plugin '{plugin.name}'...")
                        photos = plugin.change_photos_list(
                            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                            Constants.PHOTOS_SOURCE_LABEL,
                            photos,
                            photo_manager,
                            index_manager,
                            FilteringManager(),
                        )
                        logging.log("Success!")
                    except Exception as exception:
                        logging.log(f"Error: {exception}")
                        raise

                # get number of photos available from the album
                filter_number = photo_manager.get_num_of_photos(photos)
                logging.log(f"Filtered {filter_number} photos")

                # exit if no photos
                if filter_number == 0:
                    logging.log("No photos after filtering!")
                else:
                    if not bool(config.getint("randomize")):
                        # find previous photo
                        photo_id = next(
                            iter(
                                photos[
                                    photo_manager.get_photos_attribute(
                                        photos,
                                        Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                                    )
                                    == index_manager.get_id()
                                ].index
                            ),
                            Constants.NOMATCH_INDICATOR_STRING,
                        )

                        if photo_id != Constants.NOMATCH_INDICATOR_STRING:
                            index_manager.set_index(photo_id + 1)
                        else:
                            index_manager.set_index(index_manager.get_index() + 1)

                        # don't go above the number of photos
                        index_manager.check_index(filter_number)
                    else:
                        # get random photo
                        random_manager = RandomManager(
                            config.get("photo_list_file"),
                            photos,
                            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                        )
                        index_manager.set_index(
                            random_manager.get_random(
                                index_manager.get_id(),
                                "--no-skip"
                                in [argument.lower() for argument in sys.argv],
                            )
                        )

                    # get filename + extension, download url and download file
                    photo = photo_manager.get_photo_by_index(
                        photos, index_manager.get_index()
                    )
                    logging.log(f"Photo to show:\n{photo}")

                    index_manager.set_id(
                        photo_manager.get_photo_attribute(
                            photo, Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER
                        )
                    )

                    for old_file in glob.glob(
                        os.path.join(
                            config.get("photo_convert_path"),
                            config.get("photo_download_name"),
                        )
                        + ".*"
                    ):
                        os.remove(old_file)

                    logging.log("Getting next photo...")
                    returned_value = None
                    if (
                        photo[Constants.PHOTOS_SOURCE_LABEL]
                        == Constants.GOOGLE_PHOTOS_SOURCE
                    ):
                        filename = (
                            config.get("photo_download_name")
                            + "."
                            + Constants.TYPE_TO_EXTENSION[
                                photo_manager.get_photo_attribute(
                                    photo,
                                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER,
                                )
                            ]
                        )

                        download_url = (
                            photo_manager.get_photo_attribute(
                                photo,
                                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_BASEURL_HEADER,
                            )
                            + Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_GET_DETAILS
                        )

                        try:
                            returned_value = Connection.download_file(
                                download_url,
                                config.get("photo_convert_path"),
                                filename,
                                Constants.OK_STATUS_ERRORCODE,
                                Constants.CHECK_CONNECTION_TIMEOUT,
                            )
                        except Exception as exception:
                            returned_value = str(exception)

                        if returned_value != Constants.OK_STATUS_ERRORCODE:
                            logging.log(f"Fail! Server error: {str(returned_value)}")
                    else:
                        plugin_with_source = next(
                            (
                                plugin
                                for plugin in plugins_manager.get_plugin_source()
                                if plugin.SOURCE == photo[Constants.PHOTOS_SOURCE_LABEL]
                            ),
                            None,
                        )

                        if (
                            plugin_with_source
                            and plugins_manager.plugin_source_get_file(
                                plugin_with_source
                            )
                        ):
                            filename = plugin_with_source.add_photo_source_get_file(
                                photo,
                                config.get("photo_convert_path"),
                                config.get("photo_download_name"),
                                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                                Constants.PHOTOS_SOURCE_LABEL,
                                photo_manager,
                            )
                        else:
                            source_file = photo[
                                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER
                            ]
                            error, image_type = ConvertManager().get_image_format(
                                config.get("convert_bin_path"),
                                source_file,
                                Constants.FIRST_FRAME_GIF,
                            )

                            filename = (
                                config.get("photo_download_name")
                                + "."
                                + str(source_file).rsplit(".")[-1].lower()
                            )
                            if not error and image_type:
                                try:
                                    filename = (
                                        config.get("photo_download_name")
                                        + "."
                                        + Constants.TYPE_TO_EXTENSION[
                                            Constants.MIME_START + image_type.lower()
                                        ]
                                    )
                                except Exception:
                                    pass

                            filename = os.path.join(
                                config.get("photo_convert_path"), filename
                            )
                            try:
                                shutil.copy(source_file, filename)
                            except Exception:
                                pass

                    if not os.path.exists(filename):
                        logging.log(
                            f"Fail! File was not retrieved! : {str(returned_value)}"
                        )
                    else:
                        logging.log("Success!")

                        interval_multiplication(config, filename, photo, photo_manager)

                        # save index of current photo for next run
                        try:
                            if "--no-skip" not in [
                                argument.lower() for argument in sys.argv
                            ]:
                                index_manager.save()
                        except IOError as exception:
                            logging.log(
                                "Error saving file {}: {}".format(
                                    config.get("photo_index_file"), exception
                                )
                            )
                            raise

                        convert_file(config, filename, logging, photo, plugins_manager)

        if "--test-convert" in [argument.lower() for argument in sys.argv]:
            test_convert(config, logging, plugins_manager)

        if "--test-display" in [argument.lower() for argument in sys.argv]:
            test_display(config, logging)

        end_time = Logs.end_time()
        logging.log(f"Done in{Logs.execution_time(start_time, end_time)}")


def interval_multiplication(
    config: ConfigManager, filename: str, photo, photo_manager: PhotoManager
):
    if bool(config.getint("interval_mult")):
        # if photo comment contains hot word then multiply interval by its value and photo will
        # be displayed longer
        interval_manager = IntervalManager(config.get("interval_mult_file"))
        if "--no-skip" not in [argument.lower() for argument in sys.argv]:
            interval_manager.remove()
        try:
            if "--no-skip" not in [argument.lower() for argument in sys.argv]:
                if (
                    photo[Constants.PHOTOS_SOURCE_LABEL]
                    == Constants.GOOGLE_PHOTOS_SOURCE
                ):
                    comment = str(
                        photo_manager.get_photo_attribute(
                            photo,
                            Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_DESCRIPTION_HEADER,
                        )
                    )
                else:
                    (error, comment,) = ConvertManager().get_image_comment(
                        config.get("convert_bin_path"), filename
                    )
                interval_manager.save_interval(
                    comment,
                    config.get("interval_mult_hotword"),
                    config.getint("interval_max_mult"),
                )
        except Exception:
            pass


def convert_file(
    config: ConfigManager,
    filename: str,
    logging: Logs,
    photo,
    plugins_manager: PluginsManager,
):
    target_filename = os.path.join(
        config.get("photo_convert_path"),
        config.get("photo_convert_filename"),
    )
    if convert(
        filename,
        target_filename,
        config,
        plugins_manager,
        logging,
        photo,
    ):
        if "--test" not in [
            argument.lower() for argument in sys.argv
        ] and "--no-skip" not in [argument.lower() for argument in sys.argv]:
            send_to_display(config, logging, target_filename)
    else:
        logging.log("Fail!")


def send_to_display(config: ConfigManager, logging: Logs, target_filename: str):
    logging.log("Sending to display...")
    display_manager = DisplayManager(config)
    try:
        display_manager.show_image(target_filename)
    except Exception as exception:
        logging.log(f"Error sending photo to display: {exception}")
        raise


def test_convert(config: ConfigManager, logging: Logs, plugins_manager: PluginsManager):
    filename = os.path.join(
        config.get("photo_convert_path"), config.get("photo_download_name")
    )
    target_filename = os.path.join(
        config.get("photo_convert_path"), config.get("photo_convert_filename")
    )
    file = next(
        (
            variable
            for variable in [argument.lower() for argument in sys.argv[1:]]
            if "--" not in variable
        ),
        "",
    )
    returned_value = None
    if file:
        filename = file
    else:
        files = glob.glob(f"{filename}.*")
        if not files:
            raise Exception(f"No file: {filename}.*!")
        file = max(files, key=os.path.getctime)
        filename = file
    if not os.path.exists(filename):
        raise Exception(f"No file: {filename}!")
    error, image_type = ConvertManager().get_image_format(
        config.get("convert_bin_path"), filename, Constants.FIRST_FRAME_GIF
    )
    source = (
        config.get("photo_download_name") + "." + str(filename).rsplit(".")[-1].lower()
    )
    if not error and image_type:
        try:
            source = (
                config.get("photo_download_name")
                + "."
                + Constants.TYPE_TO_EXTENSION[Constants.MIME_START + image_type.lower()]
            )
        except Exception as exception:
            returned_value = str(exception)
    try:
        shutil.copy(filename, source)
    except Exception:
        pass
    if not os.path.exists(source):
        logging.log(f"Fail! File was not retrieved! : {str(returned_value)}")
    else:
        import pandas as pandas_engine

        if not convert(
            source,
            target_filename,
            config,
            plugins_manager,
            logging,
            pandas_engine.DataFrame(),
        ):
            logging.log("Fail!")


def test_display(config: ConfigManager, logging: Logs):
    target_filename = os.path.join(
        config.get("photo_convert_path"), config.get("photo_convert_filename")
    )
    file = next(
        (
            element
            for element in [argument.lower() for argument in sys.argv[1:]]
            if "--" not in element
        ),
        "",
    )
    if file:
        target_filename = file
    if not os.path.exists(target_filename):
        raise Exception(f"No file: {target_filename}!")
    logging.log("Sending to display...")
    display_manager = DisplayManager(config)
    try:
        display_manager.show_image(target_filename)
    except Exception as exception:
        logging.log(f"Error sending photo to display: {exception}")
        raise


def convert(
    _filename: str,
    _targetFilename: str,
    _config: ConfigManager,
    _plugins: PluginsManager,
    _logging: Logs,
    _photo,
):
    return_value = False

    if bool(_config.getint("auto_orientation")):
        _logging.log("Auto-orientate the photo...")
        error = ConvertManager().orient_image(
            _config.get("convert_bin_path"), _filename, Constants.FIRST_FRAME_GIF
        )

        if error:
            _logging.log(f"Fail! {str(error)}")
            raise
        else:
            _logging.log("Success!")

    filename_pre = os.path.join(
        os.path.split(_filename)[0], "pre_" + os.path.split(_filename)[1]
    )
    try:
        shutil.copy(_filename, filename_pre)
    except Exception:
        pass

    for plugin in _plugins.plugin_preprocess():
        try:
            _logging.log(f"Preprocessing photo by plugin '{plugin.name}'...")
            plugin.preprocess_photo(
                filename_pre,
                bool(_config.getint("horizontal")),
                ConvertManager(),
                _photo,
                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                Constants.PHOTOS_SOURCE_LABEL,
            )
            _logging.log("Success!")
        except Exception as exception:
            _logging.log(f"Error: {exception}")
            raise

    error, width, height = ConvertManager().get_image_size(
        _config.get("convert_bin_path"), filename_pre, Constants.FIRST_FRAME_GIF
    )

    _logging.log("Processing the photo...")
    # convert image
    if (
        error
        or ConvertManager().convert_image(
            width,
            height,
            filename_pre + Constants.FIRST_FRAME_GIF,
            _targetFilename,
            _config,
            DisplayManager.is_hdmi(_config.get("display_type")),
        )
        is not None
    ):
        _logging.log(f"Fail! {str(error)}")
    else:
        _logging.log("Success!")

        for plugin in _plugins.plugin_postprocess():
            try:
                _logging.log(f"Postprocessing photo by plugin '{plugin.name}'...")
                plugin.postprocess_photo(
                    _targetFilename,
                    _config.getint("image_width"),
                    _config.getint("image_height"),
                    bool(_config.getint("horizontal")),
                    ConvertManager(),
                    _photo,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER,
                    Constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,
                    Constants.PHOTOS_SOURCE_LABEL,
                )
                _logging.log("Success!")
            except Exception as exception:
                _logging.log(f"Error: {exception}")
                raise

        if bool(_config.getint("show_weather")):
            _logging.log("Getting weather data...")
            weatherman = WeatherManager(
                _config.get("apikey"),
                _config.get("units"),
                _config.get("lat"),
                _config.get("lon"),
            )

            try:
                weatherman.send_request(
                    Constants.WEATHER_BASE_URL, Constants.CHECK_CONNECTION_TIMEOUT
                )
                if not weatherman.get_data():
                    raise Exception("Couldn't retrieve weather data!")
                _logging.log("Success!")
                _logging.log("Putting weather stamp...")
                weather_stamp_manager = WeatherStampManager(
                    _targetFilename,
                    _config.getint("image_width"),
                    _config.getint("image_height"),
                    bool(_config.getint("horizontal")),
                    _config.getint("font"),
                    _config.get("font_color"),
                    _config.getint("position"),
                    _config.getint("rotation"),
                )
                weather_stamp_manager.compose(
                    float(
                        weatherman.get_temperature(
                            Constants.WEATHER_TEMP_MAINTAG, Constants.WEATHER_TEMP_TAG
                        )
                    ),
                    _config.get("units"),
                    weatherman.get_weather_icon(
                        Constants.WEATHER_ICON_MAINTAG,
                        Constants.WEATHER_ICON_POSITION,
                        Constants.WEATHER_ICON_TAG,
                    ),
                )
                _logging.log("Success!")
            except Exception as exception:
                _logging.log(f"Fail! {str(exception)}")
        return_value = True
    return return_value


if __name__ == "__main__":
    main()
