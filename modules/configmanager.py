import sys, os
import configparser
import subprocess
from modules.filteringmanager import filteringmanager
from modules.timermanager import timermanager

class configmanager:
	
	__SPI_CHECK1 = 'ls -l /dev/spidev*'
	__SPI_CHECK2 = 'lsmod | grep spi_'
		
	__CONFIG_STRING = {
		'cred_file' 				: 'Credentials',
		'pickle_file' 				: 'Credentials',
		
		'photo_convert_path' 		: 'Files and paths',
		'photo_download_name' 		: 'Files and paths',
		'photo_convert_filename' 	: 'Files and paths',
		'convert_bin_path' 			: 'Files and paths',
		'photo_index_file' 			: 'Files and paths',
		'photo_list_file' 			: 'Files and paths',
		'pid_file' 					: 'Files and paths',
		'interval_mult_file'		: 'Files and paths',
		
		'display' 					: 'Display settings',
		'slide_interval' 			: 'Display settings',
		'interval_mult' 			: 'Display settings',
		'interval_max_mult' 		: 'Display settings',
		'interval_mult_hotword'		: 'Display settings',
		'start_times'	 			: 'Display settings',
		'stop_times'	 			: 'Display settings',
		
		'convert_option' 			: 'Image settings',
		'image_width' 				: 'Image settings',
		'image_height' 				: 'Image settings', 
		'invert_colors'				: 'Image settings',
		'background_color'			: 'Image settings', 		
		'horizontal'				: 'Image settings', 		
		
		'album_names' 				: 'Album settings',
		'randomize' 				: 'Album settings',
		'photos_from' 				: 'Album settings',
		'photos_to' 				: 'Album settings',
		'no_photos' 				: 'Album settings',
		'sort_desc' 				: 'Album settings'
	}
	
	def __init__ (self, path:str):
		self.config = configparser.ConfigParser()
		
		with open(path) as f:
			self.config.read_file(f)
						
	def get (self, name:str):
		ret = None
		
		try:
			ret = self.config.get(self.__CONFIG_STRING[name], name)
		except Exception as e: 
			raise Exception("Error parsing {} configuration entry".format(name))		
		return ret
		
	def getint (self, name:str):
		ret = 0
		
		try:
			ret = self.config.getint(self.__CONFIG_STRING[name], name)
		except Exception as e: 
			raise Exception("Error parsing {} configuration entry".format(name))		
		return ret
	
	def check_system (self):
		ret = False;
		
		process = subprocess.Popen(self.__SPI_CHECK1, shell=True, stdout=subprocess.PIPE)
		process.wait()
		out, err = process.communicate()
		
		process = subprocess.Popen(self.__SPI_CHECK2, shell=True, stdout=subprocess.PIPE)
		process.wait()
		out2, err2 = process.communicate()
		
		if not err and out2:
			ret = True

		return ret		
	
	def verify (self):
		if not self.get('cred_file'):
			raise Exception('Credentials cred_file configuration entry is missing!')
		if not self.get('pickle_file'):
			raise Exception('Pickle file pickle_file configuration entry is missing!')
		if not os.path.exists(self.get('cred_file')):
			raise FileNotFoundError("Error! {} - Credentials file does not exist!".format(self.get('cred_file')))
		if not self.get('photo_convert_path'):
			raise Exception('Configuration photo_convert_path entry is missing!')
		if not os.path.exists(self.get('photo_convert_path')):
			raise FileNotFoundError("Error! {} - image convert path does not exist!".format(self.get('photo_convert_path')))
		if not self.get('photo_download_name'):
			raise Exception('Configuration photo_download_name entry is missing!')
		if not self.get('photo_convert_filename'):
			raise Exception('Configuration photo_convert_filename entry is missing!')
		if not self.get('convert_bin_path'):
			raise Exception('Configuration convert_bin_path entry is missing!')
		if not os.path.exists(self.get('convert_bin_path')):
			raise FileNotFoundError("Error! {} - image convert binary does not exist! is ImageMagick installed? ".format(self.get('convert_bin_path')))
		if not self.get('photo_index_file'):
			raise Exception('Configuration photo_index_file entry is missing!')
		if not self.get('photo_list_file'):
			raise Exception('Configuration photo_list_file entry is missing!')
		if not self.get('pid_file'):
			raise Exception('Configuration pid_file entry is missing!')
		if not self.get('display'):
			raise Exception('Configuration display entry is missing!')
		if not self.get('slide_interval'):
			raise Exception('Configuration slide_interval entry is missing!')
		self.getint('convert_option')
		if not self.get('convert_option'):
			raise Exception('Configuration convert_option entry is missing!')
		self.getint('convert_option')
		if not self.get('image_width'):
			raise Exception('Configuration image_width entry is missing!')
		self.getint('image_width')
		if not self.get('image_height'):
			raise Exception('Configuration image_height entry is missing!')
		self.getint('image_height')
		if not self.get('invert_colors'):
			raise Exception('Configuration invert_colors entry is missing!')
		self.getint('invert_colors')
		if not self.get('horizontal'):
			raise Exception('Configuration horizontal entry is missing!')
		self.getint('horizontal')
		if not self.get('background_color'):
			raise Exception('Configuration background_color entry is missing!')
		if not self.get('randomize'):
			raise Exception('Configuration randomize entry is missing!')
		self.getint('randomize')
		if self.get('no_photos'):
			self.getint('no_photos')
		if self.get('sort_desc'):
			self.getint('sort_desc')
		
		if self.getint('interval_mult') == 1:
			if not self.get('interval_mult_hotword'):
				raise Exception('Configuration interval_mult_hotword entry is missing!')
			self.getint('interval_max_mult')
			if not self.get('interval_mult_file'):
				raise Exception('Pickle file interval_mult_file configuration entry is missing!')
			
		if self.get('photos_from'):
			filteringmanager.verify(self.get('photos_from'))
		if self.get('photos_to'):
			filteringmanager.verify(self.get('photos_to'))
			
		if self.get('photos_from') and self.get('photos_to'):
			filteringmanager.verify_times(self.get('photos_from'),self.get('photos_to'))
			
		if not self.get('start_times'):
			raise Exception('Configuration start_times entry is missing!')
		if not self.get('stop_times'):
			raise Exception('Configuration stop_times entry is missing!')
			
		if not len(self.get('start_times').split(',')) == 7:
			raise Exception('Configuration start_times is missing all values!')
			
		if not len(self.get('stop_times').split(',')) == 7:
			raise Exception('Configuration stop_times is missing all values!')
		
		timermanager.verify (self.get('start_times').split(','), self.get('stop_times').split(','))