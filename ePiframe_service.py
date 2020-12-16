#!/usr/bin/env python3

import sys, time, sched, os, signal
import subprocess
from misc.daemon import daemon
from misc.constants import constants
from modules.configmanager import configmanager
from modules.timermanager import timermanager
from modules.intervalmanager import intervalmanager

class service(daemon):
	
	__sched = sched.scheduler(time.time, time.sleep)
	__config_path = os.path.dirname(os.path.realpath(__file__))
	__script = [sys.executable, os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ePiframe.py')]
	
	def run(self):
		try:
			config = configmanager(os.path.join(self.__config_path, constants.CONFIG_FILE))
		except Exception as e:
			logs.show_log("Error loading {} configuration file! {}".format(constants.CONFIG_FILE ,e))
			raise
		
		interval = intervalmanager(config.get('interval_mult_file'))
		interval.remove()
		
		self.__sched.enter(0, 1, self.task, (self.__sched,))
		self.__sched.run()
		
	def task(self, scheduler):
		try:
			config = configmanager(os.path.join(self.__config_path, constants.CONFIG_FILE))
		except Exception as e:
			logs.show_log("Error loading {} configuration file! {}".format(constants.CONFIG_FILE ,e))
			raise
			
		timer = timermanager(config.get('start_times').split(','),config.get('stop_times').split(','))
		
		if config.getint('interval_mult') == 1:
			interval = intervalmanager(config.get('interval_mult_file'))
			inter = -1
			try:
				inter = interval.read()
			except Exception:
				pass

			if inter > 0:
				inter -= 1
				interval.save(inter)
			else:
				interval.remove()
				if timer.should_i_work_now():
					subprocess.Popen(self.__script)
		else:
			if timer.should_i_work_now():
				subprocess.Popen(self.__script)
			
		frameTime = config.get('slide_interval')
		self.__sched.enter(int(frameTime), 1, self.task, (scheduler,))
			
if __name__ == "__main__":
	daemon = service('/tmp/ePiframe-service.pid', os.path.dirname(os.path.realpath(__file__)))

	if len(sys.argv) == 2:
		if 'start' == sys.argv[1]:
			p = subprocess.Popen(['ps', '-efa'], stdout=subprocess.PIPE)	
			p.wait()		
			out, err = p.communicate()
			
			if out:
				for line in out.splitlines():
					if str(os.path.basename(__file__)) in str(line):
						pid = int(line.split()[1])
						if not pid == os.getpid():
							os.kill(pid, signal.SIGKILL)
			daemon.start()
		elif 'stop' == sys.argv[1]:
			daemon.stop()
		elif 'restart' == sys.argv[1]:
			daemon.restart()
		else:
			print ("Unknown command")
			sys.exit(2)
		sys.exit(0)
	else:
		print ("ePiframe daemon service")
		print ("usage: %s start|stop|restart" % sys.argv[0])
		sys.exit(2)