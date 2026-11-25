from pathlib import Path

import pytest

from epiframe.bot import commands as bot
from epiframe.bot.commands import COMMANDS, Command, Commands, help_text, parse
from tests.epiframe.bot.conftest import FakeChat, FakeFrame

HELP = """\
*ePiframe (e-Paper Raspberry Pi Photo Frame) Telegram bot*

Commands:
/start - Show help
/help - Show help
/ping - Ping frame
/echo # - Say # text
/status - Show frame status
/reboot - Reboot frame
/when - Show next update time
/next - Trigger frame update
/current - Show current photo
/original - Show current original photo
/longer # - Display current photo # times longer

Upload photo to display it on frame"""


def run(commands: Commands, text: str) -> list[tuple[str, object]]:
    chat = FakeChat()
    commands.run(text, chat)
    return chat.sent


def test_command_usage() -> None:
    assert Command("ping", "Ping frame").usage == "/ping"
    assert Command("echo", "Say # text", argument=True).usage == "/echo #"


def test_commands_have_handlers(commands: Commands) -> None:
    assert [command.name for command in COMMANDS] == list(commands.handlers)


def test_help_text() -> None:
    assert help_text() == HELP


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/ping", ("ping", "")),
        ("  /Ping  ", ("ping", "")),
        ("/echo hello  world ", ("echo", "hello  world")),
        ("/echo\nhello", ("echo", "hello")),
        ("/echo@ePiframeBot a@b c", ("echo", "a@b c")),
        ("/longer@ePiframeBot 2", ("longer", "2")),
        ("hello there", ("", "there")),
        ("", ("", "")),
    ],
)
def test_parse(text: str, expected: tuple[str, str]) -> None:
    assert parse(text) == expected


@pytest.mark.parametrize("text", ["/start", "/help", "/HELP@bot"])
def test_help(commands: Commands, text: str) -> None:
    assert run(commands, text) == [("markdown", HELP)]


def test_ping(commands: Commands) -> None:
    assert run(commands, "/ping") == [("text", "Pong")]


def test_echo(commands: Commands) -> None:
    # plain text: Markdown characters are sent as they are
    assert run(commands, "/echo snake_case *bold") == [("text", "snake_case *bold")]


def test_echo_without_text(commands: Commands) -> None:
    assert run(commands, "/echo") == [("text", "What to say? /echo #")]


@pytest.mark.parametrize("text", ["/unknown", "hello", ""])
def test_unknown(commands: Commands, text: str) -> None:
    assert run(commands, text) == [("text", "Unsupported command")]


def test_reboot(commands: Commands, frame: FakeFrame) -> None:
    chat = FakeChat()
    frame.calls.append(("before",))

    commands.run("/reboot", chat)

    assert chat.sent == [("text", "OK")]
    assert frame.calls == [("before",), ("reboot",)]


def test_when(commands: Commands) -> None:
    assert run(commands, "/when") == [
        ("text", "Next update:\nat 12:00:00\nin 5 mins 0 secs")
    ]


def test_next(commands: Commands, frame: FakeFrame) -> None:
    assert run(commands, "/next") == [("text", "OK")]
    assert frame.calls == [("next_photo",)]


def test_next_busy(commands: Commands, frame: FakeFrame) -> None:
    frame.busy = True

    assert run(commands, "/next") == [("text", "Frame update already in progress")]
    assert frame.calls == []


def test_current(commands: Commands, frame: FakeFrame) -> None:
    frame.current = Path("/frame/photo.bmp")

    assert run(commands, "/current") == [("photo", Path("/frame/photo.bmp"))]


def test_original(commands: Commands, frame: FakeFrame) -> None:
    frame.original = Path("/frame/origphoto.jpg")

    assert run(commands, "/original") == [("photo", Path("/frame/origphoto.jpg"))]


@pytest.mark.parametrize("text", ["/current", "/original"])
def test_photo_missing(commands: Commands, text: str) -> None:
    assert run(commands, text) == [("text", "Error")]


def test_longer(commands: Commands, frame: FakeFrame) -> None:
    assert run(commands, "/longer 2 and more") == [
        ("text", "OK\nWill be displayed 2 time(s) longer (5 is max in configuration)")
    ]
    assert frame.calls == [("save_multiplier", 2)]


def test_longer_sums_up(commands: Commands, frame: FakeFrame) -> None:
    frame.multiplier.value = 2

    assert run(commands, "/longer 1") == [
        (
            "text",
            "OK\nWill be displayed 3 time(s) longer (5 is max in configuration)"
            "\nMultiplication sum up if already set",
        )
    ]
    assert frame.calls == [("save_multiplier", 3)]


def test_longer_is_capped(commands: Commands, frame: FakeFrame) -> None:
    frame.multiplier.value = 4

    run(commands, "/longer 7")

    assert frame.calls == [("save_multiplier", 5)]


def test_longer_negative_interval_ignored(commands: Commands, frame: FakeFrame) -> None:
    frame.multiplier.value = -1

    run(commands, "/longer 1")

    assert frame.calls == [("save_multiplier", 1)]


@pytest.mark.parametrize("value", ["0", "-1", "x", "1.5"])
def test_longer_invalid(commands: Commands, frame: FakeFrame, value: str) -> None:
    assert run(commands, f"/longer {value}") == [("text", "Invalid number")]
    assert frame.calls == []


def test_longer_without_value(commands: Commands) -> None:
    assert run(commands, "/longer") == [("text", "How many times longer? /longer #")]


def test_longer_disabled(commands: Commands, frame: FakeFrame) -> None:
    frame.interval_enabled = False

    assert run(commands, "/longer 2") == [
        ("text", "Interval multiplication is disabled in configuration")
    ]
    assert frame.calls == []


def write_system(tmp_path: Path) -> None:
    (tmp_path / "meminfo").write_text(
        "MemTotal: 3906250 kB\nMemAvailable: 2929688 kB\n"
        "SwapTotal: 102400 kB\nSwapFree: 102400 kB\n"
    )
    (tmp_path / "uptime").write_text("273906.75 1009238.48\n")
    (tmp_path / "loadavg").write_text("0.5 0.25 0.125 1/389 12345\n")
    (tmp_path / "temp").write_text("48300\n")


def test_status(commands: Commands, tmp_path: Path) -> None:
    write_system(tmp_path)

    assert run(commands, "/status") == [
        (
            "text",
            "Memory: 1000 / 4000 MB used (25 %)\n"
            "Swap: 0 / 105 MB used (0 %)\n"
            "Uptime: 3 days, 4:05:06\n"
            "Load: 0.50 0.25 0.12\n"
            "Temperature: 48.3 \N{DEGREE SIGN}C",
        )
    ]


def test_status_fahrenheit(
    commands: Commands, frame: FakeFrame, tmp_path: Path
) -> None:
    (tmp_path / "temp").write_text("50000\n")
    frame.metric = False

    assert run(commands, "/status") == [("text", "Temperature: 122.0 \N{DEGREE SIGN}F")]


def test_status_nothing_available(commands: Commands) -> None:
    assert run(commands, "/status") == [("text", "Error")]


def test_status_lines_default_paths() -> None:
    commands = Commands(FakeFrame(Path()))

    assert commands.proc == Path("/proc")
    assert commands.thermal == Path("/sys/class/thermal/thermal_zone0/temp")


def test_not_allowed_message() -> None:
    assert bot.NOT_ALLOWED_REP.format(42) == (
        "This chat is not allowed to control the frame.\n"
        "Add its id 42 to chat_id in the [Telegram bot] section of the configuration."
    )
