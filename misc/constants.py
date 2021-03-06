class constants:

	#minimal needed python version
	MINIMAL_PYTHON_VERSION = 3

	#config filename
	CONFIG_FILE = 'config.cfg'
	
	
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
	
	
	CHECK_CONNECTION_TIMEOUT = 5
	OK_STATUS_ERRORCODE = 200
	
	
	IMAGE_MIMETYPE_STARTING_STRING = 'image'
	
	#image mime type to extension dictionary
	TYPE_TO_EXTENSION = {
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
		'image/gif' : 'gif[0]',
		'image/webp' : 'webp',
		'image/jpeg' : 'jpg',
		'image/png' : 'png',
		'image/tiff' : 'tiff',
		'image/ico' : 'ico',
		'image/icon' : 'ico',
		'image/x-icon' : 'ico',
		'image/vnd.microsoft.icon' : 'ico',
		'image/bmp' : 'bmp'}	
	
	NOMATCH_INDICATOR_STRING = 'no match'