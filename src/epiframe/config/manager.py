"""Settings of ePiframe itself (``config.cfg``).

The option lists and validators still come from 1.x modules; the imports switch
to ``epiframe.*`` as those modules are ported (Phase 3).
"""

from typing import TypedDict

from epiframe.config.base import ConfigBase, LegacyEntry
from epiframe.config.property import ConfigProperty, CrossCheck, PropertyType
from epiframe.core import schedule
from epiframe.core.network import validate_ip
from epiframe.display.options import Background
from epiframe.photos import selection
from epiframe.processing import imagemagick
from epiframe.sources import drive
from epiframe.sources.local import create_directory
from modules.displaymanager import DisplayManager
from modules.telebotmanager import TelebotManager
from modules.weathermanager import WeatherManager
from modules.weatherstampmanager import WeatherStampManager

BOOLEAN = PropertyType.BOOLEAN
INTEGER = PropertyType.INTEGER


class _Dependency(TypedDict):
    dependency: str
    dependency_value: str


def _on_display(display_type: str) -> _Dependency:
    """Make an entry active only for the given ``display_type``."""
    return {"dependency": "display_type", "dependency_value": display_type}


def _source_settings() -> list[ConfigProperty]:
    return [
        ConfigProperty("use_local", BOOLEAN),
        ConfigProperty(
            "local_path",
            PropertyType.FILE,
            dependency="use_local",
            convert=create_directory,
        ),
        ConfigProperty("local_subfolders", BOOLEAN, dependency="use_local"),
        ConfigProperty("use_drive", BOOLEAN),
        ConfigProperty(
            "drive_folders",
            PropertyType.STRING_LIST,
            dependency="use_drive",
            delimiter=",",
            check=drive.folder_ids,
        ),
        ConfigProperty("drive_key_file", PropertyType.FILE, dependency="use_drive"),
        ConfigProperty("drive_subfolders", BOOLEAN, dependency="use_drive"),
    ]


def _general_settings() -> list[ConfigProperty]:
    return [
        ConfigProperty("units", possible=WeatherManager.get_units()),
        ConfigProperty("photo_convert_path", PropertyType.FILE),
        ConfigProperty("log_files", not_empty=False),
        ConfigProperty("convert_bin_path", PropertyType.FILE),
        ConfigProperty("rrdtool_bin_path", PropertyType.FILE),
        ConfigProperty("fbi_bin_path", PropertyType.FILE),
    ]


def _display_settings() -> list[ConfigProperty]:
    spi = _on_display(DisplayManager.get_spi())
    hdmi = _on_display(DisplayManager.get_hdmi())
    timer_check = CrossCheck(schedule.verify, ("start_times", "stop_times"))
    return [
        ConfigProperty("display_type", possible=DisplayManager.get_displays()),
        ConfigProperty("epaper_type", possible=DisplayManager.get_epapers(), **spi),
        ConfigProperty("epaper_color", possible=DisplayManager.get_colors(), **spi),
        ConfigProperty("display", **spi),
        ConfigProperty("clear_display", BOOLEAN, **spi),
        ConfigProperty("tty", INTEGER, min_value=0, **hdmi),
        ConfigProperty("slide_interval", INTEGER, min_value=180),
        ConfigProperty("interval_mult", BOOLEAN),
        ConfigProperty("interval_mult_hotword", dependency="interval_mult"),
        ConfigProperty(
            "interval_max_mult", INTEGER, dependency="interval_mult", min_value=1
        ),
        *(
            ConfigProperty(
                name,
                PropertyType.STRING_LIST,
                delimiter=",",
                length=7,
                cross_check=timer_check,
            )
            for name in ("start_times", "stop_times")
        ),
        ConfigProperty("control_display_power", BOOLEAN, **hdmi),
        ConfigProperty("allow_triggers", BOOLEAN),
    ]


