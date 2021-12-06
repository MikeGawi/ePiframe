# ePiframe API

## General

General API command:

```
<ePiframe IP with port>/api/<command>?api_key=<api key value>[&<optional parameter>=<optional value>&...]
```
e.g.: 

```
192.168.0.123:8080/api/get_image?api_key=1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p&original&thumb
```

**_NOTE_** - When there are no users in the database API key can be ommited but then everyone can control the frame.

**_NOTE_** - Header authentication (basic) with API key (Base64 encoding allowed) is also possible.

## Get Image

| Command | Type | Parameters |
|--|--|--|
| ```/api/get_image``` | GET | <ul><li>```thumb``` - show thumbnail</li><li>```original``` - show original photo</li></ul> |

Returns image of displayed photo (by default). Can display thumbnail with ```thumb``` parameter and original photo with ```original```.

**Examples:**
* ```/api/get_image?original&thumb``` - original photo thumbnail
* ```/api/get_image?original``` - original photo
* ```/api/get_image?thumb``` - displayed photo thumbnail
* ```/api/get_image``` - displayed photo

**Returns:**
Image, MIME type according to the image type.

## Get Status

| Command | Type | Parameters |
|--|--|--|
| ```/api/get_status``` | GET | None |

Returns status of ePiframe in JSON format.

**Examples:**
* ```/api/get_status```

**Returns:**

JSON format:
* ```converted``` - converted/displayed photo modification timestamp (to keep track of photo change)
* ```original``` - original photo modification timestamp (to keep track of photo change)
* ```load``` - current OS load, 3 float values (1, 5, 15 minutes), space separated
* ```mem``` - allocated memory percentage status (with % sign at the end)
* ```service``` - ePiframe service status: _Running_ or _Not running!_
* ```state``` - ePiframe state: _Idle_ or _Busy_
* ```temp``` - current core temperature (with degree sign at the end)
* ```update``` - date and time of the next frame update in format: _DD.MM.YYYY_ (not visible when the same day) _at hh:mm:ss_ (next line) _in d days m mins s secs_ (days not visible when less than one day)
* ```uptime``` - device running time
* ```version``` - version of ePiframe

e.g.

```
{
   "converted":1638394810.5973678,
   "load":"0.8 0.11 0.09",
   "mem":"21%",
   "original":1638394806.737437,
   "service":"Running",
   "state":"Idle",
   "temp":"32.6\u00b0C",
   "update":"at 22:54:37\nin 0 mins 46 secs",
   "uptime":"up 1 week, 1 day, 14 hours, 52 minutes",
   "version":"v0.9.7 beta"
}
```

## Get Log

| Command | Type | Parameters |
|--|--|--|
| ```/api/get_log``` | GET | None |

Returns ePiframe log file for current day.

**Examples:**
* ```/api/get_log```

**Returns:**

Real time ePiframe log file in text format with line breaks

## Action

| Command | Type | Parameters |
|--|--|--|
| ```/api/action=<action>``` | GET | where ```<action>``` should be one of</br><ul><li>```next``` - trigger photo change</li><li>```restart``` - restart ePiframe service</li><li>```reboot``` - reboot ePiframe</li><li>```poweroff``` - power off ePiframe</li></ul> |

Performs action on ePiframe. **No confirmation is needed!**

**Examples:**
* ```/api/action=next``` - show next photo
* ```/api/action=reboot``` - reboot ePiframe

etc.

**Returns:**

Response or error in JSON format.

```
{ "status":"OK" }
```

**Errors:**

```
{ "error":"<error message>" }
```

* ```Action Unknown!``` - when action value is unknown
* ```No Action!``` - when no action value was provided

## Upload Photo

| Command | Type | Parameters |
|--|--|--|
| ```/api/upload_photo``` | POST | None |

Upload photo target that will automatically convert and display uploaded image. The next update time will be resetted.

**Examples:**
* ```/api/upload_photo```

**Returns:**

Response or error in JSON format.

```
{ "status":"OK" }
```

**Errors:**

```
{ "error":"<error message>" }
```

* ```File unknown!``` - when uploaded photo MIME type can't be recognized

**_HINT_** ```curl -F "file=@photo.jpg" "http://<IP>:<PORT>/api/upload_photo?api_key=<API key value>"```