"""The settings forms of the WebUI (ePiframe's and the plugins' ``config.cfg``).

The forms keep the 1.x pages (``settings.html``, ``plugins.html``) working until
the new UI (Phase 5). Changes stay in the configuration object in memory until
they are saved: a page posts the values of its section together with the button
that was pressed (``SAVE``, ``CANCEL``, ``DEFAULTS`` or the ``-<[name]>-``
"Reset" button of one entry).
"""

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from flask import flash, session
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    Field,
    FloatField,
    IntegerField,
    SelectChoice,
    SelectField,
    StringField,
)
from wtforms.widgets import NumberInput, PasswordInput

from epiframe.config.base import ConfigBase
from epiframe.config.property import (
    ConfigError,
    ConfigProperty,
    ConfigWarning,
    PropertyType,
)

RESET_BUTTON = re.compile(r"^-<\[(.+)\]>-$")
CONTROL = " form-control form-control-sm"
SELECT = " form-select form-select-sm"
CHECKBOX = " checkbox form-check-input"
INVALID = " is-invalid"
FALSE_VALUES = (0, "0", "")
CHOICE_TYPES = (PropertyType.STRING, PropertyType.INTEGER, PropertyType.FLOAT)
FieldFactory = Callable[[ConfigProperty, dict[str, Any]], Field]


def label(config: ConfigBase, name: str) -> str:
    """``local_path`` → ``- Local Path`` (dependent entries are indented)."""
    prefix = "- " if config.get_property(name).dependency else ""
    return prefix + name.replace("_", " ").title()


def _render(config: ConfigBase, prop: ConfigProperty) -> dict[str, str]:
    render = {"class": (prop.dependency or "") + CONTROL, "fill": "flex-fill"}
    if prop.dependency:
        render |= {
            "pad": "px-3",
            "classdep": prop.dependency,
            "depval": prop.dependency_value or "1",
        }
        if not prop.is_active(config):
            render["disabled"] = "disabled"
    return render


def _select(prop: ConfigProperty, options: dict[str, Any]) -> Field:
    options["render_kw"] |= {"class": (prop.dependency or "") + SELECT, "fill": ""}
    # WTForms >= 3.3 silently drops int choices and deprecates tuples
    choices = [SelectChoice(value=value, label=str(value)) for value in prop.choices]
    return SelectField(choices=choices, **options)


def _integer(prop: ConfigProperty, options: dict[str, Any]) -> Field:
    options["render_kw"]["fill"] = ""
    widget = NumberInput(min=prop.min_value, max=prop.max_value)
    return IntegerField(widget=widget, **options)


def _float(prop: ConfigProperty, options: dict[str, Any]) -> Field:
    options["render_kw"]["fill"] = ""
    widget = NumberInput(min=prop.min_value, max=prop.max_value, step="0.1")
    return FloatField(widget=widget, **options)


def _boolean(prop: ConfigProperty, options: dict[str, Any]) -> Field:
    options["render_kw"]["class"] = (prop.dependency or "") + CHECKBOX
    return BooleanField(false_values=FALSE_VALUES, **options)


def _text(prop: ConfigProperty, options: dict[str, Any]) -> Field:
    return StringField(**options)


def _password(prop: ConfigProperty, options: dict[str, Any]) -> Field:
    return StringField(widget=PasswordInput(hide_value=False), **options)


FIELDS: dict[PropertyType, FieldFactory] = {
    PropertyType.STRING: _text,
    PropertyType.INTEGER: _integer,
    PropertyType.FLOAT: _float,
    PropertyType.INT_LIST: _text,
    PropertyType.STRING_LIST: _text,
    PropertyType.FILE: _text,
    PropertyType.BOOLEAN: _boolean,
    PropertyType.PASSWORD: _password,
}


def _factory(prop: ConfigProperty) -> FieldFactory:
    if prop.choices and prop.type in CHOICE_TYPES:
        return _select
    return FIELDS[prop.type]


def _field(config: ConfigBase, name: str) -> Field:
    prop = config.get_property(name)
    options = {
        "label": label(config, name),
        "default": config.get_default(name),
        "description": config.get_comment(name),
        "render_kw": _render(config, prop),
    }
    return _factory(prop)(prop, options)


def _value(config: ConfigBase, name: str) -> str | int:
    is_boolean = config.get_property(name).type == PropertyType.BOOLEAN
    return config.getint(name) if is_boolean else config.get(name)


def _mark_error(config: ConfigBase, field: Any, name: str) -> None:
    try:
        config.validate(name)
    except ConfigWarning:
        return
    except ConfigError as error:
        field.errors = str(error)
        field.render_kw["class"] += INVALID
        field.render_kw["invalid"] = INVALID


def settings_form(config: ConfigBase, names: Iterable[str]) -> Any:
    """The form of the entries ``names`` with their current values and errors."""

    class SettingsForm(FlaskForm):  # type: ignore[misc]  # flask_wtf is untyped
        pass

    names = list(names)
    for name in names:
        setattr(SettingsForm, name, _field(config, name))
    form = SettingsForm(data={name: _value(config, name) for name in names})
    for name in names:
        _mark_error(config, getattr(form, name), name)
    return form


def reset_needed(config: ConfigBase, names: Iterable[str]) -> bool:
    """Whether changing one of the entries needs a service restart."""
    return any(config.get_property(name).reset_needed for name in names)


# ------------------------------------------------------------------ posted forms


def _set_values(
    config: ConfigBase, names: Iterable[str], form: Mapping[str, str]
) -> None:
    for name in names:
        if config.get_property(name).type == PropertyType.BOOLEAN:
            config.set(name, "1" if form.get(name) == "y" else "0")
        elif name in form:
            config.set(name, form[name])


def _reset(config: ConfigBase, names: Iterable[str]) -> None:
    for name in names:
        config.set(name, str(config.get_default(name)))


def _save(config: ConfigBase, names: Iterable[str]) -> None:
    try:
        config.verify_warnings()
    except ConfigWarning as warning:
        flash(str(warning))
    try:
        config.verify_exceptions()
    except ConfigError:
        session.pop("_flashes", None)  # the page shows the errors
        return
    config.save()


def _cancel(config: ConfigBase, names: Iterable[str]) -> None:
    config.reload()


BUTTONS: dict[str, Callable[[ConfigBase, list[str]], None]] = {
    "SAVE": _save,
    "DEFAULTS": _reset,
    "CANCEL": _cancel,
}


def _reset_button(form: Mapping[str, str]) -> str | None:
    for key in form:
        if match := RESET_BUTTON.match(key):
            return match.group(1)
    return None


def apply_form(
    config: ConfigBase, names: Iterable[str], form: Mapping[str, str]
) -> None:
    """Take the posted values of ``names`` and do what the pressed button says."""
    names = list(names)
    _set_values(config, names, form)
    single = _reset_button(form)
    if single in names:
        _reset(config, [single])
        return
    for button, handle in BUTTONS.items():
        if form.get(button) == button:
            handle(config, names)
