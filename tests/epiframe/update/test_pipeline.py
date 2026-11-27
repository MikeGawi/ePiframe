import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests_mock
from PIL import Image

from epiframe.config.manager import ConfigManager
from epiframe.display.controller import NO_SPI, DisplayController
from epiframe.photos.model import Photo
from epiframe.plugins.base import PhotoFile
from epiframe.processing.imagemagick import (
    ConvertSettings,
    ImageMagickError,
    Thumbnails,
)
from epiframe.update import UpdateError
from epiframe.update.pipeline import WORK_PREFIX, Pipeline
from epiframe.weather.openweather import API_URL
from tests.epiframe.update.conftest import add_photo, make_plugin

MakePipeline = Callable[..., Pipeline]
PHOTO = Photo("photos/a.jpg", "Local", datetime(2024, 5, 1, 10))


@pytest.fixture
def original(tmp_path: Path) -> Path:
    return add_photo(tmp_path, "origphoto.jpg")


def test_defaults(config: ConfigManager, plugins: MagicMock, magick: MagicMock) -> None:
    pipeline = Pipeline(config, plugins, magick)

    assert isinstance(pipeline.display, DisplayController)
    assert pipeline.display.settings() is config
    assert pipeline.target == Path("photo.bmp")
    assert not pipeline.hdmi


