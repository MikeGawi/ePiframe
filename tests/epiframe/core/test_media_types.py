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
