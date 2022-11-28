import subprocess
from modules.filteringmanager import FilteringManager
from modules.timermanager import TimerManager
from modules.weathermanager import WeatherManager
from modules.weatherstampmanager import WeatherStampManager
from modules.telebotmanager import TelebotManager
from modules.convertmanager import ConvertManager
from modules.localsourcemanager import LocalSourceManager
from modules.displaymanager import DisplayManager
from modules.base.configbase import ConfigBase
from misc.configproperty import ConfigProperty
from misc.connection import Connection


class ConfigManager(ConfigBase):
    __SPI_CHECK1 = "ls -l /dev/spidev*"
    __SPI_CHECK2 = "lsmod | grep spi_"

    def load_settings(self):
        self.SETTINGS = [
            ConfigProperty(
                "use_google_photos", self, prop_type=ConfigProperty.BOOLEAN_TYPE
            ),
            ConfigProperty(
                "cred_file",
                self,
                prop_type=ConfigProperty.FILE_TYPE,
                dependency="use_google_photos",
            ),
            ConfigProperty(
                "pickle_file",
                self,
                prop_type=ConfigProperty.FILE_TYPE,
                dependency="use_google_photos",
            ),
            ConfigProperty(
                "album_names", self, not_empty=False, dependency="use_google_photos"
            ),
            ConfigProperty("use_local", self, prop_type=ConfigProperty.BOOLEAN_TYPE),
            ConfigProperty(
                "local_path",
                self,
                prop_type=ConfigProperty.FILE_TYPE,
                dependency="use_local",
                convert=LocalSourceManager.create_directory,
            ),
            ConfigProperty(
                "local_subfolders",
                self,
                prop_type=ConfigProperty.BOOLEAN_TYPE,
                dependency="use_local",
            ),
            ConfigProperty("units", self, possible=WeatherManager.get_units()),
            ConfigProperty(
                "photo_convert_path", self, prop_type=ConfigProperty.FILE_TYPE
            ),
            ConfigProperty("log_files", self, not_empty=False),
            ConfigProperty(
                "convert_bin_path", self, prop_type=ConfigProperty.FILE_TYPE
            ),
            ConfigProperty(
                "rrdtool_bin_path", self, prop_type=ConfigProperty.FILE_TYPE
            ),
            ConfigProperty("fbi_bin_path", self, prop_type=ConfigProperty.FILE_TYPE),
            ConfigProperty(
                "display_type", self, possible=DisplayManager.get_displays()
            ),
            ConfigProperty(
                "display", self, dependency=["display_type", DisplayManager.get_spi()]
            ),
            ConfigProperty(
                "tty",
                self,
                minvalue=0,
                prop_type=ConfigProperty.INTEGER_TYPE,
                dependency=["display_type", DisplayManager.get_hdmi()],
            ),
            ConfigProperty(
                "slide_interval",
                self,
                minvalue=180,
                prop_type=ConfigProperty.FLOAT_TYPE,
            ),
            ConfigProperty(
                "interval_mult", self, prop_type=ConfigProperty.BOOLEAN_TYPE
            ),
            ConfigProperty("interval_mult_hotword", self, dependency="interval_mult"),
            ConfigProperty(
                "interval_max_mult",
                self,
                dependency="interval_mult",
                minvalue=1,
                prop_type=ConfigProperty.INTEGER_TYPE,
            ),
            ConfigProperty(
                "start_times",
                self,
                delimiter=",",
                prop_type=ConfigProperty.STRING_LIST_TYPE,
                length=7,
                special=ConfigProperty.Special(
                    TimerManager.verify, ["start_times", "stop_times"]
                ),
            ),
            ConfigProperty(
                "stop_times",
                self,
                delimiter=",",
                prop_type=ConfigProperty.STRING_LIST_TYPE,
                length=7,
                special=ConfigProperty.Special(
                    TimerManager.verify, ["start_times", "stop_times"]
                ),
            ),
            ConfigProperty(
                "control_display_power",
                self,
                prop_type=ConfigProperty.BOOLEAN_TYPE,
                dependency=["display_type", DisplayManager.get_hdmi()],
            ),
            ConfigProperty(
                "allow_triggers", self, prop_type=ConfigProperty.BOOLEAN_TYPE
            ),
            ConfigProperty(
                "convert_option",
                self,
                prop_type=ConfigProperty.INTEGER_TYPE,
                possible=ConvertManager.get_convert_options(),
                dependency=["display_type", DisplayManager.get_spi()],
            ),
            ConfigProperty(
                "image_width", self, minvalue=1, prop_type=ConfigProperty.INTEGER_TYPE
            ),
            ConfigProperty(
                "image_height", self, minvalue=1, prop_type=ConfigProperty.INTEGER_TYPE
            ),
            ConfigProperty(
                "invert_colors", self, prop_type=ConfigProperty.BOOLEAN_TYPE
            ),
            ConfigProperty(
                "grayscale",
                self,
                prop_type=ConfigProperty.BOOLEAN_TYPE,
                dependency=["display_type", DisplayManager.get_hdmi()],
            ),
            ConfigProperty(
                "colors_num",
                self,
                minvalue=1,
                not_empty=False,
                prop_type=ConfigProperty.INTEGER_TYPE,
                dependency=["display_type", DisplayManager.get_hdmi()],
            ),
            ConfigProperty("horizontal", self, prop_type=ConfigProperty.BOOLEAN_TYPE),
            ConfigProperty(
                "auto_orientation", self, prop_type=ConfigProperty.BOOLEAN_TYPE
            ),
            ConfigProperty(
                "turned",
                self,
                prop_type=ConfigProperty.BOOLEAN_TYPE,
                dependency="horizontal",
            ),
            ConfigProperty(
                "rotation",
                self,
                prop_type=ConfigProperty.INTEGER_TYPE,
                dependency=["horizontal", "0"],
                possible=ConvertManager.get_rotation(),
            ),
            ConfigProperty("auto_gamma", self, prop_type=ConfigProperty.BOOLEAN_TYPE),
            ConfigProperty("auto_level", self, prop_type=ConfigProperty.BOOLEAN_TYPE),
            ConfigProperty("normalize", self, prop_type=ConfigProperty.BOOLEAN_TYPE),
            ConfigProperty(
                "brightness",
                self,
                minvalue=-100,
                maxvalue=100,
                prop_type=ConfigProperty.INTEGER_TYPE,
            ),
            ConfigProperty(
                "contrast",
                self,
                minvalue=-100,
                maxvalue=100,
                prop_type=ConfigProperty.INTEGER_TYPE,
            ),
            ConfigProperty(
                "background_color",
                self,
                possible=ConvertManager.get_background_colors(),
            ),
            ConfigProperty("randomize", self, prop_type=ConfigProperty.BOOLEAN_TYPE),
            ConfigProperty(
                "photos_from",
                self,
                not_empty=False,
                convert=FilteringManager.convert,
                check_function=FilteringManager.verify,
                special=ConfigProperty.Special(
                    FilteringManager.verify_times, ["photos_from", "photos_to"]
                ),
            ),
            ConfigProperty(
                "photos_to",
                self,
                not_empty=False,
                convert=FilteringManager.convert,
                check_function=FilteringManager.verify,
                special=ConfigProperty.Special(
                    FilteringManager.verify_times, ["photos_from", "photos_to"]
                ),
            ),
            ConfigProperty(
                "no_photos",
                self,
                minvalue=1,
                not_empty=False,
                prop_type=ConfigProperty.INTEGER_TYPE,
            ),
            ConfigProperty("sorting", self, possible=FilteringManager.get_sorting()),
            ConfigProperty("show_weather", self, prop_type=ConfigProperty.BOOLEAN_TYPE),
            ConfigProperty("apikey", self, dependency="show_weather"),
            ConfigProperty("lat", self, dependency="show_weather"),
            ConfigProperty("lon", self, dependency="show_weather"),
            ConfigProperty(
                "position",
                self,
                dependency="show_weather",
                prop_type=ConfigProperty.INTEGER_TYPE,
                possible=WeatherStampManager.get_positions(),
            ),
            ConfigProperty(
                "font",
                self,
                dependency="show_weather",
                minvalue=8,
                prop_type=ConfigProperty.INTEGER_TYPE,
            ),
            ConfigProperty(
                "font_color",
                self,
                dependency="show_weather",
                possible=WeatherStampManager.get_colors(),
            ),
            ConfigProperty(
                "use_telebot",
                self,
                prop_type=ConfigProperty.BOOLEAN_TYPE,
                reset_needed=True,
            ),
            ConfigProperty(
                "token",
                self,
                dependency="use_telebot",
                check_function=TelebotManager.check_token,
            ),
            ConfigProperty(
                "chat_id",
                self,
                not_empty=False,
                dependency="use_telebot",
                delimiter=",",
                prop_type=ConfigProperty.INT_LIST_TYPE,
            ),
            ConfigProperty(
                "use_web",
                self,
                prop_type=ConfigProperty.BOOLEAN_TYPE,
                reset_needed=True,
            ),
            ConfigProperty(
                "web_host", self, dependency="use_web", check_function=Connection.is_ip
            ),
            ConfigProperty(
                "web_port",
                self,
                minvalue=1,
                maxvalue=65535,
                dependency="use_web",
                prop_type=ConfigProperty.INTEGER_TYPE,
            ),
            ConfigProperty(
                "show_stats",
                self,
                dependency="use_web",
                prop_type=ConfigProperty.BOOLEAN_TYPE,
            ),
            ConfigProperty(
                "dark_theme",
                self,
                dependency="use_web",
                prop_type=ConfigProperty.BOOLEAN_TYPE,
            ),
        ]

    def legacy_convert(self):
        # legacy exceptional backward handling for converting one property to another property under different name
        # and the ones that convert could not handle
        legacy = [
            type(
                "",
                (),
                {
                    "old": ["Album settings", "sort_desc"],
                    "new": ["Filtering", "sorting"],
                    "convert": FilteringManager.get_descending,
                },
            )
        ]

        for setting in legacy:
            try:
                if not self.config.has_section(setting.new[0]):
                    self.config.add_section(setting.new[0])
                val = self.config.get(setting.old[0], setting.old[1])
                self.config.set(setting.new[0], setting.new[1], setting.convert(val))
            except Exception:
                pass

    # end

    def check_system(self):
        return_value = False

        process = subprocess.Popen(
            self.__SPI_CHECK1, shell=True, stdout=subprocess.PIPE
        )
        process.wait()
        out, error = process.communicate()

        process = subprocess.Popen(
            self.__SPI_CHECK2, shell=True, stdout=subprocess.PIPE
        )
        process.wait()
        out2, error2 = process.communicate()

        if not error and out2:
            return_value = True

        return return_value
