"""INI configuration file described by a default file and validated by properties.

The default file is the template of the configuration: it defines the sections,
the entries (with their default values and order) and the help texts. Lines
starting with ``# `` before an entry are its help text shown in the WebUI, lines
starting with ``; `` are comments hidden from the WebUI.

Loading is backward compatible with older files (1.x ``config.cfg``):

* entries are matched by name, not by section, so an entry found in another
  section is moved to the section of the default file;
* entries missing in the file are added with their default values;
* entries that are not in the default file anymore are dropped and reported by
  ``get_obsolete()``;
* ``LEGACY`` renames entries, converting their values;
* ``ConfigProperty.convert`` converts old value formats.

The file is saved again when any of this changed it.
"""

import configparser
import contextlib
import os
import shutil
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from epiframe.config.property import (
    Choice,
    ConfigError,
    ConfigProperty,
    ConfigWarning,
    PropertyType,
)
from epiframe.core.files import write_text_atomic

HELP_PREFIX = "# "
COMMENT_PREFIXES = ("#", ";")
SECTION_PREFIX = "["
VALUE_SEPARATOR = "="

Layout = dict[str, dict[str, str]]


@dataclass(frozen=True)
class LegacyEntry:
    """Entry renamed in a later version; the old value is converted on load."""

    old: str
    new: str
    convert: Callable[[str], str]


def _new_parser() -> configparser.ConfigParser:
    # no interpolation: values may contain "%" (passwords, API keys)
    return configparser.ConfigParser(interpolation=None)


def _entry_name(line: str) -> str | None:
    """Return the entry name defined by ``line`` or ``None`` for other lines."""
    if not line.strip() or line.startswith((*COMMENT_PREFIXES, SECTION_PREFIX)):
        return None
    return line.split(VALUE_SEPARATOR, 1)[0].strip().lower()


def _parse_help(lines: Iterable[str]) -> dict[str, str]:
    """Collect the ``# `` help lines written before each entry."""
    help_texts: dict[str, str] = {}
    collected: list[str] = []
    for line in lines:
        if line.startswith(HELP_PREFIX):
            collected.append(line[len(HELP_PREFIX) :].strip())
        elif name := _entry_name(line):
            help_texts[name] = " ".join(collected)
            collected = []
    return help_texts


def _layout(parser: configparser.ConfigParser) -> Layout:
    return {section: dict(parser.items(section)) for section in parser.sections()}


