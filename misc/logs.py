import time, os
import logging
import zlib, gzip
from time import strftime
from datetime import datetime 
from time import gmtime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

class logs:
	
	def __init__(self, path=""):
		if path:
			self.__path = path

			pathos = Path(path)
			pathos.parent.mkdir(parents=True, exist_ok=True) 

			self.__logger = logging.getLogger("ePiframe")
			self.__logger.setLevel(logging.INFO)

			handler = TimedRotatingFileHandler(path, when="midnight", interval=1, backupCount=6)

			def namer(name):
				return name + ".gz"

			def rotator(source, dest):
				with open(source, "rb") as sf:
					data = sf.read()
					with gzip.open(dest, "wb") as df:
						df.write(data)
				os.remove(source)

			handler.rotator = rotator
			handler.namer = namer
		
			self.__logger.addHandler(handler)
		else:
			self.__path = ""
	
	@classmethod
	def show_log (self, text:str):
		timeObj = datetime.now().strftime("%Y-%m-%d %H:%M:%S :")
		print(timeObj, text)

	@classmethod		
	def start_time (self):    
		return (time.time())

	@classmethod
	def end_time (self):
		return (time.time())

	@classmethod
	def execution_time (self, startTime, endTime):
	   return (strftime(" %H:%M:%S",gmtime(int('{:.0f}'.format(float(str((endTime - startTime))))))))
	
	def log (self, text:str, silent = False):
		timeObj = datetime.now().strftime("%Y-%m-%d %H:%M:%S :")
		if not silent:
			print(timeObj, text)
		if self.__path:
			self.__logger.info(timeObj + " " + text)