def _image_settings() -> list[ConfigProperty]:
    spi = _on_display(DisplayManager.get_spi())
    hdmi = _on_display(DisplayManager.get_hdmi())
    return [
        ConfigProperty("convert", BOOLEAN),
        ConfigProperty(
            "convert_option",
            INTEGER,
            possible=imagemagick.CONVERT_OPTIONS,
            **spi,
        ),
        ConfigProperty("image_width", INTEGER, min_value=1),
        ConfigProperty("image_height", INTEGER, min_value=1),
        ConfigProperty("grayscale", BOOLEAN, **hdmi),
        ConfigProperty("colors_num", INTEGER, min_value=1, not_empty=False, **hdmi),
        ConfigProperty("invert_colors", BOOLEAN),
        ConfigProperty("background_color", possible=Background.values()),
        ConfigProperty("auto_orientation", BOOLEAN),
        ConfigProperty("horizontal", BOOLEAN),
        ConfigProperty("turned", BOOLEAN, dependency="horizontal"),
        ConfigProperty(
            "rotation",
            INTEGER,
            dependency="horizontal",
            dependency_value="0",
            possible=imagemagick.ROTATIONS,
        ),
        ConfigProperty("auto_gamma", BOOLEAN),
        ConfigProperty("auto_level", BOOLEAN),
        ConfigProperty("normalize", BOOLEAN),
        ConfigProperty("brightness", INTEGER, min_value=-100, max_value=100),
        ConfigProperty("contrast", INTEGER, min_value=-100, max_value=100),
        ConfigProperty(
            "pimoroni_saturation",
            PropertyType.FLOAT,
            min_value=0.0,
            max_value=0.99,
            dependency="epaper_type",
            dependency_value=DisplayManager.get_pimoroni(),
        ),
    ]


def _filtering_settings() -> list[ConfigProperty]:
    times_check = CrossCheck(selection.verify_range, ("photos_from", "photos_to"))
    return [
        ConfigProperty("randomize", BOOLEAN),
        *(
            ConfigProperty(
                name,
                not_empty=False,
                convert=selection.convert_legacy_date,
                check=selection.verify_date,
                cross_check=times_check,
            )
            for name in ("photos_from", "photos_to")
        ),
        ConfigProperty("no_photos", INTEGER, min_value=1, not_empty=False),
        ConfigProperty("sorting", possible=selection.Sorting.values()),
    ]


def _weather_settings() -> list[ConfigProperty]:
    return [
        ConfigProperty("show_weather", BOOLEAN),
        ConfigProperty("apikey", dependency="show_weather"),
        ConfigProperty("lat", dependency="show_weather"),
        ConfigProperty("lon", dependency="show_weather"),
        ConfigProperty(
            "position",
            INTEGER,
            dependency="show_weather",
            possible=WeatherStampManager.get_positions(),
        ),
        ConfigProperty("font", INTEGER, dependency="show_weather", min_value=8),
        ConfigProperty(
            "font_color",
            dependency="show_weather",
            possible=WeatherStampManager.get_colors(),
        ),
    ]


def _telegram_settings() -> list[ConfigProperty]:
    return [
        ConfigProperty("use_telebot", BOOLEAN, reset_needed=True),
        ConfigProperty(
            "token", dependency="use_telebot", check=TelebotManager.check_token
        ),
        ConfigProperty(
            "chat_id",
            PropertyType.INT_LIST,
            not_empty=False,
            dependency="use_telebot",
            delimiter=",",
        ),
    ]


def _web_settings() -> list[ConfigProperty]:
    return [
        ConfigProperty("use_web", BOOLEAN, reset_needed=True),
        ConfigProperty("web_host", dependency="use_web", check=validate_ip),
        ConfigProperty(
            "web_port", INTEGER, dependency="use_web", min_value=1, max_value=65535
        ),
        ConfigProperty("show_stats", BOOLEAN, dependency="use_web"),
        ConfigProperty("dark_theme", BOOLEAN, dependency="use_web"),
    ]


class ConfigManager(ConfigBase):
    """``config.cfg`` of the frame."""

    LEGACY = (
        # 1.x "Album settings" sort_desc=0/1 became "Filtering" sorting=asc/desc
        LegacyEntry("sort_desc", "sorting", selection.sorting_from_sort_desc),
    )

    def load_settings(self) -> list[ConfigProperty]:
        return [
            *_source_settings(),
            *_general_settings(),
            *_display_settings(),
            *_image_settings(),
            *_filtering_settings(),
            *_weather_settings(),
            *_telegram_settings(),
            *_web_settings(),
        ]
