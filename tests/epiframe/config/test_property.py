from pathlib import Path

import pytest

from epiframe.config.property import (
    ConfigError,
    ConfigProperty,
    ConfigWarning,
    CrossCheck,
    PropertyType,
)


class Values:
    """``ValueSource`` backed by a dict."""

    def __init__(self, **values: str) -> None:
        self.values = values

    def get(self, name: str) -> str:
        return self.values[name]

    def getint(self, name: str) -> int:
        return int(self.values[name])


def validate(prop: ConfigProperty, value: str, **others: str) -> None:
    prop.validate(Values(**{prop.name: value}, **others))


def fail(message: str) -> None:
    raise ValueError(message)


def warn(message: str) -> None:
    raise Warning(message)


def test_config_warning_is_a_config_error_and_a_warning() -> None:
    assert issubclass(ConfigWarning, ConfigError)
    assert issubclass(ConfigWarning, Warning)


def test_defaults() -> None:
    prop = ConfigProperty("entry")

    assert prop.type == PropertyType.STRING
    assert prop.not_empty is True
    assert prop.dependency is None
    assert prop.reset_needed is False
    assert prop.choices == []


def test_choices() -> None:
    assert ConfigProperty("entry", possible=("a", "b")).choices == ["a", "b"]
    assert ConfigProperty("entry", PropertyType.BOOLEAN).choices == [0, 1]


def test_property_type_values_match_1x_names() -> None:
    assert [member.value for member in PropertyType] == [
        "STRING",
        "FILE",
        "INTEGER",
        "FLOAT",
        "BOOLEAN",
        "STRING_LIST",
        "INT_LIST",
        "PASSWORD",
    ]


@pytest.mark.parametrize(
    ("prop", "values", "active"),
    [
        (ConfigProperty("entry"), {}, True),
        (ConfigProperty("entry", dependency="flag"), {"flag": "1"}, True),
        (ConfigProperty("entry", dependency="flag"), {"flag": "0"}, False),
        (
            ConfigProperty("entry", dependency="kind", dependency_value="SPI"),
            {"kind": "SPI"},
            True,
        ),
        (
            ConfigProperty("entry", dependency="kind", dependency_value="SPI"),
            {"kind": "HDMI"},
            False,
        ),
    ],
)
def test_is_active(prop: ConfigProperty, values: dict[str, str], active: bool) -> None:
    assert prop.is_active(Values(**values)) is active


def test_inactive_entry_is_not_validated() -> None:
    prop = ConfigProperty("entry", PropertyType.INTEGER, dependency="flag")

    validate(prop, "not a number", flag="0")
    with pytest.raises(ConfigError):
        validate(prop, "not a number", flag="1")


def test_empty_value() -> None:
    with pytest.raises(ConfigError, match=r"^entry configuration entry is missing!$"):
        validate(ConfigProperty("entry"), "")
    validate(ConfigProperty("entry", PropertyType.INTEGER, not_empty=False), "")


@pytest.mark.parametrize(
    ("prop_type", "value"),
    [
        (PropertyType.STRING, "text"),
        (PropertyType.PASSWORD, "secret%value"),
        (PropertyType.INTEGER, "-8"),
        (PropertyType.FLOAT, "2.1"),
        (PropertyType.BOOLEAN, "0"),
        (PropertyType.BOOLEAN, "1"),
        (PropertyType.STRING_LIST, "one two"),
        (PropertyType.INT_LIST, "1 2 3"),
    ],
)
def test_valid_types(prop_type: PropertyType, value: str) -> None:
    validate(ConfigProperty("entry", prop_type), value)


@pytest.mark.parametrize(
    ("prop_type", "value", "message"),
    [
        (PropertyType.INTEGER, "8.5", "is not an integer value!"),
        (PropertyType.FLOAT, "value", "is not a float value!"),
        (PropertyType.BOOLEAN, "2", "is not a boolean (0 or 1) value!"),
        (PropertyType.BOOLEAN, "yes", "is not a boolean (0 or 1) value!"),
        (PropertyType.INT_LIST, "1 a", "values are not all integers!"),
        (PropertyType.FILE, "/not/existing/file", "path does not exist!"),
    ],
)
def test_invalid_types(prop_type: PropertyType, value: str, message: str) -> None:
    with pytest.raises(ConfigError) as error:
        validate(ConfigProperty("entry", prop_type), value)
    assert str(error.value) == f"entry configuration entry {message}"


def test_file(tmp_path: Path) -> None:
    validate(ConfigProperty("entry", PropertyType.FILE), str(tmp_path))


@pytest.mark.parametrize("prop_type", [PropertyType.INTEGER, PropertyType.FLOAT])
def test_range(prop_type: PropertyType) -> None:
    prop = ConfigProperty("entry", prop_type, min_value=1, max_value=10)

    validate(prop, "1")
    validate(prop, "10")
    with pytest.raises(ConfigError, match="should be >= 1!"):
        validate(prop, "0")
    with pytest.raises(ConfigError, match="should be <= 10!"):
        validate(prop, "11")


def test_float_range_with_fractions() -> None:
    prop = ConfigProperty("entry", PropertyType.FLOAT, min_value=0.0, max_value=0.99)

    validate(prop, "0.99")
    with pytest.raises(ConfigError):
        validate(prop, "0.991")


@pytest.mark.parametrize("prop_type", [PropertyType.STRING_LIST, PropertyType.INT_LIST])
def test_list_length_and_delimiter(prop_type: PropertyType) -> None:
    prop = ConfigProperty("entry", prop_type, delimiter=",", length=2)

    validate(prop, "1,2")
    with pytest.raises(ConfigError, match="should have 2 values!"):
        validate(prop, "1,2,3")
    with pytest.raises(ConfigError, match="should have 2 values!"):
        validate(prop, "1;2")


def test_possible() -> None:
    prop = ConfigProperty("entry", PropertyType.INTEGER, possible=(0, 90))

    validate(prop, "90")
    with pytest.raises(ConfigError, match=r"value should be one of \[0, 90\]!"):
        validate(prop, "45")


def test_check() -> None:
    validate(ConfigProperty("entry", check=lambda value: None), "value")
    with pytest.raises(ConfigError) as error:
        validate(ConfigProperty("entry", check=fail), "bad")
    assert not isinstance(error.value, ConfigWarning)
    assert str(error.value) == "entry configuration entry error: bad"
    assert isinstance(error.value.__cause__, ValueError)


def test_check_warning() -> None:
    with pytest.raises(ConfigWarning, match="entry configuration entry error: odd"):
        validate(ConfigProperty("entry", check=warn), "odd")


def test_cross_check_gets_values_in_order() -> None:
    received: list[list[str]] = []
    prop = ConfigProperty(
        "first", cross_check=CrossCheck(received.append, ("first", "second"))
    )

    validate(prop, "1", second="2")

    assert received == [["1", "2"]]


@pytest.mark.parametrize(
    ("warning", "expected"), [(False, ConfigError), (True, ConfigWarning)]
)
def test_cross_check_failure(warning: bool, expected: type[ConfigError]) -> None:
    def check(values: list[str]) -> None:
        raise ValueError("first > second")

    prop = ConfigProperty(
        "first", cross_check=CrossCheck(check, ("first", "second"), warning=warning)
    )

    with pytest.raises(
        expected, match="first configuration entry error: first > second"
    ):
        validate(prop, "2", second="1")
