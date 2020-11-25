<img align="right" src="https://github.com/MikeGawi/ePiframe/blob/main/assets/logo.png">

# ePiframe

Python 3 e-Paper Raspberry Pi Photo Frame with Google Photos

## Table of Contents
<!--ts-->
   * [Main features](#main-features)
   * [Hardware required](#hardware-required)
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
   * [Performance](#performance) 
   * [Service control](#service-control)
   * [This is not what I'm looking for](#this-is-not-what-im-looking-for)
<!--te-->

## Main features

* Pulls photos (videos are ignored) from one or more albums in Google Photos and automatically prepares them for attached e-paper display
* Non-HDMI e-Paper Waveshare SPI displays supported
* No additional storage or 3rd party software is required as only one and current photo is downloaded and processed per frame update
* Updating after time interval with option to change time per photo
* Off hours per different days
* Photo filtering (by creation date, number of images)
* Showing randomly, descendingly or ascendingly by creation date
* Automatic conversion to black and white with 6 different presets, color inversion and various background colors 
* For vertical or horizontal frame position
* Even for Raspberry Pi Zero W + Raspberry Pi OS Lite
* Low energy consumption

Color presets              |  Different backgrounds
:-------------------------:|:-------------------------:
![](https://github.com/MikeGawi/ePiframe/blob/main/assets/movie.gif)  |  ![](https://github.com/MikeGawi/ePiframe/blob/main/assets/movie2.gif)

## Hardware required

* A Raspberry Pi (Zero W, 1, 2 were tested but I am sure all will work)
* microSD card for Raspberry Pi OS, 4GB minimum
* [e-Paper Waveshare SPI display](https://www.waveshare.com/product/raspberry-pi/displays/e-paper.htm) (7.5 inch black and white with RasPi HAT was used but probably all B&W will work out-of-the-box, the rest will with small modifications)
* Raspberry Pi power supply (as display is usually powered from RasPi HAT then 3A 5V is preferred)
* Photo frame (for 7.5 inch screen I used 13x18cm /5''x7''/ with printed parts)


## Advantages

* Low energy consuming and cheap ($80) photo frame on Raspberry Pi Zero W pulling photos from Google Photos albums shared between users who can modify the content
* Autonomic device, once configured can be left headless
* e-paper display gives an unique look and You don't need to worry about ambient light control, light sensors or turning off screen light functions as it would be with LCDs
* Supports all image formats including RAW
* Photo is displayed even if power (or network) is down to avoid blank frame - e-paper takes power only during refresh
* Powerful [ImageMagick](https://imagemagick.org/) on board to convert photos on-fly and adjust them to the display
* Currently displayed photo can be removed from the album but ePiframe will remember where it should continue
* Simple script in Python to automate frame update, everything is configurable (within one config file) and in one place
* System service supervising whole process that is auto recovering and auto starting by itself
* Fully customizable: from photos and how they are displayed, to display size and frame (buy one, print it or create/decorate it Yourself) - a great gift idea
* Simple yet powerful

## Installation

* [Install Raspberry Pi OS](https://www.raspberrypi.org/documentation/installation/installing-images/README.md) formerly known as Raspbian. LITE version is supported
* [Setup network connection](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md)
* [Enable SSH](https://www.raspberrypi.org/documentation/remote-access/ssh/) - chapter *3. Enable SSH on a headless Raspberry Pi (add file to SD card on another machine)*
* [Assemble Raspberry Pi and power it](https://projects.raspberrypi.org/en/projects/raspberry-pi-setting-up)
* [Find Raspberry Pi IP address](https://www.raspberrypi.org/documentation/remote-access/ip-address.md)
* [Log in with SSH](https://www.raspberrypi.org/documentation/remote-access/ssh/) - chapter *4. Set up your client*

### Automatic

Use *install.sh* script:

```
wget https://raw.githubusercontent.com/MikeGawi/ePiframe/master/install.sh
./install.sh
```

Move to [next steps](#next-steps)


### Manual

* Install APTs:
```bash
sudo apt-get install imagemagick webp ufraw-batch libatlas-base-dev python3 python3-pip
```
* Install PIPs:
```bash
sudo -H pip3 install requests python-dateutil configparser pandas RPi.GPIO spidev image
sudo -H pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```
* Download ePiframe ZIP file (or use git) and extract it to *path*:
```
cd <path>
sudo wget -q https://github.com/MikeGawi/ePiframe/archive/master.zip -O ePiframe.zip
unzip -q ePiframe.zip
cp -r ePiframe/* .
rm -r ePiframe/ ePiframe.zip
```
* Download Waveshare ZIP file (or use git) and extract all RasPi Waveshare display libraries to lib inside *path*:
```
cd <path>
wget -q https://github.com/waveshare/e-Paper/archive/master.zip -O waveshare.zip
unzip -q waveshare.zip
cp -r e-Paper-master/RaspberryPi&JetsonNano/python/lib .
rm -r e-Paper-master/ waveshare.zip
```
* Enable SPI support:
```
sudo raspi-config
```
Go to *Advanced Options > SPI* and choose “Yes” for both questions then select *Finish* to exit *raspi-config*.

Either reboot your Pi or run this command to load the kernel module
```
sudo modprobe spi-bcm2708
```
* Install ePiframe service
```
#replace paths
sed 's/EPIEPIEPI/'$(pwd | sed 's_/_\\/_g')'\//g' ePiframe.service.org > ePiframe.service
#enable service
sudo systemctl enable `pwd`/ePiframe.service
```

Move to [next steps](#next-steps)


## Next steps

* Connect display to Raspberry Pi
* Add Your Google account support to Google Photos API on [Google Console](https://developers.google.com/photos/library/guides/get-started)
  * Name it *ePiframe*
  * *Use TV and Limited Input* as application type
* Download credentials JSON file for the API from the previous step
  *  Download icon in [Google Console](https://console.cloud.google.com/) -> Credentials -> OAuth 2.0 Client IDs 
* Generate token pickle file with *getToken.py* script to use with Google Photos:
  * ```wget https://raw.githubusercontent.com/MikeGawi/ePiframe/master/getToken.py && ./getToken.py```
  * Run it on internet browser accessible machine as Google authentication is needed. I doesn't need to be ePiframe device.
  * Script will produce *token.pickle* file
* Copy credentials JSON and token pickle file to ePiframe device inside installation path
* Configure ePiframe with *config.cfg* file inside installation path
* Check configuration with ```./ePiframe.py --check-config```
* Do a test with ```./ePiframe.py --test``` without sending photo to display
* Reboot ePiframe device or ```sudo modprobe spi-bcm2708``` to start enabled SPI support and automatically run frame
* Enjoy Your ePiframe!


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

* Configure ePiframe with *config.cfg* file inside installation path. Just one file and with lots of descriptions. No need to restart service after changing any of config file values as file is loaded per every display refresh/run
* ALWAYS check configuration with ```./ePiframe.py --check-config```

## Performance

Image processing is the most resources consuming process but ePiframe is meant to work on Raspberry Pi Zero. Script does one thing at a time and moves to another task, there are no parallel jobs and the peak of load is only during frame update. On Raspberry Pi Zero W v1.1 it took around 2-3 minutes average to pull the UHD photo, process it and put it on display. Here's a graph of loads during ePiframe tests:

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

## This is not what I'm looking for

If You're looking for an LCD frame with Google Photos [mrworf's Photo Frame](https://github.com/mrworf/photoframe/) is a great choice: color LCD support, ambient light sensor, off hours and many many more. 

I also wanted to use [Magic Mirror](https://github.com/MichMich/MagicMirror) to create frame with [MMM-GooglePhotos](https://github.com/ChrisAcrobat/MMM-GooglePhotos) and doing a screen shot of the page for e-paper display like [rpi-magicmirror-eink](https://github.com/BenRoe/rpi-magicmirror-eink) does. MM is a great software but my Raspberry Pi Zero was too slow for me with it.

Also a very nice e-paper Waveshare display with Raspberry Pi idea is [Inky Calendar](https://github.com/aceisace/Inky-Calendar)
