import os
import subprocess
from unittest.mock import patch
from modules.configmanager import ConfigManager
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import remove_file, not_raises

filename = "config_test.cfg"
default_path = f"{os.path.dirname(os.path.realpath(__file__))}/../misc/config.default"


def test_no_file():
    remove_file(filename)
    config: ConfigManager = ConfigManager(
        path=filename,
        default_path=default_path,
    )

    assert config.get_sections() == [
        "Sources",
        "General",
        "Display",
        "Image",
        "Filtering",
        "Weather",
        "Telegram bot",
        "Web interface",
    ]
    assert config.getint("use_google_photos") == 1
    assert config.get("units") == "metric"
    assert (
        config.get_comment("convert_bin_path")
        == "Path and name of the ImageMagick convert tool binary.  Default: /usr/bin/convert"
    )
    assert config.get_path() == filename
    assert config.get_default_path() == default_path
    assert config.get_possible_values("units") == ["metric", "imperial"]
    assert config.get_section_properties("Weather") == [
        "show_weather",
        "apikey",
        "lat",
        "lon",
        "position",
        "font",
        "font_color",
    ]
    assert config.get_property(config.SETTINGS[0].get_name()) == config.SETTINGS[0]
    config.save()
    assert get_files_differences(default_path) == set()


def test_read():
    config: ConfigManager = ConfigManager(
        path=filename,
        default_path=default_path,
    )

    with not_raises(Exception):
        config.set("dark_theme", "1")

    config.save()
    assert get_files_differences(default_path) == {"dark_theme=1\n"}
    assert config.getint("dark_theme") == 1
    assert config.get_default("dark_theme") == 0


def test_re_read():
    config: ConfigManager = ConfigManager(
        path=filename,
        default_path=default_path,
    )
    assert config.getint("dark_theme") == 1
    assert config.get_default("dark_theme") == 0


def test_verify():
    remove_file(filename)
    config: ConfigManager = ConfigManager(
        path=filename,
        default_path=default_path,
    )
    with not_raises(Exception):
        config.verify()

    with not_raises(Exception):
        config.verify_exceptions()

    with not_raises(Warning):
        config.verify_warnings()


def test_check_system():
    remove_file(filename)
    config: ConfigManager = ConfigManager(
        path=filename,
        default_path=default_path,
    )
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("data")
        config.check_system()

    assert output == [
        "ls -l /dev/spidev*",
        "lsmod | grep spi_",
    ]


def test_legacy_convert():
    remove_file(filename)
    lines = "\n".join(
        [
            "[Album settings]",
            "sort_desc=1",
        ]
    )
    with open(filename, "w") as file:
        file.write(lines)
    with not_raises(Exception):
        config: ConfigManager = ConfigManager(
            path=filename,
            default_path=default_path,
        )

    assert config.get("sorting") == "desc"
    remove_file(filename)


class MockedPopen:
    _data = None

    def __init__(self, args, *arguments, **kwargs):
        self._args = args

    @classmethod
    def set_data(cls, data):
        cls._data = data

    def wait(self, timeout=None):
        pass

    def communicate(self, input=None, timeout=None):
        print(self._args)
        return self._data, ""


def get_files_differences(other_path):
    with open(filename, "r") as file:
        with open(other_path, "r") as default:
            difference = set(file).difference(default)
    return difference
