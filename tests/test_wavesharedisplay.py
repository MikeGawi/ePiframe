import importlib
import os
from unittest.mock import patch
from misc.configproperty import ConfigProperty
from misc.constants import Constants
from misc.wavesharedisplay import WaveshareDisplay
from modules.base.configbase import ConfigBase
from modules.displaymanager import DisplayManager
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import remove_file, set_file

filename = "config_test.cfg"
bitmap = os.path.dirname(os.path.realpath(__file__)) + "/assets/waveshare.bmp"
module = importlib.import_module("tests.helpers.waveshare_display")


def test_bw_display():
    set_config(Constants.COLOR_BW)

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import):
        with Capturing() as output:
            display = WaveshareDisplay(config)
            display.clear()
            display.show_image(bitmap)

    assert output
    assert "init" in output
    assert "__init__" in output
    assert "Clear" in output
    assert "image1" in output
    assert "image2" not in output
    assert "display" in output
    assert "sleep" in output


def test_bwr_display():
    set_config(Constants.COLOR_BWR)

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import):
        with Capturing() as output:
            display = WaveshareDisplay(config)
            display.show_image(bitmap)

    assert output
    assert "init" in output
    assert "__init__" in output
    assert "Clear" not in output
    assert "image1" in output
    assert "image2" in output
    assert "display" in output
    assert "sleep" in output


def test_bwy_display():
    set_config(Constants.COLOR_BWY, clear=1)

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import):
        with Capturing() as output:
            display = WaveshareDisplay(config)
            display.show_image(bitmap)

    assert output
    assert "init" in output
    assert "__init__" in output
    assert "Clear" in output
    assert "image1" in output
    assert "image2" in output
    assert "display" in output
    assert "sleep" in output

    remove_file(filename)


def set_config(color_schema, clear=0):
    binary_value = filename
    display_value = "Waveshare"
    tty_value = 1
    set_file(
        "\n".join(
            [
                "[test_section]",
                f"fbi_bin_path={binary_value}",
                f"display={display_value}",
                f"display_type={DisplayManager.get_spi()}",
                f"tty={tty_value}",
                f"epaper_color={color_schema}",
                f"clear_display={clear}",
            ]
        ),
        filename,
    )


def mocked_import(name, package=None):
    return module


def get_config():
    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    "display_type", self, possible=DisplayManager.get_displays()
                ),
                ConfigProperty(
                    "tty",
                    self,
                    minvalue=0,
                    prop_type=ConfigProperty.INTEGER_TYPE,
                    dependency=["display_type", DisplayManager.get_hdmi()],
                ),
                ConfigProperty(
                    "fbi_bin_path", self, prop_type=ConfigProperty.FILE_TYPE
                ),
                ConfigProperty(
                    "display",
                    self,
                    dependency=["display_type", DisplayManager.get_spi()],
                ),
                ConfigProperty(
                    "clear_display",
                    self,
                    dependency=["display_type", DisplayManager.get_spi()],
                    prop_type=ConfigProperty.BOOLEAN_TYPE,
                ),
                ConfigProperty(
                    "epaper_color",
                    self,
                    possible=DisplayManager.get_colors(),
                    dependency=["display_type", DisplayManager.get_spi()],
                ),
            ]

    return ConfigTest(filename, filename)
