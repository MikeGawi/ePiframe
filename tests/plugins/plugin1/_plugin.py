"""Test plugin using every hook (Plugin API v2)."""

from dataclasses import dataclass
from pathlib import Path

from epiframe.photos.model import Photo
from epiframe.plugins.base import PhotoFile
from epiframe.plugins.base import Plugin as PluginBase
from epiframe.web.api import api
from epiframe.web.extensions import Action, MenuEntry, Route


@dataclass(frozen=True)
class TextPath:
    text: str


@dataclass(frozen=True)
class Text:
    text_label: str


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

    @api("Echo", path=TextPath, response=Text)
    def get_text(self, path: TextPath) -> Text:
        return Text(path.text)

    def undeclared(self):
        return "not declared with @api"

    @staticmethod
    def dummy():
        print("I'm dummy")

    def extend_api(self, frame):
        print("extend_api")
        return [
            Route("/api/get_text/<text>", self.get_text),
            Route("/api/undeclared", self.undeclared),  # skipped
            Route("/not_api/<text>", self.get_text),  # skipped
        ]

    def add_website(
        self,
        web_manager,
        users_manager,
        backend,
    ):
        menus = [
            MenuEntry("Server", "127.0.0.1", "server-menu", "bi bi-server")
        ]  # can be more than one
        web_manager.add_menu_entries(menus)
        print("add_website")
        return []

    def add_action(self, frame):
        print("add_action")
        return [Action("lightoff", "Turn Light Off", self.dummy, "bi bi-lightbulb")]

    def service_thread(self, frame, stop):
        print("service_thread")
