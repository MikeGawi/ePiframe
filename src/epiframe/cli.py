"""The ``epiframe`` command (also ``ePiframe.py`` and ``python -m epiframe``).

Without a command it changes the photo now. The service runs ``epiframe
prepare`` for every change and shows the prepared photo itself. The other
commands test or set up parts of the frame, convert files and run the service;
``epiframe <command> --help`` describes each.
"""

import argparse
import time
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path

from epiframe.bot.console import TelegramTest
from epiframe.config import paths
from epiframe.config.base import ConfigBase
from epiframe.config.manager import ConfigManager
from epiframe.config.property import ConfigError
from epiframe.core.logs import format_duration, get_logger, setup_logging
from epiframe.display.base import DisplayError
from epiframe.plugins.manager import PluginManager
from epiframe.processing.imagemagick import ImageMagick
from epiframe.service import daemon
from epiframe.service.daemon import PARTS
from epiframe.sources.drive_setup_console import ConsoleSetup
from epiframe.update import UpdateError
from epiframe.update.commands import FileCommands
from epiframe.update.flow import Mode, PhotoUpdate
from epiframe.update.lock import update_lock
from epiframe.update.pipeline import Pipeline
from epiframe.users.console import USERS_ACTIONS_TAG, UsersConsole
from epiframe.users.store import Users
from epiframe.version import VERSION
from epiframe.weather.console import WeatherTest
from epiframe.web.app import serve_test
from epiframe.web.console import WebTest

DESCRIPTION = "ePiframe - e-Paper Raspberry Pi Photo Frame"
INTERRUPTED = 130  # exit code after Ctrl+C (128 + SIGINT)

log = get_logger()

Handler = Callable[[argparse.Namespace], int]
Tool = Callable[[ConfigManager], int]
Action = Callable[[argparse.Namespace, ConfigManager, PluginManager], None]


# ------------------------------------------------------------ configuration


def load_config() -> ConfigManager:
    """Load the configuration (the log file is known then)."""
    try:
        config = ConfigManager(paths.CONFIG_FILE, paths.CONFIG_FILE_DEFAULT)
    except Exception as error:
        raise ConfigError(
            f"Error loading {paths.CONFIG_FILE} configuration file! {error}"
        ) from error
    setup_logging(config.get("log_files"))
    return config


def verify_config(config: ConfigManager) -> PluginManager:
    """Verify the configuration and the plugins' ones; return the plugins."""
    log.info("Verifying configuration...")
    obsolete = config.get_obsolete()
    if obsolete:
        log.warning(
            f"Warning! Obsolete configuration entries removed: {', '.join(obsolete)}"
        )
    try:
        warnings = config.check()
    except ConfigError as error:
        raise ConfigError(f"Error verifying configuration file! {error}") from error
    for warning in warnings:
        log.warning(f"Warning verifying configuration file! {warning}")
    plugins = PluginManager(paths.PLUGINS_DIR, config)
    for plugin in plugins.enabled():
        _verify_plugin(plugin.name, plugin.config)
    log.info("OK!")
    return plugins


def _verify_plugin(name: str, config: ConfigBase) -> None:
    what = f"configuration file for '{name}' plugin!"
    try:
        warnings = config.check()
    except ConfigError as error:
        raise ConfigError(f"Error verifying {what} {error}") from error
    for warning in warnings:
        log.warning(f"Warning verifying {what} {warning}")


# ----------------------------------------------------------------- commands


def run_tool(tool: Tool, arguments: argparse.Namespace) -> int:
    """A setup or test tool: the configuration is not verified (it may be
    incomplete until the tool fills it in)."""
    return tool(load_config())


def manage_users(config: ConfigManager) -> int:
    log.info(USERS_ACTIONS_TAG + "Starting users management module...")
    users = Users(paths.USERS_DB_FILE)
    log.info(USERS_ACTIONS_TAG + "Success!")
    return UsersConsole(users).run()


def web_test(config: ConfigManager) -> int:
    login_needed = Users(paths.USERS_DB_FILE).login_needed()
    return WebTest(config, serve_test).run(login_needed)


TOOLS: dict[str, tuple[Tool, str]] = {
    "users": (manage_users, "manage the WebUI users"),
    "setup-drive": (
        lambda config: ConsoleSetup(config).run(),
        "set up the Google Drive source (service account)",
    ),
    "test-telegram": (
        lambda config: TelegramTest(config).run(),
        "test the Telegram bot token and show the chat ids",
    ),
    "test-weather": (
        lambda config: WeatherTest(config).run(),
        "test the OpenWeather API key and coordinates",
    ),
    "test-web": (web_test, "check the WebUI address and port, then serve the WebUI"),
}


def check_config(arguments: argparse.Namespace) -> int:
    verify_config(load_config())
    return 0


def run_service(arguments: argparse.Namespace) -> int:
    return daemon.run(arguments.part)


def pipeline(config: ConfigManager, plugins: PluginManager) -> Pipeline:
    return Pipeline(config, plugins, ImageMagick(config.get("convert_bin_path")))


