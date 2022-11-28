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
)
from flask_login import LoginManager, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, IntegerField, SelectField, FloatField
from wtforms.widgets import NumberInput, PasswordInput
from misc.user import User
from typing import TYPE_CHECKING

import modules.usersmanager as users_manager
import modules.databasemanager as database_manager
import modules.configmanager as config_manager
from misc.configproperty import ConfigProperty
from misc.constants import Constants
from werkzeug.utils import secure_filename
from tempfile import mkstemp
import re
import os
import glob
import logging
import base64

if TYPE_CHECKING:
    import modules.backendmanager as backend_manager


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
        def __init__(self, url: str, func, methods: List[str] = ["GET"], defaults=None):
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

    def __init__(self, backend: backend_manager.BackendManager):
        self.__backend = backend
        self.__db_manager = database_manager.DatabaseManager()
        self.__users_manager = users_manager.UsersManager(self.__db_manager)

        self.app = Flask(__name__, root_path=backend.get_path())
        self.app.config["SECRET_KEY"] = Constants.EPIFRAME_SECRET

        self.MENU = [
            self.MenuEntry("Home", "/", "home-menu", "bi bi-house"),
            self.MenuEntry("Logs", "/logs", "logs-menu", "bi bi-activity"),
            self.MenuEntry("Stats", "/stats", "stats-menu", "bi bi-graph-up"),
            self.MenuEntry("Settings", "/settings", "settings-menu", "bi bi-gear"),
            self.MenuEntry("Tools", "/tools", "tools-menu", "bi bi-tools"),
            self.MenuEntry("Plugins", "/plugins", "plugins-menu", "bi bi-plug"),
        ]

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

        for plugin in self.__backend.get_plugins().plugin_website():
            for website in plugin.add_website(
                self, self.__users_manager, self.__backend
            ):
                self.app.register_blueprint(website, url_prefix="/")

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

        for plugin in self.__backend.get_plugins().plugin_api():
            self.API += plugin.extend_api(self, self.__users_manager, self.__backend)

        for api_site in self.API:
            self.app.add_url_rule(
                api_site.url,
                methods=api_site.methods,
                view_func=api_site.func,
                defaults=api_site.defaults,
            )

        self.ACTIONS = {
            self.__NEXT_ACT: self.ActionEntry(
                "Next Photo",
                self.__backend.next_photo,
                "bi bi-skip-end",
                self.__NEXT_ACT,
            ),
            self.__RESTART_ACT: self.ActionEntry(
                "Restart Service",
                self.__backend.restart,
                "bi bi-arrow-repeat",
                self.__RESTART_ACT,
            ),
            self.__REBOOT_ACT: self.ActionEntry(
                "Reboot",
                self.__backend.reboot,
                "bi bi-arrow-counterclockwise",
                self.__REBOOT_ACT,
            ),
        }

        def merge_dicts(dictionary1: dict, dictionary2: dict) -> dict:
            result_dictionary = dictionary1.copy()
            result_dictionary.update(dictionary2)
            return result_dictionary

        for plugin in self.__backend.get_plugins().plugin_action():
            self.ACTIONS = merge_dicts(
                self.ACTIONS,
                plugin.add_action(self, self.__users_manager, self.__backend),
            )

        self.app.context_processor(self.inject_context)

        self.__login_manager = LoginManager()
        self.__login_manager.init_app(self.app)
        self.__login_manager.login_view = "login"
        self.__login_manager.user_loader(self.load_user)
        self.__login_manager.request_loader(self.load_user_from_request)

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

    def config(self) -> config_manager.ConfigManager:
        return self.__backend.get_config()

    @staticmethod
    def __adapt_name(config: config_manager.ConfigManager, name: str) -> str:
        return (
            "- " if config.get_property(name).get_dependency() else str()
        ) + name.replace("_", " ").title()

    # @app.route('/login')
    def login(self):
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            remember = True if request.form.get("remember") else False

            if username:
                try:
                    self.__users_manager.check(username, password)
                    login_user(self.load_user(username), remember=remember)
                except Exception:
                    pass
                    flash("Please check your login details and try again!")
            else:
                flash("Please fill in all required data!")
            return redirect("/")
        else:
            return render_template("login.html")

    # @app.route('/logout')
    @login_required
    def logout(self):
        logout_user()
        return redirect("/")

    def load_user(self, username: str) -> Optional[User]:
        return_value = None

        try:
            result = self.__users_manager.get_by_username(username)
            return_value = result[0] if result and len(result) > 0 else None
        except Exception:
            pass

        return return_value

    def load_user_from_request(self, request) -> Optional[User]:
        result = None
        api_key = request.args.get("api_key")

        if not api_key:
            api_key = request.headers.get("Authorization")
            if api_key:
                api_key = api_key.replace("Basic ", "", 1)

                try:
                    key = base64.b64decode(api_key)
                    if "\\" not in key.decode():
                        api_key = key.decode()
                except Exception:
                    pass

        if api_key:
            try:
                result_value = self.__users_manager.get_by_api(api_key)
                result = (
                    result_value[0] if result_value and len(result_value) > 0 else None
                )
            except Exception:
                pass

        return result

    # @app.route('/get_image')
    @login_required
    def get_image(self):
        thumb = self.__THUMB_IND if self.__THUMB_TAG in request.args else str()
        filename = str()

        if self.__ORIGINAL_TAG in request.args:
            if not thumb:
                files = glob.glob(f"{self.__backend.get_download_file()}.*")
                if files:
                    filename = max(files, key=os.path.getctime)
            else:
                filename = self.__backend.get_filename_if_exists(
                    "thumb_photo_download_name"
                )
        else:
            filename = self.__backend.get_filename_if_exists(
                thumb + "photo_convert_filename"
            )

        return (
            send_file(
                filename,
                mimetype=Constants.EXTENSION_TO_TYPE[
                    str(filename).rsplit(".")[-1].lower()
                ],
            )
            if filename
            else self.__NO_PHOTO_ERROR
        )

    # @app.route('/_get_status')
    @login_required
    def get_status(self):
        return jsonify(
            mem=self.__backend.get_mem() + "%",
            load=self.__backend.get_load(),
            uptime=self.__backend.get_uptime(),
            state=self.__backend.get_state(),
            temp=self.__backend.get_temp(),
            update=self.__backend.get_next_time(),
            service=self.__backend.get_service_state(),
            original=self.__backend.get_filename_modification_time_if_exists(
                "thumb_photo_download_name"
            ),
            converted=self.__backend.get_filename_modification_time_if_exists(
                "thumb_photo_convert_filename"
            ),
            version=Constants.EPIFRAME_VERSION,
        )

    # @app.route('/_upload_photo', methods=['POST'])
    @login_required
    def upload_photo(self):
        is_api = (
            "REQUEST_URI" in request.environ
            and request.environ["REQUEST_URI"]
            and "/api/" in request.environ["REQUEST_URI"]
        )
        result = jsonify(status="OK")

        if request.method == "POST":
            file = request.files[self.__FILE_TAG]
            extension = file.filename.rsplit(".")[-1].lower()
            if file and extension in Constants.EXTENSIONS:
                secure_filename(file.filename)
                file.save(self.__backend.get_download_file() + "." + extension)
            else:
                result = jsonify(error="File unknown!")
            self.__backend.refresh_frame()
        else:
            result = jsonify(error="Method Not Allowed!")

        return result if is_api else redirect("/")

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
        return send_file(Constants.CONFIG_FILE, as_attachment=True)

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
                    temp_conf = config_manager.ConfigManager(
                        temp, Constants.CONFIG_FILE_DEFAULT
                    )
                    temp_conf.verify()
                    temp_conf.save(Constants.CONFIG_FILE)
                    self.__backend.refresh()
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
        template = render_template(
            self.__INDEX_HTML, version=Constants.EPIFRAME_VERSION
        )
        if url == self.__TOOLS_HTML.replace(self.__HTML_IND, str()):
            template = render_template(
                self.__TOOLS_HTML,
                version=Constants.EPIFRAME_VERSION,
                actions=list(self.ACTIONS.values()),
            )
        elif url == self.__LOGS_HTML.replace(self.__HTML_IND, str()):
            template = render_template(self.__LOGS_HTML)
        elif url == self.__STATS_HTML.replace(self.__HTML_IND, str()):
            template = render_template(
                self.__STATS_HTML, version=Constants.EPIFRAME_VERSION
            )
        elif url == self.__SETTINGS_HTML.replace(self.__HTML_IND, str()):
            self.__backend.refresh()
            template = redirect(
                "/{}/{}".format(
                    self.__SETTINGS_HTML.replace(self.__HTML_IND, str()),
                    str(self.config().get_sections()[0]),
                )
            )
        elif url == self.__PLUGINS_HTML.replace(self.__HTML_IND, str()):
            self.__backend.refresh()
            template = redirect(
                f"/{self.__PLUGINS_HTML.replace(self.__HTML_IND, str())}"
            )
        return template

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
                    self.__backend.power_off()
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
                    self.__backend.display_power(False)
                elif action.lower() in ["1", "true", "on"]:
                    self.__backend.display_power(True)
                else:
                    result = jsonify(error="Action Unknown!")
            else:
                result = jsonify(state=self.__backend.get_display_power())
        else:
            result = jsonify(error="Method Not Allowed!")
        return result

    def __build_settings(self, config: config_manager.ConfigManager, properties):
        class MyForm(FlaskForm):
            pass

        for property in properties:
            prop = config.get_property(property)
            render = dict()
            render[self.__HTML_CLASS] = (
                str(prop.get_dependency()) if prop.get_dependency() else ""
            ) + self.__HTML_FORM
            render[self.__HTML_FILL] = self.__HTML_FLEX_FILL
            if prop.get_dependency():
                render[self.__HTML_PAD] = self.__HTML_PX3
                render[self.__HTML_CLASS_DEP] = prop.get_dependency()
                render[self.__HTML_CLASS_DEP_VAL] = (
                    prop.get_dependency_value() if prop.get_dependency_value() else "1"
                )
                if (
                    not prop.get_dependency_value()
                    and not bool(config.getint(prop.get_dependency()))
                ) or (
                    prop.get_dependency_value()
                    and not config.get(prop.get_dependency())
                    == prop.get_dependency_value()
                ):
                    render[self.__HTML_DISABLED] = self.__HTML_DISABLED

            if (
                prop.get_type() == ConfigProperty.STRING_TYPE
                or prop.get_type() == ConfigProperty.INTEGER_TYPE
                or prop.get_type() == ConfigProperty.FLOAT_TYPE
            ):
                if prop.get_possible():
                    render[self.__HTML_CLASS] = (
                        str(prop.get_dependency()) if prop.get_dependency() else ""
                    ) + self.__HTML_SELECT
                    render[self.__HTML_FILL] = str()
                    setattr(
                        MyForm,
                        property,
                        SelectField(
                            self.__adapt_name(config, property),
                            default=config.get_default(property),
                            choices=prop.get_possible(),
                            render_kw=render,
                            description=config.get_comment(property),
                        ),
                    )
                elif prop.get_type() == ConfigProperty.STRING_TYPE:
                    setattr(
                        MyForm,
                        property,
                        StringField(
                            self.__adapt_name(config, property),
                            default=config.get_default(property),
                            description=config.get_comment(property),
                            render_kw=render,
                        ),
                    )
                elif prop.get_type() == ConfigProperty.INTEGER_TYPE:
                    render[self.__HTML_FILL] = str()
                    setattr(
                        MyForm,
                        property,
                        IntegerField(
                            self.__adapt_name(config, property),
                            widget=NumberInput(min=prop.get_min(), max=prop.get_max()),
                            default=config.get_default(property),
                            render_kw=render,
                            description=config.get_comment(property),
                        ),
                    )
                else:
                    render[self.__HTML_FILL] = str()
                    setattr(
                        MyForm,
                        property,
                        FloatField(
                            self.__adapt_name(config, property),
                            widget=NumberInput(
                                min=prop.get_min(), max=prop.get_max(), step="any"
                            ),
                            default=config.get_default(property),
                            render_kw=render,
                            description=config.get_comment(property),
                        ),
                    )
            elif prop.get_type() == ConfigProperty.FILE_TYPE:
                setattr(
                    MyForm,
                    property,
                    StringField(
                        self.__adapt_name(config, property),
                        default=config.get_default(property),
                        render_kw=render,
                        description=config.get_comment(property),
                    ),
                )
            elif prop.get_type() == ConfigProperty.BOOLEAN_TYPE:
                render[self.__HTML_CLASS] = (
                    str(prop.get_dependency()) if prop.get_dependency() else ""
                ) + self.__HTML_CHECKBOX
                setattr(
                    MyForm,
                    property,
                    BooleanField(
                        self.__adapt_name(config, property),
                        default=config.get_default(property),
                        false_values=self.__FALSE_VALS,
                        description=config.get_comment(property),
                        render_kw=render,
                    ),
                )
            elif prop.get_type() == ConfigProperty.STRING_LIST_TYPE:
                setattr(
                    MyForm,
                    property,
                    StringField(
                        self.__adapt_name(config, property),
                        default=config.get_default(property),
                        render_kw=render,
                        description=config.get_comment(property),
                    ),
                )
            elif prop.get_type() == ConfigProperty.INT_LIST_TYPE:
                setattr(
                    MyForm,
                    property,
                    StringField(
                        self.__adapt_name(config, property),
                        default=config.get_default(property),
                        render_kw=render,
                        description=config.get_comment(property),
                    ),
                )
            elif prop.get_type() == ConfigProperty.PASSWORD_TYPE:
                setattr(
                    MyForm,
                    property,
                    StringField(
                        self.__adapt_name(config, property),
                        widget=PasswordInput(hide_value=False),
                        default=config.get_default(property),
                        description=config.get_comment(property),
                        render_kw=render,
                    ),
                )

        form = MyForm(
            data=[
                (name, config.get(name))
                for name in properties
                if config.get_property(name).get_type() != ConfigProperty.BOOLEAN_TYPE
            ]
        )
        for iterator in [
            prop
            for prop in properties
            if config.get_property(prop).get_type() == ConfigProperty.BOOLEAN_TYPE
        ]:
            getattr(form, iterator).data = config.getint(iterator)

        for iterator in properties:
            try:
                config.validate(iterator)
                getattr(form, iterator).errors = ()
            except Warning:
                getattr(form, iterator).errors = ()
                pass
            except Exception as exception:
                getattr(form, iterator).errors = exception
                getattr(form, iterator).render_kw[
                    self.__HTML_CLASS
                ] += self.__HTML_IS_INVALID
                getattr(form, iterator).render_kw[
                    self.__HTML_INVALID
                ] = self.__HTML_IS_INVALID
        return form

    # @app.route('/settings/<variable>', methods=['GET', 'POST'])
    @login_required
    def setting(self, variable=str()):
        properties = self.config().get_section_properties(
            variable if variable else self.config().get_sections()[0]
        )

        if request.method == "POST":
            for property in properties:
                if (
                    self.config().get_property(property).get_type()
                    != ConfigProperty.BOOLEAN_TYPE
                ):
                    if request.form.get(property) is not None:
                        self.config().set(property, str(request.form.get(property)))
                else:
                    self.config().set(
                        property, "1" if str(request.form.get(property)) == "y" else "0"
                    )
            regex = re.search(r"\-\<\[.*?\]\>\-", str(request.form))
            if regex:
                property_name = regex.group(0).replace("-<[", "").replace("]>-", "")
                self.config().set(
                    property_name, str(self.config().get_default(property_name))
                )
            elif request.form.get(self.__BUT_SAVE) == self.__BUT_SAVE:
                try:
                    self.config().verify_warnings()
                except Warning as exception:
                    flash(str(exception))
                    pass
                try:
                    self.config().verify_exceptions()
                    self.config().save()
                except Exception:
                    session.pop("_flashes", None)
                    pass
            elif request.form.get(self.__BUT_DEFAULTS) == self.__BUT_DEFAULTS:
                for property in properties:
                    self.config().set(
                        property, str(self.config().get_default(property))
                    )
            elif request.form.get(self.__BUT_CANCEL) == self.__BUT_CANCEL:
                self.config().read_config()
            return redirect(request.path)

        reset_needed = False
        for property in properties:
            if self.config().get_property(property).get_reset_needed():
                reset_needed = True
                break

        return render_template(
            self.__SETTINGS_HTML,
            form=self.__build_settings(self.config(), properties),
            navlabels=self.config().get_sections(),
            reset_needed=reset_needed,
            version=Constants.EPIFRAME_VERSION,
        )

    # @app.route('/plugins', self.plugins, methods=['GET', 'POST'])
    @login_required
    def plugins(self):
        if len(self.__backend.get_plugins().get_plugins()) > 0:
            if not request.args.get("plugin") == self.__ORDER_LABEL:
                curr_plugin = (
                    [
                        plugin
                        for plugin in self.__backend.get_plugins().get_plugins()
                        if plugin.name == request.args.get("plugin")
                    ][0]
                    if request.args.get("plugin")
                    else self.__backend.get_plugins().get_plugins()[0]
                )
                config = curr_plugin.config
                settings = (
                    request.args.get("variable")
                    if request.args.get("variable")
                    else config.get_sections()[0]
                )
                properties = config.get_section_properties(settings)

                if request.method == "POST":
                    for property in properties:
                        if (
                            config.get_property(property).get_type()
                            != ConfigProperty.BOOLEAN_TYPE
                        ):
                            if request.form.get(property) is not None:
                                config.set(property, str(request.form.get(property)))
                        else:
                            config.set(
                                property,
                                "1" if str(request.form.get(property)) == "y" else "0",
                            )
                    regex = re.search(r"\-\<\[.*?\]\>\-", str(request.form))
                    if regex:
                        property_name = (
                            regex.group(0).replace("-<[", "").replace("]>-", "")
                        )
                        config.set(
                            property_name, str(config.get_default(property_name))
                        )
                    elif request.form.get(self.__BUT_SAVE) == self.__BUT_SAVE:
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
                    elif request.form.get(self.__BUT_DEFAULTS) == self.__BUT_DEFAULTS:
                        for property in properties:
                            config.set(property, str(config.get_default(property)))
                    elif request.form.get(self.__BUT_CANCEL) == self.__BUT_CANCEL:
                        config.read_config()
                    return redirect(
                        "{}?plugin={}&variable={}".format(
                            request.base_url, curr_plugin.name, settings
                        )
                    )

                reset_needed = False
                for property in properties:
                    if config.get_property(property).get_reset_needed():
                        reset_needed = True
                        break

                template = render_template(
                    self.__PLUGINS_HTML,
                    info="",
                    order="",
                    plugin_name=curr_plugin.name,
                    sett_name=settings,
                    plugins=[x.name for x in self.__backend.get_plugins().get_plugins()]
                    + [self.__ORDER_LABEL],
                    form=self.__build_settings(config, properties),
                    navlabels=config.get_sections(),
                    reset_needed=reset_needed,
                    version=Constants.EPIFRAME_VERSION,
                )
            else:
                order = self.__backend.get_plugins().read_order()
                if request.method == "POST":
                    if request.form.get(self.__BUT_SAVE) == self.__BUT_SAVE:
                        self.__backend.get_plugins().save_order(
                            request.form.get("list_order").split(",")
                        )
                    elif request.form.get(self.__BUT_DEFAULTS) == self.__BUT_DEFAULTS:
                        order.sort()
                        self.__backend.get_plugins().save_order(order)
                    return redirect(
                        "{}?plugin={}".format(request.base_url, self.__ORDER_LABEL)
                    )

                template = render_template(
                    self.__PLUGINS_HTML,
                    info="",
                    order=order,
                    plugin_name=self.__ORDER_LABEL,
                    sett_name="",
                    plugins=[
                        plugin.name
                        for plugin in self.__backend.get_plugins().get_plugins()
                    ]
                    + [self.__ORDER_LABEL],
                    form=None,
                    navlabels="",
                    reset_needed=False,
                    version=Constants.EPIFRAME_VERSION,
                )

        else:
            template = render_template(
                self.__PLUGINS_HTML,
                info="<ul><li>There are no <b>ePiframe</b> plugins installed! </li><li>Go to <a "
                'href="https://github.com/MikeGawi/ePiframe_plugin" target="_blank">ePiframe_plugin</a> site to '
                "find something for You!</li></ul>",
            )
        return template
