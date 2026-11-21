"""Lookups derived from a MIME type to file extension(s) mapping.

The mapping value is a single extension or a list of extensions, the first one being
the preferred extension for that MIME type, e.g.
``{"image/png": "png", "image/jpeg": ["jpg", "jpeg"]}``.
"""

from collections.abc import Iterator, Mapping, Sequence
from typing import TypeAlias

ExtensionMap: TypeAlias = Mapping[str, str | Sequence[str]]


def _as_list(extensions: str | Sequence[str]) -> list[str]:
    return [extensions] if isinstance(extensions, str) else list(extensions)


def type_to_extension(mapping: ExtensionMap) -> dict[str, str]:
    """Map every MIME type to its preferred (first) extension."""
    return {
        mime_type: _as_list(extensions)[0] for mime_type, extensions in mapping.items()
    }


def _extension_type_pairs(mapping: ExtensionMap) -> Iterator[tuple[str, str]]:
    for mime_type, extensions in mapping.items():
        for extension in _as_list(extensions):
            yield extension, mime_type


def extension_to_type(mapping: ExtensionMap) -> dict[str, str]:
    """Map every extension to its MIME type.

    When an extension belongs to several MIME types, the last one in the mapping wins.
    """
    return dict(_extension_type_pairs(mapping))


def all_extensions(mapping: ExtensionMap) -> list[str]:
    """Return all extensions without duplicates, in mapping order."""
    return list(extension_to_type(mapping))


MIME_PREFIX = "image/"

# Supported image MIME types and their extensions, the preferred extension first.
MIME_TO_EXTENSIONS: ExtensionMap = {
    "image/x-sony-arw": "arw",
    "image/x-canon-cr2": "cr2",
    "image/x-canon-crw": "crw",
    "image/x-kodak-dcr": "dcr",
    "image/x-adobe-dng": "dng",
    "image/x-epson-erf": "erf",
    "image/x-kodak-k25": "k25",
    "image/x-kodak-kdc": "kdc",
    "image/x-minolta-mrw": "mrw",
    "image/x-nikon-nef": "nef",
    "image/x-olympus-orf": "orf",
    "image/x-pentax-pef": "pef",
    "image/x-fuji-raf": "raf",
    "image/x-panasonic-raw": "raw",
    "image/x-sony-sr2": "sr2",
    "image/x-sony-srf": "srf",
    "image/x-sigma-x3f": "x3f",
    "image/x-dcraw": "cr2",
    "image/raw": "raw",
    # only the first frame of a GIF is shown
    "image/gif": "gif",
    "image/webp": "webp",
    "image/jpeg": ("jpg", "jpeg", "jfif", "pjpeg", "pjp"),
    "image/png": "png",
    "image/tiff": ("tiff", "tif"),
    "image/vnd.microsoft.icon": "ico",
    "image/ico": "ico",
    "image/icon": "ico",
    "image/x-icon": "ico",
    "image/bmp": "bmp",
    "image/heif": ("heic", "heif"),
}

TYPE_TO_EXTENSION = type_to_extension(MIME_TO_EXTENSIONS)
EXTENSION_TO_TYPE = extension_to_type(MIME_TO_EXTENSIONS)
EXTENSIONS = all_extensions(MIME_TO_EXTENSIONS)
