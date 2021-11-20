import os
import pandas as pd

class randommanager:
	
	__COLUMN_NAME = "random"
	
	def __init__ (self, path:str, photos, idheader:str):
		self.__path = path
		self.__data = photos.copy().get([idheader])
		self.__data[self.__COLUMN_NAME] = 0
		self.__idheader = idheader
		
		olddata = pd.DataFrame()
		
		try:
			if os.path.exists(path):
				olddata = pd.read_csv(self.__path)	
		except Exception:
			pass
		
		if not olddata.empty:
			self.__data.loc[self.__data.id.isin(olddata.id), [self.__COLUMN_NAME]] = olddata[self.__COLUMN_NAME]
			
		self.__data[self.__COLUMN_NAME].fillna(0, inplace=True)
		
	def __save (self):
		self.__data.to_csv(self.__path)
	
	def get_random (self, lastid:str, nosave=False):
		randoms = self.__data.copy().loc[self.__data[self.__COLUMN_NAME] != 1]
		
		if randoms.empty:
			self.__data[self.__COLUMN_NAME] = 0
			randoms = self.__data
				
		#prevent last photo showing again after full cycle
		if lastid and len(randoms.axes[0]) > 1:
			indexNames = randoms[ randoms[self.__idheader] == lastid ].index
			randoms.drop(indexNames, inplace=True, errors='ignore')

		sample = randoms.sample()
		
		index = sample.index.values[0]
		
		self.__data.at[index, self.__COLUMN_NAME] = 1
		
		if not nosave:
			self.__save()
		
		return index