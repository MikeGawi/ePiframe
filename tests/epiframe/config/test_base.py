import os
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

from epiframe.config.base import ConfigBase, LegacyEntry
from epiframe.config.property import (
    ConfigError,
    ConfigProperty,
    ConfigWarning,
    CrossCheck,
    PropertyType,
)

DEFAULT = """\
; hidden comment
[First]
# Help of the flag,
# second line.
flag=1
; hidden comment between help and entry does not reset the help
# Help of the number.
number=10

name=default name
[Second]
# Help of the date.
date=2020-01-01
secret=
label=text
"""


def warn(value: str) -> None:
    raise Warning("suspicious")


def legacy_flag(value: str) -> str:
    return "0" if value == "no" else "1"


class Config(ConfigBase):
    LEGACY = (LegacyEntry("old_flag", "flag", legacy_flag),)

    def load_settings(self) -> list[ConfigProperty]:
        return [
            ConfigProperty(
                "number", PropertyType.INTEGER, min_value=1, reset_needed=True
            ),
            ConfigProperty("flag", PropertyType.BOOLEAN),
            ConfigProperty("name", dependency="flag", check=warn),
            ConfigProperty("date", convert=lambda value: value.replace(".", "-")),
            ConfigProperty("secret", PropertyType.PASSWORD, not_empty=False),
        ]


@pytest.fixture
def default_file(tmp_path: Path) -> Path:
    path = tmp_path / "config.default"
    path.write_text(DEFAULT)
    return path


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    return tmp_path / "config.cfg"


def load(config_file: Path, default_file: Path, content: str | None = None) -> Config:
    if content is not None:
        config_file.write_text(content)
    return Config(config_file, default_file)


def test_missing_file_is_created_from_default(
    config_file: Path, default_file: Path
) -> None:
    config = load(config_file, default_file)

    assert config_file.read_text() == DEFAULT
    assert config.path == config_file
    assert config.default_path == default_file
    assert config.get_obsolete() == []


def test_unchanged_file_is_not_saved(config_file: Path, default_file: Path) -> None:
    config_file.write_text(DEFAULT)
    os.utime(config_file, (0, 0))

    load(config_file, default_file)

    assert config_file.stat().st_mtime == 0


def test_getters(config_file: Path, default_file: Path) -> None:
    config = load(config_file, default_file)

    assert config.get("name") == "default name"
    assert config.getint("number") == 10
    assert config.get_sections() == ["First", "Second"]
    assert config.get_section_properties("First") == ["flag", "number", "name"]
    assert config.get_section_properties("Second") == ["date", "secret", "label"]
    assert config.get_section_properties("Unknown") == []
    assert config.get_comment("flag") == "Help of the flag, second line."
    assert config.get_comment("number") == "Help of the number."
    assert config.get_comment("secret") == ""
    assert config.get_default("number") == 10
    assert config.get_default("flag") == 1
    assert config.get_default("name") == "default name"
    assert config.get_default("secret") == ""
    assert config.get_possible_values("flag") == [0, 1]
    assert config.get_property("number").reset_needed is True


def test_settings_order_and_undeclared_entries(
    config_file: Path, default_file: Path
) -> None:
    config = load(config_file, default_file)

    assert [prop.name for prop in config.settings] == [
        "number",
        "flag",
        "name",
        "date",
        "secret",
        "label",
    ]
    assert config.get_property("label") == ConfigProperty("label")


@pytest.mark.parametrize(
    "call",
    [
        lambda config: config.get("unknown"),
        lambda config: config.set("unknown", "1"),
        lambda config: config.get_property("unknown"),
        lambda config: config.get_comment("unknown"),
        lambda config: config.get_default("unknown"),
        lambda config: config.getint("name"),
    ],
)
def test_parse_errors(
    config_file: Path, default_file: Path, call: Callable[[Config], object]
) -> None:
    config = load(config_file, default_file)

    with pytest.raises(
        ConfigError, match=r"^Error parsing (unknown|name) configuration entry$"
    ):
        call(config)


def test_declared_entry_missing_in_default(
    config_file: Path, default_file: Path
) -> None:
    class Broken(ConfigBase):
        def load_settings(self) -> list[ConfigProperty]:
            return [ConfigProperty("flag"), ConfigProperty("missing")]

    with pytest.raises(ConfigError, match=r"Entries \['missing'\] are not in"):
        Broken(config_file, default_file)


def test_set_and_save(config_file: Path, default_file: Path) -> None:
    config = load(config_file, default_file)

    config.set("name", "100% new")
    config.save()

    assert config_file.read_text() == DEFAULT.replace(
        "name=default name", "name=100% new"
    )
    assert load(config_file, default_file).get("name") == "100% new"


def test_save_to_another_path(
    tmp_path: Path, config_file: Path, default_file: Path
) -> None:
    config = load(config_file, default_file)
    other = tmp_path / "other.cfg"

    config.save(other)

    assert other.read_text() == DEFAULT


