"""Test plugin with a photo source only (Plugin API v2)."""

from epiframe.plugins.base import Plugin as PluginBase


class Plugin(PluginBase):
    name = "Plugin3"
    author = "Author Name"
    description = "Test Plugin3"
    site = "Plugin site URL and documentation"
    info = "Additional info, license, etc."

    def source_photos(self):
        print("source_photos")
        return []
