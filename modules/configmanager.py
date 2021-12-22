import configparser, subprocess, itertools, os, shutil
from modules.filteringmanager import filteringmanager
from modules.timermanager import timermanager
from modules.weathermanager import weathermanager
from modules.weatherstampmanager import weatherstampmanager
from modules.telebotmanager import telebotmanager
from modules.convertmanager import convertmanager
from misc.configprop import configprop
from misc.connection import connection

class configmanager:
	
	__SPI_CHECK1 = 'ls -l /dev/spidev*'
	__SPI_CHECK2 = 'lsmod | grep spi_'
	
	__ERROR_PARSE = "Error parsing {} configuration entry"
	__ERROR_SAVE = "Error saving config file!"
	
	__COMMENT_IND_OK = '# '
	__COMMENT_IND_NOK = '; '
	__SECTION_IND = '['
	__REPLACE_IND = ' '
	__VALUE_IND = '='
	
	__FILE_WRITE_FLAG = 'w'
	
	__DEFAULT_FILE = "misc/config.default"
	
	def __init__ (self, path:str):
		self.config = configparser.ConfigParser()
		self.__path = path
		self.__load_default_file()
		self.read_config()
		
		self.__COMMENTS = {}
		with open(self.__DEFAULT_FILE) as f:
			parse = str()
			for line in f:
				if line.startswith(self.__COMMENT_IND_OK): 
					parse = parse + str.strip(line).replace(self.__COMMENT_IND_OK, self.__REPLACE_IND)
				elif str.strip(line) and not line.startswith(self.__SECTION_IND) and not line.startswith(self.__COMMENT_IND_NOK):
					self.__COMMENTS[line.split(self.__VALUE_IND)[0]] = str.lstrip(parse)
					parse = str()
				
		self.__SETTINGS = [
			configprop('cred_file', self, prop_type=configprop.FILE_TYPE),
			configprop('pickle_file', self, prop_type=configprop.FILE_TYPE),
			configprop('photo_convert_path', self, prop_type=configprop.FILE_TYPE),
			configprop('log_files', self, notempty=False),
			configprop('convert_bin_path', self, prop_type=configprop.FILE_TYPE),
			configprop('rrdtool_bin_path', self, prop_type=configprop.FILE_TYPE),
			configprop('slide_interval', self, minvalue=180, prop_type=configprop.INTEGER_TYPE),
			configprop('interval_mult', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('interval_mult_hotword', self, dependency='interval_mult'),
			configprop('interval_max_mult', self, dependency='interval_mult', minvalue=1, prop_type=configprop.INTEGER_TYPE),
			configprop('start_times', self, delimiter=',', prop_type=configprop.STRINGLIST_TYPE, length=7, special=configprop.special(timermanager.verify, ['start_times', 'stop_times'])),
			configprop('stop_times', self, delimiter=',', prop_type=configprop.STRINGLIST_TYPE, length=7, special=configprop.special(timermanager.verify, ['start_times', 'stop_times'])),
			configprop('allow_triggers', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('convert_option', self, prop_type=configprop.INTEGER_TYPE, possible=convertmanager.get_convert_options()),
			configprop('image_width', self, minvalue=1, prop_type=configprop.INTEGER_TYPE),
			configprop('image_height', self, minvalue=1, prop_type=configprop.INTEGER_TYPE),
			configprop('invert_colors', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('horizontal', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('auto_gamma', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('auto_level', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('normalize', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('brightness', self, minvalue=-100, maxvalue=100, prop_type=configprop.INTEGER_TYPE),
			configprop('contrast', self, minvalue=-100, maxvalue=100, prop_type=configprop.INTEGER_TYPE),
			configprop('background_color', self, possible=convertmanager.get_background_colors()),
			configprop('album_names', self, notempty=False),
			configprop('randomize', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('photos_from', self, notempty=False, checkfunction=filteringmanager.verify, special=configprop.special(filteringmanager.verify_times, ['photos_from', 'photos_to'])),
			configprop('photos_to', self, notempty=False, checkfunction=filteringmanager.verify, special=configprop.special(filteringmanager.verify_times, ['photos_from', 'photos_to'])),
			configprop('no_photos', self, minvalue=1, notempty=False, prop_type=configprop.INTEGER_TYPE),
			configprop('sort_desc', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('show_weather', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('apikey', self, dependency='show_weather'),
			configprop('lat', self, dependency='show_weather'),
			configprop('lon', self, dependency='show_weather'),
			configprop('units', self, dependency='show_weather', possible=weathermanager.get_units()),
			configprop('position', self, dependency='show_weather', prop_type=configprop.INTEGER_TYPE, possible=weatherstampmanager.get_positions()),
			configprop('font', self, dependency='show_weather', minvalue=8, prop_type=configprop.INTEGER_TYPE),
			configprop('font_color', self, dependency='show_weather', possible=weatherstampmanager.get_colors()),
			configprop('use_telebot', self, prop_type=configprop.BOOLEAN_TYPE, resetneeded=True),
			configprop('token', self, dependency='use_telebot', checkfunction=telebotmanager.check_token),
			configprop('chat_id', self, notempty=False, dependency='use_telebot', delimiter=',', prop_type=configprop.INTLIST_TYPE),
			configprop('use_web', self, prop_type=configprop.BOOLEAN_TYPE, resetneeded=True),
			configprop('web_host', self, dependency='use_web', checkfunction=connection.is_ip),
			configprop('web_port', self, minvalue=1, maxvalue=65535, dependency='use_web', prop_type=configprop.INTEGER_TYPE),
			configprop('show_stats', self, dependency='use_web', prop_type=configprop.BOOLEAN_TYPE)
		]
		
		for p in self.__CONFIG_STRING.keys():
			try:
				self.get_property(p)
			except Exception:
				self.__SETTINGS.append(configprop(p,self))
				
	def read_config(self):
		if not os.path.exists(self.__path):
			shutil.copy(self.__DEFAULT_FILE, self.__path)
		
		with open(self.__path) as f:
			self.config.read_file(f)
			
		for sect in self.def_config.sections():
			for prop in list(dict(self.def_config.items(sect)).keys()):
				try:
					self.config.get(sect, prop)
				except Exception:
					self.config.set(sect, prop, self.def_config.get(sect, prop))
					pass
				
		self.__CONFIG_STRING = {}
		for sect in self.def_config.sections():
			for prop in list(dict(self.def_config.items(sect)).keys()):
				self.__CONFIG_STRING[prop] = sect
				
		self.save()
				
	def get (self, name:str):
		ret = ''
		
		try:
			ret = self.config.get(self.__CONFIG_STRING[name], name)
		except Exception as e: 
			raise Exception(self.__ERROR_PARSE.format(name))		
		return ret
	
	def __load_default_file(self):
		self.def_config = configparser.ConfigParser()
		with open(self.__DEFAULT_FILE) as f:
			self.def_config.read_file(f)
	
	def getint (self, name:str):
		ret = 0
		
		try:
			ret = self.config.getint(self.__CONFIG_STRING[name], name)
		except Exception as e: 
			raise Exception(self.__ERROR_PARSE.format(name))		
		return ret
	
	def set (self, name:str, val):
		self.config.set(self.__CONFIG_STRING[name], name, val)
		
	def save (self):
		filestr =''
		
		iterator = itertools.cycle(self.__CONFIG_STRING.keys())
		nex = next(iterator)
		
		with open(self.__DEFAULT_FILE) as f:
			for line in f:
				if line.startswith(self.__COMMENT_IND_OK) or line.startswith(self.__SECTION_IND) or line.startswith(self.__COMMENT_IND_NOK) or not str.strip(line):
					filestr = filestr + line
				elif nex in line:					
					filestr += "{}{}{}\n".format(nex, self.__VALUE_IND, self.get(nex))
					nex = next(iterator)
				else:
					raise Exception(self.__ERROR_SAVE)
		
		with open(self.__path, self.__FILE_WRITE_FLAG) as f:
			f.write(filestr)
	
	def get_default (self, name:str):
		proper = self.get_property(name)
		return proper.get_default() if str(proper.get_default()) else ''
	
	def get_possible_values (self, name:str):
		proper = self.get_property(name)
		return proper.get_possible()
	
	def get_comment (self, name:str):
		ret = None
		
		try:
			ret = self.__COMMENTS[name]
		except Exception as e: 
			raise Exception(self.__ERROR_PARSE.format(name))		
		return ret
	
	def get_property (self, name:str):
		ret = None
		
		try:
			ret = next((prop for prop in self.__SETTINGS if prop.get_name() == name), None)
			if not ret: 
				raise Exception
		except Exception as e: 
			raise Exception(self.__ERROR_PARSE.format(name))		
		return ret
	
	def validate (self, name:str):
		proper = self.get_property(name)
		proper.validate()
		
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
	
	def get_sections(self):
		return self.config.sections()
	
	def get_section_properties(self, section):
		return [prop for prop in self.__CONFIG_STRING.keys() if self.__CONFIG_STRING[prop] == section]
	
	def verify (self):
		for prop in self.__SETTINGS:
			prop.validate()
	
	def verify_exceptions (self):
		for prop in self.__SETTINGS:
			try:			
				prop.validate()
			except Warning:
				pass
			except Exception as e:
				raise e
	
	def verify_warnings (self):
		for prop in self.__SETTINGS:
			try:			
				prop.validate()
			except Warning as e:
				raise e
			except Exception:
				pass