"""Photo processing with ImageMagick (the ``convert`` tool).

One ``convert`` call prepares the photo for the display: it scales it (with a
background, a blurred copy of the photo or a crop for the empty area), applies
the enhancements, reduces the colors for e-Paper (dithering presets) and writes
the thumbnails for the WebUI and Telegram.

Commands are argument lists (never a shell string), so paths with spaces work.
Failures (exit code, missing tool, timeout) raise ``ImageMagickError``; 1.x
didn't read the error output, so a failed conversion went unnoticed.
"""

import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, Self

from epiframe.core.logs import get_logger
from epiframe.display.options import Background, ColorMode

log = get_logger("processing")

# only the first frame of an animated GIF (or a multi-page file) is used
FIRST_FRAME = "[0]"
TIMEOUT = 600  # seconds; a big RAW photo takes minutes on a Raspberry Pi Zero
THUMBNAIL_SIZE = "200x120"
ROTATIONS = (90, 270)
TURNED = 180  # horizontal frame mounted upside down
# EXIF orientations that need no turning ("1" = top left, "" = none)
UPRIGHT = ("", "1", "Undefined")

# e-Paper black & white presets (convert_option): color reduction arguments
# https://legacy.imagemagick.org/Usage/quantize/
DITHERING: dict[str, tuple[str, ...]] = {
    "1": ("-dither", "FloydSteinberg", "-remap", "pattern:gray50"),
    "2": ("-dither", "FloydSteinberg"),
    "3": ("-dither", "FloydSteinberg", "-remap", "pattern:gray50"),
    "4": ("-dither", "FloydSteinberg", "-ordered-dither", "o4x4"),
    "5": (),
    "6": ("-colors", "2", "+dither"),
}
CONVERT_OPTIONS = tuple(DITHERING)
DEFAULT_OPTION = "1"


class ImageMagickError(RuntimeError):
    """An ImageMagick call failed."""


class Settings(Protocol):
    """Configuration values (``ConfigManager``)."""

    def get(self, name: str) -> str: ...

    def getint(self, name: str) -> int: ...


