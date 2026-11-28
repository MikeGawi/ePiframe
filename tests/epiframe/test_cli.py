import importlib
import logging
import runpy
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest

from epiframe import cli
from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.config.property import ConfigError, ConfigWarning
from epiframe.core.logs import get_logger, setup_logging
from epiframe.plugins.base import Plugin, PluginConfig
from epiframe.plugins.manager import PluginManager
from epiframe.service import daemon
from epiframe.service.frame import Trigger
from epiframe.update import UpdateError
from epiframe.update.commands import FileCommands
from epiframe.update.flow import Mode, PhotoUpdate
from epiframe.version import VERSION
from epiframe.web.app import serve_test

# FILE entries that exist on every machine (verification of a full config)
MACHINE_INDEPENDENT = {
    "convert_bin_path": sys.executable,
    "fbi_bin_path": sys.executable,
}


@pytest.fixture(autouse=True)
def frame_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A frame in ``tmp_path`` (the working directory); the logger is reset."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paths, "CONFIG_FILE", str(tmp_path / "config.cfg"))
    monkeypatch.setattr(paths, "PLUGINS_DIR", str(tmp_path / "plugins"))
    monkeypatch.setattr(paths, "USERS_DB_FILE", str(tmp_path / "users.db"))
    write_config(tmp_path, **MACHINE_INDEPENDENT)
    yield tmp_path
    setup_logging(console=False)
    get_logger().setLevel(logging.NOTSET)


def write_config(folder: Path, **entries: str) -> None:
    config = ConfigManager(folder / "config.cfg", paths.CONFIG_FILE_DEFAULT)
    for name, value in entries.items():
        config.set(name, value)
    config.save()


def make_plugin(name: str, check: MagicMock) -> MagicMock:
    plugin: MagicMock = create_autospec(Plugin, instance=True)
    plugin.name = name
    plugin.config = create_autospec(PluginConfig, instance=True)
    plugin.config.check = check
    return plugin


