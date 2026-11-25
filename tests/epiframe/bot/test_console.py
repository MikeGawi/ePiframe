from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, create_autospec

import pytest
import requests
import telebot
from telebot.apihelper import ApiTelegramException
from telebot.types import Message, User

from epiframe.bot.console import CHAT_ID_REP, CONFLICT_MSG, POLL_SECONDS, TelegramTest
from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from tests.epiframe.bot.conftest import message
from tests.helpers.console import Answer, Console

TOKEN = "123456:SECRET-token"  # noqa: S105 (fake)
OTHER_TOKEN = "654321:OTHER-token"  # noqa: S105 (fake)
GROUP = {"id": -5, "type": "group", "title": "Family"}


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigManager:
    monkeypatch.chdir(tmp_path)
    return ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)


@pytest.fixture
def api() -> MagicMock:
    api: MagicMock = create_autospec(telebot.TeleBot, instance=True)
    api.get_me.return_value = User(123456, True, "ePiframe", username="ePiframeBot")
    return api


def deliver(api: MagicMock, *messages: Message | None) -> None:
    """``get_updates`` returns ``messages`` (``None``: an update without a message),
    then nothing, then the user presses Ctrl+C."""
    updates = [
        SimpleNamespace(update_id=10 + number, message=message)
        for number, message in enumerate(messages)
    ]
    api.get_updates.side_effect = [updates, [], KeyboardInterrupt()]


@dataclass
class Result:
    code: int
    console: Console
    connected: list[str]  # tokens

    @property
    def output(self) -> str:
        return self.console.output

    @property
    def prompts(self) -> list[str]:
        return self.console.prompts


def run(config: ConfigManager, api: MagicMock, *answers: Answer) -> Result:
    console = Console(*answers)
    connected: list[str] = []

    def connect(token: str) -> telebot.TeleBot:
        connected.append(token)
        return api

    code = TelegramTest(
        config, console.ask, console.say, connect, ask_secret=console.ask
    ).run()
    return Result(code, console, connected)


def saved(tmp_path: Path) -> ConfigManager:
    return ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)


def test_new_bot(config: ConfigManager, api: MagicMock, tmp_path: Path) -> None:
    deliver(api, message(chat_id=7), message(chat={**GROUP}), message(chat_id=7))

    result = run(config, api, f" {TOKEN} ", "")

    assert result.code == 0
    assert result.connected == [TOKEN]
    assert "Connected to the bot ePiframe (@ePiframeBot)" in result.output
    assert "Message from chat 7 (private, not in chat_id)" in result.output
    assert "Message from chat -5 (Family, not in chat_id)" in result.output
    assert api.send_message.call_args_list == [
        call(7, CHAT_ID_REP.format(7), parse_mode=""),
        call(-5, CHAT_ID_REP.format(-5), parse_mode=""),
        call(7, CHAT_ID_REP.format(7), parse_mode=""),
    ]
    assert result.prompts[-1] == (
        "Save the token and add the chats 7, -5 to chat_id and enable the bot? [Y/n] "
    )
    config = saved(tmp_path)
    assert config.get("use_telebot") == "1"
    assert config.get("token") == TOKEN
    assert config.get("chat_id") == "7,-5"
    assert "Restart the ePiframe service" in result.output
    assert TOKEN not in result.output


def test_empty_token_asked_again(config: ConfigManager, api: MagicMock) -> None:
    deliver(api)

    result = run(config, api, "", TOKEN, "n")

    assert result.connected == [TOKEN]
    assert result.prompts[:2] == ["Bot token (from BotFather): "] * 2


def test_configured_bot(config: ConfigManager, api: MagicMock, tmp_path: Path) -> None:
    config.set("use_telebot", "1")
    config.set("token", TOKEN)
    config.set("chat_id", "7")
    config.save()
    deliver(
        api, message(chat_id=7, chat={"id": 7, "type": "private", "username": "me"})
    )

    result = run(config, api, "")

    assert result.code == 0
    assert result.prompts == ["Use the token from the configuration? [Y/n] "]
    assert result.connected == [TOKEN]
    assert "Message from chat 7 (me, allowed)" in result.output
    assert "already has this bot and these chats" in result.output


