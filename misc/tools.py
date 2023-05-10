import itertools
from typing import Any


class Tools:
    @staticmethod
    def check_if_list(key: str, value: str) -> Any:
        return key, value[0] if isinstance(value, list) else value

    @staticmethod
    def get_type_to_extension(extensions: dict) -> dict:
        return dict(Tools.check_if_list(key, value) for key, value in extensions.items())

    @staticmethod
    def get_product(key: str, value: str):
        return itertools.product(value if isinstance(value, list) else [value], [key])

    @staticmethod
    def get_products(extensions: dict):
        return [Tools.get_product(key, value) for key, value in extensions.items()]

    @staticmethod
    def get_extension_to_type(extensions: dict) -> dict:
        return dict(
            [
                the_type
                for extension in Tools.get_products(extensions)
                for the_type in extension
            ]
        )

    @staticmethod
    def get_extension(extension: Any) -> list:
        return extension if isinstance(extension, list) else [extension]

    @staticmethod
    def get_extensions(extensions: list) -> list:
        return sum(
            [Tools.get_extension(extension) for extension in list(extensions)],
            [],
        )
