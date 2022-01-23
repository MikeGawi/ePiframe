<img align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/docs/assets/logo.png">

# ePiframe

Python 3 e-Paper (or any other HDMI/Composite display) Raspberry Pi Photo Frame with Google Photos and/or local storage (and more), weather information, Telegram Bot, Web User Interface and API.

## Main features

* Pulls photos (videos are ignored) from one or more albums in Google Photos and/or from local folder and automatically prepares them for attached display
* Non-HDMI e-Paper Waveshare SPI or any other HDMI, Composite displays supported
* Works with Desktop or CLI (console) OS versions
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

<p align="center">
	<img src ="https://github.com/MikeGawi/ePiframe/blob/master/docs/assets/frame.gif">
</p>

### Newest features 🎉

* **Local source** - (optional) use local folder as the photo source [#16](https://github.com/MikeGawi/ePiframe/issues/16)
* **HDMI screens support** - ePiframe with HDMI/Composite display [#33](https://github.com/MikeGawi/ePiframe/issues/33)
* **WebUI Dark Theme** - (optional) dark mode for Web User Interface [#43](https://github.com/MikeGawi/ePiframe/issues/43)

## Hardware required

<a href="http://www.raspberrypi.org"><img width="100" align="right" src="https://github.com/MikeGawi/ePiframe/blob/master/docs/assets/RPi-Logo.png"></a>

* A Raspberry Pi with standard GPIO 40 pins (for e-Paper HAT). Models Zero (offline - when using local source), Zero W and Zero WH supported
* [microSD card for Raspberry Pi OS](https://www.raspberrypi.com/documentation/computers/getting-started.html#sd-cards), 4GB minimum
* [e-Paper Waveshare SPI display](https://www.waveshare.com/product/raspberry-pi/displays/e-paper.htm) (7.5 inch black and white with RasPi HAT was used but probably all B&W will work out-of-the-box, the rest as well but with small modifications) or any other HDMI, Composite display
* Raspberry Pi power supply (for e-Paper display 5V/3A is preferred as it is usually powered from RasPi HAT)
* Photo frame

### Frame

You can use any photo frame for your ePiframe and cut the back to make place for the display connector and glue Raspberry Pi onto it. Also a good passe-partout piece should frame your display and cover all unwanted elements. 

Or you can 3D print a nice standing frame back with case for your Raspberry Pi and even passe-partout and assemble it with bought photo frame like I did here:

<div align="center">

|<img src="https://github.com/MikeGawi/ePiframe/blob/master/docs/assets/frame1.jpg" width="500"/>| 
|:--:| 
|*Printed back (black) of 13x18cm (5"x7") frame for 7.5" screen with passe-partout (white)*|

</div>

[Thing files](https://www.thingiverse.com/thing:4727060)

## Advantages

* Photo frame on Raspberry Pi Zero, Zero W (or WH) pulling photos from Google Photos albums (shared between users who can modify the content) and/or local source 
* Autonomic device, once configured can be left headless
* Supports HDMI, Composite and SPI (e-Paper) outputs and can adapt photos to the display (black & white, limited pallete, etc.)
* With e-Paper display photo is shown even if power (or network) is down as e-Paper takes power only during refresh and doesn't have back light - so no blank frames
* Powerful [ImageMagick](https://imagemagick.org/) on board to convert photos on the fly and adjust them to the display. No matter what quality and what size they are
* Supports all image formats including RAW
* Currently displayed photo can be removed from the album but ePiframe will remember where to continue
* System service supervising whole process that is auto recovering and auto starting by itself
* Fully customizable: from photos and how they are displayed (presets, different backgrounds or completely change [ImageMagick conversion](https://legacy.imagemagick.org/Usage/quantize/)), to display size and frame (buy one, print it or create/decorate it yourself)

ePiframe is a very nice handmade gift idea: create an album that whole family can edit, decorate frame (e.g. [decoupage](https://en.wikipedia.org/wiki/Decoupage)) or print it, print family signatures or baby drawings on the back, put some wishes picture on the e-Paper display before handing it and many more. 

## Installation

Installation, configuration and API documentation can be found <font size="+2"><b>[HERE](https://github.com/MikeGawi/ePiframe/blob/master/INSTALL.md)</b></font>

## Future plans
	
ePiframe to-do list for 2022:
* **A surprise feature, something big that will take some time to implement** - in progress

Stay tuned!

## Resources
	
This project uses:

[Google Photos API](https://developers.google.com/photos/library/guides/overview) :white_small_square: [Official Waveshare e-Paper libraries](https://github.com/waveshare/e-Paper) :white_small_square: [Pandas Dataframe](https://pandas.pydata.org/) :white_small_square: [ImageMagick](https://imagemagick.org/) :white_small_square: [OpenWeather API](https://openweathermap.org/api) :white_small_square: [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) :white_small_square: [Flask](https://flask.palletsprojects.com/) :white_small_square: [WTForms](https://wtforms.readthedocs.io/) :white_small_square: [FlaskWTF](https://flask-wtf.readthedocs.io/) :white_small_square: [Flask-Login](https://flask-login.readthedocs.io/) :white_small_square: [Bootstrap](https://getbootstrap.com/) :white_small_square: [bootstrap-dark-5](https://vinorodrigues.github.io/bootstrap-dark-5/) :white_small_square: [jQuery](https://jquery.com/) :white_small_square: [Dropzone.js](https://www.dropzone.dev/js/) :white_small_square: [SQLite](https://www.sqlite.org) :white_small_square: [RRDtool](https://oss.oetiker.ch/rrdtool/) :white_small_square: [javascriptRRD](http://javascriptrrd.sourceforge.net/) :white_small_square: [Flot](http://www.flotcharts.org/) :white_small_square: [FBI framebuffer imageviewer](https://github.com/kraxel/fbida)
