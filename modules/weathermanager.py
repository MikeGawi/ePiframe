import requests

class weathermanager:
	
	__UNITS_VALUES = ['metric', 'imperial']

	def __init__ (self, apikey, units, lat, lon):
		self.__apikey = apikey
		self.__units = units
		self.__lat = lat
		self.__lon = lon

	def get_response_json (self, url:str, timeout:int):
		try:
			ret = requests.get(url, timeout=timeout)
			ret.raise_for_status()		
		except requests.ConnectionError as exc:
			ret = None
		
		return ret.json() if ret else None
		
	def send_request (self, baseurl, timeout):
		url = baseurl.format(self.__lat, self.__lon, self.__units, self.__apikey)
		self.__data = self.get_response_json(url, timeout)
		
	def get_data (self):
		return self.__data
		
	def get_weathericon (self, maintag, position, icontag):
		return self.__data[maintag][position][icontag]
		
	def get_temperature (self, maintag, temptag):
		return self.__data[maintag][temptag]
	
	@classmethod		
	def verify_units (self, val):
		if not val in self.__UNITS_VALUES:
			raise Exception('Configuration units should be one of {}'.format(self.__UNITS_VALUES))
	
	@classmethod		
	def is_metric (self, val):
		return val == self.__UNITS_VALUES[0]