import os.path
from unittest.mock import patch
import pytest
import telebot
from starlette import status
from misc.telebotcmd import TelebotCmd
from modules.telebotmanager import TelebotManager
from tests.helpers.backend_manager import MockedBackendManager
from tests.helpers.bot import MockedBot, MockedBotFail
from tests.helpers.capturing import Capturing
from tests.helpers.helpers import remove_file, not_raises
from tests.helpers.message import (
    MockedChat,
    MockedMessage,
    MockedPhotoId,
    MockedPhotoPath,
)


def test_init(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot):
        TelebotManager(backend)

    assert output == normal_response


def test_init_fail(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_404_NOT_FOUND)
    backend = MockedBackendManager()
    with patch.object(telebot, "TeleBot", MockedBotFail), pytest.raises(Warning) as warning:
        TelebotManager(backend)

    assert warning
    assert str(warning.value) == 'This is exception'


def test_start(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot):
        TelebotManager(backend).start()

    assert output == normal_response + ["infinity_polling"]


def test_message_unsupported(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(content_type="rubbish", text="text", chat=MockedChat(1))
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "send_message Content type unsupported to 1",
    ]


def test_message_unknown_command(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG, text="rubbish", chat=MockedChat(1)
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "send_message Unsupported command to 1",
    ]


def test_message_unknown_id(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.HELP_CMD,
            chat=MockedChat(5),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response


def test_message_ping(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.PING_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "send_message Pong to 1",
    ]


def test_message_help(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.HELP_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == help_response


def test_message_start(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.START_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == help_response


def test_message_echo_empty(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.ECHO_CMD.replace(TelebotCmd.OPTION_IND, ""),
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "send_message What to say? /echo # to 1",
    ]


def test_message_echo(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=f"{TelebotCmd.ECHO_CMD.replace(TelebotCmd.OPTION_IND, '')} THIS IS ECHO",
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "send_message THIS IS ECHO to 1",
    ]


def test_message_reboot(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.REBOOT_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "send_message OK to 1",
        "reboot",
    ]


def test_message_next_nok(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_pid(True)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.NEXT_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "pid_file_exists",
        "send_message Frame update already in progress to 1",
    ]


def test_message_next_ok(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_pid(False)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.NEXT_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "pid_file_exists",
        "fire_event",
        "send_message OK to 1",
    ]


def test_message_current(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.CURRENT_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "send_chat_action upload_photo to 1",
        "get_current_file",
        "get_current_file",
        "send_photo <_io.BufferedReader name='tests/assets/waveshare.bmp'> to 1",
    ]


def test_message_original(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.ORIGINAL_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "get_original_file",
        "send_chat_action upload_photo to 1",
        "get_original_file",
        "send_photo <_io.BufferedReader name='tests/assets/waveshare.bmp'> to 1",
    ]


def test_message_status_metric_nok(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_metric(True)
    backend.set_cmd(None)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.STATUS_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "is_metric",
        "start_system_command",
        '/usr/bin/free --mega -t | /usr/bin/awk \'{print (NR==1?"Type":""), $1, $2, $3,(NR==1?"":$4)}\' | column '
        "-t | /bin/sed 's/ \\+/ /g' && /usr/bin/uptime | /bin/sed 's/ \\+/ /g' | /bin/sed 's/^ //g' && vcgencmd "
        "measure_temp",
        "send_message Error to 1",
    ]


def test_message_status_non_metric(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_metric(False)
    backend.set_cmd("cmd_response")
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.STATUS_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "is_metric",
        "start_system_command",
        '/usr/bin/free --mega -t | /usr/bin/awk \'{print (NR==1?"Type":""), $1, $2, $3,(NR==1?"":$4)}\' | column -t | '
        "/bin/sed 's/ \\+/ /g' && /usr/bin/uptime | /bin/sed 's/ \\+/ /g' | /bin/sed 's/^ //g' && echo "
        '"temp="$(awk "BEGIN {print `vcgencmd measure_temp | egrep -o \'[0-9]*\\.[0-9]*\'`*1.8+32}")"\'F"',
        "send_message cmd_response to 1",
    ]


def test_message_status_metric(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_metric(True)
    backend.set_cmd("cmd_response")
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.STATUS_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "is_metric",
        "start_system_command",
        '/usr/bin/free --mega -t | /usr/bin/awk \'{print (NR==1?"Type":""), $1, $2, $3,(NR==1?"":$4)}\' | column '
        "-t | /bin/sed 's/ \\+/ /g' && /usr/bin/uptime | /bin/sed 's/ \\+/ /g' | /bin/sed 's/^ //g' && vcgencmd "
        "measure_temp",
        "send_message cmd_response to 1",
    ]


def test_message_when(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.WHEN_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "get_next_time",
        "send_message Next update:",
        "next_time to 1",
    ]


def test_message_longer_wrong(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_max_interval(5)
    backend.set_interval(1)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.LONGER_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "is_interval_mult_enabled",
        "send_message Invalid number to 1",
    ]


def test_message_longer_off(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_max_interval(5)
    backend.set_interval(1)
    backend.set_interval_mult_enabled(False)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=TelebotCmd.LONGER_CMD,
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "is_interval_mult_enabled",
        "send_message Interval multiplication is disabled in configuration to 1",
    ]


def test_message_longer_minus(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_max_interval(5)
    backend.set_interval(1)
    backend.set_interval_mult_enabled(True)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=f"{TelebotCmd.LONGER_CMD.replace(TelebotCmd.OPTION_IND, '')} -1",
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "is_interval_mult_enabled",
        "send_message Invalid number to 1",
    ]


def test_message_longer_max(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_max_interval(5)
    backend.set_interval(0)
    backend.set_interval_mult_enabled(True)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=f"{TelebotCmd.LONGER_CMD.replace(TelebotCmd.OPTION_IND, '')} 7",
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "is_interval_mult_enabled",
        "get_interval",
        "get_max_interval",
        "save_interval",
        "5",
        "send_message OK",
        "Will be displayed 5 time(s) longer (5 is max in configuration) to 1",
    ]


def test_message_longer_sum(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_max_interval(5)
    backend.set_interval(1)
    backend.set_interval_mult_enabled(True)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=f"{TelebotCmd.LONGER_CMD.replace(TelebotCmd.OPTION_IND, '')} 1",
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "is_interval_mult_enabled",
        "get_interval",
        "get_max_interval",
        "save_interval",
        "2",
        "send_message OK",
        "Will be displayed 2 time(s) longer (5 is max in configuration)",
        "Multiplication sum up if already set to 1",
    ]


def test_message_longer_ok(requests_mocker):
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_max_interval(5)
    backend.set_interval(0)
    backend.set_interval_mult_enabled(True)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.TEXT_TAG,
            text=f"{TelebotCmd.LONGER_CMD.replace(TelebotCmd.OPTION_IND, '')} 1",
            chat=MockedChat(1),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "is_interval_mult_enabled",
        "get_interval",
        "get_max_interval",
        "save_interval",
        "1",
        "send_message OK",
        "Will be displayed 1 time(s) longer (5 is max in configuration) to 1",
    ]


def test_message_photo(requests_mocker):
    file_name = "test_upload_file.jpg"
    file_content = b"12345"
    remove_file(file_name)
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_pid(False)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.PHOTO_TAG,
            text="file_content",
            chat=MockedChat(1),
            photo_id=MockedPhotoId(photo_info=MockedPhotoPath(file_content)),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "pid_file_exists",
        "get_file",
        "download_file",
        "get_download_file",
        "refresh_frame",
        "reply_to Sending photo to display to 1",
    ]
    assert os.path.exists(file_name)
    with open(file_name, "rb") as file:
        assert file.read() == file_content

    os.remove(file_name)


def test_message_photo_nok(requests_mocker):
    file_name = "test_upload_file.jpg"
    file_content = b"12345"
    remove_file(file_name)
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_pid(True)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.PHOTO_TAG,
            text="file_content",
            chat=MockedChat(1),
            photo_id=MockedPhotoId(photo_info=MockedPhotoPath(file_content)),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "pid_file_exists",
        "send_message Frame update already in progress",
        "Try again later to 1",
    ]


