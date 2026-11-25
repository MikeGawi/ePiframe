from pathlib import Path
from typing import Any

import pytest
from telebot.types import Message

from epiframe.bot.commands import Commands


def message(chat_id: int = 1, **fields: Any) -> Message:
    data = {"message_id": 1, "date": 0, "chat": {"id": chat_id, "type": "private"}}
    parsed: Message = Message.de_json(data | fields)  # type: ignore[no-untyped-call]
    return parsed


class FakeMultiplier:
    """:class:`epiframe.bot.commands.Multiplier` recording saves in ``calls``."""

    def __init__(self, calls: list[tuple[Any, ...]]) -> None:
        self.calls = calls
        self.value = 0

    def read(self) -> int:
        return self.value

    def save(self, multiplier: int) -> None:
        self.calls.append(("save_multiplier", multiplier))


class FakeFrame:
    """:class:`epiframe.bot.commands.Frame` recording the actions in ``calls``."""

    def __init__(self, tmp_path: Path) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.token = "123456:SECRET-token"  # noqa: S105 (fake)
        self.chat_id = "1,-2"
        self.busy = False
        self.metric = True
        self.interval_enabled = True
        self.max_interval = 5
        self.multiplier = FakeMultiplier(self.calls)
        self.download = tmp_path / "photo"
        self.current: Path | None = None
        self.original: Path | None = None

    def refresh(self) -> None:
        self.calls.append(("refresh",))

    def next_photo(self) -> None:
        self.calls.append(("next_photo",))

    def redisplay(self) -> None:
        self.calls.append(("redisplay",))

    def download_file(self, extension: str) -> Path:
        return Path(f"{self.download}.{extension}")

    def current_file(self) -> Path | None:
        return self.current

    def original_file(self) -> Path | None:
        return self.original

    def next_update_text(self) -> str:
        return "at 12:00:00\nin 5 mins 0 secs"

    def reboot(self) -> None:
        self.calls.append(("reboot",))


class FakeChat:
    """:class:`epiframe.bot.commands.Chat` recording what was sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, Any]] = []

    def send_text(self, text: str, markdown: bool = False) -> None:
        self.sent.append(("markdown" if markdown else "text", text))

    def send_photo(self, path: Path) -> None:
        self.sent.append(("photo", path))


@pytest.fixture
def frame(tmp_path: Path) -> FakeFrame:
    return FakeFrame(tmp_path)


@pytest.fixture
def chat() -> FakeChat:
    return FakeChat()


@pytest.fixture
def commands(frame: FakeFrame, tmp_path: Path) -> Commands:
    # an empty /proc and no thermal file unless a test writes them
    return Commands(frame, proc=tmp_path, thermal=tmp_path / "temp")
