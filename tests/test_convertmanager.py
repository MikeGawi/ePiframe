import subprocess
from unittest.mock import patch
import pytest

from misc.configproperty import ConfigProperty
from modules.base.configbase import ConfigBase
from modules.convertmanager import ConvertManager
from modules.displaymanager import DisplayManager
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import not_raises, set_file, remove_file

filename = "config_test.cfg"


def test_get_background_colors():
    colors = ConvertManager.get_background_colors()
    assert colors == ["black", "white", "photo", "crop"]


def test_get_convert_options():
    options = ConvertManager.get_convert_options()
    assert options == ["1", "2", "3", "4", "5", "6"]


def test_get_rotations():
    rotation = ConvertManager.get_rotation()
    assert rotation == [90, 270]


@pytest.mark.parametrize("value", ["black", "white", "photo", "crop"])
def test_verify_color_ok(value):
    with not_raises(Exception):
        ConvertManager.verify_background_color(value)


def test_verify_color_nok():
    with pytest.raises(Exception) as exception:
        ConvertManager.verify_background_color("non_existing_color")

    assert (
        str(exception.value)
        == "Configuration background_color should be one of ['black', 'white', 'photo', 'crop']"
    )


def test_orientation_image():
    output_data = '"output"'
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data(data=output_data.encode())
        orientation = ConvertManager().get_image_orientation(
            "binary", "file", "first_frame"
        )

    assert output == [
        'binary filefirst_frame -quiet -format "%[EXIF:Orientation]" info:'
    ]
    assert orientation == ("", output_data.replace('"', ""))


def test_image_comment():
    output_data = '"output"'
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data(data=output_data.encode())
        orientation = ConvertManager().get_image_comment("binary", "file")

    assert output == ['binary file -format "%c" info:']
    assert orientation == ("", output_data.replace('"', ""))


def test_image_format():
    output_data = '"output"'
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data(data=output_data.encode())
        orientation = ConvertManager().get_image_format("binary", "file", "first_frame")

    assert output == ['binary filefirst_frame -format "%m" info:']
    assert orientation == ("", output_data.replace('"', ""))


def test_image_size():
    output_data = '"output1,output2"'
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data(data=output_data.encode())
        orientation = ConvertManager().get_image_size("binary", "file", "first_frame")

    assert output == ['binary filefirst_frame -format "%w,%h" info:']
    assert orientation == (
        "",
        output_data.replace('"', "").split(",")[0],
        output_data.replace('"', "").split(",")[1],
    )


def test_orient_image():
    output_data = '"output"'
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data(data=output_data.encode())
        orientation = ConvertManager().orient_image("binary", "file", "first_frame")

    assert output == [
        'binary filefirst_frame -quiet -format "%[EXIF:Orientation]" info:',
        "binary file -auto-orient file",
    ]
    assert orientation == ""


