import time
from time import strftime
from datetime import datetime 
from time import gmtime

class logs:
	
	def start_time ():    
		return (time.time())

	def end_time ():
		return (time.time())

	def execution_time (startTime, endTime):
	   return (strftime(" %H:%M:%S",gmtime(int('{:.0f}'.format(float(str((endTime - startTime))))))))
	
	def show_log (text:str):
		timeObj = datetime.now().strftime("%Y-%m-%d %H:%M:%S :")
		print(timeObj, text)