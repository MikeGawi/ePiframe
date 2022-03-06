import os

class pluginbase():
	
	CONFIG_FILE = 'config.cfg'	
	DEFAULT_CONFIG_FILE = 'default/config.default'
	SOURCE = None
	
	def __init__ (self, path, pidmgr, logging, globalconfig):
		self.pidmgr = pidmgr
		self.logging = logging
		self.globalconfig = globalconfig
		self.path = path
		self.load_config()
	
	def is_function_used (self, func):
		return getattr(type(self),func) != getattr(pluginbase, func)
		
	def load_config (self):
		self.config = self.configmgr(os.path.join(self.path, self.CONFIG_FILE), os.path.join(self.path, self.DEFAULT_CONFIG_FILE), self)
		
	def is_enabled (self):
		return bool(self.config.getint('is_enabled'))
	
	def add_photo_source (self, idlabel, creationlabel, sourcelabel, photomgr):
		pass
	
	def add_photo_source_get_file (self, photo, path, filename, idlabel, creationlabel, sourcelabel, photomgr):
		pass
	
	def change_photos_list (self, idlabel, creationlabel, sourcelabel, photo_list, photomgr, indexmgr, filteringmgr):
		pass
	
	def preprocess_photo (self, orgphoto, is_horizontal, convertmgr, photo, idlabel, creationlabel, sourcelabel):
		pass
		
	def postprocess_photo (self, finalphoto, width, height, is_horizontal, convertmgr, photo, idlabel, creationlabel, sourcelabel):
		pass
	
	def extend_api (self, webmgr, usersmgr, backend):
		pass
	
	def add_website (self, webmgr, usersmgr, backend):
		pass
	
	def add_action (self, webmgr, usersmgr, backend):
		pass
	
	def add_service_thread (self, service, backend):
		pass	