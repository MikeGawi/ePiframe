import re
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from epiframe.processing.imagemagick import ImageMagickError
from epiframe.update import UpdateError
from epiframe.update.commands import FileCommands
from epiframe.update.pipeline import Pipeline
from tests.epiframe.update.conftest import add_photo

MakeCommands = Callable[..., FileCommands]


@pytest.fixture
def make_commands(make_pipeline: Callable[..., Pipeline]) -> MakeCommands:
    def make(**entries: str) -> FileCommands:
        return FileCommands(make_pipeline(**entries))

    return make


def test_test_convert_of_a_file(
    make_commands: MakeCommands, magick: MagicMock, tmp_path: Path
) -> None:
    file = add_photo(tmp_path / "photos", "a.jpg")

    make_commands().test_convert(file)

    # the file becomes the original photo (the WebUI and the bot offer it)
    assert Path("origphoto.jpg").read_bytes() == file.read_bytes()
    assert Path("photo.bmp").read_bytes() == file.read_bytes()
    assert magick.convert.call_args.args[3] is not None  # with thumbnails


def test_test_convert_of_the_original(
    make_commands: MakeCommands, tmp_path: Path
) -> None:
    original = add_photo(tmp_path, "origphoto.png")

    make_commands().test_convert()

    assert Path("photo.bmp").read_bytes() == original.read_bytes()


def test_test_convert_without_original(make_commands: MakeCommands) -> None:
    with pytest.raises(UpdateError, match=re.escape("No file: origphoto.*!")):
        make_commands().test_convert()


def test_test_convert_of_a_missing_file(make_commands: MakeCommands) -> None:
    with pytest.raises(UpdateError, match=re.escape("No file: gone.jpg!")):
        make_commands().test_convert(Path("gone.jpg"))


def test_test_display(
    make_commands: MakeCommands, display: MagicMock, tmp_path: Path
) -> None:
    converted = add_photo(tmp_path, "photo.bmp")
    file = add_photo(tmp_path, "ready.bmp")
    commands = make_commands()

    commands.test_display()
    commands.test_display(file)

    assert [call.args for call in display.show.call_args_list] == [
        (Path("photo.bmp"),),
        (file,),
    ]
    assert converted.exists()


def test_test_display_without_file(
    make_commands: MakeCommands, display: MagicMock
) -> None:
    with pytest.raises(UpdateError, match=re.escape("No file: photo.bmp!")):
        make_commands().test_display()

    display.show.assert_not_called()


def test_redisplay(
    make_commands: MakeCommands, display: MagicMock, tmp_path: Path
) -> None:
    uploaded = add_photo(tmp_path, "origphoto.jpg")

    make_commands().redisplay()

    assert Path("photo.bmp").read_bytes() == uploaded.read_bytes()
    display.show.assert_called_once_with(Path("photo.bmp"))


def test_convert(
    make_commands: MakeCommands, magick: MagicMock, tmp_path: Path
) -> None:
    source = add_photo(tmp_path / "photos", "my.photo.jpg")
    content = source.read_bytes()
    magick.auto_orient.side_effect = lambda file: Path(file).write_bytes(b"turned")

    target = make_commands(auto_orientation="1").convert(source, tmp_path / "a.b.jpg")

    assert target == tmp_path / "a.b.bmp"  # 1.x: "ab.bmp"
    assert target.read_bytes() == b"turned"
    assert source.read_bytes() == content  # 1.x turned the source itself
    assert magick.convert.call_args.args[3] is None  # no thumbnails


def test_convert_into_a_folder(make_commands: MakeCommands, tmp_path: Path) -> None:
    source = add_photo(tmp_path / "photos", "a.jpg")
    folder = tmp_path / "converted"
    folder.mkdir()

    assert make_commands().convert(source, folder) == folder / "a.bmp"
    assert (folder / "a.bmp").exists()


def test_convert_of_a_missing_file(make_commands: MakeCommands) -> None:
    with pytest.raises(UpdateError, match=re.escape("No file: gone.jpg!")):
        make_commands().convert(Path("gone.jpg"), Path("out.bmp"))


def test_convert_of_an_unknown_format(
    make_commands: MakeCommands, magick: MagicMock, tmp_path: Path
) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("not a photo")
    magick.image_format.side_effect = ImageMagickError("convert: no decode delegate")

    with pytest.raises(
        UpdateError,
        match=re.escape(f"Unknown file {source} format! convert: no decode"),
    ):
        make_commands().convert(source, tmp_path / "out.bmp")