@dataclass(frozen=True)
class ConvertSettings:
    """How a photo is converted for the display."""

    width: int
    height: int
    option: str = DEFAULT_OPTION  # e-Paper black & white preset
    background: str = Background.WHITE
    invert: bool = False
    rotation: int = 0  # degrees, 0 = none
    auto_gamma: bool = False
    auto_level: bool = False
    normalize: bool = False
    grayscale: bool = False
    brightness: int = 0
    contrast: int = 0
    colors: int | None = None  # color limit (HDMI)
    bilevel: bool = True  # black & white e-Paper: dithered to two colors

    @classmethod
    def from_config(cls, config: Settings, hdmi: bool) -> Self:
        flag = config.getint
        return cls(
            width=flag("image_width"),
            height=flag("image_height"),
            option=_option(config.get("convert_option")),
            background=_background(config.get("background_color")),
            invert=bool(flag("invert_colors")),
            rotation=_rotation(config),
            auto_gamma=bool(flag("auto_gamma")),
            auto_level=bool(flag("auto_level")),
            normalize=bool(flag("normalize")),
            grayscale=bool(flag("grayscale")),
            brightness=flag("brightness"),
            contrast=flag("contrast"),
            colors=flag("colors_num") if hdmi and config.get("colors_num") else None,
            bilevel=not hdmi
            and config.get("epaper_color").lower() == ColorMode.BW.lower(),
        )

    @property
    def size(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def fill(self) -> str:
        """Color of the empty area (none is left by a photo background or a crop)."""
        filled = self.background in (Background.PHOTO, Background.CROP)
        return Background.WHITE if filled else self.background


def _option(value: str) -> str:
    """The preset; an unknown one falls back to the default (1.x behaviour)."""
    return value if value in DITHERING else DEFAULT_OPTION


def _background(value: str) -> str:
    value = value.strip().lower()
    return value if value in Background.values() else Background.WHITE


def _rotation(config: Settings) -> int:
    if not config.getint("horizontal"):
        return config.getint("rotation")
    return TURNED if config.getint("turned") else 0


@dataclass(frozen=True)
class Thumbnails:
    """Thumbnail files of the original and of the converted photo."""

    original: str
    converted: str

    @classmethod
    def from_config(cls, config: Settings) -> Self:
        folder = config.get("photo_convert_path")
        return cls(
            os.path.join(folder, config.get("thumb_photo_download_name")),
            os.path.join(folder, config.get("thumb_photo_convert_filename")),
        )


# ----------------------------------------------------------------- arguments


def _scaling(settings: ConvertSettings, original: tuple[int, int]) -> list[str]:
    """Scaling to the display size; the empty area depends on the background."""
    width, height = settings.width, settings.height
    if settings.background == Background.CROP:
        return [
            "-resize",
            f"{settings.size}^",
            "-gravity",
            "Center",
            "-extent",
            settings.size,
        ]
    if settings.background != Background.PHOTO:
        return ["-sample", settings.size]
    # Don't use blur, it kills a Raspberry Pi Zero: sampling down and scaling up
    # blurs the photo for the background ~10x faster.
    aspect_ratio = original[0] / original[1]
    background_height = max(int(width / aspect_ratio), height)
    return [
        *("(", "-clone", "0", "-gravity", "center", "-sample", f"x{background_height}"),
        *("-scale", f"{round(aspect_ratio * 10.0, 2)}%"),
        *("-resize", f"{width}x{background_height}^", "-crop", f"{width}x+0+0"),
        *("+repage", ")", "(", "-clone", "0", "-sample", settings.size, ")"),
        *("-delete", "0", "-gravity", "center", "-compose", "over", "-composite"),
    ]


def _enhancements(settings: ConvertSettings) -> list[str]:
    flags = (
        (settings.auto_gamma, ("-auto-gamma",)),
        (settings.auto_level, ("-channel", "rgb", "-auto-level")),
        (settings.normalize, ("-normalize",)),
        (settings.grayscale, ("-colorspace", "Gray")),
    )
    arguments = [argument for wanted, flag in flags if wanted for argument in flag]
    return [
        *arguments,
        "-brightness-contrast",
        f"{settings.brightness},{settings.contrast}",
    ]


def _colors(settings: ConvertSettings) -> tuple[list[str], list[str]]:
    """Color reduction before and after the background/extent arguments."""
    negate = ["-negate"] if settings.invert else []
    if settings.bilevel:
        return [*DITHERING[settings.option], *negate], ["-type", "bilevel"]
    colors = ["-colors", str(settings.colors)] if settings.colors else []
    return negate, colors


def _thumbnails(
    settings: ConvertSettings, thumbnails: Thumbnails | None
) -> tuple[list[str], list[str]]:
    if thumbnails is None:
        return [], []
    original = [
        *("(", "+clone", "-background", "white", "-gravity", "center"),
        *("-sample", settings.size, "-extent", settings.size),
        *("-thumbnail", THUMBNAIL_SIZE, "-write", thumbnails.original, "+delete", ")"),
    ]
    converted = [
        "(",
        "+clone",
        "-thumbnail",
        THUMBNAIL_SIZE,
        "-write",
        thumbnails.converted,
        ")",
    ]
    return original, converted


def convert_arguments(
    source: str,
    target: str,
    settings: ConvertSettings,
    original_size: tuple[int, int],
    thumbnails: Thumbnails | None = None,
) -> list[str]:
    """``convert`` arguments that turn ``source`` into ``target`` (and thumbnails)."""
    rotation = ["-rotate", str(settings.rotation)] if settings.rotation else []
    before, after = _colors(settings)
    original_thumbnail, converted_thumbnail = _thumbnails(settings, thumbnails)
    return [
        *(source, "-limit", "thread", "1", *original_thumbnail, "(", "+clone"),
        *rotation,
        *_scaling(settings, original_size),
        *_enhancements(settings),
        *before,
        *("-background", settings.fill, "-gravity", "center"),
        *("-extent", settings.size, *after, "-write", target, ")"),
        *converted_thumbnail,
        "NULL:",
    ]


# ------------------------------------------------------------------- runner


class ImageMagick:
    """ImageMagick ``convert`` tool at ``binary``."""

    def __init__(self, binary: str, timeout: float | None = TIMEOUT) -> None:
        self.binary = binary
        self.timeout = timeout

    def run(self, arguments: Sequence[str]) -> str:
        """Run the tool; return its output, raise ``ImageMagickError`` on failure."""
        command = [self.binary, *arguments]
        log.debug(" ".join(command))
        try:
            result = subprocess.run(  # noqa: S603 (no shell, fixed tool)
                command,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ImageMagickError(str(error)) from error
        if result.returncode:
            # the tool's messages already start with its name
            name = os.path.basename(self.binary)
            message = f"{name}: exit code {result.returncode}"
            raise ImageMagickError(result.stderr.strip() or message)
        return result.stdout

    def _info(self, file: str, pattern: str, *options: str) -> str:
        return self.run([file, *options, "-format", pattern, "info:"]).strip()

    def size(self, file: str) -> tuple[int, int]:
        """Width and height (of the first frame)."""
        text = self._info(file + FIRST_FRAME, "%w,%h")
        try:
            width, height = (int(value) for value in text.split(","))
        except ValueError:
            raise ImageMagickError(f"Unknown size of {file}: {text!r}") from None
        return width, height

    def image_format(self, file: str) -> str:
        """ImageMagick format name, e.g. ``JPEG`` (of the first frame)."""
        return self._info(file + FIRST_FRAME, "%m")

    def comment(self, file: str) -> str:
        """Image comment (holds the interval hot word)."""
        return self._info(file, "%c")

    def orientation(self, file: str) -> str:
        """EXIF orientation (``""`` when there is none)."""
        return self._info(file + FIRST_FRAME, "%[EXIF:Orientation]", "-quiet")

    def auto_orient(self, file: str) -> bool:
        """Turn ``file`` upright by its EXIF orientation; ``True`` if it changed.

        An upright photo is not rewritten (1.x re-encoded it, losing quality).
        """
        if self.orientation(file) in UPRIGHT:
            return False
        self.run([file, "-auto-orient", file])
        return True

    def convert(
        self,
        source: str,
        target: str,
        settings: ConvertSettings,
        thumbnails: Thumbnails | None = None,
    ) -> None:
        """Convert ``source`` (first frame) to ``target`` for the display."""
        arguments = convert_arguments(
            source + FIRST_FRAME, target, settings, self.size(source), thumbnails
        )
        self.run(arguments)
