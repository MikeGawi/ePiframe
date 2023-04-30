import importlib
import os
from unittest.mock import patch
import pytest
from misc.configproperty import ConfigProperty
from misc.constants import Constants
from modules.base.configbase import ConfigBase
from modules.convertmanager import ConvertManager
from modules.displaymanager import DisplayManager
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import not_raises, set_file, remove_file

filename = "config_test.cfg"
bitmap = os.path.dirname(os.path.realpath(__file__)) + "/assets/waveshare.bmp"
pimoroni_module = importlib.import_module("tests.helpers.pimoroni_display")
waveshare_module = importlib.import_module("tests.helpers.waveshare_display")


def test_verify_display_hdmi():
    with not_raises(Exception):
        DisplayManager.verify_display("HDMI".lower())


def test_verify_display_spi():
    with not_raises(Exception):
        DisplayManager.verify_display("SPI".lower())


def test_verify_display_wrong():
    with pytest.raises(Exception) as exception:
        DisplayManager.verify_display("non_existing_display")
    assert (
        str(exception.value)
        == "Configuration display_type should be one of ['SPI', 'HDMI']"
    )


def test_verify_epaper_waveshare():
    with not_raises(Exception):
        DisplayManager.verify_epaper("Waveshare".lower())


def test_verify_epaper_pimoroni():
    with not_raises(Exception):
        DisplayManager.verify_epaper("Pimoroni".lower())


def test_verify_epaper_wrong():
    with pytest.raises(Exception) as exception:
        DisplayManager.verify_epaper("non_existing_epaper")
    assert (
        str(exception.value)
        == "Configuration epaper_type should be one of ['Waveshare', 'Pimoroni']"
    )


@pytest.mark.parametrize(
    "value",
    [
        "BW",
        "BW+Yellow",
        "BW+Red",
        "4 colors",
        "7 colors",
        "Other",
    ],
)
def test_verify_colors_ok(value):
    with not_raises(Exception):
        DisplayManager.verify_color(value.lower())


def test_verify_color_wrong():
    with pytest.raises(Exception) as exception:
        DisplayManager.verify_color("non_existing_color")
    assert (
        str(exception.value)
        == "Configuration Display_color should be one of ['BW', 'BW+Red', 'BW+Yellow', '4 colors', '7 colors', 'Other']"
    ), str(exception.value)


def test_get_displays():
    assert DisplayManager.get_displays() == ["SPI", "HDMI"]


def test_get_epapers():
    assert DisplayManager.get_epapers() == ["Waveshare", "Pimoroni"]


def test_get_colors():
    assert DisplayManager.get_colors() == [
        "BW",
        "BW+Red",
        "BW+Yellow",
        "4 colors",
        "7 colors",
        "Other",
    ]


def test_get_spi():
    assert DisplayManager.get_spi() == "SPI"


def test_get_hdmi():
    assert DisplayManager.get_hdmi() == "HDMI"


def test_get_pimoroni():
    assert DisplayManager.get_pimoroni() == "Pimoroni"


def test_is_hdmi_ok():
    assert DisplayManager.is_hdmi("HDMI") is True


@pytest.mark.parametrize(
    "value",
    [
        "",
        "DUMMY_HDMI",
        "SPI",
    ],
)
def test_verify_colors_nok(value):
    assert DisplayManager.is_hdmi(value) is False


def test_should_convert_ok():
    assert DisplayManager.should_convert("BW") is True


@pytest.mark.parametrize(
    "value",
    [
        "BW+Yellow",
        "BW+Red",
        "4 colors",
        "7 colors",
        "Other",
    ],
)
def test_should_convert_nok(value):
    assert DisplayManager.should_convert(value) is False


def test_control_display_power_true():
    with patch.object(os, "popen", mocked_popen), Capturing() as output:
        DisplayManager.control_display_power(True)

    assert output == ["sudo vcgencmd display_power 1 2> /dev/null"]


def test_control_display_power_false():
    with patch.object(os, "popen", mocked_popen), Capturing() as output:
        DisplayManager.control_display_power(False)

    assert output == ["sudo vcgencmd display_power 0 2> /dev/null"]


