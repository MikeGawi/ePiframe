from itertools import chain
from misc.constants import Constants


def test_type_to_extension():
    extensions = Constants.EXTEN
    type_to_extension = Constants.TYPE_TO_EXTENSION

    for type_extension in type_to_extension.keys():
        assert type_extension in extensions
        assert type_to_extension[type_extension] in extensions[type_extension]


def test_extension_to_type():
    extensions = Constants.EXTEN
    extension_to_type = Constants.EXTENSION_TO_TYPE

    for type_extension in extension_to_type.keys():
        assert type_extension in extensions[extension_to_type[type_extension]]


def test_extensions():
    extensions = [
        extension if isinstance(extension, list) else [extension]
        for extension in list(Constants.EXTEN.values())
    ]
    assert sorted(Constants.EXTENSIONS) == sorted(list(chain(*extensions)))
