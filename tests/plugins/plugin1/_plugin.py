"""Test plugin using every hook (Plugin API v2)."""

from pathlib import Path

from epiframe.photos.model import Photo
from epiframe.plugins.base import PhotoFile
from epiframe.plugins.base import Plugin as PluginBase
from modules.webuimanager import WebUIManager


class Plugin(PluginBase):
    name = "Plugin1"
    author = "Author Name"
    description = "Test Plugin1"
    site = "Plugin site URL and documentation"
    info = "Additional info, license, etc."

    def source_photos(self):
        print("source_photos")
        return []

    def fetch_photo(self, photo: Photo, directory: Path, name: str) -> Path:
        print("fetch_photo")
        return directory / f"{name}.jpg"

    def preprocess_photo(self, photo: PhotoFile) -> None:
        print("preprocess_photo")

    def postprocess_photo(self, photo: PhotoFile) -> None:
        print("postprocess_photo")

    @staticmethod
    def get_text_func(text=str()):
        from flask import jsonify

        return jsonify(text_label=text)

    @staticmethod
    def dummy():
        print("I'm dummy")

    def extend_api(
        self,
        web_manager,
        users_manager,
        backend,
    ):
        print("extend_api")
        new_api = [
            WebUIManager.SiteBind("/api/get_text/<text>", self.get_text_func),
        ]
        return new_api

    def add_website(
        self,
        web_manager,
        users_manager,
        backend,
    ):
        menus = [
            WebUIManager.MenuEntry("Server", "127.0.0.1", "server-menu", "bi bi-server")
        ]  # can be more than one
        web_manager.add_menu_entries(menus)
        print("add_website")
        return []

    def add_action(
        self,
        web_manager,
        users_manager,
        backend,
    ):
        print("add_action")
        new_action = {
            "lightoff": WebUIManager.ActionEntry(
                "Turn Light Off", self.dummy, "bi bi-lightbulb", "lightoff"
            ),
        }
        return new_action

    def add_service_thread(self, service, backend):
        print("add_service_thread")
