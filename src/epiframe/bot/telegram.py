"""Telegram bot (pyTelegramBotAPI): moves messages between Telegram and the commands.

Only the chats listed in ``chat_id`` control the frame. With an empty list nobody
does: the bot answers every chat with its id, so the owner knows what to add.
"""

from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

import telebot
from telebot.types import BotCommand, Document, Message

from epiframe.bot.commands import (
    COMMANDS,
    ERROR_REP,
    LATER_REP,
    NOT_ALLOWED_REP,
    PROGRESS_REP,
    SENDING_REP,
    UNSUPPORTED_REP,
    Commands,
    Frame,
)
from epiframe.core.logs import get_logger
from epiframe.core.media_types import EXTENSIONS, MIME_PREFIX, TYPE_TO_EXTENSION
from epiframe.core.network import check_internet

API_URL = "https://api.telegram.org"
CONNECTION_TIMEOUT = 5
MARKDOWN = "Markdown"
UPLOAD_PHOTO_ACTION = "upload_photo"
PHOTO_EXTENSION = "jpg"  # Telegram sends compressed photos as JPEG
HIDDEN = "<token>"

log = get_logger("telegram")


def hide_token(text: str, token: str) -> str:
    """Remove the token from ``text`` (request URLs contain it: ``/bot<token>/``)."""
    return text.replace(token, HIDDEN) if token else text


def connect(token: str, timeout: float = CONNECTION_TIMEOUT) -> telebot.TeleBot:
    """Return a bot for ``token`` that Telegram accepted.

    A malformed token raises ``ValueError``; no connection or a token refused by
    Telegram raise ``Warning`` (a configuration warning, the network may be down).
    The messages never contain the token.
    """
    bot = telebot.TeleBot(token)
    error = check_internet(API_URL, timeout)
    if error:
        raise Warning(error)
    try:
        bot.get_me()
    except Exception as exception:
        raise Warning(hide_token(str(exception), token)) from None
    return bot


def check_token(token: str) -> None:
    """Configuration check of the ``token`` entry."""
    connect(token)


def allowed_chats(value: str) -> set[int]:
    """The ``chat_id`` entry (comma separated ids) as a set."""
    return {int(item) for item in value.split(",") if item.strip()}


def document_extension(document: Document) -> str | None:
    """Extension for an image sent as a file, ``None`` for other files."""
    mime_type = document.mime_type or ""
    if not mime_type.startswith(MIME_PREFIX):
        return None
    extension = TYPE_TO_EXTENSION.get(mime_type) or _name_extension(document.file_name)
    return extension if extension in EXTENSIONS else None


def _name_extension(name: str | None) -> str:
    return Path(name or "").suffix[1:].lower()


def attachment(message: Message) -> tuple[str, str] | None:
    """``(file id, extension)`` of the photo in ``message``, ``None`` without one.

    A photo comes in several sizes (the biggest is the last one); an image sent as
    a file (document) keeps its original quality.
    """
    if message.photo:
        return message.photo[-1].file_id, PHOTO_EXTENSION
    if message.document and (extension := document_extension(message.document)):
        return message.document.file_id, extension
    return None


class TelegramChat:
    """:class:`epiframe.bot.commands.Chat` of one Telegram chat."""

    def __init__(self, bot: telebot.TeleBot, chat_id: int) -> None:
        self.bot = bot
        self.chat_id = chat_id

    def send_text(self, text: str, markdown: bool = False) -> None:
        # no parse mode by default: "_" or "*" in an echo or a path would break it
        self.bot.send_message(
            self.chat_id, text, parse_mode=MARKDOWN if markdown else ""
        )

    def send_photo(self, path: Path) -> None:
        self.bot.send_chat_action(self.chat_id, UPLOAD_PHOTO_ACTION)
        with path.open("rb") as photo:
            self.bot.send_photo(self.chat_id, photo)


class TelegramBot:
    """The bot of the frame; :meth:`start` blocks while it polls Telegram."""

    def __init__(self, frame: Frame, bot: telebot.TeleBot | None = None) -> None:
        frame.refresh()
        self.frame = frame
        self.token = frame.get_token()
        self.bot = bot or connect(self.token)
        self.commands = Commands(frame)
        self.bot.set_update_listener(self.handle)
        if not allowed_chats(frame.get_chat_id()):
            log.warning(
                "Telegram bot: chat_id is empty, nobody can control the frame "
                "(the bot answers with the chat id to add)"
            )

    def start(self) -> None:
        self.register_commands()
        self.bot.infinity_polling()

    def stop(self) -> None:
        self.bot.stop_polling()  # type: ignore[no-untyped-call]

    def register_commands(self) -> None:
        """Show the commands in the Telegram menu (no BotFather setup needed)."""
        commands = [
            BotCommand(command.name, command.description) for command in COMMANDS
        ]
        try:
            self.bot.set_my_commands(commands)
        except Exception as exception:
            log.warning(
                "Telegram bot: can't register the commands: %s",
                hide_token(str(exception), self.token),
            )

    def handle(self, messages: Iterable[Message]) -> None:
        self.frame.refresh()
        for message in messages:
            self.handle_message(message)

    def handle_message(self, message: Message) -> None:
        chat = TelegramChat(self.bot, message.chat.id)
        try:
            self.dispatch(message, chat)
        except Exception as exception:
            log.error("Telegram bot error: %s", hide_token(str(exception), self.token))
            with suppress(Exception):
                chat.send_text(ERROR_REP)

    def dispatch(self, message: Message, chat: TelegramChat) -> None:
        allowed = allowed_chats(self.frame.get_chat_id())
        if chat.chat_id not in allowed:
            self.refuse(chat, bool(allowed))
        elif message.content_type == "text":
            self.commands.run(message.text or "", chat)
        elif found := attachment(message):
            self.show_photo(*found, chat)
        else:
            chat.send_text(UNSUPPORTED_REP)

    @staticmethod
    def refuse(chat: TelegramChat, whitelist: bool) -> None:
        log.warning("Telegram bot: message from a not allowed chat %s", chat.chat_id)
        if not whitelist:
            chat.send_text(NOT_ALLOWED_REP.format(chat.chat_id))

    def show_photo(self, file_id: str, extension: str, chat: TelegramChat) -> None:
        """Save the photo as the downloaded photo and send it to the display."""
        if self.frame.pid_file_exists():
            chat.send_text(f"{PROGRESS_REP}\n{LATER_REP}")
            return
        info = self.bot.get_file(file_id)
        if not info.file_path:
            raise ValueError("Telegram gave no file to download")
        content = self.bot.download_file(info.file_path)
        Path(f"{self.frame.get_download_file()}.{extension}").write_bytes(content)
        self.frame.refresh_frame()
        chat.send_text(SENDING_REP)
