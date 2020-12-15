import sys, os
import requests

class connection:
	
	@classmethod
	def check_internet (cls, url:str, timeout:int):
		ret = None

		try:
			requests.get(url, timeout=timeout)
		except requests.ConnectionError as exc:
			ret = str(exc)

		return ret

	@classmethod
	def download_file (cls, url:str, destination_folder:str, file_name:str, code:int):
		response = requests.get(url)
		
		if response.status_code == code:
			filename = os.path.join(destination_folder, file_name)
			
			with open(filename, 'wb') as f:	
				f.write(response.content)
				f.close()
				
		return response.status_code