def test_save_keeps_file_mode(config_file: Path, default_file: Path) -> None:
    config = load(config_file, default_file)
    config_file.chmod(0o640)

    config.save()

    assert stat.S_IMODE(config_file.stat().st_mode) == 0o640


def test_failed_save_leaves_file_and_no_temporary(
    config_file: Path, default_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load(config_file, default_file)
    config.set("name", "changed")

    def broken_render() -> str:
        raise OSError("disk full")

    monkeypatch.setattr(config, "render", broken_render)
    with pytest.raises(OSError, match="disk full"):
        config.save()

    assert config_file.read_text() == DEFAULT
    assert {path.name for path in config_file.parent.iterdir()} == {
        "config.default",
        "config.cfg",
    }


def test_missing_entries_and_sections_are_added(
    config_file: Path, default_file: Path
) -> None:
    config = load(config_file, default_file, "[First]\nnumber=5\n")

    assert config.getint("number") == 5
    assert config.get("date") == "2020-01-01"
    assert config_file.read_text() == DEFAULT.replace("number=10", "number=5")


def test_entries_are_matched_by_name_not_section(
    config_file: Path, default_file: Path
) -> None:
    config = load(
        config_file, default_file, "[Second]\nnumber=5\n[Other]\nname=moved\n"
    )

    assert config.getint("number") == 5
    assert config.get("name") == "moved"
    assert config.get_obsolete() == []
    assert config.get_sections() == ["First", "Second"]
    assert "[Other]" not in config_file.read_text()


def test_obsolete_entries_are_dropped(config_file: Path, default_file: Path) -> None:
    config = load(
        config_file,
        default_file,
        "[First]\ngone=1\nnumber=5\n[Removed section]\nalso_gone=x\n",
    )

    assert config.get_obsolete() == ["gone", "also_gone"]
    saved = config_file.read_text()
    assert "gone" not in saved
    assert "Removed section" not in saved
    assert load(config_file, default_file).get_obsolete() == []


def test_legacy_entry_is_converted(config_file: Path, default_file: Path) -> None:
    config = load(config_file, default_file, "[Old]\nold_flag=no\n")

    assert config.getint("flag") == 0
    assert config.get_obsolete() == []
    assert "old_flag" not in config_file.read_text()


def test_legacy_entry_does_not_override_new_entry(
    config_file: Path, default_file: Path
) -> None:
    config = load(config_file, default_file, "[First]\nflag=1\nold_flag=no\n")

    assert config.getint("flag") == 1
    assert config.get_obsolete() == ["old_flag"]


def test_convert_is_applied_and_saved(config_file: Path, default_file: Path) -> None:
    config = load(
        config_file, default_file, DEFAULT.replace("2020-01-01", "2021.02.03")
    )

    assert config.get("date") == "2021-02-03"
    assert "date=2021-02-03" in config_file.read_text()


def test_reload_discards_unsaved_changes(config_file: Path, default_file: Path) -> None:
    config = load(config_file, default_file)
    config.set("name", "unsaved")

    assert config.reload() is False
    assert config.get("name") == "default name"


def test_values_are_not_interpolated(config_file: Path, default_file: Path) -> None:
    config = load(
        config_file, default_file, DEFAULT.replace("secret=", "secret=%(x)s%")
    )

    assert config.get("secret") == "%(x)s%"


def test_verify(config_file: Path, default_file: Path) -> None:
    config = load(config_file, default_file)
    config.set("flag", "0")  # "name" (with a warning check) is not active

    config.verify()
    config.verify_exceptions()
    config.verify_warnings()
    config.validate("number")


def test_verify_with_error(config_file: Path, default_file: Path) -> None:
    config = load(config_file, default_file)
    config.set("flag", "0")
    config.set("number", "0")

    with pytest.raises(ConfigError, match="number configuration entry should be >= 1!"):
        config.verify()
    with pytest.raises(ConfigError):
        config.verify_exceptions()
    with pytest.raises(ConfigError):
        config.validate("number")
    config.verify_warnings()


def test_verify_with_warning(config_file: Path, default_file: Path) -> None:
    config = load(config_file, default_file)

    with pytest.raises(
        ConfigWarning, match="name configuration entry error: suspicious"
    ):
        config.verify()
    with pytest.raises(ConfigWarning):
        config.verify_warnings()
    config.verify_exceptions()


def test_verify_warnings_raises_first_warning_after_errors(
    config_file: Path, default_file: Path
) -> None:
    config = load(config_file, default_file)
    config.set("number", "0")  # error before the "name" warning

    with pytest.raises(ConfigWarning):
        config.verify_warnings()
    with pytest.raises(ConfigError) as error:
        config.verify_exceptions()
    assert not isinstance(error.value, ConfigWarning)


def test_cross_check_reads_other_entries(config_file: Path, default_file: Path) -> None:
    received: list[list[str]] = []

    class Checked(ConfigBase):
        def load_settings(self) -> list[ConfigProperty]:
            return [
                ConfigProperty(
                    "number",
                    cross_check=CrossCheck(received.append, ("number", "date")),
                )
            ]

    Checked(config_file, default_file).validate("number")

    assert received == [["10", "2020-01-01"]]
