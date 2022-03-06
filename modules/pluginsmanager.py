import os, importlib
from glob import glob

class pluginsmanager:

	__PLUGINS_DIR = 'plugins/'
	__PLUGIN_NAME = '_plugin.py'
	__PLUGIN_CLASS = '_plugin'
	
	__PLUGINS = []
	
	def __init__(self, path, pidmgr, logging, config):
		self.__config = config		
		self.__pidmgr = pidmgr
		self.__logging = logging
		self.__globalpath = path
		
		self.discover()
		
	def discover(self):
		lists = glob(self.__PLUGINS_DIR + '**/' + self.__PLUGIN_NAME)
		
		if lists and len(lists) > 0:
			for el in lists: 
				mod = os.path.dirname(el).replace('/', '.')
				module = importlib.import_module(mod + '.' + self.__PLUGIN_CLASS)
				self.__PLUGINS.append (module.plugin(os.path.join(os.path.realpath(self.__globalpath), os.path.dirname(el)), self.__pidmgr, self.__logging, self.__config))
			
	def get_plugins(self):
		return self.__PLUGINS
	
	def get_enabled(self):
		return [x for x in self.__PLUGINS if x.is_enabled()]
	
	def plugin_source (self):
		return [p for p in self.get_enabled() if p.is_function_used('add_photo_source')]
	
	def get_plugin_source (self):
		return [p for p in self.get_enabled() if p.SOURCE]
	
	def plugin_source_get_file (self, plugin):
		return plugin.is_function_used('add_photo_source_get_file')
	
	def plugin_photos_list (self):
		return [p for p in self.get_enabled() if p.is_function_used('change_photos_list')]
	
	def plugin_preprocess (self):
		return [p for p in self.get_enabled() if p.is_function_used('preprocess_photo')]
		
	def plugin_postprocess (self):
		return [p for p in self.get_enabled() if p.is_function_used('postprocess_photo')]
	
	def plugin_api (self):
		return [p for p in self.get_enabled() if p.is_function_used('extend_api')]
	
	def plugin_website (self):
		return [p for p in self.get_enabled() if p.is_function_used('add_website')]
	
	def plugin_action (self):
		return [p for p in self.get_enabled() if p.is_function_used('add_action')]
	
	def plugin_service_thread (self):
		return [p for p in self.get_enabled() if p.is_function_used('add_service_thread')]