import os
from unittest.mock import patch
from misc.configproperty import ConfigProperty
from modules.base.configbase import ConfigBase
from modules.base.displaybase import DisplayBase
from modules.displaymanager import DisplayManager
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import remove_file, set_file

filename = "config_test.cfg"


def test_getters():
    binary_value = filename
    display_value = "Waveshare"
    tty_value = 1

    set_file(
        "\n".join(
            [
                "[test_section]",
                f"fbi_bin_path={binary_value}",
                f"display={display_value}",
                f"display_type={DisplayManager.get_hdmi()}",
                f"tty={tty_value}",
            ]
        ),
        filename,
    )

    config = get_config()
    display = DisplayBase(config)
    assert display.get_display() == display_value
    assert display.get_vt() == tty_value


def test_showimage():
    with patch.object(os, "popen", mocked_popen):
        config = get_config()
        display = DisplayBase(config)
        photo_path = "test_photo_path"
        with Capturing() as output:
            display.show_image(photo_path)

        cmd = "".join(output)
        assert cmd
        assert (
            cmd
            == "sudo killall -SIGKILL fbi > /dev/null 2>&1;sudo config_test.cfg -vt 1 -noverbose -a "
            "test_photo_path > /dev/null 2>&1"
        )
    remove_file(filename)


def mocked_popen(cmd, mode="r", buffering=-1):
    print(cmd)


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
            ]

    return ConfigTest(filename, filename)
