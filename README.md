<img align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/assets/logo.png">


# ePiframe

Python 3 e-Paper Raspberry Pi Photo Frame with Google Photos


## Table of Contents
<!--ts-->
   * [Main features](#main-features)
      * [New features](#new-features)
   * [Hardware required](#hardware-required)
      * [Frame](#frame)
   * [Advantages](#advantages)
   * [Installation](#installation)
      * [Automatic](#automatic)
      * [Manual](#manual)
      * [Next steps](#next-steps)
   * [Uninstalling](#uninstalling)
      * [Automatic](#automatic-1)
      * [Manual](#manual-1)
      * [Next steps](#next-steps-1)
   * [Configuration](#configuration)
   * [Command line](#command-line)
   * [Debugging](#debugging)
   * [Performance](#performance) 
   * [Service control](#service-control)
   * [Flow](#flow)
   * [Future plans](#future-plans)
   * [Resources](#resources)
   * [This is not what I'm looking for](#this-is-not-what-im-looking-for)
<!--te-->


## Main features

* Pulls photos (videos are ignored) from one or more albums in Google Photos and automatically prepares them for attached e-Paper display
* Non-HDMI e-Paper Waveshare SPI displays supported
* No additional storage or 3rd party software is required as only one and current photo is downloaded and processed per frame update
* Updating after time interval with option to change time per photo (by *hot word* in photo description)
* Off hours per different days
* Photo filtering (by creation date, number of images)
* Showing randomly, descendingly or ascendingly by creation date
* Automatic conversion to black-and-white with 6 different presets, color inversion and various background colors 
* For vertical or horizontal frame position
* Even for Raspberry Pi Zero W + Raspberry Pi OS Lite
* Low power consumption

![](https://github.com/MikeGawi/ePiframe/blob/master/assets/frame.gif)

### New features 🎉

* (06.10.2021 since [ePiframe v0.9.3 beta](https://github.com/MikeGawi/ePiframe/releases/tag/v0.9.3-beta)) Weather stamp (optional) - subtly showing current weather icon and temperature in defined display corner, size and color. Taken from free API of [OpenWeather](https://openweathermap.org/api) according to [Maps.ie](https://www.maps.ie/coordinates.html) coordinates - [#3](https://github.com/MikeGawi/ePiframe/issues/3)

| Color presets             | Different backgrounds     |
|:-------------------------:|:-------------------------:|
| ![](https://github.com/MikeGawi/ePiframe/blob/master/assets/movie.gif) | ![](https://github.com/MikeGawi/ePiframe/blob/master/assets/movie2.gif) |
|<ul align="left"><li>Floyd-Steinberg dither + enhanced contrast</li><li>Floyd-Steinberg dither + high remap</li><li>GIMP-like result</li><li>Floyd-Steinberg ordered dither</li><li>direct conversion to black-and-white</li><li>simple conversion to black-and-white + basic dither</li><li>inverted colors (all presets above will work with this function)</li></ul> |<ul align="left"><li>white</li><li>black</li><li>blurred and enlarged source photo to cover empty areas</li></ul> |


## Hardware required

<a href="http://www.raspberrypi.org"><img width="100" align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/assets/RPi-Logo.png"></a>

* A Raspberry Pi (Zero W, 1, 2 were tested but I am sure all will work)
* [microSD card for Raspberry Pi OS](https://www.raspberrypi.org/documentation/installation/sd-cards.md), 4GB minimum
* [e-Paper Waveshare SPI display](https://www.waveshare.com/product/raspberry-pi/displays/e-paper.htm) (7.5 inch black and white with RasPi HAT was used but probably all B&W will work out-of-the-box, the rest as well but with small modifications)
* Raspberry Pi power supply (as display is usually powered from RasPi HAT then 5V/3A is preferred)
* Photo frame (for 7.5" screen I used 13x18cm /5"x7"/ with printed parts)


### Frame

You can use any photo frame for your ePiframe and cut the back to make place for the display connector and glue Raspberry Pi with HAT on to it. Also a good passe-partout piece should frame your display and cover all unwanted elements. 

Or you can 3D print a nice standing frame back with case for your Raspberry Pi and even passe-partout and assemble it with bought photo frame like I did here:

|<img src="https://github.com/MikeGawi/ePiframe/blob/master/assets/frame1.jpg" width="500"/>| 
|:--:| 
|*Printed back (black) of 13x18cm (5"x7") frame for 7.5" screen with passe-partout (white)*|

[Thing files](https://www.thingiverse.com/thing:4727060)


## Advantages

* Low power consuming and cheap ($90) photo frame on Raspberry Pi Zero W pulling photos from Google Photos albums shared between users who can modify the content
* Autonomic device, once configured can be left headless
* e-Paper display gives an unique look and you don't need to worry about ambient light control, light sensors or turning off screen light functions (as with LCDs)
* Photo is displayed even if power (or network) is down as e-Paper takes power only during refresh and doesn't have back light - so no blank frames
* Powerful [ImageMagick](https://imagemagick.org/) on board to convert photos on the fly and adjust them to the display. No matter what quality and what size they are
* Supports all image formats including RAW
* Currently displayed photo can be removed from the album but ePiframe will remember where to continue
* Simple script in Python to automate frame update, everything is configurable (within one [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) file) and in one place
* System service supervising whole process that is auto recovering and auto starting by itself
* Fully customizable: from photos and how they are displayed (presets, different backgrounds or completely change [ImageMagick conversion](https://legacy.imagemagick.org/Usage/quantize/)), to display size and frame (buy one, print it or create/decorate it yourself)
* Simple yet powerful

ePiframe is a very nice handmade gift idea: create an album that whole family can edit, decorate frame (e.g. [decoupage](https://en.wikipedia.org/wiki/Decoupage)) or print it, print family signatures or baby drawings on the back, put some wishes picture on the display before handing it (using [command line](#command-line)) and many more. 


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
wget https://raw.githubusercontent.com/MikeGawi/ePiframe/master/install.sh
chmod +x install.sh
./install.sh
```
Move to [next steps](#next-steps)


### Manual

* Install APTs:
```
sudo apt-get install imagemagick webp ufraw-batch libatlas-base-dev wiringpi python3 python3-pip
```
* Install PIPs:
```
sudo -H pip3 install requests python-dateutil configparser pandas RPi.GPIO spidev image pillow
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
	sed 's/EPIEPIEPI/'$(pwd | sed 's_/_\\/_g')'\//g' ePiframe.service.org > ePiframe.service
	```
  * enable service
	```
	sudo systemctl enable `pwd`/ePiframe.service
	```

Move to [next steps](#next-steps)


## Next steps

* Connect display to Raspberry Pi
* Add your Google account (the one used to pull photos from) support to Google Photos API on [Google Console](https://developers.google.com/photos/library/guides/get-started) - *Enable the Google Photos Library API*
  * Name it *ePiframe*
  * Use *TVs and Limited Input* as application type (sometimes works only with *Desktop Application* but You can change it later)
  * Or through the Google API Console:  
    * Go to the [Google API Console](https://console.developers.google.com/apis/library)
    * From the menu bar, select a project or create a new project
    * To open the Google API Library, from the Navigation menu, select *APIs & Services -> Library*
    * Search for *Google Photos Library API*. Select the correct result and click *Enable*
* Download credentials JSON file for the API from the previous step - *Download client configuration* button
  *  Or Download icon in *[Google Console](https://console.cloud.google.com/) -> Credentials -> OAuth 2.0 Client IDs*
* Generate token pickle file with *getToken.py* script to use with Google Photos:
  * ```wget https://raw.githubusercontent.com/MikeGawi/ePiframe/master/getToken.py && chmod +x getToken.py && ./getToken.py```
  * Run it on internet browser accessible machine as Google authentication is needed. It doesn't need to be ePiframe device
  * Script will produce *token.pickle* file
* Copy credentials JSON and token pickle file to ePiframe device inside installation path (using [*rsync*](https://ss64.com/bash/rsync.html) or [*scp*](https://ss64.com/bash/scp.html))
* Configure ePiframe with [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) file inside installation path
* Check configuration with ```./ePiframe.py --check-config```
* Do a test with ```./ePiframe.py --test``` without sending photo to display
* Do a test with ```./ePiframe.py --test-display``` to test display
* Reboot ePiframe device to automatically run frame
* Enjoy your ePiframe!


~~Also consider changing Waveshare scripts in *lib* inside *path* according to those two pull requests:~~

  ~~* [Fix display resume from sleep issue](https://github.com/waveshare/e-Paper/pull/71)~~
  ~~* [Significantly increase speed of displaying images](https://github.com/waveshare/e-Paper/pull/104)~~

~~I hope those improvements will be adapted to the master branch in the future.~~


## Uninstalling
### Automatic

Use *install.sh* script:
```
wget https://raw.githubusercontent.com/MikeGawi/ePiframe/master/install.sh
./install.sh --uninstall
```
Move to [next steps](#next-steps-1)


### Manual

```
sudo systemctl stop ePiframe.service
sudo systemctl disable ePiframe.service
```
Move to [next steps](#next-steps-1)


### Next steps

* Whole ePiframe code is in the directory where it was installed so delete it if not needed
* All dependecies installed for ePiframe are [here](#manual)


## Configuration

* Configure ePiframe with [*config.cfg*](https://github.com/MikeGawi/ePiframe/blob/master/config.cfg) file inside installation path. Just one file and with lots of descriptions. No need to restart service after changing any of config file values as file is loaded per every display refresh/run
* **__ALWAYS__** check configuration with ```./ePiframe.py --check-config```

**_NOTE_** - Interval multiplication option which can enlonger the photo display time, uses *hot word* (i.e. *hotword #*, where # is interval multiplicator value) in the **photo description** field. You can change this attribute only for your own photos or for all *only* when you're an owner of the album. It's description in the photo information panel not photo comment. Comments are inacessible from Google Photos level (unfortunately) as [are stored in different database](https://support.google.com/photos/thread/3272278?hl=en) :(


## Command line

Main ePiframe script *ePiframe.py* is written in Python and can work from CLI, the ePiframe service daemon *ePiframe_service.py* just runs it without any arguments. But here are additional available commands helpful for tests and debugging:

Syntax: ```ePiframe.py [option]```
* ```--check-config``` - checks configuration file syntax
* ```--test``` - tests whole chain: credentials, pickle file and downloads photo **but without** sending it to the display. Used to test configuration, photo filtering, etc
* ```--test-display [file]``` - displays the photo ```file``` on attached display with current ePiframe configuration. If no file is provided the ```photo_convert_filename``` from the configuration is used. __Only__ converted photos should be put on display! Use ```--test-convert``` for that
* ```--test-convert [file]``` - converts the photo ```file``` to configured ```photo_convert_filename``` with current ePiframe configuration. If no file is provided the ```photo_download_name``` from the configuration is used
* ```--no-skip``` - like ```--test``` but is not skipping to another photo, not marking photo as showed, etc.
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


## Performance

Image processing is the most resources consuming process but ePiframe is meant to work on Raspberry Pi Zero. Script does one thing at a time and moves to another task, there are no parallel jobs (even image conversion has been stripped to one thread) and the peak of load is only during frame update. On Raspberry Pi Zero W v1.1 it took maximum up to 2 minutes (avg. 60 seconds) to pull the 4K photo, process it and put it on display. The conversion has been [optimized](https://stackoverflow.com/questions/28704984/how-to-speed-up-a-complex-image-processing): filters are not used, scale + resize instead of blur but with the same results, resampling instead of resizing, etc. Here's a graph of loads during ePiframe tests:

|<img src="https://github.com/MikeGawi/ePiframe/blob/master/assets/graph.png" width="720"/>| 
|:--:| 
|*Graph of loads for ePiframe run on Raspberry Pi Zero W v1.1 and Raspberry Pi OS 10 Buster (5.4.79+). Off hours from 23:30 to 5:30, frame refresh interval was 10 minutes, various photo types and quality (4K UHD photos too) with Floyd-Steinberg dither + enhanced contrast preset and photo background (so the heaviest conversion possible)*|

|||
|--|--|
|Highest load peak during runtime |*0.67* |
|Average of maximum load peaks during runtime |*0.43* |
|Average load during runtime (except off hours) |*0.105* |


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


## Flow
 
|<img src="https://github.com/MikeGawi/ePiframe/blob/master/assets/flow.png" width="600"/>| 
|:--:| 
|*Flow diagram of ```ePiframe.py``` - main script. If any step fails or has no result then script will exit*|

	
## Future plans
	
ePiframe to-do list (for 2021):
* Add web interface based on [Flask](https://flask.palletsprojects.com/en/1.1.x/) for configuration, control and photos upload
* Add Telegram bot service to control frame and upload photos
* Easier token generation from the web interface (is this even possible?)
* ✔️ Weather and temperature displayed on the photo - [#3](https://github.com/MikeGawi/ePiframe/issues/3)
* Frame lasers, robot arms and making lunch functionality...

Stay tuned!


## Resources
	
This project uses:
* [Google Photos API](https://developers.google.com/photos/library/guides/overview)
* [Official Waveshare e-Paper libraries](https://github.com/waveshare/e-Paper)
* [Pandas Dataframe](https://pandas.pydata.org/)
* [ImageMagick](https://imagemagick.org/)

Helpful links:
* [Najeem Muhammed: Analyzing my Google Photos library with Python and Pandas](https://medium.com/@najeem/analyzing-my-google-photos-library-with-python-and-pandas-bcb746c2d0f2)
* [Jie Jenn: Google Photos API Python tutorial](https://learndataanalysis.org/category/python-tutorial/google-photos-api/)
* [Leon Miller-Out: Auto-recovery of crashed services with systemd](https://singlebrook.com/2017/10/23/auto-restart-crashed-service-systemd/)
* [Sander Marechal: A simple unix/linux daemon in Python](https://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/)
	

## This is not what I'm looking for

If you're looking for an LCD frame with Google Photos, [mrworf's Photo Frame](https://github.com/mrworf/photoframe/) is the best choice: color LCD support, ambient light sensor, off hours and many, many more. 


I also wanted to use [Magic Mirror](https://github.com/MichMich/MagicMirror) to create frame with [MMM-GooglePhotos](https://github.com/ChrisAcrobat/MMM-GooglePhotos) and doing a screen shot of the page for e-paper display like [rpi-magicmirror-eink](https://github.com/BenRoe/rpi-magicmirror-eink) does. Magic Mirror is a great software but I decided to do it by myself (not to get crazy during the lockdown).


Or you can just use Arduino or ESP controller (even with attached card controller) and display photos from the storage. There are some projects like that in the Web but you lose Google Photos synchronisation.
	
	
Also a very nice e-paper Waveshare display with Raspberry Pi idea is [inkycal](https://github.com/aceisace/Inky-Calendar)
