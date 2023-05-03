from __future__ import annotations

import re
import telebot
from typing import Union
from misc.connection import Connection
from misc.telebotcmd import TelebotCmd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.backendmanager import BackendManager


class TelebotManager:

    __STATUS_OS_CMD = (
        '/usr/bin/free --mega -t | /usr/bin/awk \'{print (NR==1?"Type":""), $1, $2, $3,'
        "(NR==1?\"\":$4)}' | column -t | /bin/sed 's/ \+/ /g' && /usr/bin/uptime | /bin/sed 's/ \+/ /g' | "
        "/bin/sed 's/^ //g' && vcgencmd measure_temp"
    )
    __STATUS_OS_CMD_F = (
        '/usr/bin/free --mega -t | /usr/bin/awk \'{print (NR==1?"Type":""), $1, $2, $3,'
        "(NR==1?\"\":$4)}' | column -t | /bin/sed 's/ \+/ /g' && /usr/bin/uptime | /bin/sed 's/ "
        "\+/ /g' | /bin/sed 's/^ //g' && echo \"temp=\"$(awk \"BEGIN {print `vcgencmd measure_temp | "
        "egrep -o '[0-9]*\.[0-9]*'`*1.8+32}\")\"'F\""
    )

    def __init__(self, backend: BackendManager):
        self.__backend = backend
        self.__backend.refresh()
        self.__bot = self.check_token(self.__backend.get_token())
        self.__bot.set_update_listener(self.__handle_messages)
        self.__backend.update_time()

    @staticmethod
    def check_token(token: str) -> telebot:
        return_value = Connection.check_internet(
            "http://" + TelebotCmd.API_URL, int(TelebotCmd.API_CONNECTION_TIMEOUT)
        )
        if return_value:
            raise Exception(return_value)
        bot = telebot.TeleBot(token, parse_mode=TelebotCmd.TG_PARSE_MODE)
        bot.get_me()
        return bot

    def start(self):
        self.__bot.infinity_polling()

    def __handle_messages(self, messages):
        self.__backend.refresh()

        if messages:
            for message in messages:
                self.__messages(message)

    def __messages(self, message):
        chat_id = message.chat.id
        ids = (
            [int(value) for value in self.__backend.get_chat_id().split(",")]
            if self.__backend.get_chat_id()
            else [chat_id]
        )
        self.__process_ids(chat_id, ids, message)

    def __process_ids(self, chat_id, ids, message):
        if chat_id in ids:
            if message.content_type == TelebotCmd.TEXT_TAG:
                command = re.sub(r"@.+ ", " ", message.text).split("@")[0]
                self.__process_command(chat_id, command)
            elif message.content_type == TelebotCmd.PHOTO_TAG:
                self.__process_file(chat_id, message)
            else:
                self.__bot.send_message(chat_id, TelebotCmd.UNSUPPORTED_REP)

    def __process_file(self, chat_id: Union[int, str], message):
        if self.__backend.pid_file_exists():
            self.__bot.send_message(
                chat_id, f"{TelebotCmd.PROGRESS_REP}\n{TelebotCmd.LATER_REP}"
            )
        else:
            file_info = self.__bot.get_file(message.photo[-1].file_id)
            downloaded_file = self.__bot.download_file(file_info.file_path)
            try:
                with open(
                    self.__backend.get_download_file() + TelebotCmd.DOWNLOAD_PHOTO_EXT,
                    TelebotCmd.DOWNLOAD_PHOTO_PERM_TAG,
                ) as new_file:
                    new_file.write(downloaded_file)

                self.__backend.refresh_frame()
                self.__bot.reply_to(message, TelebotCmd.SENDING_REP)
            except Exception:
                self.__bot.reply_to(message, TelebotCmd.ERROR_REP)

    def __process_longer_command(self, chat_id: Union[int, str], command: str):
        if self.__backend.is_interval_mult_enabled():
            self.__process_interval(chat_id, command)
        else:
            self.__bot.send_message(chat_id, TelebotCmd.LONGER_OFF_REP)

    def __process_interval(self, chat_id: Union[int, str], command: str):
        if len(command.split(" ")) == 1:
            self.__bot.send_message(chat_id, TelebotCmd.LONGER_REP)
        else:
            value = command.split(" ")[1]
            self.__process_value(chat_id, value)

    def __process_value(self, chat_id: Union[int, str], value: str):
        try:
            value = int(value)
            if value <= 0:
                raise
            interval = self.__get_interval()
            value += 0 if interval < 0 else interval
            max_interval = self.__backend.get_max_interval()
            value = max_interval if value > max_interval else value
            self.__backend.save_interval(value)
            self.__send_longer_message(chat_id, interval, max_interval, value)
        except Exception:
            self.__bot.send_message(chat_id, TelebotCmd.VALUE_REP)

    def __send_longer_message(
        self, chat_id: Union[int, str], interval: int, max_interval: int, value: int
    ):
        self.__bot.send_message(
            chat_id,
            "{}\n{} ({} is max in configuration){}".format(
                TelebotCmd.OK_REP,
                TelebotCmd.LONGER_MSG.format(value),
                max_interval,
                TelebotCmd.LONGER2_MSG if interval > 0 else "",
            ),
        )

    def __get_interval(self) -> int:
        try:
            interval = self.__backend.get_interval()
        except Exception:
            interval = 0
        return interval

    def __process_command(self, chat_id: Union[int, str], command: str):
        commands = {
            TelebotCmd.CURRENT_CMD: self.__process_current_command,
            TelebotCmd.NEXT_CMD: self.__process_next_command,
            TelebotCmd.WHEN_CMD: self.__process_when_command,
            TelebotCmd.LONGER_CMD.replace(
                TelebotCmd.OPTION_IND, ""
            ): self.__process_longer_command,
            TelebotCmd.PING_CMD: self.__process_ping_command,
            TelebotCmd.ECHO_CMD.replace(
                TelebotCmd.OPTION_IND, ""
            ): self.__process_echo_command,
            TelebotCmd.ORIGINAL_CMD: self.__process_original_command,
            TelebotCmd.START_CMD: self.__process_start_command,
            TelebotCmd.HELP_CMD: self.__process_start_command,
            TelebotCmd.STATUS_CMD: self.__process_status_command,
            TelebotCmd.REBOOT_CMD: self.__process_reboot_command,
        }

        cmd = commands.get(command.split(" ")[0], self.__process_unknown_command)
        cmd.__call__(chat_id, command)

    def __process_ping_command(self, chat_id: Union[int, str], command: str):
        return self.__bot.send_message(chat_id, TelebotCmd.PING_REP)

    def __process_current_command(self, chat_id: Union[int, str], command: str):
        self.__bot.send_chat_action(chat_id, TelebotCmd.UPLOAD_PHOTO_TAG)
        if self.__backend.get_current_file():
            self.__bot.send_photo(
                chat_id,
                open(
                    self.__backend.get_current_file(),
                    TelebotCmd.UPLOAD_PHOTO_PERM_TAG,
                ),
            )
        else:
            self.__bot.send_message(chat_id, TelebotCmd.ERROR_REP)

    def __process_next_command(self, chat_id: Union[int, str], command: str):
        if self.__backend.pid_file_exists():
            self.__bot.send_message(chat_id, TelebotCmd.PROGRESS_REP)
        else:
            self.__backend.fire_event()
            self.__bot.send_message(chat_id, TelebotCmd.OK_REP)

    def __process_when_command(self, chat_id: Union[int, str], command: str):
        self.__bot.send_message(
            chat_id,
            f"{TelebotCmd.NEXT_UPDATE_MSG}\n{self.__backend.get_next_time()}",
        )

    def __process_echo_command(self, chat_id: Union[int, str], command: str):
        if len(command.split(" ")) == 1:
            self.__bot.send_message(chat_id, TelebotCmd.ECHO_REP)
        else:
            self.__bot.send_message(chat_id, " ".join(command.split()[1:]))

    def __process_original_command(self, chat_id: Union[int, str], command: str):
        if self.__backend.get_original_file():
            self.__bot.send_chat_action(chat_id, TelebotCmd.UPLOAD_PHOTO_TAG)
            self.__bot.send_photo(
                chat_id,
                open(
                    self.__backend.get_original_file(),
                    TelebotCmd.UPLOAD_PHOTO_PERM_TAG,
                ),
            )
        else:
            self.__bot.send_message(chat_id, TelebotCmd.ERROR_REP)

    def __process_start_command(self, chat_id: Union[int, str], command: str):
        self.__bot.send_message(
            chat_id,
            "*{}*\n\n{}\n{}\n\n{}\n\n{}".format(
                TelebotCmd.HELLO_MSG,
                TelebotCmd.COMMANDS_MSG,
                TelebotCmd.DESCRIPTIONS,
                TelebotCmd.UPLOAD_MSG,
                TelebotCmd.ALL,
            ),
        )

    def __process_status_command(self, chat_id: Union[int, str], command: str):
        result = (
            self.__backend.start_system_command(self.__STATUS_OS_CMD)
            if self.__backend.is_metric()
            else self.__backend.start_system_command(self.__STATUS_OS_CMD_F)
        )
        if result:
            self.__bot.send_message(chat_id, result)
        else:
            self.__bot.send_message(chat_id, TelebotCmd.ERROR_REP)

    def __process_reboot_command(self, chat_id: Union[int, str], command: str):
        self.__bot.send_message(chat_id, TelebotCmd.OK_REP)
        self.__backend.reboot()

    def __process_unknown_command(self, chat_id: Union[int, str], command: str):
        self.__bot.send_message(chat_id, TelebotCmd.UNKNOWN_REP)