def test_message_photo_error(requests_mocker):
    file_name = "test_upload_file.jpg"
    file_content = "rubbish"
    remove_file(file_name)
    requests_mocker.get(url="http://api.telegram.org", status_code=status.HTTP_200_OK)
    backend = MockedBackendManager()
    backend.set_pid(False)
    with Capturing() as output, patch.object(telebot, "TeleBot", MockedBot) as bot:
        msg = MockedMessage(
            content_type=TelebotCmd.PHOTO_TAG,
            text="file_content",
            chat=MockedChat(1),
            photo_id=MockedPhotoId(photo_info=MockedPhotoPath(file_content)),
        )
        TelebotManager(backend)
        bot.handle_messages([msg])

    assert output == chat_response + [
        "pid_file_exists",
        "get_file",
        "download_file",
        "get_download_file",
        "reply_to Error to 1",
    ]
    remove_file(file_name)


normal_response = [
    "refresh",
    "get_token",
    "bot_init token='token' parse_mode='MARKDOWN'",
    "get_me",
    "set_update_listener __handle_messages",
    "update_time",
]

chat_response = normal_response + [
    "refresh",
    "get_chat_id",
    "get_chat_id",
]

help_response = chat_response + [
    "send_message *ePiframe (e-Paper RPi Google Photos frame) Telegram bot*",
    "",
    "Commands:",
    "_start_ - Show help",
    "_help_ - Show help",
    "_ping_ - Ping frame",
    "_echo_ - Say # text",
    "_status_ - Show frame status",
    "_reboot_ - Reboot frame",
    "_when_ - Show next update time",
    "_next_ - Trigger frame update",
    "_current_ - Show current photo",
    "_original_ - Show current original photo",
    "_longer_ - Display current photo # times longer",
    "",
    "Upload photo to display it on frame",
    "",
    "/start-/help-/ping-/echo #-/status-/reboot-/when-/next-/current-/original-/longer # to 1",
]
