"""Declarative description and validation of a single configuration entry."""

import os
from collections.abc import Callable, Sequence
from dataclasses import KW_ONLY, dataclass
from enum import StrEnum
from typing import Protocol, TypeAlias

Choice: TypeAlias = str | int | float
"""A value offered by an entry with a fixed set of possible values."""

BOOLEAN_CHOICES: tuple[Choice, ...] = (0, 1)


class ConfigError(Exception):
    """A configuration entry (or file) is invalid."""


class ConfigWarning(ConfigError, Warning):
    """A configuration entry is suspicious, but the frame can still run.

    It is also a ``Warning``, so callers that handle warnings before errors
    (``except Warning`` first, then ``except Exception``) keep working.
    """


class PropertyType(StrEnum):
    """Type of a configuration entry; decides validation and the WebUI field."""

    STRING = "STRING"
    FILE = "FILE"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    STRING_LIST = "STRING_LIST"
    INT_LIST = "INT_LIST"
    PASSWORD = "PASSWORD"  # noqa: S105 (type name, not a password)


class ValueSource(Protocol):
    """Read access to configuration values (implemented by ``ConfigBase``)."""

    def get(self, name: str) -> str: ...

    def getint(self, name: str) -> int: ...


@dataclass(frozen=True)
class CrossCheck:
    """Check that needs the values of several entries (e.g. a start/stop time pair).

    ``function`` gets the values of ``names`` (in that order) and raises on error.
    With ``warning=True`` a failure is reported as a ``ConfigWarning``.
    """

    function: Callable[[list[str]], object]
    names: Sequence[str]
    warning: bool = False


@dataclass(frozen=True)
class ConfigProperty:
    """Validation rules and WebUI metadata of one configuration entry.

    The entry is validated only when it is active (see ``is_active``). An empty
    value is an error when ``not_empty`` is set and is otherwise not checked
    further.
    """

    name: str
    type: PropertyType = PropertyType.STRING
    _: KW_ONLY
    not_empty: bool = True
    # active only when the ``dependency`` entry is 1 (BOOLEAN) or, with
    # ``dependency_value``, equal to that value
    dependency: str | None = None
    dependency_value: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    possible: Sequence[Choice] = ()
    length: int | None = None
    delimiter: str | None = None
    # raises on an invalid value; a raised ``Warning`` becomes a ``ConfigWarning``
    check: Callable[[str], object] | None = None
    cross_check: CrossCheck | None = None
    # applied to the value when the file is loaded (legacy value formats)
    convert: Callable[[str], str] | None = None
    # changing the entry needs a service restart
    reset_needed: bool = False

    @property
    def choices(self) -> list[Choice]:
        """Values offered in the WebUI (``[0, 1]`` for BOOLEAN entries)."""
        if self.type == PropertyType.BOOLEAN:
            return list(BOOLEAN_CHOICES)
        return list(self.possible)

    def is_active(self, values: ValueSource) -> bool:
        """Return whether the entry is used with the current values."""
        if not self.dependency:
            return True
        if self.dependency_value is None:
            return bool(values.getint(self.dependency))
        return values.get(self.dependency) == self.dependency_value

    def validate(self, values: ValueSource) -> None:
        """Raise ``ConfigError`` (or ``ConfigWarning``) if the value is invalid."""
        if not self.is_active(values):
            return
        value = values.get(self.name)
        if not value:
            if self.not_empty:
                raise ConfigError(f"{self.name} configuration entry is missing!")
            return
        _TYPE_CHECKS[self.type](self, value)
        self._check_possible(value)
        self._run_check(value)
        self._run_cross_check(values)

    def _error(self, message: str) -> ConfigError:
        return ConfigError(f"{self.name} configuration entry {message}")

    def _check_file(self, value: str) -> None:
        if not os.path.exists(value):
            raise self._error("path does not exist!")

    def _check_integer(self, value: str) -> None:
        try:
            number = int(value)
        except ValueError:
            raise self._error("is not an integer value!") from None
        self._check_range(number)

    def _check_float(self, value: str) -> None:
        try:
            number = float(value)
        except ValueError:
            raise self._error("is not a float value!") from None
        self._check_range(number)

    def _check_range(self, number: float) -> None:
        if self.min_value is not None and number < self.min_value:
            raise self._error(f"should be >= {self.min_value}!")
        if self.max_value is not None and number > self.max_value:
            raise self._error(f"should be <= {self.max_value}!")

    def _check_boolean(self, value: str) -> None:
        if value.strip() not in ("0", "1"):
            raise self._error("is not a boolean (0 or 1) value!")

    def _check_string_list(self, value: str) -> list[str]:
        items = value.split(self.delimiter)
        if self.length and len(items) != self.length:
            raise self._error(f"should have {self.length} values!")
        return items

    def _check_int_list(self, value: str) -> None:
        try:
            [int(item) for item in self._check_string_list(value)]
        except ValueError:
            raise self._error("values are not all integers!") from None

    def _check_nothing(self, value: str) -> None:
        pass

    def _check_possible(self, value: str) -> None:
        if self.possible and value not in [str(choice) for choice in self.possible]:
            raise self._error(f"value should be one of {list(self.possible)}!")

    def _run_check(self, value: str) -> None:
        if not self.check:
            return
        try:
            self.check(value)
        except Warning as warning:
            raise ConfigWarning(self._message(warning)) from warning
        except Exception as exception:
            raise ConfigError(self._message(exception)) from exception

    def _run_cross_check(self, values: ValueSource) -> None:
        if not self.cross_check:
            return
        try:
            self.cross_check.function(
                [values.get(name) for name in self.cross_check.names]
            )
        except Exception as exception:
            error = ConfigWarning if self.cross_check.warning else ConfigError
            raise error(self._message(exception)) from exception

    def _message(self, exception: BaseException) -> str:
        return f"{self.name} configuration entry error: {exception}"


_TYPE_CHECKS: dict[PropertyType, Callable[[ConfigProperty, str], object]] = {
    PropertyType.STRING: ConfigProperty._check_nothing,
    PropertyType.PASSWORD: ConfigProperty._check_nothing,
    PropertyType.FILE: ConfigProperty._check_file,
    PropertyType.INTEGER: ConfigProperty._check_integer,
    PropertyType.FLOAT: ConfigProperty._check_float,
    PropertyType.BOOLEAN: ConfigProperty._check_boolean,
    PropertyType.STRING_LIST: ConfigProperty._check_string_list,
    PropertyType.INT_LIST: ConfigProperty._check_int_list,
}
