from epiframe.version import VERSION
from misc.tools import Tools


class Constants:
    # single source of truth: `version` in pyproject.toml
    EPIFRAME_VERSION = VERSION
    EPIFRAME_SECRET = "ePiframeSecretlyLovesYourPhotos"

    # minimal needed python version
    MINIMAL_PYTHON_VERSION = (3, 11)

    # config filename
    CONFIG_FILE = "config.cfg"
    CONFIG_FILE_DEFAULT = "misc/config.default"

    # photo list (DataFrame) column labels, also passed to plugins
    PHOTOS_ID_HEADER = "id"
    PHOTOS_CREATIONTIME_HEADER = "creationTime"
    PHOTOS_SOURCE_LABEL = "source"
    LOCAL_SOURCE = "Local"

    CHECK_CONNECTION_TIMEOUT = 5
    OK_STATUS_ERRORCODE = 200

    WEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&units={}&appid={}"
    WEATHER_ICON_MAINTAG = "weather"
    WEATHER_ICON_POSITION = 0
    WEATHER_ICON_TAG = "icon"

    WEATHER_TEMP_MAINTAG = "main"
    WEATHER_TEMP_TAG = "temp"

    # image mime type to extension dictionary
    EXTEN = {
        "image/x-sony-arw": "arw",
        "image/x-canon-cr2": "cr2",
        "image/x-canon-crw": "crw",
        "image/x-kodak-dcr": "dcr",
        "image/x-adobe-dng": "dng",
        "image/x-epson-erf": "erf",
        "image/x-kodak-k25": "k25",
        "image/x-kodak-kdc": "kdc",
        "image/x-minolta-mrw": "mrw",
        "image/x-nikon-nef": "nef",
        "image/x-olympus-orf": "orf",
        "image/x-pentax-pef": "pef",
        "image/x-fuji-raf": "raf",
        "image/x-panasonic-raw": "raw",
        "image/x-sony-sr2": "sr2",
        "image/x-sony-srf": "srf",
        "image/x-sigma-x3f": "x3f",
        "image/x-dcraw": "cr2",
        "image/raw": "raw",
        # only the first frame of gif
        "image/gif": "gif",
        "image/webp": "webp",
        "image/jpeg": ["jpg", "jpeg", "jfif", "pjpeg", "pjp"],
        "image/png": "png",
        "image/tiff": ["tiff", "tif"],
        "image/vnd.microsoft.icon": "ico",
        "image/ico": "ico",
        "image/icon": "ico",
        "image/x-icon": "ico",
        "image/bmp": "bmp",
        "image/heif": ["heic", "heif"],
    }

    MIME_START = "image/"
    GIF_EXTENSION = "gif"
    FIRST_FRAME_GIF = "[0]"

    TYPE_TO_EXTENSION = Tools.get_type_to_extension(EXTEN)
    EXTENSION_TO_TYPE = Tools.get_extension_to_type(EXTEN)
    EXTENSIONS = Tools.get_extensions(list(EXTEN.values()))

    NOMATCH_INDICATOR_STRING = "no match"

    USERS_DB_FILE = "misc/users.db"

    DB_NULL = "NULL"
    DB_ALL = "*"
    DB_SQL_COL = "sql"
    DB_NAME_COL = "name"
    DB_SQLITE_MASTER_TAB = "sqlite_master"
    USERS_TABLE_NAME = "users"
    USERS_TABLE_ID_HEADER = "id"
    USERS_TABLE_USERNAME_HEADER = "username"
    USERS_TABLE_HASH_HEADER = "hash"
    USERS_TABLE_API_HEADER = "api"

    SALTS_TABLE_NAME = "salts"
    SALTS_TABLE_ID_HEADER = "id"
    SALTS_TABLE_USERID_HEADER = "userid"
    SALTS_TABLE_SALT_HEADER = "salt"

    USERS_ACTIONS_TAG = "--------Users management: "

    STATS_STEP = 10

    COLOR_BW = "BW"
    COLOR_BWY = "BW+Yellow"
    COLOR_BWR = "BW+Red"
    COLOR_4C = "4 colors"
    COLOR_7C = "7 colors"
    COLOR_OTHER = "Other"
    COLOR_VALUES = [
        COLOR_BW,
        COLOR_BWR,
        COLOR_BWY,
        COLOR_4C,
        COLOR_7C,
        COLOR_OTHER,
    ]

    BACK_WHITE = "white"
    BACK_BLACK = "black"
    BACK_PHOTO = "photo"
    BACK_CROP = "crop"
