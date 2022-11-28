class TelebotCmd:

    OPTION_IND = " #"

    START_CMD = "/start"
    HELP_CMD = "/help"
    PING_CMD = "/ping"
    ECHO_CMD = "/echo" + OPTION_IND
    STATUS_CMD = "/status"
    REBOOT_CMD = "/reboot"
    WHEN_CMD = "/when"
    NEXT_CMD = "/next"
    CURRENT_CMD = "/current"
    ORIGINAL_CMD = "/original"
    LONGER_CMD = "/longer" + OPTION_IND

    API_CONNECTION_TIMEOUT = "5"
    API_URL = "api.telegram.org"

    OK_REP = "OK"
    PROGRESS_REP = "Frame update already in progress"
    LATER_REP = "Try again later"
    SENDING_REP = "Sending photo to display"
    PING_REP = "Pong"
    ECHO_REP = "What to say? " + ECHO_CMD
    LONGER_REP = "How many times longer? " + LONGER_CMD
    LONGER_OFF_REP = "Interval multiplication is disabled in configuration"
    UNKNOWN_REP = "Unsupported command"
    UNSUPPORTED_REP = "Content type unsupported"
    VALUE_REP = "Invalid number"
    ERROR_REP = "Error"

    HELLO_MSG = "ePiframe (e-Paper RPi Google Photos frame) Telegram bot"
    UPLOAD_MSG = "Upload photo to display it on frame"
    COMMANDS_MSG = "Commands:"
    NEXT_UPDATE_MSG = "Next update:"
    LONGER_MSG = "Will be displayed {} time(s) longer"
    LONGER2_MSG = "\nMultiplication sum up if already set"

    ALL = "-".join([k for k in locals().values() if "/" in k and "?" not in k])

    UPLOAD_PHOTO_TAG = "upload_photo"
    UPLOAD_PHOTO_FILEID_TAG = "FILEID"
    UPLOAD_PHOTO_PERM_TAG = "rb"

    DOWNLOAD_PHOTO_EXT = ".jpg"
    DOWNLOAD_PHOTO_PERM_TAG = "wb"

    TG_PARSE_MODE = "MARKDOWN"

    PHOTO_TAG = "photo"
    TEXT_TAG = "text"

    DESC = {
        START_CMD.replace("/", ""): "Show help",
        HELP_CMD.replace("/", ""): "Show help",
        PING_CMD.replace("/", ""): "Ping frame",
        ECHO_CMD.replace("/", "").replace(OPTION_IND, ""): "Say # text",
        STATUS_CMD.replace("/", ""): "Show frame status",
        REBOOT_CMD.replace("/", ""): "Reboot frame",
        WHEN_CMD.replace("/", ""): "Show next update time",
        NEXT_CMD.replace("/", ""): "Trigger frame update",
        CURRENT_CMD.replace("/", ""): "Show current photo",
        ORIGINAL_CMD.replace("/", ""): "Show current original photo",
        LONGER_CMD.replace("/", "").replace(
            OPTION_IND, ""
        ): "Display current photo # times longer",
    }

    DESCRIPTIONS = "\n".join(
        "_{}_ - {}".format(key, value) for key, value in DESC.items()
    )
