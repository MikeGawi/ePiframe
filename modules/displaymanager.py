import sys
import os
import importlib

libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')

if os.path.exists(libdir):
    sys.path.append(libdir)

from PIL import Image

#!!! more displays on https://github.com/waveshare/e-Paper

class displaymanager:

	def __init__ (self, display:str):
		#it's like : from waveshare_epd import 'display'
		module = importlib.import_module("waveshare_epd." + display)
		
		self.__epd = module.EPD()
		self.__epd.init()
	
	def clear (self):
		self.__epd.Clear()
		
	def power_off (self):
		self.__epd.sleep()
		self.__epd.Dev_exit()
		
	def show_image (self, photo_path:str):
		try:
			#uncomment if experiencing image shadowing
			#self.clear()
			image = Image.open(photo_path)
			self.__epd.display(self.__epd.getbuffer(image))
			self.power_off()
		except KeyboardInterrupt: 
			self.__epd.Dev_exit()
			raise