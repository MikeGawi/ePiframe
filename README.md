# ePiframe

Python 3 e-Paper Raspberry Pi Photo Frame with Google Photos


## Main Features

* Pulls photos from one or more albums in Google Photos and automatically prepares them for attached e-paper display
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


## Hardware required

* A Raspberry Pi (Zero W, 1, 2 were tested but I am sure all will work)
* [e-Paper Waveshare SPI display](https://www.waveshare.com/product/raspberry-pi/displays/e-paper.htm) (7.5 inch black and white with RasPi HAT was used but probably all B&W will work out-of-the-box, the rest will with small modifications)
* Raspberry Pi power supply (as display is usually powered from RasPi HAT then 3A 5V is preferred)
* Photo frame (for 7.5 inch screen I used 13x18cm /5''x7''/ with printed parts)


## Advantages

* Low energy consuming and cheap ($75) photo frame on Raspberry Pi Zero W pulling photos from Google Photos albums shared between users who can modify the content
* Autonomic device, once configured can be left headless
* e-paper display gives an unique look and You don't need to worry about ambient light control, light sensors or turning off screen light functions as it would be with LCDs
* Supports all image formats including RAW
* Photo is displayed even if power (or network) is down to avoid blank frame - e-paper takes power only during refresh
* Powerful [ImageMagick](https://imagemagick.org/) on board to convert photos on-fly and adjust them to the display
* Currently displayed photo can be removed from the album but ePiframe will remember where it should continue
* Simple script in Python to automate frame update, everything is configurable (within one config file) and in one place
* System service supervising whole process that is auto recovering and auto starting by itself
* Simple yet powerful


## Installation

Install 

### Automatic

Use *install.sh* script:

```
wget https://raw.githubusercontent.com/MikeGawi/ePiframe/master/install.sh
./install.sh
```

Move to [Next steps](#Next steps)


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
sed 's/EPIEPIEPI/'$(pwd | sed 's_/_\\/_g')'\//g' ePiframe.service.org >> ePiframe.service
#enable service
sudo systemctl enable `pwd`/ePiframe.service
```

## Next steps

* Add account support to Google Photos API on [Google Console](https://console.cloud.google.com/)
* Get credentials JSON file for the API from the previous step
* Generate token pickle file with getToken.py script to use with Google Photos
* Copy credentials JSON and token pickle file to ePiframe device
* Configure ePiframe with config.cfg file
* Check configuration with ./ePiframe.py --check-config
* Do a test with ./ePiframe.py --test without sending photo to display
* Reboot ePiframe device or "sudo modprobe spi-bcm2708" to start enabled SPI support
* Enjoy Your ePiframe!
