import sys,os

class intervalmanager:
	
	__path = None

	def __init__ (self, path:str):
		self.__path = path
		
	def read (self):
		interval = -1
		
		if os.path.exists(self.__path):
			with open(self.__path, 'r') as f:
				lines=f.readlines()	
				interval=str(lines[0]).rstrip()
				f.close()
		return int(interval)
		
	def save (self, interval:int):
		if interval <= 1:
			self.remove()
		else:
			with open(self.__path , 'w') as f:
				f.write(str(interval))
				f.close()
			
	def remove (self):
		if os.path.exists(self.__path):
			os.remove(self.__path)
		
	def save_interval (self, interval:str, hotword:str, max:int):
		if hotword.lower() in interval.lower():
			inter = interval.lower().replace(hotword.lower(), '').strip()
			try:
				self.save(max) if int(inter) > max else self.save(int(inter))
			except Exception:
				pass