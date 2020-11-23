# ePiframe

e-Paper Raspberry Pi Photo Frame with Google Photos


## Main Features

* Pulls photos from one or more albums in Google Photos
* Non-HDMI e-Paper Waveshare SPI displays supported
* No additional storage of 3rd party software is required as only one and current photo is downloaded and processed per frame update
* Updating after time interval with option to change time per photo
* Off hours per different days
* Photo filtering (by creation date, number of images)
* Showing randomly, descendingly or ascendingly by creation date
* Automatic conversion to black and white with 6 different presets, color inversion and background colors 
* For vertical or horizontal frame position
* For Raspberry Pi Zero W + Raspberry Pi OS Lite
* Low energy consumption


## Hardware required

* A Raspberry Pi (Zero W, 1, 2 were tested, but I am sure all will work)
* [e-Paper Waveshare SPI display](https://www.waveshare.com/product/raspberry-pi/displays/e-paper.htm) (7.5 inch black and white with RasPi HAT was used but probably all will work with small modifications)
* Raspberry Pi power supply (as display is usually powered from RasPi HAT then 3A 5V is preferred)
* Photo frame (for 7.5 inch screen I used 13x18cm /5''x7''/ with printed parts)


## Goals

* Create a low energy and cheap ($75) photo frame on Raspberry Pi Zero W pulling photos from Google Photos albums shared between users who can modify the content
* Use e-paper display to have an unique look and don't need to use ambient light control or turn off screen as it would be with LCDs
* Have photo displayed even if power is down to avoid blank frame - e-paper takes power only during refresh
* Have powerful [ImageMagick](https://imagemagick.org/) on board to convert photos on-fly and adjust them to the display
* Have a simple script in Python to control everything, having everything configurable and in one place
* System service supervising whole process that is auto recovering and auto starting by itself
* Simple yet powerful


## Installation


### Automatic

Use install.sh script:

Move to Next steps


### Manual

* Install APTs:
```bash
sudo apt-get install imagemagick
sudo apt-get install webp
sudo apt-get install ufraw-batch
sudo apt-get install libatlas-base-dev
sudo apt-get install python3
sudo apt-get install python3-pip
```
* Install PIPs:
```bash
sudo -H pip3 install requests
sudo -H pip3 install python-dateutil
sudo -H pip3 install configparser
sudo -H pip3 install pandas
sudo -H pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
sudo -H pip3 install RPi.GPIO
sudo -H pip3 install spidev
sudo -H pip3 install image
```
* download ePiframe ZIP file (or use git) and extract it to *path
* download Waveshare ZIP file (or use git) 