def test_convert_1():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center -extent 800x600 -type "
        "bilevel -write target \) \( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center -extent 800x600 -type "
        "bilevel -write target ) ( +clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_2():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=2",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -background white -gravity center -extent 800x600 -type bilevel -write target \) "
        "\( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -background white -gravity center -extent 800x600 -type bilevel -write target ) ( "
        "+clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_3():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=3",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center -extent 800x600 -type "
        "bilevel -write target \) \( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center -extent 800x600 -type "
        "bilevel -write target ) ( +clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_4():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=4",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -ordered-dither o4x4 -background white -gravity center -extent 800x600 -type "
        "bilevel -write target \) \( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -ordered-dither o4x4 -background white -gravity center -extent 800x600 -type "
        "bilevel -write target ) ( +clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_5():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=5",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -background white -gravity center -extent 800x600 -type bilevel -write target \) \( +clone -thumbnail "
        "200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -background white -gravity center -extent 800x600 -type bilevel -write target ) ( +clone -thumbnail "
        "200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_6():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=6",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -colors 2 +dither -background white -gravity center -extent 800x600 -type bilevel -write target \) \( "
        "+clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -colors 2 +dither -background white -gravity center -extent 800x600 -type bilevel -write target ) ( "
        "+clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_background():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=photo",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone \( -clone 0 -gravity center -sample x640 "
        "-scale 12.5% -resize 800x640^ -crop 800x+0+0 +repage \) \( -clone 0 -sample 800x600 \) -delete 0 -gravity "
        "center -compose over -composite -brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 "
        "-background white -gravity center -extent 800x600 -type bilevel -write target \) \( +clone -thumbnail "
        "200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone ( -clone 0 -gravity center -sample x640 "
        "-scale 12.5% -resize 800x640^ -crop 800x+0+0 +repage ) ( -clone 0 -sample 800x600 ) -delete 0 -gravity "
        "center -compose over -composite -brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 "
        "-background white -gravity center -extent 800x600 -type bilevel -write target ) ( +clone -thumbnail 200x120 "
        "-write path/convert_name ) NULL:",
    ]


def test_convert_invert():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=black",
                "invert_colors=1",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -remap pattern:gray50 -negate -background black -gravity center -extent 800x600 "
        "-type bilevel -write target \) \( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -remap pattern:gray50 -negate -background black -gravity center -extent 800x600 "
        "-type bilevel -write target ) ( +clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_background_crop():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=crop",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent "
        "800x600 -thumbnail 200x120 -write path/download_name +delete \) \( +clone -resize 800x600^ "
        "-gravity Center -extent 800x600 -brightness-contrast 0,10 -dither FloydSteinberg -remap "
        "pattern:gray50 -background white -gravity center -extent 800x600 -type bilevel -write target "
        "\) \( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent "
        "800x600 -thumbnail 200x120 -write path/download_name +delete ) ( +clone -resize 800x600^ "
        "-gravity Center -extent 800x600 -brightness-contrast 0,10 -dither FloydSteinberg -remap "
        "pattern:gray50 -background white -gravity center -extent 800x600 -type bilevel -write target ) "
        "( +clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_rotation():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=270",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center -extent 800x600 -type "
        "bilevel -write target \) \( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center -extent 800x600 -type "
        "bilevel -write target ) ( +clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_horizontal():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=0",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -rotate 90 -sample 800x600 "
        "-brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center "
        "-extent 800x600 -type bilevel -write target \) \( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -rotate 90 -sample 800x600 "
        "-brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center "
        "-extent 800x600 -type bilevel -write target ) ( +clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_turned():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=1",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -rotate 180 -sample 800x600 "
        "-brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center "
        "-extent 800x600 -type bilevel -write target \) \( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -rotate 180 -sample 800x600 "
        "-brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center "
        "-extent 800x600 -type bilevel -write target ) ( +clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_quality():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=1",
                "auto_level=1",
                "normalize=1",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -auto-gamma -channel rgb "
        "-auto-level -normalize -brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 -background "
        "white -gravity center -extent 800x600 -type bilevel -write target \) \( +clone -thumbnail 200x120 -write "
        "path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -auto-gamma -channel rgb "
        "-auto-level -normalize -brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 -background "
        "white -gravity center -extent 800x600 -type bilevel -write target ) ( +clone -thumbnail 200x120 -write "
        "path/convert_name ) NULL:",
    ]


def test_convert_grayscale():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=1",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -colorspace Gray "
        "-brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center "
        "-extent 800x600 -type bilevel -write target \) \( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -colorspace Gray "
        "-brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center "
        "-extent 800x600 -type bilevel -write target ) ( +clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_brightness():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=90",
                "contrast=0",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -brightness-contrast 90,"
        "0 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center -extent 800x600 -type "
        "bilevel -write target \) \( +clone -thumbnail 200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -brightness-contrast 90,"
        "0 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center -extent 800x600 -type "
        "bilevel -write target ) ( +clone -thumbnail 200x120 -write path/convert_name ) NULL:",
    ]


