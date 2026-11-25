import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, create_autospec, patch

import pytest
import requests
import requests_mock
import telebot
from telebot.apihelper import ApiTelegramException
from telebot.types import BotCommand

from epiframe.bot import telegram
from epiframe.bot.commands import COMMANDS, help_text
from epiframe.bot.telegram import (
    API_URL,
    HIDDEN,
    TelegramBot,
    TelegramChat,
    allowed_chats,
    attachment,
    check_token,
    connect,
    hide_token,
)
from tests.epiframe.bot.conftest import FakeFrame, message

TOKEN = "123456:SECRET-token"  # noqa: S105 (fake)
GET_ME = f"{API_URL}/bot{TOKEN}/getMe"
ME = {"ok": True, "result": {"id": 123456, "is_bot": True, "first_name": "ePiframe"}}


@pytest.fixture
def http() -> Iterator[requests_mock.Mocker]:
    with requests_mock.Mocker() as mocker:
        yield mocker


@pytest.fixture
def api() -> MagicMock:
    api: MagicMock = create_autospec(telebot.TeleBot, instance=True)
    return api


@pytest.fixture
def bot(frame: FakeFrame, api: MagicMock) -> TelegramBot:
    return TelegramBot(frame, api)


@pytest.fixture(autouse=True)
def info_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="epiframe")


def photo_sizes(*ids: str) -> list[dict[str, Any]]:
    return [
        {"file_id": file_id, "file_unique_id": file_id, "width": 1, "height": 1}
        for file_id in ids
    ]


def document(**fields: Any) -> dict[str, Any]:
    return {"file_id": "doc", "file_unique_id": "doc"} | fields


# ------------------------------------------------------------------ helpers


def test_hide_token() -> None:
    assert hide_token(f"url /bot{TOKEN}/getMe", TOKEN) == f"url /bot{HIDDEN}/getMe"
    assert hide_token("no token", TOKEN) == "no token"
    assert hide_token("empty token", "") == "empty token"


def test_allowed_chats() -> None:
    assert allowed_chats("1, -2,3") == {1, -2, 3}
    assert allowed_chats("") == set()
    assert allowed_chats("1,") == {1}


def test_attachment_photo() -> None:
    # the biggest size is the last one
    assert attachment(message(photo=photo_sizes("small", "big"))) == ("big", "jpg")


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"mime_type": "image/png", "file_name": "a.jpg"}, ("doc", "png")),
        ({"mime_type": "image/x-unknown", "file_name": "A.JPEG"}, ("doc", "jpeg")),
        ({"mime_type": "image/x-unknown", "file_name": "a.xyz"}, None),
        ({"mime_type": "image/x-unknown"}, None),
        ({"mime_type": "application/pdf", "file_name": "a.jpg"}, None),
        ({"file_name": "a.jpg"}, None),
    ],
)
def test_attachment_document(
    fields: dict[str, Any], expected: tuple[str, str] | None
) -> None:
    assert attachment(message(document=document(**fields))) == expected


def test_attachment_text() -> None:
    assert attachment(message(text="/ping")) is None


# ------------------------------------------------------------------ connect


def test_connect(http: requests_mock.Mocker) -> None:
    http.get(API_URL)
    http.get(GET_ME, json=ME)

    assert isinstance(connect(TOKEN), telebot.TeleBot)


def test_connect_malformed_token() -> None:
    with pytest.raises(ValueError, match="colon"):
        connect("no-colon")


def test_connect_no_internet(http: requests_mock.Mocker) -> None:
    http.get(API_URL, exc=requests.ConnectionError("no route to host"))

    with pytest.raises(Warning, match="no route to host"):
        connect(TOKEN)


def test_connect_refused_token(http: requests_mock.Mocker) -> None:
    http.get(API_URL)
    http.get(
        GET_ME,
        status_code=401,
        json={"ok": False, "error_code": 401, "description": "Unauthorized"},
    )

    with pytest.raises(Warning, match="Unauthorized"):
        connect(TOKEN)


