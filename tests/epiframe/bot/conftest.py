from pathlib import Path
from typing import Any

import pytest
from telebot.types import Message

from epiframe.bot.commands import Commands


def message(chat_id: int = 1, **fields: Any) -> Message:
    data = {"message_id": 1, "date": 0, "chat": {"id": chat_id, "type": "private"}}
    parsed: Message = Message.de_json(data | fields)  # type: ignore[no-untyped-call]
    return parsed


class FakeFrame:
    """:class:`epiframe.bot.commands.Frame` recording the actions in ``calls``."""

    def __init__(self, tmp_path: Path) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.token = "123456:SECRET-token"  # noqa: S105 (fake)
        self.chat_id = "1,-2"
        self.busy = False
        self.download = str(tmp_path / "photo")
        self.current: str | None = None
        self.original: str | None = None
        self.multiplication = True
        self.interval = 0
        self.max_interval = 5
        self.metric = True

    def refresh(self) -> None:
        self.calls.append(("refresh",))

    def get_token(self) -> str:
        return self.token

    def get_chat_id(self) -> str:
        return self.chat_id

    def pid_file_exists(self) -> bool:
        return self.busy

    def fire_event(self) -> None:
        self.calls.append(("fire_event",))

    def refresh_frame(self) -> None:
        self.calls.append(("refresh_frame",))

    def get_download_file(self) -> str:
        return self.download

    def get_current_file(self) -> str | None:
        return self.current

    def get_original_file(self) -> str | None:
        return self.original

    def get_next_time(self) -> str:
        return "at 12:00:00\nin 5 mins 0 secs"

    def is_interval_mult_enabled(self) -> bool:
        return self.multiplication

    def get_interval(self) -> int:
        return self.interval

    def get_max_interval(self) -> int:
        return self.max_interval

    def save_interval(self, number: int) -> None:
        self.calls.append(("save_interval", number))

    def is_metric(self) -> bool:
        return self.metric

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
