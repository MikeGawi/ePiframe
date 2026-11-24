"""Telegram bot test (``ePiframe.py --test-telegram``).

Checks the token and the connection, then listens: every chat that writes to the
bot gets its chat id back. Works before the bot is configured and without the
service; at the end it offers to save the token and the new chat ids.
"""

from collections.abc import Callable, Iterable

import telebot
from telebot.apihelper import ApiTelegramException
from telebot.types import Message

from epiframe.bot.telegram import allowed_chats, connect, hide_token
from epiframe.config.base import ConfigBase
from epiframe.core.console import Ask, Say, ask_yes, read_secret

Connect = Callable[[str], telebot.TeleBot]

CHAT_ID_REP = "ePiframe test: the id of this chat is {}"
POLL_SECONDS = 10  # long polling: Telegram answers at once when a message comes
CONFLICT = 409
CONFLICT_MSG = (
    "Another program is using this bot right now (Telegram: 409 Conflict), e.g. the"
    " ePiframe service or another frame with the same token. It gets the messages"
    " instead of this test: stop it and run the test again."
)


class TelegramTest:
    """The test dialogue; ``ask``/``say`` are ``input``/``print`` by default."""

    def __init__(
        self,
        config: ConfigBase,
        ask: Ask = input,
        say: Say = print,
        connect: Connect = connect,
        ask_secret: Ask = read_secret,
    ) -> None:
        self.config = config
        self.ask = ask
        self.say = say
        self.connect = connect
        self.ask_secret = ask_secret
        self.token = ""
        self.chats: list[int] = []

    def run(self) -> int:
        """Run the test; return the exit code (0 = the bot works)."""
        try:
            self.say("ePiframe - Telegram bot test (Ctrl+C to stop)")
            self.token = self._token()
            bot = self._bot()
            if not bot or not self._listen(bot):
                return 1
            self._offer_save()
        except (EOFError, KeyboardInterrupt):
            self.say("\nTest stopped, nothing saved.")
            return 1
        return 0

    def _token(self) -> str:
        current = self.config.get("token")
        if current and ask_yes(self.ask, "Use the token from the configuration?", True):
            return current
        while True:
            if token := self.ask_secret("Bot token (from BotFather): ").strip():
                return token

    def _bot(self) -> telebot.TeleBot | None:
        self.say("Connecting to Telegram...")
        try:
            bot = self.connect(self.token)
            me = bot.get_me()
        except Exception as error:
            self.say(f"Error: {hide_token(str(error), self.token)}")
            return None
        self.say(f"Connected to the bot {me.first_name} (@{me.username})")
        self.say(
            f"Write anything to @{me.username} in Telegram: the bot answers with the"
            " chat id. Ctrl+C to stop.\n"
            "(If the ePiframe service runs this bot, stop it first: Telegram allows"
            " one program per bot.)"
        )
        return bot

    def _listen(self, bot: telebot.TeleBot) -> bool:
        """Answer the messages until Ctrl+C; ``False`` if polling fails."""
        offset: int | None = None
        try:
            while True:
                offset = self._poll(bot, offset)
        except KeyboardInterrupt:
            self.say("")
            return True
        except Exception as error:
            self.say(self._failure(error))
            return False

    def _poll(self, bot: telebot.TeleBot, offset: int | None) -> int | None:
        """Answer the new messages; return the offset that confirms them."""
        updates = bot.get_updates(
            offset=offset, timeout=POLL_SECONDS, long_polling_timeout=POLL_SECONDS
        )
        self._answer(bot, [update.message for update in updates if update.message])
        return updates[-1].update_id + 1 if updates else offset

    def _failure(self, error: Exception) -> str:
        if isinstance(error, ApiTelegramException) and error.error_code == CONFLICT:
            return CONFLICT_MSG
        return f"Error: {hide_token(str(error), self.token)}"

    def _answer(self, bot: telebot.TeleBot, messages: Iterable[Message]) -> None:
        for message in messages:
            chat = message.chat
            if chat.id not in self.chats:
                self.chats.append(chat.id)
            self.say(f"Message from chat {chat.id} ({self._name(message)})")
            try:
                bot.send_message(chat.id, CHAT_ID_REP.format(chat.id), parse_mode="")
            except Exception as error:
                self.say(f"Error: {hide_token(str(error), self.token)}")

    def _name(self, message: Message) -> str:
        chat = message.chat
        name = chat.title or chat.username or chat.first_name or chat.type
        allowed = chat.id in allowed_chats(self.config.get("chat_id"))
        return f"{name}, {'allowed' if allowed else 'not in chat_id'}"

    def _offer_save(self) -> None:
        existing = sorted(allowed_chats(self.config.get("chat_id")))
        new = [chat for chat in self.chats if chat not in existing]
        if not self._changed(new):
            self.say("The configuration already has this bot and these chats.")
        elif ask_yes(self.ask, self._save_question(new), True):
            self._save(existing + new)
        else:
            self.say("Nothing saved.")

    @staticmethod
    def _save_question(new: list[int]) -> str:
        chats = (
            f" and add the chats {', '.join(map(str, new))} to chat_id" if new else ""
        )
        return f"Save the token{chats} and enable the bot?"

    def _save(self, chats: list[int]) -> None:
        self.config.set("use_telebot", "1")
        self.config.set("token", self.token)
        self.config.set("chat_id", ",".join(map(str, chats)))
        self.config.save()
        self.say(f"Saved to {self.config.path}.")
        self.say("Restart the ePiframe service to start the bot.")

    def _changed(self, new: list[int]) -> bool:
        enabled = self.config.getint("use_telebot")
        return bool(new) or not enabled or self.token != self.config.get("token")
