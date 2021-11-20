import sys, os, time, atexit, signal

class daemon:
	#Based on a generic daemon class.
	#https://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
	#Usage: subclass the daemon class and override the run() method.

	def __init__(self, pidfile, path): 
		self.pidfile = pidfile
		self.path = path
	
	def daemonize(self):
		try: 
			pid = os.fork() 
			if pid > 0:
				# exit first parent
				sys.exit(0) 
		except OSError as err: 
			sys.stderr.write('fork #1 failed: {0}\n'.format(err))
			sys.exit(1)
	
		# decouple from parent environment
		os.chdir(self.path) 
		os.setsid() 
		os.umask(0) 
	
		# do second fork
		try: 
			pid = os.fork() 
			if pid > 0:

				# exit from second parent
				sys.exit(0) 
		except OSError as err: 
			sys.stderr.write('fork #2 failed: {0}\n'.format(err))
			sys.exit(1) 
	
		# redirect standard file descriptors
		sys.stdout.flush()
		sys.stderr.flush()
		si = open(os.devnull, 'r')
		so = open(os.devnull, 'a+')
		se = open(os.devnull, 'a+')

		os.dup2(si.fileno(), sys.stdin.fileno())
		os.dup2(so.fileno(), sys.stdout.fileno())
		os.dup2(se.fileno(), sys.stderr.fileno())
	
		# write pidfile
		atexit.register(self.delpid)

		pid = str(os.getpid())
		with open(self.pidfile,'w+') as f:
			f.write(pid + '\n')
	
	def delpid(self):
		os.remove(self.pidfile)

	def start(self, args):
		# Check for a pidfile to see if the daemon already runs
		#try:
		#		pf = file(self.pidfile,'r')
		#		pid = int(pf.read().strip())
		#		pf.close()
		#except IOError:
		#		pid = None

		#if pid:
		#		message = "pidfile %s already exist. Daemon already running?\n"
		#		sys.stderr.write(message % self.pidfile)
		#		sys.exit(1)
		
		# Start the daemon
		self.daemonize()
		self.run(args)

	def stop(self):
		# Get the pid from the pidfile
		try:
			with open(self.pidfile,'r') as pf:
				pid = int(pf.read().strip())
		except IOError:
			pid = None
	
		if not pid:
			message = "pidfile {0} does not exist. " + \
					"Daemon not running?\n"
			sys.stderr.write(message.format(self.pidfile))
			return # not an error in a restart

		# Try killing the daemon process	
		try:
			while 1:
				os.kill(pid, signal.SIGTERM)
				time.sleep(0.1)
		except OSError as err:
			e = str(err.args)
			if e.find("No such process") > 0:
				if os.path.exists(self.pidfile):
					os.remove(self.pidfile)
			else:
				print (str(err.args))
				sys.exit(1)

	def restart(self):
		self.stop()
		self.start()

	#You should override this method when you subclass Daemon.
	#It will be called after the process has been daemonized by 
	#start() or restart().
	def run(self):
		pass		