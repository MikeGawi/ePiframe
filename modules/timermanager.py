from datetime import datetime, timedelta
from itertools import cycle, islice

class timermanager:

	__DATE_MASK = '%H:%M'
	__NO_TIME_MARK = '-'

	def __init__ (self, startTimes:str, endTimes:str):
		self.__startTimes = startTimes
		self.__endTimes = endTimes		

	def should_i_work_now(self):
		now = datetime.now()
		
		dow = now.weekday()
		yesterday = (datetime.now() - timedelta(1)).weekday()
		
		ret = False
		
		startTab = self.__startTimes[dow].strip()
		endTab = self.__endTimes[dow].strip()
		
		if startTab == self.__NO_TIME_MARK:
			ret = False
		elif now.time() < self.get_time_from_string(startTab).time() and self.__endTimes[yesterday].strip() == self.__NO_TIME_MARK:
			ret = True
		elif now.time() > self.get_time_from_string(startTab).time() and not self.__endTimes[dow].strip() == self.__NO_TIME_MARK:
			ret = now.time() > self.get_time_from_string(startTab).time() and now.time() < self.get_time_from_string(endTab).time()
		elif now.time() > self.get_time_from_string(startTab).time() and self.__endTimes[dow].strip() == self.__NO_TIME_MARK:
			ret = True
		
		return ret
	
	def when_i_work_next(self):
		now = datetime.now()
		dow = now.weekday()
		
		ret = datetime.now(datetime.now().astimezone().tzinfo)	
		nowTab = islice(cycle(self.__startTimes), dow, None)
		
		while True:
			val = next(nowTab)
			if  val == self.__NO_TIME_MARK:
				ret += timedelta(1)
			else:				
				ret = ret.replace(hour=self.get_time_from_string(val).hour, minute=self.get_time_from_string(val).minute, second=0)
				break					
		
		return ret

	@classmethod
	def get_time_from_string (self, time:str):
		return datetime.strptime(time, self.__DATE_MASK)

	@classmethod		
	def verify (self, times1, times2):
		for i in range(len(times1)):
			if not times1[i].strip() == self.__NO_TIME_MARK:
				self.get_time_from_string(times1[i].strip())
			if not times2[i].strip() == self.__NO_TIME_MARK:
				self.get_time_from_string(times2[i].strip())
			
			if not times2[i].strip() == self.__NO_TIME_MARK and not times1[i].strip() == self.__NO_TIME_MARK:
				if self.get_time_from_string(times1[i].strip()) > self.get_time_from_string(times2[i].strip()):
					raise Exception('Configuration start_times times are older than stop_times!')