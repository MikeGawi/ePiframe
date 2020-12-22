import sys,os
import subprocess

class pidmanager:
	
	__pid = None
	__path = None

	def __init__ (self, path:str):
		self.__path = path
		self.__pid = os.getpid()
		
	def read (self):
		pid = 0
		
		try:
			if os.path.exists(self.__path):
				with open(self.__path, 'r') as f:
					lines=f.readlines()	
					pid=str(lines[0]).rstrip()
					f.close()
		except Exception:
			self.remove()
		
		return pid
		
	def save (self):
		with open(self.__path , 'w') as f:
			f.write(str(self.__pid))
			f.close()
			
	def remove (self):
		if os.path.exists(self.__path):
			os.remove(self.__path)
	
	def get_pid (self):
		return self.__pid
	
	def get_pid_name (self, pid):
		p = subprocess.Popen(["ps -o cmd= {}".format(pid)], stdout=subprocess.PIPE, shell=True)	
		p.wait()		
		out, err = p.communicate()

		return out