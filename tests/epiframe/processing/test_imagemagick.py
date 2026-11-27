import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from pytest_mock import MockerFixture

from epiframe.processing import imagemagick
from epiframe.processing.imagemagick import (
    CONVERT_OPTIONS,
    GRAY4_DITHERING,
    ROTATIONS,
    ConvertSettings,
    ImageMagick,
    ImageMagickError,
    Thumbnails,
    convert_arguments,
)

ASSETS = Path(__file__).with_name("assets")
# convert commands of the 1.x ConvertManager for a matrix of settings
CASES_1X: list[dict[str, Any]] = json.loads((ASSETS / "convert_1x.json").read_text())
CONVERT = shutil.which("convert")
needs_imagemagick = pytest.mark.skipif(CONVERT is None, reason="needs ImageMagick")


class Config:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def get(self, name: str) -> str:
        return self.values[name]

    def getint(self, name: str) -> int:
        return int(self.values[name])


def test_options() -> None:
    assert CONVERT_OPTIONS == ("1", "2", "3", "4", "5", "6")
    assert ROTATIONS == (90, 270)


@pytest.mark.parametrize(
    "case", CASES_1X, ids=[str(number) for number in range(len(CASES_1X))]
)
def test_arguments_match_1x(case: dict[str, Any]) -> None:
    config = Config(case["config"])
    thumbnails = Thumbnails.from_config(config) if case["thumbs"] else None

    arguments = convert_arguments(
        "source[0]",
        "target.bmp",
        ConvertSettings.from_config(config, case["hdmi"]),
        tuple(case["size"]),
        thumbnails,
    )

    binary, *expected = case["arguments"]
    assert binary == "bin"
    assert arguments == expected


def test_settings_from_config() -> None:
    config = Config(
        CASES_1X[0]["config"]
        | {
            "convert_option": "9",
            "background_color": " CROP ",
            "horizontal": "0",
            "rotation": "270",
            "colors_num": "16",
            "invert_colors": "1",
        }
    )

    assert ConvertSettings.from_config(config, hdmi=True) == ConvertSettings(
        width=800,
        height=480,
        option="1",
        background="crop",
        invert=True,
        rotation=270,
        contrast=10,
        colors=16,
        bilevel=False,
    )
    assert ConvertSettings.from_config(config, hdmi=False).bilevel


@pytest.mark.parametrize(("hdmi", "grays"), [(False, True), (True, False)])
def test_settings_for_four_grays(hdmi: bool, grays: bool) -> None:
    config = Config(CASES_1X[0]["config"] | {"epaper_color": "4 grays"})

    settings = ConvertSettings.from_config(config, hdmi=hdmi)

    assert settings.grays is grays
    assert not settings.bilevel


@pytest.mark.parametrize("option", CONVERT_OPTIONS)
@pytest.mark.parametrize("invert", [False, True])
def test_four_gray_arguments(option: str, invert: bool) -> None:
    settings = ConvertSettings(
        80, 48, option=option, invert=invert, bilevel=False, grays=True
    )

    arguments = convert_arguments("in", "out.bmp", settings, (120, 60))

    reduce = ["-colorspace", "Gray", *GRAY4_DITHERING[option]]
    reduce += ["-negate"] if invert else []
    start = arguments.index("-colorspace")
    assert arguments[start : start + len(reduce)] == reduce
    assert arguments[start + len(reduce) : start + len(reduce) + 2] == [
        "-background",
        "white",
    ]
    end = arguments.index("-write")
    assert arguments[end - 2 : end] == ["-type", "Palette"]


def test_arguments_with_spaces_in_paths() -> None:
    arguments = convert_arguments(
        "my photos/a b.jpg[0]",
        "out dir/photo.bmp",
        ConvertSettings(800, 480),
        (100, 100),
        Thumbnails("thumbs dir/o.jpg", "thumbs dir/c.jpg"),
    )

    assert arguments[0] == "my photos/a b.jpg[0]"
    for path in ("out dir/photo.bmp", "thumbs dir/o.jpg", "thumbs dir/c.jpg"):
        assert path in arguments


# ------------------------------------------------------------------- runner


def completed(stdout: str = "", stderr: str = "", code: int = 0) -> Any:
    return subprocess.CompletedProcess([], code, stdout, stderr)


@pytest.fixture
def run(mocker: MockerFixture) -> Any:
    return mocker.patch.object(subprocess, "run", return_value=completed())


def test_run(run: Any) -> None:
    run.return_value = completed("out\n")

    assert ImageMagick("/usr/bin/convert", timeout=5).run(["a b.jpg", "x"]) == "out\n"
    run.assert_called_once_with(
        ["/usr/bin/convert", "a b.jpg", "x"],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=5,
        check=False,
    )


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (
            completed(stderr="convert: no decode delegate\n", code=1),
            "convert: no decode delegate",
        ),
        (completed(code=2), "convert: exit code 2"),
    ],
)
def test_run_failure(run: Any, result: Any, message: str) -> None:
    run.return_value = result

    with pytest.raises(ImageMagickError, match=message):
        ImageMagick("/usr/bin/convert").run(["x"])


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("no such file: convert"),
        subprocess.TimeoutExpired("convert", 1),
    ],
)
def test_run_cannot_run(run: Any, error: Exception) -> None:
    run.side_effect = error

    with pytest.raises(ImageMagickError) as raised:
        ImageMagick("convert").run(["x"])
    assert raised.value.__cause__ is error