def update(
    arguments: argparse.Namespace, config: ConfigManager, plugins: PluginManager
) -> None:
    mode = Mode.SHOW
    if arguments.command == "test":
        mode = Mode.NO_SKIP if arguments.no_skip else Mode.PREPARE
    PhotoUpdate(config, plugins, pipeline(config, plugins), mode).run()


def prepare(
    arguments: argparse.Namespace, config: ConfigManager, plugins: PluginManager
) -> None:
    """The photo change of the service, without showing the photo."""
    if arguments.again:
        FileCommands(pipeline(config, plugins)).test_convert()
        return
    PhotoUpdate(config, plugins, pipeline(config, plugins), Mode.PREPARE).run()


def frame_command(action: Action, locked: bool, arguments: argparse.Namespace) -> int:
    """A command working on the frame: the configuration must be valid."""
    start = time.monotonic()
    config = load_config()
    plugins = verify_config(config)
    if locked:
        with update_lock(config.get("pid_file")):
            action(arguments, config, plugins)
    else:
        action(arguments, config, plugins)
    log.info(f"Done in {format_duration(time.monotonic() - start)}")
    return 0


def file_command(
    arguments: argparse.Namespace, config: ConfigManager, plugins: PluginManager
) -> None:
    commands = FileCommands(pipeline(config, plugins))
    match arguments.command:
        case "test-convert":
            commands.test_convert(arguments.file)
        case "test-display":
            commands.test_display(arguments.file)
        case "redisplay":
            commands.redisplay()
        case _:
            target = commands.convert(arguments.source, arguments.target)
            log.info(f"Converted to {target}")


# ------------------------------------------------------------------- parser


def _frame_parsers(
    commands: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    test = commands.add_parser(
        "test", help="run the whole chain: get and convert a photo, don't show it"
    )
    test.add_argument(
        "--no-skip",
        action="store_true",
        help="keep the current photo (don't mark it shown, no display time multiplier)",
    )
    test.set_defaults(handler=partial(frame_command, update, True))
    service_update = commands.add_parser(
        "prepare",
        help="get and convert the next photo, don't show it (the service runs it "
        "and shows the photo)",
    )
    service_update.add_argument(
        "--again",
        action="store_true",
        help="convert the original photo again instead (e.g. a new one uploaded)",
    )
    service_update.set_defaults(handler=partial(frame_command, prepare, True))
    for name, help_text in (
        ("test-convert", "convert FILE (default: the original photo) for the display"),
        ("test-display", "show FILE (default: the converted photo) on the display"),
    ):
        parser = commands.add_parser(name, help=help_text)
        parser.add_argument("file", nargs="?", type=Path, metavar="FILE")
        parser.set_defaults(handler=partial(frame_command, file_command, True))
    commands.add_parser(
        "redisplay", help="convert and show the original photo again"
    ).set_defaults(handler=partial(frame_command, file_command, True))
    convert = commands.add_parser(
        "convert",
        help="convert SOURCE to a BMP file for the display (photos converted in "
        "advance, see the 'convert' setting)",
    )
    convert.add_argument("source", type=Path, metavar="SOURCE")
    convert.add_argument(
        "target", type=Path, metavar="TARGET", help="file or folder (SOURCE name)"
    )
    # works on any files: not an update of the frame, no PID file
    convert.set_defaults(handler=partial(frame_command, file_command, False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="epiframe",
        description=f"{DESCRIPTION}. Without a command: change the photo now.",
    )
    parser.add_argument("--version", action="version", version=f"ePiframe {VERSION}")
    parser.set_defaults(handler=partial(frame_command, update, True))
    commands = parser.add_subparsers(
        dest="command", title="commands", metavar="[COMMAND]"
    )
    commands.add_parser("check-config", help="verify the configuration").set_defaults(
        handler=check_config
    )
    _frame_parsers(commands)
    for name, (tool, help_text) in TOOLS.items():
        commands.add_parser(name, help=help_text).set_defaults(
            handler=partial(run_tool, tool)
        )
    service = commands.add_parser(
        "service",
        help="run the service: photo changes, WebUI, Telegram bot",
        description="Runs in the foreground until Ctrl+C or SIGTERM; as a system "
        "service it is controlled with systemctl (start, stop, restart, status).",
    )
    service.add_argument(
        "part",
        nargs="?",
        choices=[part for part in PARTS if part],
        help="run only the WebUI or the Telegram bot (it must be enabled in the "
        "configuration); photos then change only on request",
    )
    service.set_defaults(handler=run_service)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the command in ``arguments`` (default: the command line)."""
    namespace = build_parser().parse_args(arguments)
    setup_logging()  # the console until the configuration is loaded
    handler: Handler = namespace.handler
    try:
        return handler(namespace)
    except (ConfigError, UpdateError, DisplayError) as error:
        log.error(str(error))
    except KeyboardInterrupt:
        return INTERRUPTED
    except Exception as error:
        log.exception(f"Error! {error!r}")
    return 1
