"""Plugin API v2: the base class of ePiframe plugins.

A plugin is a folder in ``plugins/`` with ``_plugin.py`` defining ``class
Plugin(epiframe.plugins.base.Plugin)``, a ``config.cfg`` and its default
``default/config.default``. Every hook is optional; ePiframe calls only the ones
the plugin overrides:

- :meth:`Plugin.settings` — the validated configuration entries;
- :meth:`Plugin.source_photos` / :meth:`Plugin.fetch_photo` — a photo source;
- :meth:`Plugin.preprocess_photo` / :meth:`Plugin.postprocess_photo` — editing
  the photo before / after the conversion for the display.

The web and service hooks (``extend_api``, ``add_website``, ``add_action``,
``add_service_thread``) keep their 1.x shape until the WebUI (3.17), the service
(3.18) and the new UI (Phase 5) are ported.
"""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Protocol

from epiframe.config.base import ConfigBase, LegacyEntry
from epiframe.config.property import ConfigError, ConfigProperty, PropertyType
from epiframe.photos.model import Photo
from epiframe.processing.imagemagick import ImageMagick

CONFIG_FILE = "config.cfg"
DEFAULT_CONFIG_FILE = "default/config.default"
ENABLED = "is_enabled"
HOOKS = (
    "source_photos",
    "fetch_photo",
    "preprocess_photo",
    "postprocess_photo",
    "extend_api",
    "add_website",
    "add_action",
    "add_service_thread",
)


class Settings(Protocol):
    """Read access to the ePiframe configuration."""

    def get(self, name: str) -> str: ...

    def getint(self, name: str) -> int: ...


@dataclass(frozen=True)
class PluginContext:
    """What ePiframe gives every plugin."""

    path: Path  # the plugin folder (absolute)
    logger: logging.Logger  # "epiframe.plugins.<folder>"
    global_config: Settings  # ePiframe's config.cfg


@dataclass(frozen=True)
class PhotoFile:
    """The photo file a processing hook edits in place."""

    path: Path
    photo: Photo | None  # None for --test-convert / --convert runs
    width: int  # display size (image_width / image_height)
    height: int
    horizontal: bool  # False: vertical frame, the file is stored turned
    rotation: int  # of a vertical frame: 90 or 270
    image_magick: ImageMagick


class PluginConfig(ConfigBase):
    """``config.cfg`` of a plugin, validated by :meth:`Plugin.settings`."""

    def __init__(
        self,
        folder: Path,
        settings: Sequence[ConfigProperty],
        legacy: Sequence[LegacyEntry] = (),
    ):
        names = {setting.name for setting in settings}
        if ENABLED not in names:
            raise ConfigError(f"The plugin settings must contain {ENABLED!r}!")
        self._declared = list(settings)
        self._legacy = tuple(legacy)
        super().__init__(folder / CONFIG_FILE, folder / DEFAULT_CONFIG_FILE)

    def load_settings(self) -> list[ConfigProperty]:
        return self._declared

    def legacy_entries(self) -> Sequence[LegacyEntry]:
        return self._legacy


class Plugin:
    """Base class of plugins: override the metadata and the hooks you need."""

    name: ClassVar[str] = ""
    author: ClassVar[str] = ""
    description: ClassVar[str] = ""
    site: ClassVar[str] = ""
    info: ClassVar[str] = ""
    # renamed configuration entries (keep old config.cfg files working)
    LEGACY: ClassVar[Sequence[LegacyEntry]] = ()

    def __init__(self, context: PluginContext):
        if not self.name:
            raise ConfigError(f"The plugin in {context.path} has no name!")
        self.context = context
        self.path = context.path
        self.logger = context.logger
        self.global_config = context.global_config
        self.config = PluginConfig(context.path, self.settings(), self.LEGACY)

    # ------------------------------------------------------------- configuration

    def settings(self) -> list[ConfigProperty]:
        """Validated entries of ``config.cfg``; must contain ``is_enabled``.

        Entries of the default file that are not listed are plain strings.
        """
        return [ConfigProperty(ENABLED, PropertyType.BOOLEAN)]

    @property
    def enabled(self) -> bool:
        return bool(self.config.getint(ENABLED))

    @property
    def folder(self) -> str:
        return self.path.name

    @property
    def source(self) -> str:
        """The source name of this plugin's photos (``Photo.source``)."""
        return f"plugin:{self.folder}"

    def implements(self, hook: str) -> bool:
        """Whether the plugin overrides ``hook`` (ePiframe calls only those)."""
        if hook not in HOOKS:
            raise ValueError(f"Unknown plugin hook {hook!r}")
        return getattr(type(self), hook) is not getattr(Plugin, hook)

    # -------------------------------------------------------------- photo source

    def source_photos(self) -> Iterable[Photo]:
        """All photos of the source: ``Photo(id, self.source, created)``.

        Called on every refresh; the photo index stores only the changes. The id
        identifies the photo within the source (e.g. a path or a remote id).
        """
        return ()

    def fetch_photo(self, photo: Photo, directory: Path, name: str) -> Path:
        """Put the file of ``photo`` into ``directory`` as ``name`` + extension.

        Return the path of the file. Without this hook ePiframe copies the
        local file ``photo.id`` (sources listing local files need nothing more).
        """
        raise NotImplementedError

    # ---------------------------------------------------------------- processing

    def preprocess_photo(self, photo: PhotoFile) -> None:
        """Edit the original photo (before the conversion for the display)."""

    def postprocess_photo(self, photo: PhotoFile) -> None:
        """Edit the converted photo (just before it is shown)."""

    # --------------------------------------- web and service (1.x shape for now)

    def extend_api(self, web_manager: Any, users: Any, backend: Any) -> list[Any]:
        """WebUI API endpoints (``WebUIManager.SiteBind``); redesigned in 3.17."""
        return []

    def add_website(self, web_manager: Any, users: Any, backend: Any) -> list[Any]:
        """Flask blueprints of new WebUI pages; redesigned in Phase 5."""
        return []

    def add_action(self, web_manager: Any, users: Any, backend: Any) -> dict[str, Any]:
        """WebUI tool buttons (``WebUIManager.ActionEntry``); redesigned in 3.17."""
        return {}

    def add_service_thread(self, service: Any, backend: Any) -> None:
        """Body of a thread of the ePiframe service; redesigned in 3.18."""
