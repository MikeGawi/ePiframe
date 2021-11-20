import os

class configprop:
	
	STRING_TYPE = 'STRING'
	FILE_TYPE = 'FILE'
	INTEGER_TYPE = 'INTEGER'
	BOOLEAN_TYPE = 'BOOLEAN'
	STRINGLIST_TYPE = 'STRINGLIST'
	INTLIST_TYPE = 'INTLIST'
	
	STRING_ERROR_MSG = "{} configuration entry is missing!"
	FILE_ERROR_MSG = "{} configuration entry path does not exist!"
	INT_ERROR_MSG = "{} configuration entry in not an integer value!"
	BOOL_ERROR_MSG = "{} configuration entry in not a boolean (0 or 1) value!"
	MIN_ERROR_MSG = "{} configuration entry should be >= than {}!"
	MAX_ERROR_MSG = "{} configuration entry should be <= than {}!"
	LENGTH_ERROR_MSG = "{} configuration entry is missing all values!"
	INTLIST_ERROR_MSG = "{} configuration entry not all values are integer!"
	CHECK_ERROR_MSG = "{} configuration entry error: {}"
	CHECK_WARN_MSG = "{} configuration entry warning: {}"
	POSSIBLE_ERROR_MSG = "{} configuration entry value should be one of the {}"
	
	class special:
		WARNING_TYPE = 'WARNING'
		EXCEPTION_TYPE = 'EXCEPTION'
		
		def __init__ (self, function, args, exctype=EXCEPTION_TYPE):
			self.func = function
			self.args = args
			self.exctype = exctype			
	
	def __init__ (self, name, configmanager, prop_type=STRING_TYPE, notempty=True, dependency=None, minvalue=None, maxvalue=None, checkfunction=None, special=None, length=None, delimiter=None, possible=None, resetneeded=False):
		self.__type = prop_type
		self.__name = name
		self.__dependency = dependency
		self.__minvalue = minvalue
		self.__maxvalue = maxvalue
		self.__checkfunction = checkfunction
		self.__special = special
		self.__length = length
		self.__delimiter = delimiter
		self.__notempty = notempty
		self.__configmanager = configmanager
		self.__possible = possible
		self.__resetneeded = resetneeded
		
		is_break = False
		for sect in self.__configmanager.def_config.sections():
			if is_break:
				break
			for prop in list(dict(self.__configmanager.def_config.items(sect)).keys()):
				if prop == name:
					if self.__type == self.BOOLEAN_TYPE or self.__type == self.INTEGER_TYPE:
						val = self.__configmanager.def_config.get(sect, prop)	
						if val:
							self.__default = int(val)
						else:
							self.__default = val
						is_break = True
						break
					else:
						self.__default = self.__configmanager.def_config.get(sect, prop)
						is_break = True
						break
	
	def get_name(self):
		return self.__name
	
	def get_type(self):
		return self.__type
	
	def get_dependency(self):
		return self.__dependency
	
	def get_resetneeded(self):
		return self.__resetneeded
	
	def get_default(self):
		return self.__default
	
	def get_possible(self):
		ret = self.__possible
		
		if self.__type == self.BOOLEAN_TYPE:
			ret = list(range(2))
		
		return ret
	
	def validate(self):
		if self.__dependency and bool(self.__configmanager.getint(self.__dependency)) or not self.__dependency:
	
			if self.__notempty and not self.__configmanager.get(self.__name): raise Exception(self.STRING_ERROR_MSG.format(self.__name))
			
			if self.__configmanager.get(self.__name):
				if self.__type == self.FILE_TYPE:
					if not os.path.exists(self.__configmanager.get(self.__name)): raise Exception(self.FILE_ERROR_MSG.format(self.__name))
				elif self.__type == self.INTEGER_TYPE:
					try:
						self.__configmanager.getint(self.__name)
					except Exception:
						raise Exception(self.INT_ERROR_MSG.format(self.__name))

					if self.__minvalue:
						if self.__configmanager.getint(self.__name) < self.__minvalue:
							raise Exception(self.MIN_ERROR_MSG.format(self.__name, self.__minvalue))

					if self.__maxvalue:
						if self.__configmanager.getint(self.__name) > self.__maxvalue:
							raise Exception(self.MAX_ERROR_MSG.format(self.__name, self.__maxvalue))
				elif self.__type == self.BOOLEAN_TYPE:
					try:
						bool(self.__configmanager.getint(self.__name))
					except Exception:
						raise Exception(self.BOOL_ERROR_MSG.format(self.__name))
				elif self.__type == self.STRINGLIST_TYPE:
					if self.__length and not len(self.__configmanager.get(self.__name).split(self.__delimiter)) == self.__length: raise Exception(self.LENGTH_ERROR_MSG.format(self.__name))
				elif self.__type == self.INTLIST_TYPE:
					if self.__length and not len(self.__configmanager.get(self.__name).split(self.__delimiter)) == self.__length: raise Exception(self.LENGTH_ERROR_MSG.format(self.__name))
					try:
						[int(x) for x in self.__configmanager.get(self.__name).split(self.__delimiter)]
					except Exception as e:
						raise Exception(self.INTLIST_ERROR_MSG.format(self.__name))

				if self.__possible:
					if not self.__configmanager.get(self.__name) in [str(x) for x in self.__possible]:
							raise Exception(self.POSSIBLE_ERROR_MSG.format(self.__name, self.__possible))				
				
				if self.__checkfunction: 
					try:
						self.__checkfunction(self.__configmanager.get(self.__name))
					except Exception as e:
						raise Exception(self.CHECK_ERROR_MSG.format(self.__name, e))						
				
				if self.__special:
					try:
						self.__special.func([self.__configmanager.get(n) for n in self.__special.args])
					except Exception as e:
						if self.__special.exctype == self.special.EXCEPTION_TYPE:
							raise Exception(self.CHECK_ERROR_MSG.format(self.__name, e))
						else:
							raise Warning(self.CHECK_WARN_MSG.format(self.__name, e))