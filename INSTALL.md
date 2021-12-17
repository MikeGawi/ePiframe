# ePiframe Documentation

## Table of Contents
<!--ts-->
   * [Installation](#installation)
      * [Automatic](#automatic)
      * [Manual](#manual)
      * [Next steps](#next-steps)
	  	* [Activate](#activate)
			* [Activate from ePiframe device](#activate-from-epiframe-device)
			* [Activate from other device](#activate-from-other-device)
      	* [Weather Stamp](#weather-stamp)
      	* [Telegram Bot](#telegram-bot)
      	* [Web User Interface](#web-user-interface)
			* [WebUI Users](#webui-users)
			* [API](#api)
   * [Update](#update)
      * [Update Automatically](#update-automatically)
      * [Update Manually](#update-manually)
   * [Uninstalling](#uninstalling)
      * [Automatic](#automatic-1)
      * [Manual](#manual-1)
      * [Next steps](#next-steps-1)
   * [Configuration](#configuration)
   * [Command line](#command-line)
   * [Debugging](#debugging)
   * [Service control](#service-control)
<!--te-->

## Installation

* [Install Raspberry Pi OS](https://www.raspberrypi.org/documentation/installation/installing-images/README.md) formerly known as Raspbian. Lite version is supported
* [Setup network connection](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md)
* [Enable SSH](https://www.raspberrypi.org/documentation/remote-access/ssh/) - chapter *3. Enable SSH on a headless Raspberry Pi (add file to SD card on another machine)*
* [Assemble Raspberry Pi and power it](https://projects.raspberrypi.org/en/projects/raspberry-pi-setting-up)
* [Find Raspberry Pi IP address](https://www.raspberrypi.org/documentation/remote-access/ip-address.md)
* [Log in with SSH](https://www.raspberrypi.org/documentation/remote-access/ssh/) - chapter *4. Set up your client*
* [Configure Raspberry Pi](https://www.raspberrypi.org/documentation/configuration/raspi-config.md)
* [Update Raspberry Pi](https://www.raspberrypi.org/documentation/raspbian/updating.md)

### Automatic

Use *install.sh* script:
```
wget https://raw.githubusercontent.com/MikeGawi/ePiframe/master/install.sh -O install_now.sh
chmod +x install_now.sh
./install_now.sh
rm install_now.sh
```
Move to [next steps](#next-steps)

### Manual

<details>
<summary>Click to expand</summary>

* Install APTs:
```
sudo apt-get install imagemagick webp ufraw-batch libatlas-base-dev wiringpi python3 python3-pip
```
* Install PIPs:
```
sudo -H pip3 install requests python-dateutil configparser pandas RPi.GPIO spidev image pillow pyTelegramBotAPI flask flask-wtf
sudo -H pip3 install -I --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```
* Download ePiframe ZIP file (or use [git](https://github.com/MikeGawi/ePiframe)) and extract it to *path*:
```
cd <path>
wget -q https://github.com/MikeGawi/ePiframe/archive/master.zip -O ePiframe.zip
unzip -q ePiframe.zip
cp -r ePiframe-master/* .
rm -r ePiframe-master/ ePiframe.zip
chmod +x *.py
```
* Download Waveshare ZIP file (or use [git](https://github.com/waveshare/e-Paper)) and extract all RasPi Waveshare display libraries to *lib* inside *path*:
```
cd <path>
wget -q https://github.com/waveshare/e-Paper/archive/master.zip -O waveshare.zip
unzip -q waveshare.zip
cp -r e-Paper-master/RaspberryPi_JetsonNano/python/lib .
rm -r e-Paper-master/ waveshare.zip
sudo chown -R pi ..
```
* Enable SPI support:
```
sudo raspi-config
```
Go to *Advanced Options -> SPI* and choose *Yes* for both questions then select *Finish* to exit *raspi-config*

Reboot ePiframe device to start enabled SPI support.

* Install ePiframe service
  * replace paths
	```
	sed 's/EPIEPIEPI/'$(pwd | sed 's_/_\\/_g')'\//g' misc/ePiframe.service.org > ePiframe.service
	```
  * enable service
	```
	sudo systemctl enable `pwd`/ePiframe.service
	```

Move to [next steps](#next-steps)

</details>

## Next steps

* Connect display to Raspberry Pi
* [Activate](#activate) ePiframe token and credentials for using Google Photos API
* Configure ePiframe with [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) file inside installation path
* Check configuration with ```./ePiframe.py --check-config```
* Do a test with ```./ePiframe.py --test``` without sending photo to display
* Do a test with ```./ePiframe.py --test-display``` to test display
* Reboot ePiframe device to automatically run frame
* Enjoy your ePiframe!

## Activate

ePiframe needs to have credentials and access token to access Google Photos of Google accout in an unsupervised way. For this You need to activate Google Photos API for the account used by ePiframe and configure application in Google Cloud Console.

Usually You will be asked to do that after [automatic installation](#automatic) and there are two ways to do that: with the ePiframe Activation Tool website with visual guide or in the console but if not already done, here are the steps needed on Google Cloud Console:

<details>
<summary>Click to expand</summary>

* Create new or use an existing Google account for **ePiframe** and log in. 
* Go to [Google Cloud Console](https://console.cloud.google.com/).
* Click on *Select a project*.
* Click on *NEW PROJECT* 
* Put *ePiframe* in the *Project name* field and click *CREATE* You have created **ePiframe** project! 
* Now select *ePiframe* project by clicking on it 
* Click *APIs & Services* in the panel on the left hand side and pick *Library* 
* Search for *Photos* and then click *Photos Library API* 
* Click on *ENABLE*. Now You have given Your **ePiframe** project support to Google Photos API 
* Go to *Credentials* in the panel on the left hand side under *APIs & Services* and click *CONFIGURE CONSENT SCREEN* 
* Choose *External* and click *CREATE* 
* Put *ePiframe* in the *App name* field, type Google email used for Your **ePiframe** where necessary, scroll down and click on *SAVE AND CONTINUE* three times until You get to **Summary**. 
* Click *BACK TO DASHBOARD*. Your application consent screen is ready! 
* Click on *PUBLISH APP* in *Oauth consent screen* section under *APIs & Services* to publish Your application 
* Click on *+CREATE CREDENTIALS* and choose *OAuth client ID* 
* Pick *Desktop app* as *Application type* and put *ePiframe* in the *Name* field. Click *CREATE* 
* You have created OAuth client for Your **ePiframe**! Click on *DOWNLOAD JSON* to download JSON formatted credentials file 
* You can always get it from the *Credentials* dashboard by clicking download icon in *Actions* column of Your desired Client ID 

Now go to next steps for ePiframe activation.

</details>

#### Activate from ePiframe device

<img align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/assets/actweb.png" width="400">

If not already done during [automatic installation](#automatic) start the ePiframe Activation Tool with `./install.sh --activate` command in the main path and follow the instructions.

You can choose if You want to activate on website with visual guide or in the console.

#### Activate from other device

<img align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/assets/actcon.png" width="400">

It is possible to activate the access to Google Photos API for ePiframe on any other device with Python 3.

You need to have these prerequisites installed:
```
sudo -H pip3 install -I --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```
Then:
* ```wget https://raw.githubusercontent.com/MikeGawi/ePiframe/master/activate.py && chmod +x activate.py && ./activate.py```
* Only console mode is possible as there are too many dependencies needed for website mode
* Script will produce *token.pickle* and *credentials.json* files
* Copy these files to ePiframe device inside installation path (using [*rsync*](https://ss64.com/bash/rsync.html) or [*scp*](https://ss64.com/bash/scp.html))

### Weather Stamp

<img align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/assets/weather.gif" width="400">

ePiframe can show  weather stamp (icon + temperature) in defined frame corner, color and size. The weather information is taken from [OpenWeather](https://openweathermap.org/api) according to [Maps.ie](https://www.maps.ie/coordinates.html) coordinates. You need to set up some values in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) file.

To get the needed values:
* Create an account in [Open Weather Map API](https://home.openweathermap.org/users/sign_up)
* Sign in to OpenWeather account
* Go to _Profile->My API Keys_, copy the generated API key and put it in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file under ```[Weather]->apikey``` value
* Now go to [Maps.ie](https://www.maps.ie/coordinates.html)
* Find desired GPS coordinates for the weather information by location, ZIP code or simply click it on the map
* Copy Longtitude and Lattitude values and put them in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file under ```[Weather]->lon``` and ```[Weather]->lat``` values
* Enable ```[Weather]->show_weather=1``` flag in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file and set other weather stamp parameters like size, position and color
* Now the weather stamp will appear on the photo after next frame update

**_NOTE_** - To troubleshoot OpenWeather API key issues and connectivity check the [tools/testWeatherAPI.py](https://github.com/MikeGawi/ePiframe/blob/master/tools/testWeatherAPI.py) tool.

### Telegram Bot

<img align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/assets/tg.gif" width="200">

ePiframe can optionally be controlled by a Telegram Bot and expose some basic commands to control the frame. Implementation uses [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) and is a persistent thread running when ePiframe is online. You need to set up some values in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) file.

To get the needed values:
* Create a [Telegram](https://telegram.org/) account on any device
* Talk to [Bot Father](https://telegram.me/BotFather) - father of all bots
* Create a new bot with ```/newbot``` command, set name ```ePiframeBot``` and username ```ePiframeBot``` (add some numbers at the end to make it unique or use other username)
* BotFather will present _HTTP API token_, copy it and put in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file under ```[Telegram bot]->token```
* You can set other bot options with _BotFather_ (i.e. description, image, if bot can be in group, etc.) but set up the possible commands by ```/mybots``` command, choose the _ePiframeBot_, then click _Edit Bot->Edit Commands_ and paste:
	```
	start - Show help
	help - Show help
	ping - Ping frame
	echo - Say # text
	status - Show frame status
	reboot - Reboot frame
	when - Show next update time
	next - Trigger frame update
	current - Show current photo
	original - Show current original photo
	longer - Display current photo # times longer	
	```
	Now the commands will be visible in the Telegram App as a list.
* Enable ```[Telegram bot]->use_telebot=1``` flag in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file
* [Restart](#service-control) ePiframe service and from now on sending commands to ePiframe bot (search in Telegram App for username set in _BotFather_) will control the frame

**_NOTE_** - To troubleshoot Telegram bot token key issues and connectivity check the [tools/testTelegramBot.py](https://github.com/MikeGawi/ePiframe/blob/master/tools/testTelegramBot.py) tool.

**_❗ IMPORTANT ❗_** - You can limit number of users/groups that can control the ePiframe bot (all bots are public and accessible by others!) by setting ```[Telegram bot]->chat_id``` list in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) - that will allow only the defined chat ids to control bot. To get chat id use the tool above.

### Web User Interface

<img align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/assets/web.gif" width="400">

ePiframe can optionally be controlled by a web user interface under defined network port. Implementation uses [Flask](https://flask.palletsprojects.com/) and is a persistent thread running when ePiframe is online. You need to set up some values in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) file.

To configure:
* Enable ```[Web interface]->use_web=1``` flag in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file
* Set IP address in ```[Web interface]->web_host``` option in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file. Set ```0.0.0.0``` for hosting on all possible public IP addresses.
* Set port in ```[Web interface]->web_port``` option in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file. Set port value between 1-65535 that You want to have WebUI hosted under. Sometimes it is needed to [have this port open in the Firewall](https://pimylifeup.com/raspberry-pi-ufw/).
* [Restart](#service-control) ePiframe service and from now on under given IP address and port (*http://[ip]:[port]/*), You'll be able to control the frame.

**_NOTE_** - To troubleshoot WebUI IP, port issues and connectivity check the [tools/testWebUI.py](https://github.com/MikeGawi/ePiframe/blob/master/tools/testWebUI.py) tool.

**_NOTE_** - Keep in mind that any port number below 5000 needs root privilleges to be possible to assign.

#### WebUI Users

It is possible to secure Web User Interface of ePiframe with usernames and passwords. You need to create an user (multiple possible) with ```./ePiframe.py --users``` [command](#command-line).

**_NOTE_** - Keep in mind that even one account added to the ePiframe users will block the Web Interface until successfull authentication. Deleting all users will unblock it for everyone.

#### API

It is possible to control ePiframe from a simple API and even secure it with authentication keys. It is not needed to have the key but in case You need to secure API calls create an user (multiple possible) with ```./ePiframe.py --users``` [command](#command-line). Every user has an API key generated automatically which You then get in the same command tool.

**_NOTE_** - Keep in mind that even one account added to the ePiframe users will block the Web Interface until successfull authentication or API key authentication. Deleting all users will unblock it for everyone.

**_NOTE_** - The users database created in previous ePiframe versions doesn't need to be updated, recreated or modified as it will be updated automatically to the newest version and with no data lost. Old users will have their keys generated automatically.

[ePiframe API](https://github.com/MikeGawi/ePiframe/blob/master/docs/API.md)

## Update
### Update Automatically

Since [ePiframe v0.9.6 beta](https://github.com/MikeGawi/ePiframe/releases/tag/v0.9.6-beta) [#10](https://github.com/MikeGawi/ePiframe/issues/10)

Use *install.sh* script:
```
cd [Your ePiframe path]
wget https://raw.githubusercontent.com/MikeGawi/ePiframe/master/install.sh -O install_update.sh
chmod +x install_update.sh
./install_update.sh --update
rm install_update.sh
```

**_NOTE_** - Since [ePiframe v0.9.6 beta](https://github.com/MikeGawi/ePiframe/releases/tag/v0.9.6-beta) [#8](https://github.com/MikeGawi/ePiframe/issues/8) ePiframe has a [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file backward compatibility. That means that any existing configuration file can be used in the newer version of ePiframe and non-existing configuration properties will be set to default values.

### Update Manually

<details>
<summary>Click to expand</summary>
	
* Save Your [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file in other location.
* Save Your *credentials.json* file in other location. It may be under different name specified in the ```[Credentials]->cred_file``` entry in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file.
* Save Your *token.pickle* file in other location. It may be under different name specified in the ```[Credentials]->pickle_file``` entry in the [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file.
* Save Your *misc/users.db* file in other location.

</details>

[Uninstall](#uninstalling), [install](#installation) ePiframe again and copy back all files from previous steps.

**_NOTE_** - Since [ePiframe v0.9.6 beta](https://github.com/MikeGawi/ePiframe/releases/tag/v0.9.6-beta) [#8](https://github.com/MikeGawi/ePiframe/issues/8) ePiframe has a [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) configuration file backward compatibility. That means that any existing configuration file can be used in the newer version of ePiframe and non-existing configuration properties will be set to default values.

## Uninstalling
### Automatic

Use *install.sh* script:
```
cd [Your ePiframe path]
./install.sh --uninstall
```
Move to [next steps](#next-steps-1)

### Manual

<details>
<summary>Click to expand</summary>

```
sudo systemctl stop ePiframe.service
sudo systemctl disable ePiframe.service
```
Move to [next steps](#next-steps-1)

</details>

### Next steps

* Whole ePiframe code is in the directory where it was installed so delete it if not needed
* All dependecies installed for ePiframe are [here](#manual)

## Configuration

* Configure ePiframe with [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) file inside installation path. Just one file and with lots of descriptions. The service restart is needed only for all service related features (i.e. WebUI, Telegram Bot, etc.) and it's indicated in the config file, the other settings are loaded per run/refresh
* **__ALWAYS__** check configuration with ```./ePiframe.py --check-config```

**_NOTE_** - Interval multiplication option which can prolong the photo display time, uses *hot word* (i.e. *hotword #*, where # is interval multiplicator value) in the **photo description** field. You can change this attribute only for your own photos or for all *only* when you're an owner of the album. It's description in the photo information panel not photo comment. Comments are inacessible from Google Photos level (unfortunately) as [are stored in different database](https://support.google.com/photos/thread/3272278?hl=en) 😟

## Command line

Main ePiframe script *ePiframe.py* is written in Python and can work from CLI, the ePiframe service daemon *ePiframe_service.py* just runs it without any arguments. But here are additional available commands helpful for tests and debugging:

Syntax: ```ePiframe.py [option]```
* ```--check-config``` - checks configuration file syntax
* ```--test``` - tests whole chain: credentials, pickle file and downloads photo **but without** sending it to the display. Used to test configuration, photo filtering, etc
* ```--test-display [file]``` - displays the photo ```file``` on attached display with current ePiframe configuration. If no file is provided the ```photo_convert_filename``` from the configuration is used. __Only__ converted photos should be put on display! Use ```--test-convert``` for that
* ```--test-convert [file]``` - converts the photo ```file``` to configured ```photo_convert_filename``` with current ePiframe configuration. If no file is provided the ```photo_download_name``` from the configuration is used
* ```--no-skip``` - like ```--test``` but is not skipping to another photo, not marking photo as showed, etc.
* ```--users``` - manage users for the WebUI: add, change passwords, delete, etc.
* ```--help``` - show help

**_NOTE_** - To not interfere with working ePiframe thread it's better to [stop](#service-control) the service before using commands.

## Debugging

When ePiframe is not refreshing, it's a tragedy indeed. Check your wiring with display, check power supply, check internet connection and try to reboot the device. If that doesn't help:
* Check logs for service and ePiframe script that are stored in configured ```log_files``` location
* [Check configuration](#configuration)
* Do a test with ```./ePiframe.py --test``` without sending photo to display and get detailed log on what is happening
* Make sure that configured photo filtering is not narrowing too much, i.e. only one or no photos at all are filtered (test that in the step above)
* Check ePiframe service status: ```sudo systemctl status ePiframe.service``` and [restart](#service-control) if not running
* Sometimes changing a color preset can fix black screen problem as some photos react strange to image processing

If problem still occurs, please create an issue here.

**_NOTE_** - I've experienced some display issues like shadowing or distorted images when used bad or too weak power supplies so make sure you provide stable 5V/3A.

## Service control

ePiframe comes with a system service that is fully autonomic, automatic and self-recovering. It can be left completely unsupervised but it is possible to control it if needed, the same way as every service in Linux:
```
#stop
sudo systemctl stop ePiframe.service
#start
sudo systemctl start ePiframe.service
#restart
sudo systemctl restart ePiframe.service
```

It is possible to start (for test purposes) only WebUI or TelegramBot thread from the service:
```
cd <Your ePiframe path>
#stop first if running
sudo systemctl stop ePiframe.service
#WebUI
./ePiframe_service.py start web
#or TelegramBot
./ePiframe_service.py start telegram
```

**_❗ IMPORTANT ❗_** - These services must be enabled in the configuration file!

**_NOTE_** - Service will not show any errors if the configuration is wrong or the thread cannot be started. Check [debugging section](#debugging).

**_NOTE_** - Keep in mind that any port number below 5000 needs root privilleges to be possible to assign (use ```sudo ./ePiframe_service.py ...```)