def test_add_chat_to_configured_bot(
    config: ConfigManager, api: MagicMock, tmp_path: Path
) -> None:
    config.set("use_telebot", "1")
    config.set("token", TOKEN)
    config.set("chat_id", "9,7")
    deliver(api, message(chat_id=8), message(chat_id=7))

    run(config, api, "", "y")

    assert saved(tmp_path).get("chat_id") == "7,9,8"


def test_other_token(config: ConfigManager, api: MagicMock, tmp_path: Path) -> None:
    config.set("use_telebot", "1")
    config.set("token", TOKEN)
    deliver(api)

    result = run(config, api, "n", OTHER_TOKEN, "")

    assert result.connected == [OTHER_TOKEN]
    assert result.prompts[-1] == "Save the token and enable the bot? [Y/n] "
    assert saved(tmp_path).get("token") == OTHER_TOKEN


def test_disabled_bot_is_enabled(
    config: ConfigManager, api: MagicMock, tmp_path: Path
) -> None:
    config.set("token", TOKEN)
    deliver(api)

    run(config, api, "", "")

    assert saved(tmp_path).get("use_telebot") == "1"


def test_nothing_saved(config: ConfigManager, api: MagicMock, tmp_path: Path) -> None:
    deliver(api, message(chat_id=7))

    result = run(config, api, TOKEN, "n")

    assert result.code == 0
    assert "Nothing saved." in result.output
    assert saved(tmp_path).get("token") == ""


def test_connection_error(config: ConfigManager, api: MagicMock) -> None:
    def refuse(token: str) -> telebot.TeleBot:
        raise Warning(f"no connection to /bot{token}/getMe")

    console = Console(TOKEN)

    code = TelegramTest(
        config, console.ask, console.say, refuse, ask_secret=console.ask
    ).run()

    assert code == 1
    assert "Error: no connection to /bot<token>/getMe" in console.output
    assert TOKEN not in console.output


def test_answer_error(config: ConfigManager, api: MagicMock) -> None:
    api.send_message.side_effect = requests.ConnectionError(f"url /bot{TOKEN}/")
    deliver(api, message(chat_id=7))

    result = run(config, api, TOKEN, "n")

    assert result.code == 0
    assert "Error: url /bot<token>/" in result.output
    assert TOKEN not in result.output


def test_polling(config: ConfigManager, api: MagicMock) -> None:
    deliver(api, message(chat_id=7), None)

    run(config, api, TOKEN, "n")

    # the next request confirms the updates received so far
    assert api.get_updates.call_args_list == [
        call(offset=None, timeout=POLL_SECONDS, long_polling_timeout=POLL_SECONDS),
        call(offset=12, timeout=POLL_SECONDS, long_polling_timeout=POLL_SECONDS),
        call(offset=12, timeout=POLL_SECONDS, long_polling_timeout=POLL_SECONDS),
    ]
    assert api.send_message.call_count == 1


def test_conflict(config: ConfigManager, api: MagicMock, tmp_path: Path) -> None:
    # e.g. the ePiframe service (or a 1.x frame) polls the same bot
    api.get_updates.side_effect = ApiTelegramException(  # type: ignore[no-untyped-call]
        "getUpdates",
        "",
        {"error_code": 409, "description": "Conflict: terminated by other getUpdates"},
    )

    result = run(config, api, TOKEN)

    assert result.code == 1
    assert CONFLICT_MSG in result.output
    assert len(result.prompts) == 1  # no "Save ...?" question
    assert saved(tmp_path).get("token") == ""


def test_polling_error(config: ConfigManager, api: MagicMock) -> None:
    api.get_updates.side_effect = requests.ConnectionError(f"url /bot{TOKEN}/")

    result = run(config, api, TOKEN)

    assert result.code == 1
    assert "Error: url /bot<token>/" in result.output
    assert TOKEN not in result.output


@pytest.mark.parametrize("stop", [KeyboardInterrupt(), EOFError()])
def test_stopped(
    config: ConfigManager, api: MagicMock, tmp_path: Path, stop: BaseException
) -> None:
    deliver(api, message(chat_id=7))

    result = run(config, api, TOKEN, stop)

    assert result.code == 1
    assert "Test stopped, nothing saved." in result.output
    assert saved(tmp_path).get("token") == ""
