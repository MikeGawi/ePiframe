import pandas as pd
import dateutil
from dateutil.parser import parser
from datetime import datetime 

class filteringmanager:
	
	__DATE_MASK = '%Y.%m.%d %H:%M:%S'
	
	@classmethod
	def filter_by_from_date (self, photos, date:str, header:str):
		startDateTime = datetime.strptime(date, self.__DATE_MASK)
		timeFilter = (photos.apply(lambda row: dateutil.parser.isoparse(row[header]).replace(tzinfo=None) > startDateTime, axis = 1))
		return photos[timeFilter]
	
	@classmethod
	def filter_by_to_date (self, photos, date:str, header:str):
		startDateTime = datetime.strptime(date, self.__DATE_MASK)
		timeFilter = (photos.apply(lambda row: dateutil.parser.isoparse(row[header]).replace(tzinfo=None) < startDateTime, axis = 1))
		return photos[timeFilter]
	
	@classmethod
	def filter_by_number (self, photos, number:int):
		ret = photos
		
		if (number > 0):
			ret = photos.head(number)
		
		return ret
	
	@classmethod
	def sort (self, photos, header:str, column, desc:bool):
		ret = photos
		
		if desc:
			photos[header] = pd.to_datetime(column)
			ret = photos.sort_values(by = header, ascending = False)
		
		return ret
	
	@classmethod		
	def verify (self, date):
		datetime.strptime(date, self.__DATE_MASK)
		
	@classmethod		
	def verify_times (self, dates):
		date1 = dates[0]	
		date2 = dates[1]	
		if date1 and date2:
			if datetime.strptime(date1, self.__DATE_MASK) > datetime.strptime(date2, self.__DATE_MASK):
				raise Exception('Configuration photos_from time is older than photos_to!')