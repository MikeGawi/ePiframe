import sys
import os
import importlib

libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')

if os.path.exists(libdir):
    sys.path.append(libdir)

from PIL import Image	
#!!! more displays on https://github.com/waveshare/e-Paper

class displaymanager:
	
	__PROCESS_NAME = 'fbi'
	__DISPLAY_PHOTO_CODE = "sudo killall -SIGKILL {} > /dev/null 2>&1;sudo {} -vt {} -noverbose -a {} > /dev/null 2>&1"
	__DISPLAY_VALUES = ['SPI', 'HDMI']
	
	__ERROR_SVALUE_TEXT = 'Configuration display_type should be one of {}'

	def __init__ (self, display:str, distype='', binary='', vt=1):
		self.__usehdmi = self.is_hdmi(distype)
		self.__binary = binary
		self.__vt = vt
		self.__display = display
		
		if not self.__usehdmi:
			#it's like : from waveshare_epd import 'display'
			module = importlib.import_module("waveshare_epd." + display)

			self.__epd = module.EPD()
			self.__epd.init()
	
	def clear (self):
		if not self.__usehdmi:
			self.__epd.Clear()
		
	def power_off (self):
		if not self.__usehdmi:
			self.__epd.sleep()
			
	def show_image (self, photo_path:str):
		if not self.__usehdmi:
			try:
				#uncomment if experiencing image shadowing
				#self.clear()
				image = Image.open(photo_path)
				self.__epd.display(self.__epd.getbuffer(image))
				self.power_off()
			except KeyboardInterrupt: 
				self.__epd.epdconfig.module_exit()
				raise
		else:
			 os.popen(self.__DISPLAY_PHOTO_CODE.format(self.__PROCESS_NAME, self.__binary, self.__vt, photo_path))
	
	def get_display (self):
		return self.__display
	
	def get_vt (self):
		return self.__vt
	
	def is_display_hdmi (self):
		return self.__usehdmi
	
	@classmethod
	def verify_display (self, val):
		if not val in [k for k in self.__DISPLAY_VALUES]:
			raise Exception(self.__ERROR_SVALUE_TEXT.format([k for k in self.__DISPLAY_VALUES]))
			
	@classmethod		
	def get_displays (self):
		return [k for k in self.__DISPLAY_VALUES]
	
	@classmethod		
	def get_hdmi (self):
		return self.__DISPLAY_VALUES[1]
	
	@classmethod		
	def get_spi (self):
		return self.__DISPLAY_VALUES[0]
	
	@classmethod		
	def is_hdmi (self, val):
		return True if val and val.lower() == self.__DISPLAY_VALUES[1].lower() else False