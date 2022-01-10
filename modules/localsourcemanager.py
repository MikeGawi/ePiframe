import pandas as pd
import os, glob, itertools, datetime

class localsourcemanager:

	def __init__ (self, dire, recur, extensions):
		self.__directory = dire if not dire.endswith('/') else dire[0: -1]
		self.__scope = '/**/*.' if recur else '/*.'
		self.__extensions = extensions
	
	def __format_timestamp (self, ts):
		return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")+"Z"
	
	def get_files(self):
		return list(itertools.chain(*[glob.glob(self.__directory + self.__scope + e.lower()) + glob.glob(self.__directory + self.__scope + e.upper()) for e in self.__extensions]))
	
	def get_dates(self, fileslist):
		return [self.__format_timestamp(os.stat(file).st_mtime) for file in fileslist]
	
	def get_local_photos(self, idlabel, creationlabel, sourcelabel, source):
		photos = pd.DataFrame()		
		
		files = self.get_files()		
		if files and len(files) > 0:
			files = sorted(files)			
			dates = self.get_dates(files)
			photos = pd.DataFrame(list(zip(files, dates)), columns=[idlabel, creationlabel])
			photos[sourcelabel] = source
		
		return photos	
	
	@classmethod
	def create_dir(self, dire):
		if not os.path.exists(dire): 
			os.makedirs(dire, exist_ok=True)
		return dire