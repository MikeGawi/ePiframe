from epiframe.display.options import Background, ColorMode


def test_color_mode_values_in_webui_order() -> None:
    assert ColorMode.values() == [
        "BW",
        "BW+Red",
        "BW+Yellow",
        "4 colors",
        "7 colors",
        "Other",
    ]


def test_background_values() -> None:
    assert Background.values() == ["black", "white", "photo", "crop"]


def test_options_compare_as_strings() -> None:
    # config values are plain strings, 1.x code compares and looks them up directly
    config_value: str = "BW+Red"
    assert config_value == ColorMode.BWR
    colors: dict[str, str] = {ColorMode.BW: "black"}
    assert colors["BW"] == "black"
    assert ColorMode.C7.lower() == "7 colors"
    assert f"{Background.CROP}" == "crop"
