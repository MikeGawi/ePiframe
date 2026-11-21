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
