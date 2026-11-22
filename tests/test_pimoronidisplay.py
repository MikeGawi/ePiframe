import importlib
import os
from unittest.mock import patch
import pytest
from epiframe.config.property import ConfigProperty, PropertyType
from epiframe.display.options import Background, ColorMode
from misc.pimoronidisplay import PimoroniDisplay
from epiframe.config.base import ConfigBase
from modules.convertmanager import ConvertManager
from modules.displaymanager import DisplayManager
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import remove_file, set_file

filename = "config_test.cfg"
bitmap = os.path.dirname(os.path.realpath(__file__)) + "/assets/waveshare.bmp"
module = importlib.import_module("tests.helpers.pimoroni_display")


def test_phat_display():
    set_config(ColorMode.BW, display="phat")

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import):
        with Capturing() as output:
            display = PimoroniDisplay(config)
            display.clear()
            display.show_image(bitmap)

    assert output
    assert "__init__" in output
    assert "set_border" in output
    assert "set_image" in output
    assert "show" in output
    assert "border_color=1" in output
    assert "colour='black'" in output
    assert "saturation=0.8" not in output


def test_what_display():
    set_config(ColorMode.BWY, display="what", clear=1)

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import):
        with Capturing() as output:
            display = PimoroniDisplay(config)
            display.show_image(bitmap)

    assert output
    assert "__init__" in output
    assert "set_border" in output
    assert "set_image" in output
    assert "show" in output
    assert "colour='yellow'" in output
    assert "border_color=0" in output
    assert "saturation=0.8" not in output


def test_inky_ssd1608_display():
    set_config(ColorMode.BWR, display="inky_ssd1608")

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import):
        with Capturing() as output:
            display = PimoroniDisplay(config)
            display.show_image(bitmap)

    assert output
    assert "__init__" in output
    assert "set_border" not in output
    assert "set_image" in output
    assert "show" in output
    assert "colour='red'" in output
    assert "border_color=1" not in output
    assert "saturation=0.8" not in output


def test_inky_uc8159_display():
    set_config(ColorMode.BWR, display="inky_uc8159")

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import):
        with Capturing() as output:
            display = PimoroniDisplay(config)
            display.show_image(bitmap)

    assert output
    assert "__init__" in output
    assert "set_border" not in output
    assert "set_image" in output
    assert "show" in output
    assert "saturation=0.8" in output


def test_inky_ssd1683_display():
    set_config(ColorMode.BWR, display="inky_ssd1683")

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import):
        with Capturing() as output:
            display = PimoroniDisplay(config)
            display.show_image(bitmap)

    assert output
    assert "__init__" in output
    assert "set_border" not in output
    assert "set_image" in output
    assert "show" in output
    assert "colour='red'" in output
    assert "saturation=0.8" not in output


def test_inky_inky_ac073tc1a():
    set_config(ColorMode.BWR, display="inky_ac073tc1a")

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import):
        with Capturing() as output:
            display = PimoroniDisplay(config)
            display.show_image(bitmap)

    assert output
    assert "__init__" in output
    assert "set_border" not in output
    assert "set_image" in output
    assert "show" in output
    assert "colour='red'" in output
    assert "saturation=0.8" not in output


def test_non_existing_display():
    set_config(ColorMode.BWR, display="non_existing_display")

    config = get_config()
    with patch.object(importlib, "import_module", mocked_import):
        with pytest.raises(Exception) as exception:
            PimoroniDisplay(config)

    assert (
        str(exception.value)
        == "No Pimoroni display package non_existing_display in lib.inky!"
    )

    remove_file(filename)


def set_config(color_schema, clear=0, background=Background.BLACK, display="phat"):
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


def mocked_import(name, package=None):
    return module


def get_config():
    class ConfigTest(ConfigBase):
        def load_settings(self):
            return [
                ConfigProperty("display_type", possible=DisplayManager.get_displays()),
                ConfigProperty(
                    "tty",
                    min_value=0,
                    type=PropertyType.INTEGER,
                    dependency="display_type",
                    dependency_value=DisplayManager.get_hdmi(),
                ),
                ConfigProperty("fbi_bin_path", type=PropertyType.FILE),
                ConfigProperty(
                    "display",
                    dependency="display_type",
                    dependency_value=DisplayManager.get_spi(),
                ),
                ConfigProperty(
                    "clear_display",
                    dependency="display_type",
                    dependency_value=DisplayManager.get_spi(),
                    type=PropertyType.BOOLEAN,
                ),
                ConfigProperty(
                    "epaper_color",
                    possible=DisplayManager.get_colors(),
                    dependency="display_type",
                    dependency_value=DisplayManager.get_spi(),
                ),
                ConfigProperty(
                    "pimoroni_saturation",
                    min_value=0.0,
                    max_value=0.99,
                    type=PropertyType.FLOAT,
                ),
                ConfigProperty(
                    "display",
                    dependency="display_type",
                    dependency_value=DisplayManager.get_spi(),
                ),
                ConfigProperty(
                    "background_color",
                    possible=ConvertManager.get_background_colors(),
                ),
            ]

    return ConfigTest(filename, filename)
