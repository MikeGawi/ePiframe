import itertools

class constants:

	EPIFRAME_VERSION = 'v1.8.0'
	EPIFRAME_SECRET = 'ePiframeSecretlyLovesYourPhotos'
	
	#minimal needed python version
	MINIMAL_PYTHON_VERSION = 3

	#config filename
	CONFIG_FILE = 'config.cfg'
	CONFIG_FILE_DEFAULT = 'misc/config.default'
	
	
	#If modifying these scopes, delete the file token.pickle.
	#scopes of Google Photos Service
	SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
	
	SERVICE_NAME = 'photoslibrary'
	SERVICE_VERSION = 'v1'
	
	
	#google photos API specific
	GOOGLE_PHOTOS_PAGESIZE = 50
	GOOGLE_PHOTOS_PAGESIZE_HEADER = 'pageSize'
	GOOGLE_PHOTOS_NEXTTOKENPAGE_HEADER = 'pageToken'
	GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER = 'nextPageToken'
	GOOGLE_PHOTOS_EXCLUDENONAPPCREATEDDATA = False
	
	GOOGLE_PHOTOS_ALBUMS_RESPONSE = 'albums'
	GOOGLE_PHOTOS_ALBUMS_TITLE_HEADER = 'title'
	GOOGLE_PHOTOS_ALBUMS_ID_HEADER = 'id'
	GOOGLE_PHOTOS_ALBUMS_ALBUMID_HEADER = 'albumId'
	GOOGLE_PHOTOS_ALBUMS_MEDIAITEMS_HEADER = 'mediaItems'
	GOOGLE_PHOTOS_ALBUMS_MEDIAMETADATA_HEADER = 'mediaMetadata'
	GOOGLE_PHOTOS_ALBUMS_PHOTO_HEADER = 'photo'
	GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER = 'mimeType'
	GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER = 'creationTime'
	GOOGLE_PHOTOS_ALBUMS_PHOTO_DESCRIPTION_HEADER = 'description'
	GOOGLE_PHOTOS_ALBUMS_PHOTO_BASEURL_HEADER = 'baseUrl'
	GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER = 'id'
	GOOGLE_PHOTOS_ALBUMS_PHOTO_HEIGHT_HEADER = 'height'
	GOOGLE_PHOTOS_ALBUMS_PHOTO_WIDTH_HEADER = 'width'
	GOOGLE_PHOTOS_ALBUMS_PHOTO_GET_DETAILS = '=d'
	
	PHOTOS_SOURCE_LABEL = 'source'
	GOOGLE_PHOTOS_SOURCE = 'Google Photos'
	LOCAL_SOURCE = 'Local'
	
	CHECK_CONNECTION_TIMEOUT = 5
	OK_STATUS_ERRORCODE = 200
	
	
	WEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&units={}&appid={}"
	WEATHER_ICON_MAINTAG = 'weather'
	WEATHER_ICON_POSITION = 0
	WEATHER_ICON_TAG = 'icon'
	
	WEATHER_TEMP_MAINTAG = 'main'
	WEATHER_TEMP_TAG = 'temp'

	
	IMAGE_MIMETYPE_STARTING_STRING = 'image'
	
	#image mime type to extension dictionary
	EXTEN = {
		'image/x-sony-arw' : 'arw',
		'image/x-canon-cr2' : 'cr2',
		'image/x-canon-crw' : 'crw',
		'image/x-kodak-dcr' : 'dcr',
		'image/x-adobe-dng' : 'dng',
		'image/x-epson-erf' : 'erf',
		'image/x-kodak-k25' : 'k25',
		'image/x-kodak-kdc' : 'kdc',
		'image/x-minolta-mrw' : 'mrw',
		'image/x-nikon-nef' : 'nef',
		'image/x-olympus-orf' : 'orf',
		'image/x-pentax-pef' : 'pef',
		'image/x-fuji-raf' : 'raf',
		'image/x-panasonic-raw' : 'raw',
		'image/x-sony-sr2' : 'sr2',
		'image/x-sony-srf' : 'srf',
		'image/x-sigma-x3f' : 'x3f',
		'image/x-dcraw' : 'cr2',
		'image/raw' : 'raw',
		#only the first frame of gif
		'image/gif' : 'gif',
		'image/webp' : 'webp',
		'image/jpeg' : [ 'jpg', 'jpeg', 'jfif', 'pjpeg', 'pjp' ],
		'image/png' : 'png',
		'image/tiff' : [ 'tiff', 'tif' ],
		'image/vnd.microsoft.icon' : 'ico',
		'image/ico' : 'ico',
		'image/icon' : 'ico',
		'image/x-icon' : 'ico',
		'image/bmp' : 'bmp',
		'image/heif' : ['heic', 'heif']
	}
	
	MIME_START = 'image/'
	GIF_EXTENSION = 'gif'
	FIRST_FRAME_GIF = '[0]'
	
	TYPE_TO_EXTENSION = dict((k, v[0] if isinstance(v, list) else v) for k,v in EXTEN.items())
	EXTENSION_TO_TYPE = dict([y for x in [itertools.product(v if isinstance(v, list) else [v],[k]) for k,v in EXTEN.items()] for y in x])
	EXTENSIONS = sum ([ x if isinstance(x, list) else [x] for x in list(EXTEN.values()) ], [])
	
	NOMATCH_INDICATOR_STRING = 'no match'
	
	USERS_DB_FILE = "misc/users.db"
	
	DB_NULL = 'NULL'
	DB_ALL = '*'
	DB_SQL_COL = 'sql'
	DB_NAME_COL = 'name'
	DB_SQLITE_MASTER_TAB = 'sqlite_master'	
	USERS_TABLE_NAME = 'users'
	USERS_TABLE_ID_HEADER = 'id'
	USERS_TABLE_USERNAME_HEADER = 'username'
	USERS_TABLE_HASH_HEADER = 'hash'
	USERS_TABLE_API_HEADER = 'api'
	
	SALTS_TABLE_NAME = 'salts'
	SALTS_TABLE_ID_HEADER = 'id'
	SALTS_TABLE_USERID_HEADER = 'userid'
	SALTS_TABLE_SALT_HEADER = 'salt'
	
	USERS_ACTIONS_TAG = "--------Users management: "
	
	STATS_STEP = 10