class ConfigBase(ABC):
    """Configuration file with entries described by ``load_settings()``."""

    LEGACY: ClassVar[Sequence[LegacyEntry]] = ()

    def __init__(
        self, path: str | os.PathLike[str], default_path: str | os.PathLike[str]
    ) -> None:
        self._path = Path(path)
        self._default_path = Path(default_path)
        self._template = self._default_path.read_text().splitlines(keepends=True)
        self._default = _new_parser()
        self._default.read_string("".join(self._template), str(self._default_path))
        self._sections = {
            name: section
            for section in self._default.sections()
            for name in self._default.options(section)
        }
        self._help = _parse_help(self._template)
        self._settings = self._collect_settings(self.load_settings())
        self.parser = _new_parser()
        self._obsolete: list[str] = []
        changed = self.reload()
        if self._convert() or changed:
            self.save()

    def legacy_entries(self) -> Sequence[LegacyEntry]:
        """Renamed entries (``LEGACY``; overridable for configs built at runtime)."""
        return self.LEGACY

    @abstractmethod
    def load_settings(self) -> list[ConfigProperty]:
        """Return the properties of the entries that need validation.

        Entries of the default file without a property get a plain STRING one.
        """

    def _collect_settings(
        self, declared: Iterable[ConfigProperty]
    ) -> dict[str, ConfigProperty]:
        settings = {prop.name: prop for prop in declared}
        unknown = sorted(settings.keys() - self._sections.keys())
        if unknown:
            raise ConfigError(
                f"Entries {unknown} are not in the default file {self._default_path}!"
            )
        for name in self._sections:
            settings.setdefault(name, ConfigProperty(name))
        return settings

    @property
    def path(self) -> Path:
        return self._path

    @property
    def default_path(self) -> Path:
        return self._default_path

    @property
    def settings(self) -> list[ConfigProperty]:
        """Properties of all entries (declared ones first, in declaration order)."""
        return list(self._settings.values())

    def reload(self) -> bool:
        """(Re)read the file, creating it from the default file if it is missing.

        Return whether the values had to be migrated (the file should be saved).
        """
        if not self._path.exists():
            shutil.copyfile(self._default_path, self._path)
        found = _new_parser()
        found.read_string(self._path.read_text(), str(self._path))
        values = self._values_by_name(found)
        migrated = self._apply_legacy(values)
        self._obsolete = [
            name for name in values if name not in self._sections | migrated
        ]
        self.parser = self._build_parser(values)
        return _layout(self.parser) != _layout(found)

    @staticmethod
    def _values_by_name(parser: configparser.ConfigParser) -> dict[str, str]:
        values: dict[str, str] = {}
        for section in parser.sections():
            for name, value in parser.items(section):
                values.setdefault(name, value)
        return values

    def _apply_legacy(self, values: dict[str, str]) -> dict[str, str]:
        migrated: dict[str, str] = {}
        for entry in self.legacy_entries():
            if entry.old in values and entry.new not in values:
                values[entry.new] = entry.convert(values[entry.old])
                migrated[entry.old] = entry.new
        return migrated

    def _build_parser(self, values: dict[str, str]) -> configparser.ConfigParser:
        parser = _new_parser()
        for section in self._default.sections():
            parser.add_section(section)
            for name, default in self._default.items(section):
                parser.set(section, name, values.get(name, default))
        return parser

    def _convert(self) -> bool:
        changed = False
        for prop in self._settings.values():
            if prop.convert:
                value = self.get(prop.name)
                converted = prop.convert(value)
                if converted != value:
                    self.set(prop.name, converted)
                    changed = True
        return changed

    def get_obsolete(self) -> list[str]:
        """Entries dropped on the last load because they are no longer supported."""
        return list(self._obsolete)

    def _section(self, name: str) -> str:
        try:
            return self._sections[name]
        except KeyError:
            raise ConfigError(f"Error parsing {name} configuration entry") from None

    def get(self, name: str) -> str:
        return self.parser.get(self._section(name), name)

    def getint(self, name: str) -> int:
        try:
            return int(self.get(name))
        except ValueError:
            raise ConfigError(f"Error parsing {name} configuration entry") from None

    def set(self, name: str, value: str) -> None:
        self.parser.set(self._section(name), name, value)

    def render(self) -> str:
        """Return the file content: the default file with the current values."""
        return "".join(
            line
            if (name := _entry_name(line)) is None
            else f"{name}={self.get(name)}\n"
            for line in self._template
        )

    def save(self, path: str | os.PathLike[str] | None = None) -> None:
        """Write the configuration atomically (to its own file by default)."""
        write_text_atomic(path if path is not None else self._path, self.render())

    def get_property(self, name: str) -> ConfigProperty:
        self._section(name)
        return self._settings[name]

    def get_default(self, name: str) -> str | int:
        """Default value; BOOLEAN and INTEGER defaults are returned as ``int``."""
        value = self._default.get(self._section(name), name)
        numeric = self._settings[name].type in (
            PropertyType.BOOLEAN,
            PropertyType.INTEGER,
        )
        if numeric and value.isdigit():
            return int(value)
        return value

    def get_possible_values(self, name: str) -> list[Choice]:
        return self.get_property(name).choices

    def get_comment(self, name: str) -> str:
        """Help text of the entry (empty if it has none)."""
        self._section(name)
        return self._help.get(name, "")

    def get_sections(self) -> list[str]:
        return self._default.sections()

    def get_section_properties(self, section: str) -> list[str]:
        return [name for name, owner in self._sections.items() if owner == section]

    def validate(self, name: str) -> None:
        self.get_property(name).validate(self)

    def verify(self) -> None:
        """Validate all entries; raise the first error or warning."""
        for prop in self._settings.values():
            prop.validate(self)

    def verify_exceptions(self) -> None:
        """Validate all entries; raise the first error, ignore warnings."""
        for prop in self._settings.values():
            with contextlib.suppress(ConfigWarning):
                prop.validate(self)

    def verify_warnings(self) -> None:
        """Validate all entries; raise the first warning, ignore errors."""
        for prop in self._settings.values():
            try:
                prop.validate(self)
            except ConfigWarning:
                raise
            except ConfigError:
                pass
