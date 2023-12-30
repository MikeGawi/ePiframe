from typing import Callable, Optional

listener: Optional[Callable] = None


class MockedBotFail:
    def __init__(self, token, parse_mode):
        pass

    def get_me(self):
        raise Exception("This is exception")


class MockedBot:
    def __init__(self, token, parse_mode):
        print(f"bot_init {token=} {parse_mode=}")

    def send_message(self, chat_id, message):
        print(f"send_message {message} to {chat_id}")

    def set_update_listener(self, listener_local):
        print(f"set_update_listener {listener_local.__name__}")
        global listener
        listener = listener_local

    @classmethod
    def handle_messages(cls, messages):
        listener(messages)

    def send_chat_action(self, chat_id, action):
        print(f"send_chat_action {action} to {chat_id}")

    def send_photo(self, chat_id, photo):
        print(f"send_photo {photo} to {chat_id}")

    def infinity_polling(self):
        print("infinity_polling")

    def download_file(self, file):
        print(f"download_file")
        return file

    def get_file(self, file):
        print(f"get_file")
        return file

    def reply_to(self, message, msg):
        print(f"reply_to {msg} to {message.chat.id}")

    def get_me(self):
        print(f"get_me")
        return "bot"
