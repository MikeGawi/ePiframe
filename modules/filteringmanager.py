import pandas as pd
import dateutil
from dateutil.parser import parser
from datetime import datetime 

class filteringmanager:
	
	__DATE_MASK = '%Y-%m-%d %H:%M:%S'
	__DATE_MASK_OLD = '%Y.%m.%d %H:%M:%S'
	
	__SORTING_VALUES = ['none', 'asc', 'desc']
	
	__ERROR_SVALUE_TEXT = 'Configuration sorting should be one of {}'
	
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
	def sort (self, photos, header:str, column, typ):
		ret = photos
		
		if not typ == self.__SORTING_VALUES[0]:
			photos[header] = pd.to_datetime(column)
			if typ == self.__SORTING_VALUES[-1]:
				ret = photos.sort_values(by = header, ascending = False)
			else:
				ret = photos.sort_values(by = header, ascending = True)
		
		return ret
	
	@classmethod		
	def convert (self, date):
		res = date	
		try: 
			datetime.strptime(date, self.__DATE_MASK_OLD)
			res = date.replace(".", "-")
		except Exception:
			pass
	
		return res
	
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
				
	@classmethod		
	def verify_sorting (self, val):
		if not val in [k.lower() for k in self.__SORTING_VALUES]:
			raise Exception(self.__ERROR_SVALUE_TEXT.format([k.lower() for k in self.__SORTING_VALUES]))
			
	@classmethod		
	def get_sorting (self):
		return [k.lower() for k in self.__SORTING_VALUES]
	
	#legacy
	@classmethod		
	def get_descending (self, val):
		return self.__SORTING_VALUES[-1] if val else self.__SORTING_VALUES[0]