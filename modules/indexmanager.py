import sys,os

class indexmanager:
	
	__index = -1
	__id = None
	__path = None

	def __init__ (self, path:str):
		self.__path = path
		
		#read index from file to change after each run
		if os.path.exists(path):
			with open(path, 'r') as f:
				lines=f.readlines()	
				if len(lines) == 2:
					self.__id=str(lines[0]).rstrip()
					self.__index=int(lines[1])
				f.close()
	
	def save (self):
		with open(self.__path , 'w') as f:
			f.write(str(self.__id))
			f.write("\n")
			f.write(str(self.__index))
			f.close()
	
	def get_index (self):
		return self.__index
	
	def get_id (self):
		return self.__id
	
	def set_index (self, val:int):
		self.__index = val
	
	def set_id (self, val:str):
		self.__id = val
		
	def check_index (self, max:int):
		self.__index = 0 if self.__index >= max else self.__index