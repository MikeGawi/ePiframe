"""Test plugin with a photo source only (Plugin API v2)."""

from epiframe.plugins.base import Plugin as PluginBase


class Plugin(PluginBase):
    name = "Plugin2"
    author = "Author Name"
    description = "Test Plugin2"
    site = "Plugin site URL and documentation"
    info = "Additional info, license, etc."

    def source_photos(self):
        print("source_photos")
        return []