def test_convert_colors_number():
    remove_file(filename)
    set_file(
        "\n".join(
            [
                "[test_section]",
                "convert_option=1",
                "convert_bin_path=bin",
                "image_width=800",
                "image_height=600",
                "background_color=white",
                "invert_colors=0",
                "rotation=90",
                "horizontal=1",
                "turned=0",
                "auto_gamma=0",
                "auto_level=0",
                "normalize=0",
                "grayscale=0",
                "brightness=0",
                "contrast=10",
                "photo_convert_path=path",
                "thumb_photo_download_name=download_name",
                "thumb_photo_convert_filename=convert_name",
                "epaper_color=BW",
                "colors_num=25",
            ]
        ),
        filename,
    )

    config = get_config()
    with patch.object(subprocess, "Popen", MockedPopen) as popen, Capturing() as output:
        popen.set_data("".encode())
        ConvertManager().convert_image(
            original_width=1200,
            original_height=960,
            source_file="source",
            config=config,
            target="target",
            hdmi=True,
        )

    assert output == [
        "bin [] -limit thread 1 \( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete \) \( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -background white -gravity center -extent 800x600 -colors 25 -write target \) \( +clone -thumbnail "
        "200x120 -write path/convert_name \) NULL:",
        "bin source -limit thread 1 ( +clone -background white -gravity center -sample 800x600 -extent 800x600 "
        "-thumbnail 200x120 -write path/download_name +delete ) ( +clone -sample 800x600 -brightness-contrast 0,"
        "10 -background white -gravity center -extent 800x600 -colors 25 -write target ) ( +clone -thumbnail 200x120 "
        "-write path/convert_name ) NULL:",
    ]
    remove_file(filename)


def get_config():
    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    "colors_num",
                    self,
                    minvalue=1,
                    not_empty=False,
                    prop_type=ConfigProperty.INTEGER_TYPE,
                ),
                ConfigProperty(
                    "convert_option",
                    self,
                    prop_type=ConfigProperty.INTEGER_TYPE,
                    possible=ConvertManager.get_convert_options(),
                ),
                ConfigProperty(
                    "image_width",
                    self,
                    minvalue=1,
                    prop_type=ConfigProperty.INTEGER_TYPE,
                ),
                ConfigProperty(
                    "image_height",
                    self,
                    minvalue=1,
                    prop_type=ConfigProperty.INTEGER_TYPE,
                ),
                ConfigProperty(
                    "rotation",
                    self,
                    prop_type=ConfigProperty.INTEGER_TYPE,
                    possible=ConvertManager.get_rotation(),
                ),
                ConfigProperty(
                    "background_color",
                    self,
                    possible=ConvertManager.get_background_colors(),
                ),
                ConfigProperty(
                    "convert_bin_path", self, prop_type=ConfigProperty.FILE_TYPE
                ),
                ConfigProperty(
                    "turned",
                    self,
                    prop_type=ConfigProperty.BOOLEAN_TYPE,
                ),
                ConfigProperty(
                    "auto_gamma", self, prop_type=ConfigProperty.BOOLEAN_TYPE
                ),
                ConfigProperty(
                    "auto_level", self, prop_type=ConfigProperty.BOOLEAN_TYPE
                ),
                ConfigProperty(
                    "normalize", self, prop_type=ConfigProperty.BOOLEAN_TYPE
                ),
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
                    "grayscale",
                    self,
                    prop_type=ConfigProperty.BOOLEAN_TYPE,
                ),
                ConfigProperty(
                    "horizontal", self, prop_type=ConfigProperty.BOOLEAN_TYPE
                ),
                ConfigProperty(
                    "invert_colors", self, prop_type=ConfigProperty.BOOLEAN_TYPE
                ),
                ConfigProperty(
                    "photo_convert_path", self, prop_type=ConfigProperty.FILE_TYPE
                ),
                ConfigProperty(
                    "epaper_color",
                    self,
                    possible=DisplayManager.get_colors(),
                ),
            ]

    config = ConfigTest(filename, filename)
    return config


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
        print(" ".join(self._args))
        return self._data, ""
