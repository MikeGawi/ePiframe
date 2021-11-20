import os, requests, re, socket

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
	def download_file (cls, url:str, destination_folder:str, file_name:str, code:int, timeout:int):
		session = requests.Session()
		response = session.get(url, stream = True, timeout=timeout)
		response.raise_for_status()
		
		if response.status_code == code:
			filename = os.path.join(destination_folder, file_name)
			
			with open(filename, 'wb') as f:	
				for chunk in response.iter_content(chunk_size = 1024):
					if chunk:
						f.write(chunk)
				f.close()
				
		return response.status_code
	
	@classmethod
	def is_ip (cls, ip:str):
		if not re.match(r'^((\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.){3}(\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])$', ip):  
			raise Exception("Not a valid IP address!")
	
	@classmethod
	def port_check(cls, ipport):
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.settimeout(2) #Timeout in case of port not open
		if not s.connect_ex((ipport[0], int(ipport[1]))) == 0:
			raise Exception("Port {} is not open!".format(ipport[1]))