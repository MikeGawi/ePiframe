#!/usr/bin/env python3

import json
import sys
import telebot

TOKEN = None
DEBUG = False

print("ePiframe - e-Paper Raspberry Pi Photo Frame - Telegram bot check tool.")
print("This tool will help test Telegram bot for ePiframe.")

if "--help" not in [x.lower() for x in sys.argv]:
    TOKEN = input("Enter token key for Your bot: ")
    print("TOKEN = " + str(TOKEN))
    print(
        "Do You want to see JSON detailed version of messages or just simple notifications?"
    )
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}

    res = None
    while True:
        choice = input("[y/N]? [Default: No] ").lower() or "no"

        if choice in valid:
            res = valid[choice]
            break
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")
    if res:
        DEBUG = True

    try:
        print("Setting up bot...")
        bot = telebot.TeleBot(TOKEN)

        @bot.message_handler(commands=["start", "help"])
        def send_welcome(message):
            print(
                "'{}' message received from chat id {}".format(
                    message.text, message.chat.id
                )
            )
            if DEBUG:
                print(message)
            bot.reply_to(
                message,
                "Hello, I'm ePiframe Telegram bot test tool.\nStart writing something and I will reply.",
            )

        @bot.message_handler(func=lambda message: True)
        def echo_all(message):
            print(
                "'{}' message received from chat id {}".format(
                    message.text, message.chat.id
                )
            )
            if DEBUG:
                print(message)
            bot.reply_to(message, message.text)

        @bot.message_handler(
            content_types=[
                "document",
                "audio",
                "photo",
                "voice",
                "sticker",
                "video_note",
            ]
        )
        def echo_data(message):
            print(
                "Data '{}' received from chat id {}".format(
                    message.content_type, message.chat.id
                )
            )
            if DEBUG:
                print(message)
            bot.reply_to(message, "Received!")

        print("This is Your bot:")
        print(json.dumps(json.loads(bot.get_me().to_json()), indent=2, sort_keys=True))
        print("Success!")
        print("Start writing to Your bot and bot will reply, CTRL+C to quit")
        bot.infinity_polling()
    except Exception as exc:
        print("Error when setting up bot! {}".format(exc))