def test_connect_hides_token(http: requests_mock.Mocker) -> None:
    # requests errors contain the URL, and the URL contains the token
    http.get(API_URL)
    http.get(GET_ME, exc=requests.ConnectionError(f"Max retries with url: {GET_ME}"))

    with pytest.raises(Warning) as warning:
        connect(TOKEN)

    assert TOKEN not in str(warning.value)
    assert HIDDEN in str(warning.value)


def test_check_token() -> None:
    with patch.object(telegram, "connect") as connect_mock:
        check_token(TOKEN)

    connect_mock.assert_called_once_with(TOKEN)


# ------------------------------------------------------------------ chat


def test_chat_send_text(api: MagicMock) -> None:
    chat = TelegramChat(api, 5)

    chat.send_text("snake_case")
    chat.send_text("*bold*", markdown=True)

    assert api.send_message.call_args_list == [
        call(5, "snake_case", parse_mode=""),
        call(5, "*bold*", parse_mode="Markdown"),
    ]


def test_chat_send_photo(api: MagicMock, tmp_path: Path) -> None:
    photo = tmp_path / "photo.bmp"
    photo.write_bytes(b"BM")
    sent: list[bytes] = []
    api.send_photo.side_effect = lambda _chat, file: sent.append(file.read())

    TelegramChat(api, 5).send_photo(photo)

    api.send_chat_action.assert_called_once_with(5, "upload_photo")
    assert sent == [b"BM"]


# ------------------------------------------------------------------ bot


def test_bot_init(frame: FakeFrame, api: MagicMock, bot: TelegramBot) -> None:
    assert frame.calls == [("refresh",)]
    assert bot.token == TOKEN
    api.set_update_listener.assert_called_once_with(bot.handle)


def test_bot_init_connects(frame: FakeFrame, api: MagicMock) -> None:
    with patch.object(telegram, "connect", return_value=api) as connect_mock:
        bot = TelegramBot(frame)

    connect_mock.assert_called_once_with(TOKEN)
    assert bot.bot is api


