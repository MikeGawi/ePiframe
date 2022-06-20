import configparser, itertools, os, shutil
from misc.configprop import configprop
from abc import ABC, abstractmethod

class configbase(ABC):
	
	__ERROR_PARSE = "Error parsing {} configuration entry"
	__ERROR_SAVE = "Error saving config file!"
	
	__COMMENT_IND_OK = '# '
	__COMMENT_IND_NOK = '; '
	__SECTION_IND = '['
	__REPLACE_IND = ' '
	__VALUE_IND = '='
	
	__FILE_WRITE_FLAG = 'w'
	
	SETTINGS = []
	
	def __init__ (self, path:str, defpath:str, outerclass = None):		
		self.config = configparser.ConfigParser()
		self.__path = path
		self.__defpath = defpath
		self.__load_default_file()
		save = self.read_config()
		self.main_class = outerclass
		
		self.__COMMENTS = {}
		with open(self.__defpath) as f:
			parse = str()
			for line in f:
				if line.startswith(self.__COMMENT_IND_OK): 
					parse = parse + (" " if parse else "") + str.strip(line).replace(self.__COMMENT_IND_OK, self.__REPLACE_IND)
				elif str.strip(line) and not line.startswith(self.__SECTION_IND) and not line.startswith(self.__COMMENT_IND_NOK):
					self.__COMMENTS[line.split(self.__VALUE_IND)[0]] = str.lstrip(parse)
					parse = str()

		self.load_settings()			
		
		for p in self.__CONFIG_STRING.keys():
			try:
				self.get_property(p)
			except Exception:
				self.SETTINGS.append(configprop(p,self))
				
		for prop in self.SETTINGS:
			prop.convert()
			
		if save: self.save()
	
	def get_path(self):
		return self.__path
	
	def get_default_path(self):
		return self.__defpath
	
	@abstractmethod
	def load_settings(self):
		raise NotImplementedError
	
	def legacy_convert(self):
		pass
	
	def read_config(self):
		ret = False
		if not os.path.exists(self.__path):
			shutil.copy(self.__defpath, self.__path)
		
		with open(self.__path) as f:
			self.config.read_file(f)
		
		self.__CONFIG_STRING = {}
		for sect in self.config.sections():
			for prop in list(dict(self.config.items(sect)).keys()):
				self.__CONFIG_STRING[prop] = sect
		
		self.legacy_convert()
				
		for sect in self.def_config.sections():
			for prop in list(dict(self.def_config.items(sect)).keys()):
				try:
					if not self.config.has_section(sect): 
						self.config.add_section(sect)
						ret = True
					self.config.get(sect, prop)
				except Exception:
					val = str()
					try: 
						val = self.get(prop)
					except Exception:
						pass
					self.config.set(sect, prop, val if val else self.def_config.get(sect, prop))
					ret = True
					pass
				
		self.__CONFIG_STRING = {}
		for sect in self.def_config.sections():
			for prop in list(dict(self.def_config.items(sect)).keys()):
				self.__CONFIG_STRING[prop] = sect
		return ret
				
	def get (self, name:str):
		ret = ''
		
		try:
			ret = self.config.get(self.__CONFIG_STRING[name], name)
		except Exception as e: 
			raise Exception(self.__ERROR_PARSE.format(name))		
		return ret
	
	def __load_default_file(self):
		self.def_config = configparser.ConfigParser()
		with open(self.__defpath) as f:
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
		
	def save (self, pathe=None):
		path = self.__path if pathe == None else pathe
		filestr =''
		
		iterator = itertools.cycle(self.__CONFIG_STRING.keys())
		nex = next(iterator)
		
		with open(self.__defpath) as f:
			for line in f:
				if line.startswith(self.__COMMENT_IND_OK) or line.startswith(self.__SECTION_IND) or line.startswith(self.__COMMENT_IND_NOK) or not str.strip(line):
					filestr = filestr + line
				elif nex in line:					
					filestr += "{}{}{}\n".format(nex, self.__VALUE_IND, self.get(nex))
					nex = next(iterator)
				else:
					raise Exception(self.__ERROR_SAVE)
		
		with open(path, self.__FILE_WRITE_FLAG) as f:
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
			ret = next((prop for prop in self.SETTINGS if prop.get_name() == name), None)
			if not ret: 
				raise Exception
		except Exception as e: 
			raise Exception(self.__ERROR_PARSE.format(name))		
		return ret
	
	def validate (self, name:str):
		proper = self.get_property(name)
		proper.validate()
		
	def get_sections(self):
		return self.config.sections()
	
	def get_section_properties(self, section):
		return [prop for prop in self.__CONFIG_STRING.keys() if self.__CONFIG_STRING[prop] == section]
	
	def verify (self):
		for prop in self.SETTINGS:
			prop.validate()
	
	def verify_exceptions (self):
		for prop in self.SETTINGS:
			try:			
				prop.validate()
			except Warning:
				pass
			except Exception as e:
				raise e
	
	def verify_warnings (self):
		for prop in self.SETTINGS:
			try:			
				prop.validate()
			except Warning as e:
				raise e
			except Exception:
				pass