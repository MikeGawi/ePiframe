"""Bot commands, independent of the messenger.

:class:`Commands` runs a command line (``/longer 2``) against the frame and answers
through a :class:`Chat`; the Telegram part (:mod:`epiframe.bot.telegram`) only moves
messages and files.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Protocol

from epiframe.core import system

OK_REP = "OK"
PROGRESS_REP = "Frame update already in progress"
LATER_REP = "Try again later"
SENDING_REP = "Sending photo to display"
PING_REP = "Pong"
ECHO_REP = "What to say? /echo #"
LONGER_REP = "How many times longer? /longer #"
LONGER_OFF_REP = "Interval multiplication is disabled in configuration"
UNKNOWN_REP = "Unsupported command"
UNSUPPORTED_REP = "Content type unsupported"
VALUE_REP = "Invalid number"
ERROR_REP = "Error"
NOT_ALLOWED_REP = (
    "This chat is not allowed to control the frame.\n"
    "Add its id {} to chat_id in the [Telegram bot] section of the configuration."
)

HELLO_MSG = "ePiframe (e-Paper Raspberry Pi Photo Frame) Telegram bot"
UPLOAD_MSG = "Upload photo to display it on frame"
COMMANDS_MSG = "Commands:"
NEXT_UPDATE_MSG = "Next update:"
LONGER_MSG = "Will be displayed {} time(s) longer ({} is max in configuration)"
LONGER_SUM_MSG = "Multiplication sum up if already set"

MEGABYTE = 1000 * 1000


@dataclass(frozen=True)
class Command:
    name: str
    description: str
    argument: bool = False

    @property
    def usage(self) -> str:
        return f"/{self.name} #" if self.argument else f"/{self.name}"


COMMANDS = (
    Command("start", "Show help"),
    Command("help", "Show help"),
    Command("ping", "Ping frame"),
    Command("echo", "Say # text", argument=True),
    Command("status", "Show frame status"),
    Command("reboot", "Reboot frame"),
    Command("when", "Show next update time"),
    Command("next", "Trigger frame update"),
    Command("current", "Show current photo"),
    Command("original", "Show current original photo"),
    Command("longer", "Display current photo # times longer", argument=True),
)


def help_text() -> str:
    """The answer to ``/start`` and ``/help`` (Telegram Markdown)."""
    lines = (f"{command.usage} - {command.description}" for command in COMMANDS)
    return f"*{HELLO_MSG}*\n\n{COMMANDS_MSG}\n" + "\n".join(lines) + f"\n\n{UPLOAD_MSG}"


def parse(text: str) -> tuple[str, str]:
    """Split ``/Command@BotName the argument`` into ``("command", "the argument")``.

    The ``@BotName`` suffix (commands in group chats) is dropped and the name is
    lowercased; text that is not a command gives an empty name.
    """
    word, *rest = text.split(maxsplit=1) or [""]
    argument = "".join(rest).strip()
    if not word.startswith("/"):
        return "", argument
    return word[1:].split("@")[0].lower(), argument


class Chat(Protocol):
    """Where the answers go."""

    def send_text(self, text: str, markdown: bool = False) -> None: ...

    def send_photo(self, path: Path) -> None: ...


class Multiplier(Protocol):
    """Display time multiplier of the current photo."""

    def read(self) -> int: ...

    def save(self, multiplier: int) -> None: ...


class Frame(Protocol):
    """What the bot needs from the frame (:class:`epiframe.service.frame.Frame`)."""

    @property
    def token(self) -> str: ...

    @property
    def chat_id(self) -> str: ...

    @property
    def busy(self) -> bool: ...

    @property
    def metric(self) -> bool: ...

    @property
    def interval_enabled(self) -> bool: ...

    @property
    def max_interval(self) -> int: ...

    @property
    def multiplier(self) -> Multiplier: ...

    def refresh(self) -> None: ...

    def next_photo(self) -> None: ...

    def redisplay(self) -> None: ...

    def download_file(self, extension: str) -> Path: ...

    def current_file(self) -> Path | None: ...

    def original_file(self) -> Path | None: ...

    def next_update_text(self) -> str: ...

    def reboot(self) -> None: ...


Handler = Callable[[str, Chat], None]


def _megabytes(value: int) -> int:
    return round(value / MEGABYTE)


def _usage(label: str, usage: system.Usage) -> str:
    used, total = _megabytes(usage.used), _megabytes(usage.total)
    return f"{label}: {used} / {total} MB used ({usage.percent} %)"


def _memory(memory: system.Memory | None) -> list[str]:
    return [_usage("Memory", memory.ram), _usage("Swap", memory.swap)] if memory else []


def _uptime(value: timedelta | None) -> list[str]:
    return [f"Uptime: {value}"] if value else []


def _load(load: tuple[float, float, float] | None) -> list[str]:
    return ["Load: " + " ".join(f"{value:.2f}" for value in load)] if load else []


def _temperature(celsius: float | None, metric: bool) -> list[str]:
    if celsius is None:
        return []
    if metric:
        return [f"Temperature: {celsius:.1f} \N{DEGREE SIGN}C"]
    return [f"Temperature: {system.fahrenheit(celsius):.1f} \N{DEGREE SIGN}F"]


def status_lines(metric: bool, proc: Path, thermal: Path) -> list[str]:
    """Memory, swap, uptime, load and temperature; missing values are left out."""
    return [
        *_memory(system.memory(proc)),
        *_uptime(system.uptime(proc)),
        *_load(system.load_average(proc)),
        *_temperature(system.temperature(thermal), metric),
    ]


class Commands:
    """Runs the commands of :data:`COMMANDS` against ``frame``."""

    def __init__(
        self,
        frame: Frame,
        proc: Path = system.PROC_DIR,
        thermal: Path = system.THERMAL_FILE,
    ) -> None:
        self.frame = frame
        self.proc = proc
        self.thermal = thermal
        self.handlers: dict[str, Handler] = {
            "start": self.help,
            "help": self.help,
            "ping": self.ping,
            "echo": self.echo,
            "status": self.status,
            "reboot": self.reboot,
            "when": self.when,
            "next": self.next,
            "current": self.current,
            "original": self.original,
            "longer": self.longer,
        }

    def run(self, text: str, chat: Chat) -> None:
        name, argument = parse(text)
        self.handlers.get(name, self.unknown)(argument, chat)

    def help(self, _argument: str, chat: Chat) -> None:
        chat.send_text(help_text(), markdown=True)

    def ping(self, _argument: str, chat: Chat) -> None:
        chat.send_text(PING_REP)

    def echo(self, argument: str, chat: Chat) -> None:
        chat.send_text(argument or ECHO_REP)

    def status(self, _argument: str, chat: Chat) -> None:
        lines = status_lines(self.frame.metric, self.proc, self.thermal)
        chat.send_text("\n".join(lines) or ERROR_REP)

    def reboot(self, _argument: str, chat: Chat) -> None:
        chat.send_text(OK_REP)
        self.frame.reboot()

    def when(self, _argument: str, chat: Chat) -> None:
        chat.send_text(f"{NEXT_UPDATE_MSG}\n{self.frame.next_update_text()}")

    def next(self, _argument: str, chat: Chat) -> None:
        if self.frame.busy:
            chat.send_text(PROGRESS_REP)
            return
        self.frame.next_photo()
        chat.send_text(OK_REP)

    def current(self, _argument: str, chat: Chat) -> None:
        self._send_file(self.frame.current_file(), chat)

    def original(self, _argument: str, chat: Chat) -> None:
        self._send_file(self.frame.original_file(), chat)

    @staticmethod
    def _send_file(path: Path | None, chat: Chat) -> None:
        if path:
            chat.send_photo(path)
        else:
            chat.send_text(ERROR_REP)

    def longer(self, argument: str, chat: Chat) -> None:
        if not self.frame.interval_enabled:
            chat.send_text(LONGER_OFF_REP)
        elif not argument:
            chat.send_text(LONGER_REP)
        else:
            self._multiply(argument.split(maxsplit=1)[0], chat)

    def _multiply(self, text: str, chat: Chat) -> None:
        try:
            value = int(text)
        except ValueError:
            value = 0
        if value <= 0:
            chat.send_text(VALUE_REP)
            return
        current = max(self.frame.multiplier.read(), 0)
        maximum = self.frame.max_interval
        total = min(value + current, maximum)
        self.frame.multiplier.save(total)
        summed = f"\n{LONGER_SUM_MSG}" if current else ""
        chat.send_text(f"{OK_REP}\n{LONGER_MSG.format(total, maximum)}{summed}")

    def unknown(self, _argument: str, chat: Chat) -> None:
        chat.send_text(UNKNOWN_REP)
