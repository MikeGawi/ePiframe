from epiframe.core import media_types

MAPPING = {
    "image/png": "png",
    "image/jpeg": ["jpg", "jpeg"],
    "image/x-canon-cr2": "cr2",
    "image/x-dcraw": ("cr2",),
}


def test_type_to_extension() -> None:
    assert media_types.type_to_extension(MAPPING) == {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/x-canon-cr2": "cr2",
        "image/x-dcraw": "cr2",
    }


def test_extension_to_type_last_type_wins() -> None:
    assert media_types.extension_to_type(MAPPING) == {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "cr2": "image/x-dcraw",
    }


def test_all_extensions_without_duplicates_in_order() -> None:
    assert media_types.all_extensions(MAPPING) == ["png", "jpg", "jpeg", "cr2"]


def test_empty_mapping() -> None:
    assert media_types.type_to_extension({}) == {}
    assert media_types.extension_to_type({}) == {}
    assert media_types.all_extensions({}) == []


def test_supported_types_lookups_are_consistent() -> None:
    mapping = media_types.MIME_TO_EXTENSIONS
    for mime_type, extension in media_types.TYPE_TO_EXTENSION.items():
        assert mime_type.startswith(media_types.MIME_PREFIX)
        assert extension in mapping[mime_type]
    for extension, mime_type in media_types.EXTENSION_TO_TYPE.items():
        assert extension in mapping[mime_type]
    assert set(media_types.EXTENSIONS) == set(media_types.EXTENSION_TO_TYPE)
    assert len(media_types.EXTENSIONS) == len(set(media_types.EXTENSIONS))


def test_supported_types_examples() -> None:
    assert media_types.TYPE_TO_EXTENSION["image/jpeg"] == "jpg"
    assert media_types.EXTENSION_TO_TYPE["jpeg"] == "image/jpeg"
    assert media_types.EXTENSION_TO_TYPE["heic"] == "image/heif"