@pytest.fixture
def plugins(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """The plugin manager class (it would bind the ``plugins`` package)."""
    manager: MagicMock = create_autospec(PluginManager)
    manager.return_value.enabled.return_value = []
    monkeypatch.setattr(cli, "PluginManager", manager)
    return manager


@pytest.fixture
def update(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock: MagicMock = create_autospec(PhotoUpdate)
    monkeypatch.setattr(cli, "PhotoUpdate", mock)
    return mock


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock: MagicMock = create_autospec(FileCommands)
    monkeypatch.setattr(cli, "FileCommands", mock)
    return mock


def output(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


# --------------------------------------------------------------------- parser


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])

    assert exit_info.value.code == 0
    text = output(capsys)
    assert text.startswith("usage: epiframe")
    for command in [*cli.TOOLS, "check-config", "test", "convert", "service"]:
        assert command in text


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--version"])

    assert output(capsys) == f"ePiframe {VERSION}\n"


@pytest.mark.parametrize(
    "arguments", [["--test"], ["--check-config"], ["convert", "one"], ["service", "x"]]
)
def test_wrong_arguments(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(arguments)

    assert exit_info.value.code == 2


def test_trigger_arguments_are_commands() -> None:
    parser = cli.build_parser()

    for trigger in Trigger:
        parser.parse_args(trigger.arguments)


# ---------------------------------------------------------------- check-config


@pytest.mark.usefixtures("plugins")
def test_check_config(capsys: pytest.CaptureFixture[str], frame_folder: Path) -> None:
    assert cli.main(["check-config"]) == 0

    text = output(capsys)
    assert "Verifying configuration...\n" in text
    assert text.endswith(" : OK!\n")
    assert "e-Paper Raspberry Pi Photo Frame" not in text  # no 1.x banner
    assert "OK!" in (frame_folder / "logs" / "ePiframe.log").read_text()


@pytest.mark.usefixtures("plugins")
def test_check_config_error(
    capsys: pytest.CaptureFixture[str], frame_folder: Path
) -> None:
    write_config(frame_folder, use_web="1", web_port="70000")

    assert cli.main(["check-config"]) == 1

    text = output(capsys)
    assert "Error verifying configuration file! web_port configuration entry" in text
    assert "Traceback" not in text  # 1.x printed one


@pytest.mark.usefixtures("plugins")
def test_check_config_warnings(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ConfigManager, "check", lambda self: [ConfigWarning("token suspicious")]
    )
    monkeypatch.setattr(ConfigManager, "get_obsolete", lambda self: ["a", "b"])

    assert cli.main(["check-config"]) == 0

    text = output(capsys)
    assert "Warning! Obsolete configuration entries removed: a, b" in text
    assert "Warning verifying configuration file! token suspicious" in text


def test_check_config_of_plugins(
    capsys: pytest.CaptureFixture[str], plugins: MagicMock
) -> None:
    fine = make_plugin("Fine", MagicMock(return_value=[ConfigWarning("hmm")]))
    broken = make_plugin("Broken", MagicMock(side_effect=ConfigError("no folder")))
    plugins.return_value.enabled.return_value = [fine, broken]

    assert cli.main(["check-config"]) == 1

    text = output(capsys)
    plugins.assert_called_once()
    assert plugins.call_args.args[0] == paths.PLUGINS_DIR
    assert "Warning verifying configuration file for 'Fine' plugin! hmm" in text
    assert "Error verifying configuration file for 'Broken' plugin! no folder" in text


def test_broken_config_file(
    capsys: pytest.CaptureFixture[str], frame_folder: Path
) -> None:
    (frame_folder / "config.cfg").write_text("not an ini file")

    assert cli.main(["check-config"]) == 1

    assert "Error loading" in output(capsys)


# --------------------------------------------------------------------- tools


@pytest.mark.parametrize(
    ("command", "tool"),
    [
        ("setup-drive", "ConsoleSetup"),
        ("test-telegram", "TelegramTest"),
        ("test-weather", "WeatherTest"),
    ],
)
def test_tools(
    monkeypatch: pytest.MonkeyPatch, frame_folder: Path, command: str, tool: str
) -> None:
    # an unverified config (e.g. Drive enabled, not set up yet) doesn't block them
    write_config(frame_folder, use_drive="1", drive_folders="")
    console = MagicMock()
    console.return_value.run.return_value = 3
    monkeypatch.setattr(cli, tool, console)

    assert cli.main([command]) == 3

    (config,) = console.call_args.args
    assert config.get("use_drive") == "1"


def test_users(monkeypatch: pytest.MonkeyPatch, frame_folder: Path) -> None:
    console = MagicMock()
    console.return_value.run.return_value = 0
    monkeypatch.setattr(cli, "UsersConsole", console)

    assert cli.main(["users"]) == 0

    console.assert_called_once()
    assert (frame_folder / "users.db").exists()  # opened by the users store


def test_test_web(monkeypatch: pytest.MonkeyPatch) -> None:
    web_test = MagicMock()
    web_test.return_value.run.return_value = 0
    monkeypatch.setattr(cli, "WebTest", web_test)

    assert cli.main(["test-web"]) == 0

    assert web_test.call_args.args[1] is serve_test
    web_test.return_value.run.assert_called_once_with(False)  # no users


@pytest.mark.parametrize(("arguments", "part"), [([], None), (["web"], "web")])
def test_service(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str], part: str | None
) -> None:
    run = MagicMock(return_value=0)
    monkeypatch.setattr(daemon, "run", run)

    assert cli.main(["service", *arguments]) == 0

    run.assert_called_once_with(part)


# ------------------------------------------------------------ frame commands


@pytest.mark.parametrize(
    ("arguments", "mode"),
    [
        ([], Mode.SHOW),
        (["test"], Mode.PREPARE),
        (["test", "--no-skip"], Mode.NO_SKIP),
        # the service's update: the service shows the photo
        (Trigger.NEXT_PHOTO.arguments, Mode.PREPARE),
    ],
)
@pytest.mark.usefixtures("plugins")
def test_update(
    update: MagicMock,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str] | tuple[str, ...],
    mode: Mode,
) -> None:
    def run() -> None:
        assert Path("pid").exists()  # held while the update runs

    update.return_value.run.side_effect = run

    assert cli.main(arguments) == 0

    config, _, pipeline, used_mode = update.call_args.args
    assert used_mode is mode
    assert pipeline.magick.binary == config.get("convert_bin_path")
    assert not Path("pid").exists()
    assert " : Done in 00:00:0" in output(capsys)


