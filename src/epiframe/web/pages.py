"""The WebUI pages (1.x templates until the new UI of Phase 5)."""

import os
import tempfile
from typing import Any

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import login_user, logout_user

from epiframe.config import manager as config_manager
from epiframe.config import paths
from epiframe.plugins.base import Plugin
from epiframe.stats.metrics import GROUPS
from epiframe.stats.store import Period
from epiframe.users.store import UserError
from epiframe.version import VERSION
from epiframe.web.api import ApiError, login_required
from epiframe.web.context import context
from epiframe.web.endpoints import save_upload
from epiframe.web.forms import apply_form, reset_needed, settings_form

ORDER = "Execution Order"  # the plugin order "page" of the plugins page
NO_PLUGINS = (
    "<ul><li>There are no <b>ePiframe</b> plugins installed! </li><li>Go to <a "
    'href="https://github.com/MikeGawi/ePiframe_plugin" target="_blank">'
    "ePiframe_plugin</a> site to find something for You!</li></ul>"
)
GET_POST = ("GET", "POST")

# ------------------------------------------------------------------ login/logout


def login() -> Any:
    if request.method == "GET":
        return render_template("login.html")
    username = request.form.get("username")
    if not username:
        flash("Please fill in all required data!")
        return redirect("/")
    try:
        user = context().users.authenticate(username, request.form.get("password", ""))
    except UserError:
        flash("Please check your login details and try again!")
        return redirect("/")
    login_user(user, remember=bool(request.form.get("remember")))
    return redirect("/")


@login_required
def logout() -> Any:
    logout_user()
    return redirect("/")


# ---------------------------------------------------------------- simple pages


@login_required
def index() -> Any:
    return render_template("index.html", version=VERSION)


@login_required
def tools() -> Any:
    actions = [action for action in context().actions.values() if action.button]
    return render_template("tools.html", version=VERSION, actions=actions)


@login_required
def logs() -> Any:
    return render_template("logs.html")


@login_required
def stats() -> Any:
    return render_template(
        "stats.html", version=VERSION, groups=GROUPS, periods=list(Period)
    )


@login_required
def upload_photo_page() -> Any:
    """The upload form of the home page (the REST API answers JSON instead)."""
    file = request.files.get("file")
    try:
        if file is None:
            raise ApiError("No file!")
        save_upload(context().frame, file)
    except ApiError as error:
        flash(error.message)
    return redirect("/")


# -------------------------------------------------------------------- settings


@login_required
def settings_home() -> Any:
    frame = context().frame
    frame.refresh()
    return redirect(url_for("settings", section=frame.config.get_sections()[0]))


@login_required
def settings(section: str) -> Any:
    config = context().frame.config
    if section not in config.get_sections():
        abort(404)
    names = config.get_section_properties(section)
    if request.method == "POST":
        apply_form(config, names, request.form)
        return redirect(request.path)
    return render_template(
        "settings.html",
        form=settings_form(config, names),
        navlabels=config.get_sections(),
        reset_needed=reset_needed(config, names),
        version=VERSION,
    )


@login_required
def export() -> Any:
    return send_file(
        context().frame.config_file.absolute(),
        as_attachment=True,
        download_name="config.cfg",
    )


def _import(path: str) -> None:
    frame = context().frame
    imported = config_manager.ConfigManager(path, paths.CONFIG_FILE_DEFAULT)
    imported.verify()
    imported.save(frame.config_file)
    frame.refresh()


@login_required
def import_settings() -> Any:
    file = request.files.get("file")
    if file is None:
        flash("No settings file!")
        return redirect(url_for("settings_home"))
    handle, temporary = tempfile.mkstemp(suffix=".cfg")
    os.close(handle)
    try:
        file.save(temporary)
        _import(temporary)
        flash("File has been imported successfully!")
    except Exception as error:  # any problem of the file is shown to the user
        flash(f"Error importing settings file: {error}")
    finally:
        os.remove(temporary)
    return redirect(url_for("settings_home"))


# --------------------------------------------------------------------- plugins


def _plugin_names(plugins: list[Plugin]) -> list[str]:
    return [plugin.name for plugin in plugins] + [ORDER]


def _plugin(plugins: list[Plugin], name: str | None) -> Plugin:
    if not name:
        return plugins[0]
    for plugin in plugins:
        if plugin.name == name:
            return plugin
    abort(404)


def _order_page(plugins: list[Plugin]) -> Any:
    manager = context().frame.plugins
    order = manager.read_order()
    if request.method == "POST":
        if request.form.get("SAVE") == "SAVE":
            manager.save_order(request.form.get("list_order", "").split(","))
        elif request.form.get("DEFAULTS") == "DEFAULTS":
            manager.save_order(sorted(order))
        return redirect(url_for("plugins", plugin=ORDER))
    return render_template(
        "plugins.html",
        info="",
        order=order,
        plugin_name=ORDER,
        sett_name="",
        plugins=_plugin_names(plugins),
        form=None,
        navlabels="",
        reset_needed=False,
        version=VERSION,
    )


def _plugin_page(plugins: list[Plugin]) -> Any:
    plugin = _plugin(plugins, request.args.get("plugin"))
    config = plugin.config
    section = request.args.get("variable") or config.get_sections()[0]
    names = config.get_section_properties(section)
    if request.method == "POST":
        apply_form(config, names, request.form)
        return redirect(url_for("plugins", plugin=plugin.name, variable=section))
    return render_template(
        "plugins.html",
        info="",
        order="",
        plugin_name=plugin.name,
        sett_name=section,
        plugins=_plugin_names(plugins),
        form=settings_form(config, names),
        navlabels=config.get_sections(),
        reset_needed=reset_needed(config, names),
        version=VERSION,
    )


@login_required
def plugins() -> Any:
    frame = context().frame
    frame.refresh()
    loaded = frame.plugins.plugins
    if not loaded:
        return render_template("plugins.html", info=NO_PLUGINS)
    if request.args.get("plugin") == ORDER:
        return _order_page(loaded)
    return _plugin_page(loaded)


def register(app: Flask) -> None:
    """Add the pages to ``app``."""
    pages = (
        ("/", index, ("GET",)),
        ("/login", login, GET_POST),
        ("/logout", logout, ("GET",)),
        ("/tools", tools, ("GET",)),
        ("/logs", logs, ("GET",)),
        ("/stats", stats, ("GET",)),
        ("/settings", settings_home, ("GET",)),
        ("/settings/<section>", settings, GET_POST),
        ("/plugins", plugins, GET_POST),
        ("/export", export, ("GET",)),
        ("/import", import_settings, ("POST",)),
        ("/_upload_photo", upload_photo_page, ("POST",)),
    )
    for rule, view, methods in pages:
        app.add_url_rule(rule, view_func=view, methods=methods)
