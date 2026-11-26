"""The WebUI and REST API server of the frame (a thread of the service)."""

import logging
import os
import socket
from collections.abc import Iterable
from typing import Any

from flask import Flask, request
from flask_login import LoginManager
from werkzeug.exceptions import HTTPException
from werkzeug.serving import BaseWSGIServer, make_server

from epiframe.config import paths
from epiframe.core.logs import get_logger
from epiframe.plugins.base import Plugin
from epiframe.service.frame import Frame, Trigger
from epiframe.users.store import Users
from epiframe.web import auth, pages
from epiframe.web.api import API_PREFIX, declaration, error_response
from epiframe.web.context import WebContext
from epiframe.web.endpoints import ROUTES
from epiframe.web.extensions import Action, MenuEntry, Route
from epiframe.web.secret import secret_key

log = get_logger("web")

MENU = (
    MenuEntry("Home", "/", "home-menu", "bi bi-house"),
    MenuEntry("Logs", "/logs", "logs-menu", "bi bi-activity"),
    MenuEntry("Stats", "/stats", "stats-menu", "bi bi-graph-up"),
    MenuEntry("Settings", "/settings", "settings-menu", "bi bi-gear"),
    MenuEntry("Tools", "/tools", "tools-menu", "bi bi-tools"),
    MenuEntry("Plugins", "/plugins", "plugins-menu", "bi bi-plug"),
)
STATS_MENU = "/stats"


def builtin_actions(frame: Frame) -> list[Action]:
    return [
        Action("next", "Next Photo", frame.next_photo, "bi bi-skip-end"),
        Action("restart", "Restart Service", frame.restart, "bi bi-arrow-repeat"),
        Action("reboot", "Reboot", frame.reboot, "bi bi-arrow-counterclockwise"),
        # the Tools page has its own button
        Action("poweroff", "Power Off", frame.power_off, "bi bi-power", button=False),
    ]


def api_http_error(error: HTTPException) -> Any:
    """``404``, ``405``… of the REST API as ``{"error": ...}`` (pages: HTML)."""
    if request.path.startswith(API_PREFIX):
        return error_response(error.name, error.code or 500)
    return error


class WebUI:
    """The Flask app of ``frame`` (pages, REST API, plugin extensions)."""

    def __init__(
        self,
        frame: Frame,
        users: Users | None = None,
        secret_file: str | os.PathLike[str] | None = None,
    ) -> None:
        self.context = WebContext(frame, users or Users(paths.USERS_DB_FILE))
        self.context.menu.extend(MENU)
        # templates/ and static/ of the ePiframe directory
        self.app = Flask(__name__, root_path=str(frame.root))
        self.app.config["SECRET_KEY"] = secret_key(secret_file or paths.SECRET_KEY_FILE)
        self.context.install(self.app)
        self._login()
        pages.register(self.app)
        for route in ROUTES:
            self.add_route(route)
        self.add_actions(builtin_actions(frame))
        self._extend()
        self.app.context_processor(self.template_context)
        self.app.register_error_handler(HTTPException, api_http_error)

    @property
    def frame(self) -> Frame:
        return self.context.frame

    @property
    def users(self) -> Users:
        return self.context.users

    def _login(self) -> None:
        manager = LoginManager()
        manager.init_app(self.app)
        manager.login_view = "login"
        manager.user_loader(auth.user_from_session)
        manager.request_loader(auth.user_from_request)
        manager.unauthorized_handler(auth.unauthorized)

    # ------------------------------------------------------------- extensions

    def add_route(self, route: Route) -> None:
        self.app.add_url_rule(
            route.rule, view_func=route.view, methods=list(route.methods)
        )

    def add_actions(self, actions: Iterable[Action]) -> None:
        self.context.actions.update({action.id: action for action in actions})

    def add_menu_entries(self, entries: Iterable[MenuEntry]) -> None:
        self.context.menu.extend(entries)

    def _extend(self) -> None:
        plugins = self.frame.plugins
        for plugin in plugins.with_hook("extend_api"):
            self._plugin_hook(plugin, self._plugin_routes)
        for plugin in plugins.with_hook("add_action"):
            self._plugin_hook(plugin, self._plugin_actions)
        for plugin in plugins.with_hook("add_website"):
            self._plugin_hook(plugin, self._plugin_websites)

    def _plugin_hook(self, plugin: Plugin, extend: Any) -> None:
        try:
            extend(plugin)
        except Exception:  # a broken plugin must not stop the WebUI
            log.exception("Plugin %s failed to extend the WebUI", plugin.name)

    def _plugin_routes(self, plugin: Plugin) -> None:
        for route in plugin.extend_api(self.frame):
            # the endpoint is the name of the view (url_for in plugin pages); a
            # name ePiframe already uses stops the plugin's hook with an error
            if route.rule.startswith(API_PREFIX) and declaration(route.view):
                self.add_route(route)
            else:
                log.error(
                    "Plugin %s: %s skipped (must be under %s and declared with @api)",
                    plugin.name,
                    route.rule,
                    API_PREFIX,
                )

    def _plugin_actions(self, plugin: Plugin) -> None:
        self.add_actions(plugin.add_action(self.frame))

    def _plugin_websites(self, plugin: Plugin) -> None:
        for website in plugin.add_website(self, self.users, self.frame):
            self.app.register_blueprint(website, url_prefix="/")

    # ---------------------------------------------------------------- serving

    def template_context(self) -> dict[str, Any]:
        config = self.frame.config
        menu = self.context.menu
        if not config.getint("show_stats"):
            menu = [entry for entry in menu if entry.url != STATS_MENU]
        return {"dark_theme": bool(config.getint("dark_theme")), "menu": menu}

    def server(
        self, host: str | None = None, port: int | None = None
    ) -> BaseWSGIServer:
        """A server of the WebUI bound to ``host``/``port`` (they replace the
        configured ones); the login is needed if there are users.

        Raises ``OSError`` if the address can't be used (werkzeug would call
        ``sys.exit``, which silently ends the service's WebUI thread).
        """
        logging.getLogger("werkzeug").setLevel(logging.CRITICAL)
        self.app.config["LOGIN_DISABLED"] = not self.users.login_needed()
        host = host or self.frame.config.get("web_host")
        port = self.frame.config.getint("web_port") if port is None else port
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.create_server((host, port), family=family) as listening:
            # werkzeug serves a duplicate of the bound socket
            return make_server(
                host, port, self.app, threaded=True, fd=listening.fileno()
            )

    def start(self, host: str | None = None, port: int | None = None) -> None:
        """Serve until Ctrl+C (see :meth:`server`)."""
        self.server(host, port).serve_forever()


def serve_test(host: str, port: int) -> None:
    """The WebUI of ``epiframe test-web``: the frame of the config, no service."""

    def on_trigger(trigger: Trigger) -> None:
        log.warning("%s requested: only the ePiframe service changes photos", trigger)

    WebUI(Frame(on_trigger, paths.CONFIG_FILE)).start(host, port)
