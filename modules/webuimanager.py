from __future__ import annotations

from typing import List, Optional
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    jsonify,
    send_file,
    flash,
    session,
    Response,
)
from flask_login import LoginManager, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    BooleanField,
    IntegerField,
    SelectChoice,
    SelectField,
    FloatField,
)
from wtforms.widgets import NumberInput, PasswordInput
from epiframe.users.model import User
from epiframe.users.store import UserError, Users
from epiframe.config.manager import ConfigManager
from epiframe.config.property import PropertyType
from epiframe.config import paths
from epiframe.core import system
from epiframe.core.media_types import EXTENSIONS, EXTENSION_TO_TYPE
from epiframe.service.frame import Frame
from epiframe.version import VERSION
from werkzeug.utils import secure_filename
from tempfile import mkstemp
import re
import os
import logging
import base64
from datetime import timedelta
from pathlib import Path

EPIFRAME_SECRET = "ePiframeSecretlyLovesYourPhotos"
NOTHING = "-"


def memory_text(memory: system.Memory | None) -> str:
    return f"{memory.ram.percent}%" if memory else NOTHING


def load_text(load: tuple[float, float, float] | None) -> str:
    return " ".join(f"{value:.2f}" for value in load) if load else NOTHING


UPTIME_UNITS = (("week", 604800), ("day", 86400), ("hour", 3600), ("minute", 60))


def _counts(seconds: int) -> list[tuple[int, str]]:
    counts = []
    for unit, size in UPTIME_UNITS:
        count, seconds = divmod(seconds, size)
        counts.append((count, unit))
    return counts


def uptime_text(uptime: timedelta | None) -> str:
    """As ``uptime --pretty`` (1.x): ``up 1 week, 1 day, 14 hours, 52 minutes``."""
    if uptime is None:
        return NOTHING
    counts = _counts(int(uptime.total_seconds()))
    parts = [f"{count} {unit}{'s' * (count > 1)}" for count, unit in counts if count]
    return "up " + ", ".join(parts or ["0 minutes"])


def power_state_text(on: bool | None) -> str:
    """``"1"`` on, ``"0"`` off or unknown (as 1.x)."""
    return "1" if on else "0"


def temperature_text(celsius: float | None, metric: bool) -> str:
    if celsius is None:
        return NOTHING
    if metric:
        return f"{celsius:.1f}\N{DEGREE SIGN}C"
    return f"{system.fahrenheit(celsius):.1f}\N{DEGREE SIGN}F"


