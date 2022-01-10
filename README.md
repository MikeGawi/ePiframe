<img align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/assets/logo.png">

# ePiframe

Python 3 e-Paper Raspberry Pi Photo Frame with Google Photos and/or local storage (and more), weather information, Telegram Bot, Web User Interface and API.

## Main features

* Pulls photos (videos are ignored) from one or more albums in Google Photos and/or from local folder and automatically prepares them for attached e-Paper display
* Non-HDMI e-Paper Waveshare SPI displays supported
* Simple activation for Google Photos access from ePiframe device (with guide) or any other device with Python
* No additional storage for Google Photos source or 3rd party software is required as only one and current photo is downloaded and processed per frame update
* When using local source it is possible to sync photos from almost all cloud/image hosting providers using 3rd party software
* Updating after time interval with option to change time per photo (by *hot word* in photo description)
* Off hours per different days
* Photo filtering (by creation date, number of images)
* Showing randomly, descendingly or ascendingly by creation date
* Automatic conversion to black-and-white with 6 different presets, color inversion and various background colors 
* For vertical or horizontal frame position
* Can be controlled from Telegram Bot, embedded WebUI or API
* Can display weather information
* Can improve displayed photos on the fly, i.e. normalization, contrast and brightness settings, gamma correction, etc.
* Even for Raspberry Pi Zero W (wireless) and offline Raspberry Pi Zero (when using local source) + Raspberry Pi OS Lite
* Low power consumption

<p align="center">
	<img src ="https://github.com/MikeGawi/ePiframe/blob/master/assets/frame.gif">
</p>

### New features 🎉

* **Weather stamp** (optional) - subtly showing current weather icon and temperature in defined display corner, size and color - [#3](https://github.com/MikeGawi/ePiframe/issues/3)
* **Telegram Bot** (optional) - control the ePiframe with few commands from Telegram IM - [#5](https://github.com/MikeGawi/ePiframe/issues/5)
* **WebUI** (optional) - control the ePiframe with web user interface - [#9](https://github.com/MikeGawi/ePiframe/issues/9)
* **Users and passwords** (optional) for web interface - [#15](https://github.com/MikeGawi/ePiframe/issues/15)
* **API** (optional) - control the ePiframe with API calls [#17](https://github.com/MikeGawi/ePiframe/issues/17)
* **Statistics** (optional) - load, memory and temperature graphs shown in WebUI [#19](https://github.com/MikeGawi/ePiframe/issues/19)
* **Easy activation** - activate Google Photos from ePiframe device (or any other one) with visual guide [#20](https://github.com/MikeGawi/ePiframe/issues/20)
* **Photo improving**  (optional) contrast and brightness, gamma correction, etc. [#25](https://github.com/MikeGawi/ePiframe/issues/25)
* **Local source**  (optional) use local folder as the photo source [#16](https://github.com/MikeGawi/ePiframe/issues/16)

## Hardware required

<a href="http://www.raspberrypi.org"><img width="100" align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/assets/RPi-Logo.png"></a>

* A Raspberry Pi with standard GPIO 40 pins. Models Zero (offline - when using local source), Zero W and Zero WH supported
* [microSD card for Raspberry Pi OS](https://www.raspberrypi.com/documentation/computers/getting-started.html#sd-cards), 4GB minimum
* [e-Paper Waveshare SPI display](https://www.waveshare.com/product/raspberry-pi/displays/e-paper.htm) (7.5 inch black and white with RasPi HAT was used but probably all B&W will work out-of-the-box, the rest as well but with small modifications)
* Raspberry Pi power supply (as display is usually powered from RasPi HAT then 5V/3A is preferred)
* Photo frame (for 7.5" screen I used 13x18cm /5"x7"/ with printed parts)

### Frame

You can use any photo frame for your ePiframe and cut the back to make place for the display connector and glue Raspberry Pi with HAT on to it. Also a good passe-partout piece should frame your display and cover all unwanted elements. 

Or you can 3D print a nice standing frame back with case for your Raspberry Pi and even passe-partout and assemble it with bought photo frame like I did here:

<div align="center">

|<img src="https://github.com/MikeGawi/ePiframe/blob/master/assets/frame1.jpg" width="500"/>| 
|:--:| 
|*Printed back (black) of 13x18cm (5"x7") frame for 7.5" screen with passe-partout (white)*|

</div>

[Thing files](https://www.thingiverse.com/thing:4727060)

## Advantages

* Low power consuming and cheap ($90) photo frame on Raspberry Pi Zero, Zero W (or WH) pulling photos from Google Photos albums (shared between users who can modify the content) and/or local source 
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

ePiframe is a very nice handmade gift idea: create an album that whole family can edit, decorate frame (e.g. [decoupage](https://en.wikipedia.org/wiki/Decoupage)) or print it, print family signatures or baby drawings on the back, put some wishes picture on the display before handing it and many more. 

## Installation

Installation, configuration and API documentation can be found <font size="+2"><b>[HERE](https://github.com/MikeGawi/ePiframe/blob/master/INSTALL.md)</b></font>

## Future plans
	
ePiframe to-do list for 2022:
* [HDMI e-paper screens](https://github.com/MikeGawi/ePiframe/issues/33) - check what is possible

Stay tuned!

## Resources
	
This project uses:
* [Google Photos API](https://developers.google.com/photos/library/guides/overview)
* [Official Waveshare e-Paper libraries](https://github.com/waveshare/e-Paper)
* [Pandas Dataframe](https://pandas.pydata.org/)
* [ImageMagick](https://imagemagick.org/)
* [OpenWeather API](https://openweathermap.org/api)
* [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI)
* [Flask](https://flask.palletsprojects.com/), [WTForms](https://wtforms.readthedocs.io/), [FlaskWTF](https://flask-wtf.readthedocs.io/), [Flask-Login](https://flask-login.readthedocs.io/)
* [Bootstrap](https://getbootstrap.com/)
* [jQuery](https://jquery.com/)
* [Dropzone.js](https://www.dropzone.dev/js/)
* [SQLite](https://www.sqlite.org)
* [RRDtool](https://oss.oetiker.ch/rrdtool/), [javascriptRRD](http://javascriptrrd.sourceforge.net/), [Flot](http://www.flotcharts.org/)