def test_bot_init_empty_chat_id(
    frame: FakeFrame, api: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    frame.chat_id = ""

    TelegramBot(frame, api)

    assert "chat_id is empty, nobody can control the frame" in caplog.text


def test_bot_init_no_warning(
    bot: TelegramBot, caplog: pytest.LogCaptureFixture
) -> None:
    assert caplog.text == ""


def test_start(api: MagicMock, bot: TelegramBot) -> None:
    bot.start()

    commands = api.set_my_commands.call_args.args[0]
    assert [(command.command, command.description) for command in commands] == [
        (command.name, command.description) for command in COMMANDS
    ]
    assert all(isinstance(command, BotCommand) for command in commands)
    api.infinity_polling.assert_called_once_with()


def test_start_commands_not_registered(
    api: MagicMock, bot: TelegramBot, caplog: pytest.LogCaptureFixture
) -> None:
    api.set_my_commands.side_effect = requests.ConnectionError(f"url /bot{TOKEN}/")

    bot.start()

    assert f"can't register the commands: url /bot{HIDDEN}/" in caplog.text
    assert TOKEN not in caplog.text
    api.infinity_polling.assert_called_once_with()


def test_stop(api: MagicMock, bot: TelegramBot) -> None:
    bot.stop()

    api.stop_polling.assert_called_once_with()


def test_handle_refreshes_once(
    frame: FakeFrame, api: MagicMock, bot: TelegramBot
) -> None:
    bot.handle([message(text="/ping"), message(text="/ping")])

    assert frame.calls == [("refresh",), ("refresh",)]
    assert api.send_message.call_args_list == [call(1, "Pong", parse_mode="")] * 2


def test_handle_command(api: MagicMock, bot: TelegramBot) -> None:
    bot.handle([message(chat_id=-2, text="/help@ePiframeBot")])

    api.send_message.assert_called_once_with(-2, help_text(), parse_mode="Markdown")


def test_handle_not_allowed_chat(
    frame: FakeFrame, api: MagicMock, bot: TelegramBot, caplog: pytest.LogCaptureFixture
) -> None:
    bot.handle([message(chat_id=7, text="/reboot")])

    assert frame.calls == [("refresh",), ("refresh",)]
    api.send_message.assert_not_called()
    assert "message from a not allowed chat 7" in caplog.text


def test_handle_empty_whitelist(frame: FakeFrame, api: MagicMock) -> None:
    frame.chat_id = ""
    bot = TelegramBot(frame, api)

    bot.handle([message(chat_id=7, text="/reboot")])

    assert ("reboot",) not in frame.calls
    api.send_message.assert_called_once_with(
        7,
        "This chat is not allowed to control the frame.\n"
        "Add its id 7 to chat_id in the [Telegram bot] section of the configuration.",
        parse_mode="",
    )


def test_handle_unsupported_content(api: MagicMock, bot: TelegramBot) -> None:
    bot.handle([message(location={"latitude": 53.3, "longitude": 7.8})])

    api.send_message.assert_called_once_with(
        1, "Content type unsupported", parse_mode=""
    )


def test_handle_photo(frame: FakeFrame, api: MagicMock, bot: TelegramBot) -> None:
    api.get_file.return_value.file_path = "photos/file_1.jpg"
    api.download_file.return_value = b"JPEG"

    bot.handle([message(photo=photo_sizes("small", "big"))])

    api.get_file.assert_called_once_with("big")
    api.download_file.assert_called_once_with("photos/file_1.jpg")
    assert Path(f"{frame.download}.jpg").read_bytes() == b"JPEG"
    assert frame.calls[-1] == ("redisplay",)
    api.send_message.assert_called_once_with(
        1, "Sending photo to display", parse_mode=""
    )


def test_handle_document(frame: FakeFrame, api: MagicMock, bot: TelegramBot) -> None:
    api.get_file.return_value.file_path = "documents/file_2.png"
    api.download_file.return_value = b"PNG"

    bot.handle([message(document=document(mime_type="image/png"))])

    api.get_file.assert_called_once_with("doc")
    assert Path(f"{frame.download}.png").read_bytes() == b"PNG"
    assert frame.calls[-1] == ("redisplay",)


def test_handle_photo_busy(frame: FakeFrame, api: MagicMock, bot: TelegramBot) -> None:
    frame.busy = True

    bot.handle([message(photo=photo_sizes("big"))])

    api.get_file.assert_not_called()
    assert ("redisplay",) not in frame.calls
    api.send_message.assert_called_once_with(
        1, "Frame update already in progress\nTry again later", parse_mode=""
    )


def test_handle_photo_without_path(
    frame: FakeFrame, api: MagicMock, bot: TelegramBot
) -> None:
    api.get_file.return_value.file_path = None

    bot.handle([message(photo=photo_sizes("big"))])

    api.download_file.assert_not_called()
    assert ("redisplay",) not in frame.calls
    api.send_message.assert_called_once_with(1, "Error", parse_mode="")


def test_handle_photo_download_error(
    frame: FakeFrame, api: MagicMock, bot: TelegramBot, caplog: pytest.LogCaptureFixture
) -> None:
    api.get_file.return_value.file_path = "photos/file_1.jpg"
    api.download_file.side_effect = requests.ConnectionError(
        f"url /file/bot{TOKEN}/photos/file_1.jpg"
    )

    bot.handle([message(photo=photo_sizes("big"))])

    assert ("redisplay",) not in frame.calls
    api.send_message.assert_called_once_with(1, "Error", parse_mode="")
    assert f"Telegram bot error: url /file/bot{HIDDEN}/" in caplog.text
    assert TOKEN not in caplog.text


def test_handle_error_reply_fails(
    api: MagicMock, bot: TelegramBot, caplog: pytest.LogCaptureFixture
) -> None:
    api.send_message.side_effect = ApiTelegramException(  # type: ignore[no-untyped-call]
        "sendMessage", "", {"error_code": 400, "description": "Bad Request"}
    )

    bot.handle([message(text="/ping"), message(text="/ping")])

    # both messages handled, the failing reply is only logged
    assert api.send_message.call_count == 4
    assert caplog.text.count("Telegram bot error:") == 2
