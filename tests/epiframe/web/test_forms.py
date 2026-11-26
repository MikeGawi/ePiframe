from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from flask import Flask, get_flashed_messages
from werkzeug.datastructures import MultiDict
from wtforms import BooleanField, FloatField, IntegerField, SelectField, StringField
from wtforms.widgets import PasswordInput

from epiframe.config.property import ConfigProperty, PropertyType
from epiframe.plugins.base import PluginConfig
from epiframe.web.forms import apply_form, label, reset_needed, settings_form

DEFAULT = """\
[General]
# Enable the plugin
is_enabled=1
# A name
name=frame
# A number
count=5
# A ratio
ratio=0.5
# A mode
mode=fast
# A key
key=abc
# Ids
ids=1,2
# Depends on is_enabled
detail=x
# Needs a restart
port=80
# A warning for "warn"
note=ok
"""
NAMES = [
    "is_enabled",
    "name",
    "count",
    "ratio",
    "mode",
    "key",
    "ids",
    "detail",
    "port",
    "note",
]


def warn(value: str) -> None:
    if value == "warn":
        raise UserWarning("Just so you know")


SETTINGS = [
    ConfigProperty("is_enabled", PropertyType.BOOLEAN),
    ConfigProperty("count", PropertyType.INTEGER, min_value=1, max_value=10),
    ConfigProperty("ratio", PropertyType.FLOAT, min_value=0, max_value=1),
    ConfigProperty("mode", possible=["fast", "slow"]),
    ConfigProperty("key", PropertyType.PASSWORD),
    ConfigProperty("ids", PropertyType.INT_LIST, delimiter=","),
    ConfigProperty("detail", dependency="is_enabled"),
    ConfigProperty("port", PropertyType.INTEGER, reset_needed=True),
    ConfigProperty("note", check=warn),
]


@pytest.fixture
def config(tmp_path: Path) -> PluginConfig:
    (tmp_path / "default").mkdir()
    (tmp_path / "default" / "config.default").write_text(DEFAULT)
    (tmp_path / "config.cfg").write_text(DEFAULT)
    return PluginConfig(tmp_path, SETTINGS)


@pytest.fixture
def request_context() -> Iterator[None]:
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", WTF_CSRF_ENABLED=False)  # noqa: S106
    with app.test_request_context():
        yield


def test_label(config: PluginConfig) -> None:
    assert label(config, "is_enabled") == "Is Enabled"
    assert label(config, "detail") == "- Detail"


@pytest.mark.usefixtures("request_context")
def test_fields(config: PluginConfig) -> None:
    form = settings_form(config, NAMES)

    types = {name: type(getattr(form, name)) for name in NAMES}
    assert types == {
        "is_enabled": BooleanField,
        "name": StringField,
        "count": IntegerField,
        "ratio": FloatField,
        "mode": SelectField,
        "key": StringField,
        "ids": StringField,
        "detail": StringField,
        "port": IntegerField,
        "note": StringField,
    }
    assert isinstance(form.key.widget, PasswordInput)
    assert [choice.value for choice in form.mode.choices] == ["fast", "slow"]
    assert form.count.label.text == "Count"
    assert form.count.description == "A number"


@pytest.mark.usefixtures("request_context")
def test_values(config: PluginConfig) -> None:
    config.set("is_enabled", "0")
    config.set("count", "7")

    form = settings_form(config, NAMES)

    assert form.is_enabled.data is False
    assert form.count.data == 7
    assert form.name.data == "frame"


@pytest.mark.usefixtures("request_context")
def test_render_classes(config: PluginConfig) -> None:
    form = settings_form(config, NAMES)

    assert form.name.render_kw == {
        "class": " form-control form-control-sm",
        "fill": "flex-fill",
    }
    assert form.count.render_kw["fill"] == ""
    assert form.mode.render_kw["class"] == " form-select form-select-sm"
    assert form.is_enabled.render_kw["class"] == " checkbox form-check-input"
    assert form.detail.render_kw == {
        "class": "is_enabled form-control form-control-sm",
        "fill": "flex-fill",
        "pad": "px-3",
        "classdep": "is_enabled",
        "depval": "1",
    }