class WebUIManager:
    __SETTINGS_HTML = "settings.html"
    __PLUGINS_HTML = "plugins.html"
    __LOGS_HTML = "logs.html"
    __STATS_HTML = "stats.html"
    __TOOLS_HTML = "tools.html"
    __INDEX_HTML = "index.html"
    __HTML_IND = ".html"

    __THUMB_TAG = "thumb"
    __FILE_TAG = "file"
    __THUMB_IND = "thumb_"
    __ORIGINAL_TAG = "original"

    __NO_PHOTO_ERROR = "No Photo!"

    __HTML_IS_INVALID = " is-invalid"
    __HTML_INVALID = "invalid"
    __HTML_CLASS = "class"
    __HTML_FILL = "fill"
    __HTML_FLEX_FILL = "flex-fill"
    __HTML_CLASS_DEP = "classdep"
    __HTML_CLASS_DEP_VAL = "depval"
    __HTML_PAD = "pad"
    __HTML_FORM = " form-control form-control-sm"
    __HTML_SELECT = " form-select form-select-sm"
    __HTML_DISABLED = "disabled"
    __HTML_PX3 = "px-3"
    __HTML_CHECKBOX = " checkbox form-check-input"

    __BUT_DEFAULTS = "DEFAULTS"
    __BUT_CANCEL = "CANCEL"
    __BUT_SAVE = "SAVE"

    __FALSE_VALS = (0, "0", "")

    __REBOOT_ACT = "reboot"
    __RESTART_ACT = "restart"
    __POWER_OFF_ACT = "poweroff"
    __NEXT_ACT = "next"

    __ORDER_LABEL = "Execution Order"

    class SiteBind:
        def __init__(self, url: str, func, methods: List[str] = None, defaults=None):
            if not methods:
                methods = ["GET"]
            self.url = url
            self.func = func
            self.methods = methods
            self.defaults = defaults

    class MenuEntry:
        def __init__(self, name: str, url: str, identifier: str, icon: str):
            self.url = url
            self.icon = icon
            self.name = name
            self.id = identifier

    class ActionEntry:
        def __init__(self, name: str, function, icon: str, action: str):
            self.function = function
            self.name = name
            self.icon = icon
            self.action = action

    def __init__(self, frame: Frame):
        self.__frame = frame
        self.__users_manager = Users(paths.USERS_DB_FILE)

        self.app = Flask(__name__, root_path=str(frame.root))
        self.app.config["SECRET_KEY"] = EPIFRAME_SECRET

        self.__add_menu()
        self.__add_websites()
        self.__add_api()
        self.__add_actions()

        self.app.context_processor(self.inject_context)

        self.__login_manager = LoginManager()
        self.__login_manager.init_app(self.app)
        self.__login_manager.login_view = "login"
        self.__login_manager.user_loader(self.load_user)
        self.__login_manager.request_loader(self.load_user_from_request)

    def __add_menu(self):
        self.MENU = [
            self.MenuEntry("Home", "/", "home-menu", "bi bi-house"),
            self.MenuEntry("Logs", "/logs", "logs-menu", "bi bi-activity"),
            self.MenuEntry("Stats", "/stats", "stats-menu", "bi bi-graph-up"),
            self.MenuEntry("Settings", "/settings", "settings-menu", "bi bi-gear"),
            self.MenuEntry("Tools", "/tools", "tools-menu", "bi bi-tools"),
            self.MenuEntry("Plugins", "/plugins", "plugins-menu", "bi bi-plug"),
        ]

    def __add_websites(self):
        self.WEBSITES = [
            self.SiteBind("/get_image", self.get_image),
            self.SiteBind("/get_status", self.get_status),
            self.SiteBind("/_log_stream", self.stream),
            self.SiteBind("/_upload_photo", self.upload_photo, methods=["POST"]),
            self.SiteBind("/_tools$", self.tools_functions),
            self.SiteBind("/_tools$<action>", self.tools_functions),
            self.SiteBind("/<url>", self.handle, methods=["GET", "POST"]),
            self.SiteBind(
                "/", self.handle, methods=["GET", "POST"], defaults={"url": ""}
            ),
            self.SiteBind(
                "/settings/<variable>",
                self.setting,
                methods=["GET", "POST"],
                defaults={"variable": ""},
            ),
            self.SiteBind("/plugins", self.plugins, methods=["GET", "POST"]),
            self.SiteBind("/logout", self.logout),
            self.SiteBind("/login", self.login, methods=["GET", "POST"]),
            self.SiteBind("/export", self.export),
            self.SiteBind("/import", self.import_settings, methods=["POST"]),
        ]
        for site in self.WEBSITES:
            self.app.add_url_rule(site.url, methods=site.methods, view_func=site.func)
        for plugin in self.__frame.plugins.with_hook("add_website"):
            for website in plugin.add_website(self, self.__users_manager, self.__frame):
                self.app.register_blueprint(website, url_prefix="/")

    def __add_api(self):
        self.API = [
            self.SiteBind("/api/get_image", self.get_image),
            self.SiteBind("/api/get_status", self.get_status),
            self.SiteBind("/api/get_log", self.stream),
            self.SiteBind("/api/upload_photo", self.upload_photo, methods=["POST"]),
            self.SiteBind("/api/action=", self.tools_functions),
            self.SiteBind("/api/action=<action>", self.tools_functions),
            self.SiteBind("/api/display_power=", self.display_control),
            self.SiteBind("/api/display_power=<action>", self.display_control),
        ]
        for plugin in self.__frame.plugins.with_hook("extend_api"):
            self.API += plugin.extend_api(self, self.__users_manager, self.__frame)
        for api_site in self.API:
            self.app.add_url_rule(
                api_site.url,
                methods=api_site.methods,
                view_func=api_site.func,
                defaults=api_site.defaults,
            )

    def __add_actions(self):
        self.ACTIONS = {
            self.__NEXT_ACT: self.ActionEntry(
                "Next Photo",
                self.__frame.next_photo,
                "bi bi-skip-end",
                self.__NEXT_ACT,
            ),
            self.__RESTART_ACT: self.ActionEntry(
                "Restart Service",
                self.__frame.restart,
                "bi bi-arrow-repeat",
                self.__RESTART_ACT,
            ),
            self.__REBOOT_ACT: self.ActionEntry(
                "Reboot",
                self.__frame.reboot,
                "bi bi-arrow-counterclockwise",
                self.__REBOOT_ACT,
            ),
        }
        for plugin in self.__frame.plugins.with_hook("add_action"):
            self.ACTIONS = self.merge_dicts(
                self.ACTIONS,
                plugin.add_action(self, self.__users_manager, self.__frame),
            )

    @staticmethod
    def merge_dicts(dictionary1: dict, dictionary2: dict) -> dict:
        result_dictionary = dictionary1.copy()
        result_dictionary.update(dictionary2)
        return result_dictionary

    def add_menu_entries(self, entries: List[MenuEntry]):
        self.MENU += entries

    def get_app(self):
        return self.app

    def inject_context(self) -> dict:
        return dict(
            dark_theme=bool(self.config().getint("dark_theme")),
            menu=self.MENU
            if bool(self.config().getint("show_stats"))
            else [
                site
                for site in self.MENU
                if site.name != "Stats" and site.url != "/stats"
            ],
        )

    def start(self):
        log = logging.getLogger("werkzeug")
        if log:
            log.setLevel(logging.CRITICAL)

        self.app.config["LOGIN_DISABLED"] = not self.__users_manager.login_needed()
        self.app.run(
            host=self.config().get("web_host"),
            port=int(self.config().get("web_port")),
            debug=False,
        )

    def config(self) -> ConfigManager:
        return self.__frame.config

    @staticmethod
    def adapt_name(config: ConfigManager, name: str) -> str:
        return ("- " if config.get_property(name).dependency else str()) + name.replace(
            "_", " "
        ).title()

    # @app.route('/login')
    def login(self):
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            remember = True if request.form.get("remember") else False

            if username:
                self.__log_in(username, password or "", remember)
            else:
                flash("Please fill in all required data!")
            return redirect("/")
        else:
            return render_template("login.html")

    def __log_in(self, username: str, password: str, remember: bool):
        try:
            user = self.__users_manager.authenticate(username, password)
            login_user(user, remember=remember)
        except UserError:
            flash("Please check your login details and try again!")

    # @app.route('/logout')
    @login_required
    def logout(self):
        logout_user()
        return redirect("/")

    def load_user(self, username: str) -> Optional[User]:
        return self.__users_manager.by_username(username)

    def load_user_from_request(self, request_data) -> Optional[User]:
        result = None
        api_key = request_data.args.get("api_key")

        if not api_key:
            api_key = request_data.headers.get("Authorization")
            if api_key:
                api_key = self.__get_api_from_header(api_key)

        if api_key:
            result = self.__users_manager.by_api_key(api_key)

        return result

    @staticmethod
    def __get_api_from_header(api_key: str) -> str:
        api_key = api_key.replace("Basic ", "", 1)
        try:
            key = base64.b64decode(api_key)
            if "\\" not in key.decode():
                api_key = key.decode()
        except Exception:
            pass
        return api_key

    # @app.route('/get_image')
    @login_required
    def get_image(self):
        thumb = self.__THUMB_IND if self.__THUMB_TAG in request.args else str()

        if self.__ORIGINAL_TAG in request.args:
            filename = self.__get_original(thumb)
        else:
            filename = self.__frame.file(thumb + "photo_convert_filename")

        return (
            send_file(
                filename,
                mimetype=EXTENSION_TO_TYPE[str(filename).rsplit(".")[-1].lower()],
            )
            if filename
            else self.__NO_PHOTO_ERROR
        )

    def __get_original(self, thumb: str) -> Path | None:
        if not thumb:
            return self.__frame.original_file()
        return self.__frame.file("thumb_photo_download_name")

    # @app.route('/_get_status')
    @login_required
    def get_status(self):
        return jsonify(
            mem=memory_text(system.memory()),
            load=load_text(system.load_average()),
            uptime=uptime_text(system.uptime()),
            state=self.__frame.state,
            temp=temperature_text(system.temperature(), self.__frame.metric),
            update=self.__frame.next_update_text(),
            service="Running" if system.service_running() else "Not running!",
            original=self.__frame.modified("thumb_photo_download_name"),
            converted=self.__frame.modified("thumb_photo_convert_filename"),
            version=VERSION,
        )

    # @app.route('/_upload_photo', methods=['POST'])
    @login_required
    def upload_photo(self):
        is_api = (
            "REQUEST_URI" in request.environ
            and request.environ["REQUEST_URI"]
            and "/api/" in request.environ["REQUEST_URI"]
        )
        if request.method == "POST":
            result = self.__get_file_request()
        else:
            result = jsonify(error="Method Not Allowed!")

        return result if is_api else redirect("/")

    def __get_file_request(self) -> Optional[Response]:
        result = jsonify(status="OK")
        file = request.files[self.__FILE_TAG]
        extension = file.filename.rsplit(".")[-1].lower()
        if file and extension in EXTENSIONS:
            secure_filename(file.filename)
            file.save(self.__frame.download_file(extension))
        else:
            result = jsonify(error="File unknown!")
        self.__frame.redisplay()
        return result

    # @app.route('/_log_stream')
    @login_required
    def stream(self):
        if not os.path.exists(self.config().get("log_files")):
            os.makedirs(os.path.dirname(self.config().get("log_files")), exist_ok=True)
            open(self.config().get("log_files"), "a").close()
        with open(self.config().get("log_files")) as file:
            content = file.read()
        return self.app.response_class(content, mimetype="text/plain")

    # @app.route('/export')
    @login_required
    def export(self):
        return send_file(paths.CONFIG_FILE, as_attachment=True)

    # @app.route('/import', methods=['POST'])
    @login_required
    def import_settings(self):
        if request.method == "POST":
            file = request.files[self.__FILE_TAG]
            if file:
                secure_filename(file.filename)
                status, temp = mkstemp(text=True)
                file.save(temp)

                try:
                    temp_conf = ConfigManager(temp, paths.CONFIG_FILE_DEFAULT)
                    temp_conf.verify()
                    temp_conf.save(paths.CONFIG_FILE)
                    self.__frame.refresh()
                    flash("File has been imported successfully!")
                except Exception as exception:
                    flash(f"Error importing settings file: {str(exception)}")
                    pass
                finally:
                    if os.path.exists(temp):
                        os.remove(temp)
        return redirect(f"/{self.__SETTINGS_HTML.replace(self.__HTML_IND, str())}")

    # @app.route('/', defaults={'url': ''})
    # @app.route('/<url>', methods=['GET', 'POST'])
    @login_required
    def handle(self, url: str = str()):
        if url == self.__PLUGINS_HTML.replace(
            self.__HTML_IND, str()
        ) or url == self.__SETTINGS_HTML.replace(self.__HTML_IND, str()):
            self.__frame.refresh()

        templates = {
            self.__TOOLS_HTML.replace(self.__HTML_IND, str()): render_template(
                self.__TOOLS_HTML,
                version=VERSION,
                actions=list(self.ACTIONS.values()),
            ),
            self.__LOGS_HTML.replace(self.__HTML_IND, str()): render_template(
                self.__LOGS_HTML
            ),
            self.__STATS_HTML.replace(self.__HTML_IND, str()): render_template(
                self.__STATS_HTML, version=VERSION
            ),
            self.__STATS_HTML.replace(self.__HTML_IND, str()): render_template(
                self.__STATS_HTML, version=VERSION
            ),
            self.__SETTINGS_HTML.replace(self.__HTML_IND, str()): redirect(
                "/{}/{}".format(
                    self.__SETTINGS_HTML.replace(self.__HTML_IND, str()),
                    str(self.config().get_sections()[0]),
                )
            ),
            self.__PLUGINS_HTML.replace(self.__HTML_IND, str()): redirect(
                f"/{self.__PLUGINS_HTML.replace(self.__HTML_IND, str())}"
            ),
        }

        return templates.get(url, render_template(self.__INDEX_HTML, version=VERSION))

    # @app.route('/_tools$', methods=['GET'])
    # @app.route('/_tools$<action>', methods=['GET'])
    @login_required
    def tools_functions(self, action: str = str()):
        result = jsonify(status="OK")
        if request.method == "GET":
            if action:
                if action in self.ACTIONS:
                    self.ACTIONS[action].function()
                elif action == self.__POWER_OFF_ACT:
                    self.__frame.power_off()
                else:
                    result = jsonify(error="Action Unknown!")
            else:
                result = jsonify(error="No Action!")
        else:
            result = jsonify(error="Method Not Allowed!")
        return result

    @login_required
    def display_control(self, action: str = str()):
        result = jsonify(status="OK")
        if request.method == "GET":
            if action:
                if action.lower() in ["0", "false", "off"]:
                    self.__frame.hdmi.set(False)
                elif action.lower() in ["1", "true", "on"]:
                    self.__frame.hdmi.set(True)
                else:
                    result = jsonify(error="Action Unknown!")
            else:
                result = jsonify(state=power_state_text(self.__frame.hdmi.state()))
        else:
            result = jsonify(error="Method Not Allowed!")
        return result

    def __build_settings(self, config: ConfigManager, properties):
        class MyForm(FlaskForm):
            pass

        for property_name in properties:
            prop = config.get_property(property_name)
            render = dict()
            render[self.__HTML_CLASS] = (
                self.__get_dependency_or_empty(prop)
            ) + self.__HTML_FORM
            render[self.__HTML_FILL] = self.__HTML_FLEX_FILL
            render = self.__render_disabled(config, prop, render)

            setattr(
                MyForm,
                property_name,
                self.__get_field(config, prop, render, property_name),
            )
        form = MyForm(data=self.__get_form(config, properties))
        self.__get_attributes(config, form, properties)
        self.__verify_form(config, form, properties)
        return form

    @staticmethod
    def __get_dependency_or_empty(prop):
        return prop.dependency or ""

    def __get_field(self, config: ConfigManager, prop, render: dict, property_name):
        type_to_field = {
            PropertyType.STRING: self.__get_list_field,
            PropertyType.INTEGER: self.__get_integer_field,
            PropertyType.FLOAT: self.__get_float_field,
            PropertyType.INT_LIST: self.__get_list_field,
            PropertyType.STRING_LIST: self.__get_list_field,
            PropertyType.FILE: self.__get_list_field,
            PropertyType.BOOLEAN: self.__get_bool_field,
            PropertyType.PASSWORD: self.__get_password_field,
        }

        if prop.type in [
            PropertyType.STRING,
            PropertyType.INTEGER,
            PropertyType.FLOAT,
        ]:
            if prop.choices:
                return self.__get_select_field(config, prop, render, property_name)

        return type_to_field.get(prop.type).__call__(
            config, prop, render, property_name
        )

    def __get_select_field(
        self, config: ConfigManager, prop, render: dict, property_name
    ):
        render[self.__HTML_CLASS] = (
            self.__get_dependency_or_empty(prop)
        ) + self.__HTML_SELECT
        render[self.__HTML_FILL] = str()

        return SelectField(
            self.adapt_name(config, property_name),
            default=config.get_default(property_name),
            # WTForms >= 3.3 silently drops int choices and deprecates tuples
            choices=[
                SelectChoice(value=value, label=str(value)) for value in prop.choices
            ],
            render_kw=render,
            description=config.get_comment(property_name),
        )

    def __get_integer_field(
        self, config: ConfigManager, prop, render: dict, property_name
    ):
        render[self.__HTML_FILL] = str()

        return IntegerField(
            self.adapt_name(config, property_name),
            widget=NumberInput(min=prop.min_value, max=prop.max_value),
            default=config.get_default(property_name),
            render_kw=render,
            description=config.get_comment(property_name),
        )

    def __get_float_field(
        self, config: ConfigManager, prop, render: dict, property_name
    ):
        render[self.__HTML_FILL] = str()

        return FloatField(
            self.adapt_name(config, property_name),
            widget=NumberInput(min=prop.min_value, max=prop.max_value, step="0.1"),
            default=config.get_default(property_name),
            render_kw=render,
            description=config.get_comment(property_name),
        )

    def __get_bool_field(
        self, config: ConfigManager, prop, render: dict, property_name
    ):
        render[self.__HTML_CLASS] = (
            self.__get_dependency_or_empty(prop)
        ) + self.__HTML_CHECKBOX

        return BooleanField(
            self.adapt_name(config, property_name),
            default=config.get_default(property_name),
            false_values=self.__FALSE_VALS,
            description=config.get_comment(property_name),
            render_kw=render,
        )

    def __get_list_field(
        self, config: ConfigManager, _prop, render: dict, property_name
    ):
        return StringField(
            self.adapt_name(config, property_name),
            default=config.get_default(property_name),
            render_kw=render,
            description=config.get_comment(property_name),
        )

    def __get_password_field(
        self, config: ConfigManager, _prop, render: dict, property_name
    ):
        return StringField(
            self.adapt_name(config, property_name),
            widget=PasswordInput(hide_value=False),
            default=config.get_default(property_name),
            description=config.get_comment(property_name),
            render_kw=render,
        )

    def __render_disabled(self, config: ConfigManager, prop, render: dict) -> dict:
        if prop.dependency:
            render[self.__HTML_PAD] = self.__HTML_PX3
            render[self.__HTML_CLASS_DEP] = prop.dependency
            render[self.__HTML_CLASS_DEP_VAL] = prop.dependency_value or "1"
            render = self.__check_dependency(config, prop, render)

        return render

    def __check_dependency(self, config: ConfigManager, prop, render: dict) -> dict:
        if not prop.is_active(config):
            render[self.__HTML_DISABLED] = self.__HTML_DISABLED

        return render

    @staticmethod
    def __get_form(config: ConfigManager, properties):
        return [
            (name, config.get(name))
            for name in properties
            if config.get_property(name).type != PropertyType.BOOLEAN
        ]

    @staticmethod
    def __get_attributes(config: ConfigManager, form, properties):
        for iterator in [
            prop
            for prop in properties
            if config.get_property(prop).type == PropertyType.BOOLEAN
        ]:
            getattr(form, iterator).data = config.getint(iterator)

    def __verify_form(self, config: ConfigManager, form, properties):
        for iterator in properties:
            try:
                config.validate(iterator)
                getattr(form, iterator).errors = ()
            except Warning:
                getattr(form, iterator).errors = ()
                pass
            except Exception as exception:
                getattr(form, iterator).errors = exception
                getattr(form, iterator).render_kw[self.__HTML_CLASS] += (
                    self.__HTML_IS_INVALID
                )
                getattr(form, iterator).render_kw[self.__HTML_INVALID] = (
                    self.__HTML_IS_INVALID
                )

    # @app.route('/settings/<variable>', methods=['GET', 'POST'])
    @login_required
    def setting(self, variable=str()):
        properties = self.__get_section(variable)

        if request.method == "POST":
            self.__set_property_values(self.config(), properties)
            regex = re.search(r"\-\<\[.*?\]\>\-", str(request.form))
            self.__process_post(self.config(), properties, regex)
            return redirect(request.path)

        return render_template(
            self.__SETTINGS_HTML,
            form=self.__build_settings(self.config(), properties),
            navlabels=self.config().get_sections(),
            reset_needed=self.__get_reset_needed(properties, self.config()),
            version=VERSION,
        )

    @staticmethod
    def get_property_from_form(config: ConfigManager, regex):
        property_name = regex.group(0).replace("-<[", "").replace("]>-", "")
        config.set(property_name, str(config.get_default(property_name)))

    @staticmethod
    def __verify_settings(config: ConfigManager):
        try:
            config.verify_warnings()
        except Warning as exception:
            flash(str(exception))
            pass
        try:
            config.verify_exceptions()
            config.save()
        except Exception:
            session.pop("_flashes", None)
            pass

    @staticmethod
    def __set_properties(properties: list, config: ConfigManager):
        for property_name in properties:
            config.set(property_name, str(config.get_default(property_name)))

    @staticmethod
    def __get_reset_needed(properties: list, config: ConfigManager) -> bool:
        reset_needed = False
        for property_name in properties:
            if config.get_property(property_name).reset_needed:
                reset_needed = True
                break
        return reset_needed

    def __get_section(self, variable: str) -> list:
        return self.config().get_section_properties(
            variable if variable else self.config().get_sections()[0]
        )

    # @app.route('/plugins', self.plugins, methods=['GET', 'POST'])
    @login_required
    def plugins(self):
        if self.__frame.plugins.plugins:
            if not request.args.get("plugin") == self.__ORDER_LABEL:
                curr_plugin = self.__get_current_plugin()
                config = curr_plugin.config
                settings = self.get_settings(config)
                properties = config.get_section_properties(settings)

                if request.method == "POST":
                    self.__set_property_values(config, properties)
                    regex = re.search(r"\-\<\[.*?\]\>\-", str(request.form))
                    self.__process_post(config, properties, regex)

                    return redirect(
                        "{}?plugin={}&variable={}".format(
                            request.base_url, curr_plugin.name, settings
                        )
                    )

                return self.__plugin_settings_template(
                    config,
                    curr_plugin,
                    properties,
                    self.__get_reset_needed(properties, config),
                    settings,
                )
            else:
                order = self.__frame.plugins.read_order()
                if request.method == "POST":
                    return self.__process_order(order)
                return self.__order_template(order)
        return self.__no_plugins_template()

    def __process_post(self, config: ConfigManager, properties: list, regex):
        if regex:
            self.get_property_from_form(config, regex)
        elif request.form.get(self.__BUT_SAVE) == self.__BUT_SAVE:
            self.__verify_settings(config)
        elif request.form.get(self.__BUT_DEFAULTS) == self.__BUT_DEFAULTS:
            self.__set_properties(properties, config)
        elif request.form.get(self.__BUT_CANCEL) == self.__BUT_CANCEL:
            config.reload()

    def __set_property_values(self, config: ConfigManager, properties: list):
        for property_name in properties:
            if config.get_property(property_name).type != PropertyType.BOOLEAN:
                if request.form.get(property_name) is not None:
                    config.set(property_name, str(request.form.get(property_name)))
            else:
                self.set_boolean_value(config, property_name)

    @staticmethod
    def set_boolean_value(config: ConfigManager, property_name: str):
        config.set(
            property_name,
            "1" if str(request.form.get(property_name)) == "y" else "0",
        )

    @staticmethod
    def get_settings(config: ConfigManager):
        return (
            request.args.get("variable")
            if request.args.get("variable")
            else config.get_sections()[0]
        )

    def __get_current_plugin(self):
        return (
            [
                plugin
                for plugin in self.__frame.plugins.plugins
                if plugin.name == request.args.get("plugin")
            ][0]
            if request.args.get("plugin")
            else self.__frame.plugins.plugins[0]
        )

    def __process_order(self, order: list) -> Response:
        if request.form.get(self.__BUT_SAVE) == self.__BUT_SAVE:
            self.__frame.plugins.save_order(request.form.get("list_order").split(","))
        elif request.form.get(self.__BUT_DEFAULTS) == self.__BUT_DEFAULTS:
            order.sort()
            self.__frame.plugins.save_order(order)
        return redirect("{}?plugin={}".format(request.base_url, self.__ORDER_LABEL))

    def __plugin_settings_template(
        self,
        config: ConfigManager,
        curr_plugin,
        properties: list,
        reset_needed: bool,
        settings: str,
    ) -> str:
        return render_template(
            self.__PLUGINS_HTML,
            info="",
            order="",
            plugin_name=curr_plugin.name,
            sett_name=settings,
            plugins=[x.name for x in self.__frame.plugins.plugins]
            + [self.__ORDER_LABEL],
            form=self.__build_settings(config, properties),
            navlabels=config.get_sections(),
            reset_needed=reset_needed,
            version=VERSION,
        )

    def __order_template(self, order: list) -> str:
        return render_template(
            self.__PLUGINS_HTML,
            info="",
            order=order,
            plugin_name=self.__ORDER_LABEL,
            sett_name="",
            plugins=[plugin.name for plugin in self.__frame.plugins.plugins]
            + [self.__ORDER_LABEL],
            form=None,
            navlabels="",
            reset_needed=False,
            version=VERSION,
        )

    def __no_plugins_template(self) -> str:
        return render_template(
            self.__PLUGINS_HTML,
            info="<ul><li>There are no <b>ePiframe</b> plugins installed! </li><li>Go to <a "
            'href="https://github.com/MikeGawi/ePiframe_plugin" target="_blank">ePiframe_plugin</a> site to '
            "find something for You!</li></ul>",
        )