def test_warnings_are_not_errors(run: Any) -> None:
    run.return_value = completed("JPEG", "Corrupt JPEG data: 2 extraneous bytes")

    assert ImageMagick("convert").image_format("a.jpg") == "JPEG"


@pytest.mark.parametrize(
    ("method", "output", "expected", "arguments"),
    [
        ("size", "1200,960", (1200, 960), ["a.jpg[0]", "-format", "%w,%h", "info:"]),
        ("image_format", "JPEG\n", "JPEG", ["a.jpg[0]", "-format", "%m", "info:"]),
        ("comment", "hotword 3", "hotword 3", ["a.jpg", "-format", "%c", "info:"]),
        (
            "orientation",
            "6",
            "6",
            ["a.jpg[0]", "-quiet", "-format", "%[EXIF:Orientation]", "info:"],
        ),
    ],
)
def test_info(
    run: Any, method: str, output: str, expected: object, arguments: list[str]
) -> None:
    run.return_value = completed(output)

    assert getattr(ImageMagick("convert"), method)("a.jpg") == expected
    assert run.call_args.args[0] == ["convert", *arguments]


@pytest.mark.parametrize("output", ["", "x", "1,2,3", "a,b"])
def test_unknown_size(run: Any, output: str) -> None:
    run.return_value = completed(output)

    with pytest.raises(ImageMagickError, match=r"Unknown size of a\.jpg"):
        ImageMagick("convert").size("a.jpg")


@pytest.mark.parametrize(
    ("orientation", "turned"),
    [("", False), ("1", False), ("Undefined", False), ("6", True)],
)
def test_auto_orient(run: Any, orientation: str, turned: bool) -> None:
    run.return_value = completed(orientation)

    assert ImageMagick("convert").auto_orient("a.jpg") is turned

    commands = [call.args[0] for call in run.call_args_list]
    assert (["convert", "a.jpg", "-auto-orient", "a.jpg"] in commands) is turned


def test_convert(run: Any) -> None:
    run.side_effect = [completed("1200,960"), completed()]
    settings = ConvertSettings(800, 480)

    ImageMagick("convert").convert("a.jpg", "photo.bmp", settings)

    assert run.call_args.args[0] == [
        "convert",
        *convert_arguments("a.jpg[0]", "photo.bmp", settings, (1200, 960)),
    ]


# ------------------------------------------------------- real ImageMagick


@needs_imagemagick
@pytest.mark.parametrize(
    ("settings", "mode"),
    [
        (ConvertSettings(80, 48), "1"),
        (ConvertSettings(80, 48, background="photo", rotation=90), "1"),
        (ConvertSettings(80, 48, bilevel=False, colors=8, background="crop"), "P"),
        (ConvertSettings(80, 48, bilevel=False, grays=True), "P"),
    ],
)
def test_real_conversion(tmp_path: Path, settings: ConvertSettings, mode: str) -> None:
    source = tmp_path / "my photo.jpg"
    Image.new("RGB", (120, 60), "red").save(source)
    magick = ImageMagick(str(CONVERT))
    thumbnails = Thumbnails(
        str(tmp_path / "o thumb.jpg"), str(tmp_path / "c thumb.jpg")
    )

    magick.convert(str(source), str(tmp_path / "out photo.bmp"), settings, thumbnails)

    with Image.open(tmp_path / "out photo.bmp") as image:
        assert image.size == (80, 48)
        assert image.mode == mode
    assert Path(thumbnails.original).exists()
    assert Path(thumbnails.converted).exists()
    assert magick.size(str(source)) == (120, 60)
    assert magick.image_format(str(source)) == "JPEG"


@needs_imagemagick
@pytest.mark.parametrize("option", CONVERT_OPTIONS)
def test_real_four_grays(tmp_path: Path, option: str) -> None:
    source = tmp_path / "gradient.png"
    Image.linear_gradient("L").resize((120, 60)).convert("RGB").save(source)
    settings = ConvertSettings(80, 48, option=option, bilevel=False, grays=True)

    ImageMagick(str(CONVERT)).convert(str(source), str(tmp_path / "out.bmp"), settings)

    with Image.open(tmp_path / "out.bmp") as image:
        levels = set(image.convert("L").tobytes())
    # the evenly spaced grays of the 4-gray buffer (white: the background)
    assert levels <= {0, 85, 170, 255}
    assert len(levels) >= 3


@needs_imagemagick
def test_real_errors(tmp_path: Path) -> None:
    broken = tmp_path / "broken.jpg"
    broken.write_text("not an image")
    magick = ImageMagick(str(CONVERT))

    with pytest.raises(ImageMagickError):
        magick.size(str(broken))
    with pytest.raises(ImageMagickError):
        ImageMagick(sys.executable + "-missing").size(str(broken))


@needs_imagemagick
def test_real_comment_and_orientation(tmp_path: Path) -> None:
    photo = tmp_path / "a.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotated, shown 90 degrees clockwise
    Image.new("RGB", (40, 20), "blue").save(photo, exif=exif)
    magick = ImageMagick(str(CONVERT))
    magick.run([str(photo), "-set", "comment", "hotword 3", str(photo)])

    assert magick.comment(str(photo)) == "hotword 3"
    assert magick.orientation(str(photo)) == "6"
    assert magick.auto_orient(str(photo))
    assert magick.size(str(photo)) == (20, 40)
    assert not magick.auto_orient(str(photo))


def test_timeout_default() -> None:
    assert ImageMagick("convert").timeout == imagemagick.TIMEOUT