@pytest.mark.usefixtures("request_context")
def test_inactive_dependency_is_disabled(config: PluginConfig) -> None:
    config.set("is_enabled", "0")

    form = settings_form(config, ["detail"])

    assert form.detail.render_kw["disabled"] == "disabled"


@pytest.mark.usefixtures("request_context")
def test_errors_are_marked(config: PluginConfig) -> None:
    config.set("count", "11")
    config.set("note", "warn")  # warnings aren't shown on the field

    form = settings_form(config, NAMES)

    assert "count" in form.count.errors
    assert form.count.render_kw["class"].endswith(" is-invalid")
    assert form.count.render_kw["invalid"] == " is-invalid"
    assert form.note.errors == ()


def test_reset_needed(config: PluginConfig) -> None:
    assert reset_needed(config, NAMES)
    assert not reset_needed(config, ["name", "count"])


# ------------------------------------------------------------------ posted forms


def post(**values: str) -> MultiDict[str, str]:
    return MultiDict(values)


def saved(config: PluginConfig) -> str:
    return config.path.read_text()


@pytest.mark.usefixtures("request_context")
def test_values_stay_in_memory(config: PluginConfig) -> None:
    apply_form(config, NAMES, post(name="new", count="3"))

    # the checkbox of is_enabled wasn't posted: unchecked
    assert (config.get("name"), config.get("count")) == ("new", "3")
    assert config.get("is_enabled") == "0"
    assert saved(config) == DEFAULT


@pytest.mark.usefixtures("request_context")
def test_checked_box(config: PluginConfig) -> None:
    config.set("is_enabled", "0")

    apply_form(config, ["is_enabled"], post(is_enabled="y"))

    assert config.get("is_enabled") == "1"


@pytest.mark.usefixtures("request_context")
def test_save(config: PluginConfig) -> None:
    apply_form(config, ["name"], post(name="new", SAVE="SAVE"))

    assert "name=new" in saved(config)


@pytest.mark.usefixtures("request_context")
def test_save_with_a_warning(config: PluginConfig) -> None:
    apply_form(config, ["note"], post(note="warn", SAVE="SAVE"))

    assert "note=warn" in saved(config)
    assert get_flashed_messages() == [
        "note configuration entry error: Just so you know"
    ]


@pytest.mark.usefixtures("request_context")
def test_errors_are_not_saved(config: PluginConfig) -> None:
    apply_form(config, ["count", "note"], post(count="11", note="warn", SAVE="SAVE"))

    assert saved(config) == DEFAULT
    assert config.get("count") == "11"  # shown with the error
    assert get_flashed_messages() == []


@pytest.mark.usefixtures("request_context")
def test_cancel(config: PluginConfig) -> None:
    apply_form(config, ["name"], post(name="new"))
    apply_form(config, ["name"], post(CANCEL="CANCEL"))

    assert config.get("name") == "frame"


@pytest.mark.usefixtures("request_context")
def test_defaults(config: PluginConfig) -> None:
    config.set("count", "7")
    config.set("name", "other")

    apply_form(config, ["count"], post(count="7", DEFAULTS="DEFAULTS"))

    assert (config.get("count"), config.get("name")) == ("5", "other")


@pytest.mark.usefixtures("request_context")
def test_reset_one_entry(config: PluginConfig) -> None:
    form: dict[str, Any] = {"name": "new", "count": "7", "-<[count]>-": ""}

    apply_form(config, ["name", "count"], post(**form))

    assert (config.get("name"), config.get("count")) == ("new", "5")


@pytest.mark.usefixtures("request_context")
def test_reset_of_another_section_is_ignored(config: PluginConfig) -> None:
    config.set("count", "7")

    apply_form(config, ["name"], post(name="new", **{"-<[count]>-": ""}))

    assert config.get("count") == "7"