def test_get_display_power():
    with patch.object(os, "popen", mocked_popen), Capturing() as output:
        DisplayManager.get_display_power()

    assert output == ["sudo vcgencmd display_power  2> /dev/null"]


def test_waveshare_display():
    remove_file(filename)
    set_config_waveshare(Constants.COLOR_BW)

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import_waveshare):
        with Capturing() as output:
            display_manager = DisplayManager(config)
            display_manager.show_image(bitmap)
            assert display_manager.get_vt() == 1
            assert display_manager.is_display_hdmi() is False
            assert display_manager.get_display() == "Waveshare"

    assert output == ["__init__", "init", "image1", "display", "sleep"]
    remove_file(filename)


def test_pimoroni_display():
    remove_file(filename)
    set_config_pimoroni(Constants.COLOR_BW)

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import_pimoroni):
        with Capturing() as output:
            display_manager = DisplayManager(config)
            display_manager.show_image(bitmap)
            assert display_manager.get_vt() == 1
            assert display_manager.is_display_hdmi() is False
            assert display_manager.get_display() == "phat"

    assert output == ["colour='black'", "__init__", "set_image", "show"]
    remove_file(filename)


def test_hdmi_display():
    remove_file(filename)
    set_config_hdmi(Constants.COLOR_BW)

    config = get_config()
    with Capturing() as output, patch.object(os, "popen", mocked_popen):
        display_manager = DisplayManager(config)
        display_manager.show_image(bitmap)
        assert display_manager.get_vt() == 1
        assert display_manager.is_display_hdmi() is True
        assert display_manager.get_display() == "HDMI"

    assert output == [
        f"sudo killall -SIGKILL fbi > /dev/null 2>&1;sudo config_test.cfg -vt 1 -noverbose -a {bitmap} > /dev/null 2>&1"
    ]
    remove_file(filename)


def mocked_popen(cmd, mode="r", buffering=-1):
    print(cmd)
    return MockRead(cmd)


class MockRead:
    def __init__(self, text):
        self.text = text

    def read(self):
        return self.text


def set_config_pimoroni(
    color_schema, clear=0, background=Constants.BACK_BLACK, display="phat"
):
    binary_value = filename
    display_value = "Pimoroni"
    tty_value = 1
    set_file(
        "\n".join(
            [
                "[test_section]",
                f"fbi_bin_path={binary_value}",
                f"epaper_type={display_value}",
                f"display_type={DisplayManager.get_spi()}",
                f"display={display}",
                f"tty={tty_value}",
                f"epaper_color={color_schema}",
                f"clear_display={clear}",
                "pimoroni_saturation=0.8",
                f"background_color={background}",
            ]
        ),
        filename,
    )


def set_config_waveshare(color_schema, clear=0):
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
                f"epaper_type={display_value}",
                f"tty={tty_value}",
                f"epaper_color={color_schema}",
                f"clear_display={clear}",
            ]
        ),
        filename,
    )


def set_config_hdmi(color_schema, clear=0):
    binary_value = filename
    display_value = "HDMI"
    tty_value = 1
    set_file(
        "\n".join(
            [
                "[test_section]",
                f"fbi_bin_path={binary_value}",
                f"display={display_value}",
                f"display_type={DisplayManager.get_hdmi()}",
                f"epaper_type={display_value}",
                f"tty={tty_value}",
                f"epaper_color={color_schema}",
                f"clear_display={clear}",
            ]
        ),
        filename,
    )


def mocked_import_pimoroni(name, package=None):
    return pimoroni_module


def mocked_import_waveshare(name, package=None):
    return waveshare_module


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
                ConfigProperty(
                    "pimoroni_saturation",
                    self,
                    minvalue=0.0,
                    maxvalue=0.99,
                    prop_type=ConfigProperty.FLOAT_TYPE,
                ),
                ConfigProperty(
                    "display",
                    self,
                    dependency=["display_type", DisplayManager.get_spi()],
                ),
                ConfigProperty(
                    "background_color",
                    self,
                    possible=ConvertManager.get_background_colors(),
                ),
            ]

    return ConfigTest(filename, filename)
