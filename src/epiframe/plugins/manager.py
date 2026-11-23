"""Finds, orders and loads the plugins in the plugins folder.

Every subfolder with ``_plugin.py`` is a plugin, imported as
``<package>.<folder>._plugin``, so a plugin can import its own modules the same
way. The package (``plugins``) is bound to the plugins folder explicitly, so the
folder can live anywhere (``EPIFRAME_PLUGINS_DIR``). The
execution order is kept in ``order.cfg`` (``<package>.<folder>`` per line, as
1.x): listed plugins first, new ones after them by name. A plugin that can't be
loaded is logged and skipped — it doesn't stop ePiframe.
"""

import importlib
import importlib.machinery
import importlib.util
import sys
from collections.abc import Iterable
from pathlib import Path

from epiframe.core.files import write_text_atomic
from epiframe.core.logs import get_logger
from epiframe.photos.model import Photo
from epiframe.plugins.base import Plugin, PluginContext, Settings

PLUGIN_FILE = "_plugin.py"
PLUGIN_MODULE = "_plugin"
ORDER_FILE = "order.cfg"
PACKAGE = "plugins"

log = get_logger("plugins")


class PluginManager:
    """The plugins of ``directory`` (imported as the package ``package``)."""

    def __init__(
        self,
        directory: Path | str,
        global_config: Settings,
        package: str = PACKAGE,
    ):
        self.directory = Path(directory).resolve()
        self.package = package
        self._global_config = global_config
        if "." not in package:
            self._bind_package()
        self.plugins = self._load()

    def _bind_package(self) -> None:
        # A regular package of the same name elsewhere on sys.path (e.g. the
        # plugins/ folder of a source checkout) would win over this folder.
        location = [str(self.directory)]
        module = sys.modules.get(self.package)
        if module is not None and list(getattr(module, "__path__", [])) == location:
            return
        spec = importlib.machinery.ModuleSpec(self.package, None, is_package=True)
        spec.submodule_search_locations = location
        sys.modules[self.package] = importlib.util.module_from_spec(spec)

    @property
    def order_file(self) -> Path:
        return self.directory / ORDER_FILE

    def read_order(self) -> list[str]:
        """``<package>.<folder>`` entries of ``order.cfg`` (empty without it)."""
        try:
            lines = self.order_file.read_text().splitlines()
        except OSError:
            return []
        return [line.strip() for line in lines if line.strip()]

    def save_order(self, order: Iterable[str]) -> None:
        write_text_atomic(self.order_file, "".join(f"{entry}\n" for entry in order))

    def _entry(self, folder: str) -> str:
        return f"{self.package}.{folder}"

    def _folders(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        return sorted(
            item.name
            for item in self.directory.iterdir()
            if (item / PLUGIN_FILE).is_file()
        )

    def _ordered(self, folders: list[str]) -> list[str]:
        # listed ones in the order of the file, then the others (folders are sorted
        # by name and the sort is stable)
        order = self.read_order()
        rank = {entry: index for index, entry in enumerate(order)}
        return sorted(folders, key=lambda f: rank.get(self._entry(f), len(order)))

    def _load(self) -> list[Plugin]:
        folders = self._ordered(self._folders())
        order = [self._entry(folder) for folder in folders]
        if order != self.read_order():  # write only changes (SD card)
            self.save_order(order)
        plugins = []
        for folder in folders:
            plugin = self._load_plugin(folder)
            if plugin is not None:
                plugins.append(plugin)
        return plugins

    def _load_plugin(self, folder: str) -> Plugin | None:
        if not folder.isidentifier():
            log.error(
                f"Plugin folder {folder!r} skipped: the name must be a valid Python"
                " identifier (letters, digits, _), e.g. rename it to"
                f" {folder.replace('-', '_')!r}"
            )
            return None
        try:
            module = importlib.import_module(f"{self._entry(folder)}.{PLUGIN_MODULE}")
            plugin_class = module.Plugin
            if not (
                isinstance(plugin_class, type) and issubclass(plugin_class, Plugin)
            ):
                raise TypeError("Plugin must subclass epiframe.plugins.base.Plugin")
            return plugin_class(
                PluginContext(
                    self.directory / folder,
                    get_logger(f"plugins.{folder}"),
                    self._global_config,
                )
            )
        except Exception as error:
            log.error(f"Error loading plugin {folder!r}, skipped: {error!r}")
            return None

    def enabled(self) -> list[Plugin]:
        return [plugin for plugin in self.plugins if plugin.enabled]

    def with_hook(self, hook: str) -> list[Plugin]:
        """Enabled plugins implementing ``hook``, in the execution order."""
        return [plugin for plugin in self.enabled() if plugin.implements(hook)]

    def sources(self) -> list[Plugin]:
        return self.with_hook("source_photos")

    def source_of(self, photo: Photo) -> Plugin | None:
        """The enabled plugin whose source the photo comes from."""
        return next((p for p in self.sources() if p.source == photo.source), None)