def test_convert(
    make_pipeline: MakePipeline,
    magick: MagicMock,
    original: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    pipeline = make_pipeline()

    pipeline.convert(original, pipeline.target, PHOTO)

    assert pipeline.target.read_bytes() == original.read_bytes()
    work = str(original.with_name(f"{WORK_PREFIX}origphoto.jpg"))
    magick.convert.assert_called_once_with(
        work,
        "photo.bmp",
        ConvertSettings.from_config(pipeline.config, hdmi=False),
        Thumbnails.from_config(pipeline.config),
    )
    assert not Path(work).exists()  # 1.x left the pre_ files
    magick.auto_orient.assert_not_called()
    assert caplog.messages == ["Processing the photo...", "Success!"]


def test_convert_without_thumbnails(
    make_pipeline: MakePipeline,
    magick: MagicMock,
    original: Path,
) -> None:
    make_pipeline().convert(original, Path("out.bmp"), None, thumbnails=False)

    assert magick.convert.call_args.args[3] is None


def test_conversion_error(
    make_pipeline: MakePipeline,
    magick: MagicMock,
    original: Path,
) -> None:
    magick.convert.side_effect = ImageMagickError("convert: broken")
    pipeline = make_pipeline()

    with pytest.raises(UpdateError, match=r"^Fail! convert: broken$"):
        pipeline.convert(original, pipeline.target, PHOTO)

    assert list(original.parent.glob(f"{WORK_PREFIX}*")) == []


@pytest.mark.parametrize(
    "turned_message", [(True, "Success!"), (False, "Success! Already upright")]
)
def test_auto_orientation(
    make_pipeline: MakePipeline,
    magick: MagicMock,
    original: Path,
    caplog: pytest.LogCaptureFixture,
    turned_message: tuple[bool, str],
) -> None:
    turned, message = turned_message
    magick.auto_orient.return_value = turned
    pipeline = make_pipeline(auto_orientation="1")

    pipeline.convert(original, pipeline.target, PHOTO)

    # the original itself is turned (the WebUI and the bot offer it)
    magick.auto_orient.assert_called_once_with(str(original))
    assert caplog.messages[:2] == ["Auto-orientate the photo...", message]


def test_auto_orientation_error(
    make_pipeline: MakePipeline,
    magick: MagicMock,
    original: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    magick.auto_orient.side_effect = ImageMagickError("convert: broken")
    pipeline = make_pipeline(auto_orientation="1")

    pipeline.convert(original, pipeline.target, PHOTO)

    assert "Fail! convert: broken" in caplog.messages
    assert pipeline.target.exists()


def test_plugins(
    make_pipeline: MakePipeline,
    plugins: MagicMock,
    magick: MagicMock,
    original: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    received: list[PhotoFile] = []

    def edit(photo: PhotoFile) -> None:
        received.append(photo)
        photo.path.write_bytes(b"edited " + photo.path.read_bytes())

    plugin = make_plugin(preprocess_photo=edit, postprocess_photo=edit)
    plugins.with_hook.side_effect = lambda hook: [plugin]
    pipeline = make_pipeline(horizontal="0", rotation="270")
    content = original.read_bytes()

    pipeline.convert(original, pipeline.target, PHOTO)

    pre, post = received
    assert pre.path == original.with_name(f"{WORK_PREFIX}origphoto.jpg")
    assert post.path == pipeline.target
    assert (pre.photo, pre.width, pre.height) == (PHOTO, 800, 480)
    assert (pre.horizontal, pre.rotation, pre.image_magick) == (False, 270, magick)
    assert pipeline.target.read_bytes().startswith(b"edited edited ")
    assert original.read_bytes() == content  # the plugins edit a copy
    assert "Preprocessing photo by plugin 'Clock'..." in caplog.messages
    assert "Postprocessing photo by plugin 'Clock'..." in caplog.messages


def test_plugin_error_stops(
    make_pipeline: MakePipeline,
    plugins: MagicMock,
    original: Path,
) -> None:
    def broken(photo: PhotoFile) -> None:
        raise ValueError("broken")

    plugins.with_hook.side_effect = lambda hook: [make_plugin(preprocess_photo=broken)]
    pipeline = make_pipeline()

    with pytest.raises(ValueError, match="broken"):
        pipeline.convert(original, pipeline.target, PHOTO)

    assert list(original.parent.glob(f"{WORK_PREFIX}*")) == []


WEATHER = {"weather": [{"icon": "01d"}], "main": {"temp": 21.4}}


def test_weather_stamp(
    make_pipeline: MakePipeline,
    original: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    pipeline = make_pipeline(show_weather="1", apikey="key", lat="53.2", lon="7.7")
    Image.new("RGB", (200, 100), "white").save(original, format="BMP")

    with requests_mock.Mocker() as mocker:
        mocker.get(API_URL, json=WEATHER)
        pipeline.convert(original, pipeline.target, PHOTO)

    assert caplog.messages[-4:] == [
        "Getting weather data...",
        "Success!",
        "Putting weather stamp...",
        "Success!",
    ]
    with Image.open(pipeline.target) as stamped:
        assert len(stamped.getcolors(maxcolors=100_000) or []) > 1  # not all white


def test_weather_error_is_logged(
    make_pipeline: MakePipeline,
    original: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    pipeline = make_pipeline(show_weather="1", apikey="secret", lat="53.2", lon="7.7")

    with requests_mock.Mocker() as mocker:
        mocker.get(API_URL, status_code=500)
        pipeline.convert(original, pipeline.target, PHOTO)

    assert caplog.messages[-2] == "Getting weather data..."
    assert caplog.messages[-1].startswith("Fail! ")
    assert "secret" not in caplog.text
    assert pipeline.target.exists()


# ------------------------------------------------------------------- prepare


def test_prepare_converts(
    make_pipeline: MakePipeline,
    magick: MagicMock,
    original: Path,
) -> None:
    pipeline = make_pipeline()

    pipeline.prepare(original, PHOTO)

    assert pipeline.target.exists()
    magick.convert.assert_called_once()


def test_prepare_without_conversion(
    make_pipeline: MakePipeline,
    magick: MagicMock,
    original: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    pipeline = make_pipeline(convert="0")

    pipeline.prepare(original, PHOTO)

    assert pipeline.target.read_bytes() == original.read_bytes()
    magick.convert.assert_not_called()
    assert "Conversion disabled by the 'convert' setting" in caplog.text


# ---------------------------------------------------------------------- show


def test_show(
    make_pipeline: MakePipeline,
    display: MagicMock,
    original: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    make_pipeline().show(original)

    display.show.assert_called_once_with(original)
    assert caplog.messages == ["Sending to display..."]


def test_show_needs_spi(make_pipeline: MakePipeline, display: MagicMock) -> None:
    with pytest.raises(UpdateError, match=re.escape(NO_SPI)):
        make_pipeline(spi=False).show(Path("photo.bmp"))

    display.show.assert_not_called()


def test_hdmi_needs_no_spi(make_pipeline: MakePipeline, display: MagicMock) -> None:
    make_pipeline(display_type="HDMI", spi=False).show(Path("a.bmp"))

    display.show.assert_called_once_with(Path("a.bmp"))


def test_display_error(make_pipeline: MakePipeline, display: MagicMock) -> None:
    display.show.side_effect = OSError("Can't start fbi")

    with pytest.raises(
        UpdateError, match="Error sending photo to display: Can't start fbi"
    ):
        make_pipeline().show(Path("photo.bmp"))
