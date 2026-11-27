import shutil
from pathlib import Path

import pytest

from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.config.property import ConfigError, ConfigWarning, PropertyType

ASSETS = Path(__file__).with_name("assets")
CONFIG_V1 = ASSETS / "config_v1.cfg"
DEFAULT = Path(paths.CONFIG_FILE_DEFAULT)
REPOSITORY = Path(__file__).parents[3]

GOOGLE_PHOTOS_ENTRIES = [
    "use_google_photos",
    "cred_file",
    "pickle_file",
    "album_names",
    "refresh_rate",
]


@pytest.fixture(autouse=True)
def in_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # the default local_path ("photos") is created relative to the working directory
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    return tmp_path / "config.cfg"


def entries(text: str) -> list[str]:
    """Entry lines of a configuration file (without comments)."""
    return [
        line
        for line in text.splitlines()
        if line.strip() and not line.startswith(("#", ";", "["))
    ]


def test_new_config_is_the_default(config_file: Path) -> None:
    config = ConfigManager(config_file, DEFAULT)

    assert config_file.read_text() == DEFAULT.read_text()
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
    assert config.get_section_properties("Weather") == [
        "show_weather",
        "apikey",
        "lat",
        "lon",
        "position",
        "font",
        "font_color",
    ]
    assert config.getint("use_local") == 1
    assert config.get("units") == "metric"
    assert config.get_possible_values("units") == ["metric", "imperial"]
    assert config.get_comment("convert_bin_path") == (
        "Path and name of the ImageMagick convert tool binary."
        " Default: /usr/bin/convert"
    )
    assert config.get_default("dark_theme") == 0
    assert config.get_obsolete() == []


def test_tracked_config_matches_default() -> None:
    # README links to config.cfg in the repository root
    assert (REPOSITORY / "config.cfg").read_text() == DEFAULT.read_text()


def test_every_entry_has_help(config_file: Path) -> None:
    config = ConfigManager(config_file, DEFAULT)

    assert [
        prop.name for prop in config.settings if not config.get_comment(prop.name)
    ] == []


def test_property_metadata(config_file: Path) -> None:
    config = ConfigManager(config_file, DEFAULT)

    rotation = config.get_property("rotation")
    assert rotation.type == PropertyType.INTEGER
    assert (rotation.dependency, rotation.dependency_value) == ("horizontal", "0")
    assert config.get_property("tty").dependency_value == "HDMI"
    assert config.get_property("epaper_type").dependency_value == "SPI"
    assert config.get_property("use_web").reset_needed is True
    assert config.get_property("dark_theme").dependency == "use_web"


def test_default_config_verifies(config_file: Path, tmp_path: Path) -> None:
    config = ConfigManager(config_file, DEFAULT)
    # FILE entries must exist; the defaults (/usr/bin/convert, ...) depend on the
    # machine, so point them to a file that surely exists
    existing = tmp_path / "existing"
    existing.touch()
    for prop in config.settings:
        if prop.type == PropertyType.FILE:
            config.set(prop.name, str(existing))

    config.verify()


def test_invalid_value_is_reported(config_file: Path) -> None:
    config = ConfigManager(config_file, DEFAULT)
    config.set("use_web", "1")
    config.set("web_port", "70000")

    with pytest.raises(
        ConfigError, match="web_port configuration entry should be <= 65535"
    ):
        config.validate("web_port")


def test_icons_in_the_weather_stamp_corner_warn(config_file: Path) -> None:
    config = ConfigManager(config_file, DEFAULT)
    config.set("show_weather", "1")
    config.set("position", "1")
    config.set("icons_position", "1")
    config.validate("icons_position")  # no icons enabled: no warning
    config.set("error_icon", "1")

    with pytest.raises(ConfigWarning, match="same corner as the weather stamp"):
        config.validate("icons_position")


def test_1x_config_is_upgraded(config_file: Path) -> None:
    v1 = (
        CONFIG_V1.read_text()
        .replace("local_path=photos", "local_path=my_photos")
        .replace("web_port=80", "web_port=8080")
        .replace("photos_from=", "photos_from=2020.05.01 10:00:00")
    )
    config_file.write_text(v1)

    config = ConfigManager(config_file, DEFAULT)

    # the 1.x index and list files were replaced by photo_db_file (Phase 3.6),
    # RRDtool by stats_db_file (Phase 3.16)
    assert config.get_obsolete() == [
        *GOOGLE_PHOTOS_ENTRIES,
        "rrdtool_bin_path",
        "photo_index_file",
        "photo_list_file",
    ]
    # user values are kept, legacy value formats converted
    assert config.get("local_path") == "my_photos"
    assert config.getint("web_port") == 8080
    assert config.get("photos_from") == "2020-05-01 10:00:00"
    # the saved file is the 2.0 default with the user values
    expected = (
        DEFAULT.read_text()
        .replace("local_path=photos", "local_path=my_photos")
        .replace("web_port=80", "web_port=8080")
        .replace("photos_from=", "photos_from=2020-05-01 10:00:00")
    )
    assert entries(config_file.read_text()) == entries(expected)
    assert config_file.read_text() == expected


def test_1x_sort_desc_becomes_sorting(config_file: Path) -> None:
    config_file.write_text("[Album settings]\nsort_desc=1\n")

    config = ConfigManager(config_file, DEFAULT)

    assert config.get("sorting") == "desc"
    assert config.get_obsolete() == []
    assert "sort_desc" not in config_file.read_text()


def test_local_path_is_created(config_file: Path, tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    config_file.write_text(f"[Sources]\nlocal_path={photos}\n")

    ConfigManager(config_file, DEFAULT)

    assert photos.is_dir()


def test_import_of_a_copy(config_file: Path, tmp_path: Path) -> None:
    # WebUI import: load an uploaded file, save it as config.cfg
    uploaded = tmp_path / "uploaded.cfg"
    shutil.copyfile(CONFIG_V1, uploaded)

    ConfigManager(uploaded, DEFAULT).save(config_file)

    assert config_file.read_text() == DEFAULT.read_text()


def test_drive_entries(config_file: Path) -> None:
    config = ConfigManager(config_file, DEFAULT)

    assert config.getint("use_drive") == 0
    assert config.get_section_properties("Sources")[3:] == [
        "use_drive",
        "drive_folders",
        "drive_key_file",
        "drive_subfolders",
    ]
    assert config.get_property("drive_key_file").type == PropertyType.FILE
    config.validate("drive_folders")  # inactive: Google Drive is disabled

    config.set("use_drive", "1")
    config.set(
        "drive_folders",
        "https://drive.google.com/drive/folders/1AbC-dEf_12345, 2XyZ_987654321",
    )
    config.validate("drive_folders")
    config.set("drive_folders", "1AbC-dEf_12345,not a folder")
    with pytest.raises(ConfigError, match="Not a Google Drive folder ID or link"):
        config.validate("drive_folders")