@pytest.mark.usefixtures("plugins")
def test_update_error(update: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
    update.return_value.run.side_effect = UpdateError("No photos in sources!")

    assert cli.main([]) == 1

    text = output(capsys)
    assert " : No photos in sources!\n" in text
    assert "Traceback" not in text
    assert not Path("pid").exists()


@pytest.mark.usefixtures("plugins")
def test_unexpected_error_is_logged_with_traceback(
    update: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    update.return_value.run.side_effect = ValueError("plugin bug")

    assert cli.main(["test"]) == 1

    text = output(capsys)
    assert "Error! ValueError('plugin bug')" in text
    assert "Traceback (most recent call last):" in text


@pytest.mark.usefixtures("plugins")
def test_ctrl_c(update: MagicMock) -> None:
    update.return_value.run.side_effect = KeyboardInterrupt

    assert cli.main([]) == cli.INTERRUPTED


@pytest.mark.usefixtures("plugins")
def test_update_needs_a_valid_config(update: MagicMock, frame_folder: Path) -> None:
    write_config(frame_folder, use_web="1", web_port="70000")

    assert cli.main([]) == 1

    update.assert_not_called()


@pytest.mark.parametrize(
    ("arguments", "method", "expected"),
    [
        (["test-convert"], "test_convert", (None,)),
        (["test-convert", "a.jpg"], "test_convert", (Path("a.jpg"),)),
        (["test-display"], "test_display", (None,)),
        (["test-display", "b.bmp"], "test_display", (Path("b.bmp"),)),
        (["redisplay"], "redisplay", ()),
        # the service's redisplay: convert only, the service shows the photo
        (Trigger.REDISPLAY.arguments, "test_convert", ()),
    ],
)
@pytest.mark.usefixtures("plugins")
def test_file_commands(
    commands: MagicMock,
    arguments: list[str] | tuple[str, ...],
    method: str,
    expected: tuple[object],
) -> None:
    def run(*args: object) -> None:
        assert Path("pid").exists()

    getattr(commands.return_value, method).side_effect = run

    assert cli.main(arguments) == 0

    getattr(commands.return_value, method).assert_called_once_with(*expected)
    assert not Path("pid").exists()


@pytest.mark.usefixtures("plugins")
def test_convert(commands: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
    def convert(source: Path, target: Path) -> Path:
        assert not Path("pid").exists()  # not an update of the frame
        return Path("out/a.bmp")

    commands.return_value.convert.side_effect = convert

    assert cli.main(["convert", "a.jpg", "out"]) == 0

    commands.return_value.convert.assert_called_once_with(Path("a.jpg"), Path("out"))
    assert "Converted to out/a.bmp" in output(capsys)


@pytest.mark.usefixtures("plugins")
def test_file_arguments_relative_to_the_caller(
    commands: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the epiframe command runs in the frame folder and passes where it started
    monkeypatch.setenv(paths.CALLER_DIR_ENV, "/home/pi")

    assert cli.main(["convert", "a.jpg", "/srv/out"]) == 0
    assert cli.main(["test-display", "b.bmp"]) == 0

    commands.return_value.convert.assert_called_once_with(
        Path("/home/pi/a.jpg"), Path("/srv/out")
    )
    commands.return_value.test_display.assert_called_once_with(Path("/home/pi/b.bmp"))


def test_main_module_import_runs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    main = MagicMock()
    monkeypatch.setattr(cli, "main", main)
    monkeypatch.delitem(sys.modules, "epiframe.__main__", raising=False)

    importlib.import_module("epiframe.__main__")

    main.assert_not_called()


def test_python_m_epiframe(monkeypatch: pytest.MonkeyPatch) -> None:
    main = MagicMock(return_value=5)
    monkeypatch.setattr(cli, "main", main)
    monkeypatch.delitem(sys.modules, "epiframe.__main__", raising=False)

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("epiframe", run_name="__main__")

    assert exit_info.value.code == 5
    main.assert_called_once_with()
