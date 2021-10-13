#!/usr/bin/env python3

import sys, time, sched, os, signal
import subprocess
from threading import Thread
from misc.daemon import daemon
from datetime import datetime, timedelta
from misc.logs import logs
from misc.constants import constants
from modules.configmanager import configmanager
from modules.timermanager import timermanager
from modules.intervalmanager import intervalmanager
from modules.telebotmanager import telebotmanager

class service(daemon):
	
	__config_path = os.path.dirname(os.path.realpath(__file__))
	__script = [sys.executable, os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ePiframe.py')]
	__sched = sched.scheduler(time.time, time.sleep)
	
	__telebot = None
	__thread = None
	__event = None
	
	__SERVICE_LOG_IND = "--------ePiframe Service: "
	__SERVICE_LOG_STARTED = __SERVICE_LOG_IND + "STARTED"
	__SERVICE_LOG_STARTING = __SERVICE_LOG_IND + "Starting ePiframe script"
	__SERVICE_LOG_SLEEPING = __SERVICE_LOG_IND + "Off hours - sleeping"
	__SERVICE_LOG_MULT = __SERVICE_LOG_IND + "Interval multipicated for current photo"
	__SERVICE_LOG_NEXT = __SERVICE_LOG_IND + "Next update scheduled at {}"
	
	__INITIAL_EVENT_TIME = 10
	__WAIT_EVENT_TIME = 60
	
	__EVENT_PRIORITY = 1
	
	__ERROR_CONF_FILE = "Error loading {} configuration file! {}"
	__ERROR_TELE_BOT = "Error configuring Telegram Bot! {}"
	
	def run(self):
		config = self.__load_config()		
		self.__logging = logs(config.get('log_files'))
		self.__logging.log(self.__SERVICE_LOG_STARTED, silent=True)
		interval = intervalmanager(config.get('interval_mult_file'))
		interval.remove()
		
		self.__thread = Thread(target = self.thread)
		self.__thread.start()
		self.__event = self.__sched.enter(self.__INITIAL_EVENT_TIME, self.__EVENT_PRIORITY, self.task)
		self.__sched.run()
		
		while True:		
			time.sleep(self.__WAIT_EVENT_TIME)
	
	def thread(self):
		while True:
			if bool(self.__load_config().getint('use_telebot')):
				try:
					self.__telebot = telebotmanager(self.restart, self.__config_path)
					self.__telebot.start()
				except Exception as e:
					logs.show_log(self.__ERROR_TELE_BOT.format(e))
					raise
			
			time.sleep(self.__WAIT_EVENT_TIME)
	
	def __load_config(self):
		config = None
		try:
			config = configmanager(os.path.join(self.__config_path, constants.CONFIG_FILE))
		except Exception as e:
			logs.show_log(self.__ERROR_CONF_FILE.format(constants.CONFIG_FILE, e))
			raise
		return config
	
	def restart(self, params=None):
		if self.__sched and self.__event:
			self.__sched.cancel(self.__event)
		self.task(params)
				
	def task(self, params=None):
		config = self.__load_config()
			
		timer = timermanager(config.get('start_times').split(','), config.get('stop_times').split(','))
		inter = -1
		
		if bool(config.getint('interval_mult')):
			interval = intervalmanager(config.get('interval_mult_file'))
			
			try:
				inter = interval.read()
			except Exception:
				pass

			if inter > 0:
				inter -= 1
				interval.save(inter)
				self.__logging.log(self.__SERVICE_LOG_MULT, silent=True)			
			else:
				interval.remove()
				inter = -1
		
		if inter < 0:
			if timer.should_i_work_now():
				self.__logging.log(self.__SERVICE_LOG_STARTING, silent=True)

				args = self.__script + params.split() if params else self.__script
				subprocess.Popen(args)
			else:
				self.__logging.log(self.__SERVICE_LOG_SLEEPING, silent=True)
		
		frameTime = config.getint('slide_interval')
		if self.__telebot:
			self.__telebot.update_time()
		nextUpdate = datetime.now(datetime.now().astimezone().tzinfo) + timedelta(seconds=frameTime)
		self.__logging.log(self.__SERVICE_LOG_NEXT.format(nextUpdate.isoformat().replace('T', ' at ').split('.')[0]), silent=True)
		self.__event = self.__sched.enter(frameTime, self.__EVENT_PRIORITY, self.task)	
			
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