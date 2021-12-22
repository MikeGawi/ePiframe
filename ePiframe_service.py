#!/usr/bin/env python3

import sys, time, sched, os, signal, subprocess
from threading import Thread
from misc.daemon import daemon
from misc.constants import constants
from modules.backendmanager import backendmanager
from modules.telebotmanager import telebotmanager
from modules.webuimanager import webuimanager
from modules.statsmanager import statsmanager

class service(daemon):
	
	__config_path = os.path.dirname(os.path.realpath(__file__))
	__script = [sys.executable, os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ePiframe.py')]
	
	__telebot = None
	__webman = None
	__statsman = None
	__tbthread = None
	__webthread = None
	__statsthread = None
	__event = None
	
	__SERVICE_LOG_IND = "--------ePiframe Service: "
	__SERVICE_LOG_STARTED = __SERVICE_LOG_IND + "STARTED"
	__SERVICE_TRIGGER = __SERVICE_LOG_IND + "Activity triggered"
	__SERVICE_LOG_STARTING = __SERVICE_LOG_IND + "Starting ePiframe script"
	__SERVICE_LOG_SLEEPING = __SERVICE_LOG_IND + "Off hours - sleeping"
	__SERVICE_LOG_MULT = __SERVICE_LOG_IND + "Interval multiplicated for current photo"
	__SERVICE_LOG_NEXT = __SERVICE_LOG_IND + "Next update scheduled at {}"
	
	__SERVICE_WEB_START = __SERVICE_LOG_IND + "Starting ePiframe WebUI server"
	__SERVICE_TGBOT_START = __SERVICE_LOG_IND + "Starting Telegram Bot"
	
	__INITIAL_EVENT_TIME = 10
	__WAIT_EVENT_TIME = 60
	
	__EVENT_PRIORITY = 1
	__NUMBER_OF_NOTIF = 0	
	
	__ERROR_TELE_BOT = "Error configuring Telegram Bot! {}"
	__ERROR_WEB = "Error configuring WebUI! {}"
	__ERROR_STATS = "Error getting statistics! {}"
	
	__WEB_ARG = 'web'
	__TGBOT_ARG = 'telegram'
	
	def run(self, args=None):
		self.__backend = backendmanager(self.restart, self.__config_path)
		self.__backend.log(self.__SERVICE_LOG_STARTED, silent=True)
		
		self.__sched = sched.scheduler(time.time, time.sleep)
		self.__event = self.__sched.enter(self.__INITIAL_EVENT_TIME, self.__EVENT_PRIORITY, self.task)
		
		if not args or (args and args == self.__TGBOT_ARG):
			self.__tbthread = Thread(target = self.tbthread)
			self.__tbthread.start()
		
		if not args or (args and args == self.__WEB_ARG):
			self.__statsthread = Thread(target = self.statsthread)
			self.__statsthread.start()
			self.__webthread = Thread(target = self.webthread)
			self.__webthread.start()

		if not args:
			self.__sched.run()
		
		while True:		
			time.sleep(self.__WAIT_EVENT_TIME)
	
	def statsthread(self):
		self.__statsman = statsmanager(self.__backend)
		while True:
			self.__backend.refresh()
			if self.__backend.is_web_enabled() and self.__backend.stats_enabled():
				try:
					self.__statsman.feed_stats()
				except Exception as e:
					self.__backend.log(self.__ERROR_STATS.format(e), silent=True)
					pass
			
			time.sleep(constants.STATS_STEP)
	
	def webthread(self):
		while True:
			self.__backend.refresh()
			if self.__backend.is_web_enabled():
				try:
					self.__backend.log(self.__SERVICE_WEB_START, silent=True)
					self.__webman = webuimanager(self.__backend)
					self.__webman.start()
				except Exception as e:
					self.__backend.log(self.__ERROR_WEB.format(e), silent=True)
					raise
			
			time.sleep(self.__WAIT_EVENT_TIME)
	
	def tbthread(self):
		while True:
			self.__backend.refresh()
			if self.__backend.is_telebot_enabled():
				try:
					self.__backend.log(self.__SERVICE_TGBOT_START, silent=True)					
					self.__telebot = telebotmanager(self.__backend)
					self.__telebot.start()
				except Exception as e:
					self.__backend.log(self.__ERROR_TELE_BOT.format(e), silent=True)
					raise
			
			time.sleep(self.__WAIT_EVENT_TIME)
	
	def restart(self, params=None):
		self.__backend.log(self.__SERVICE_TRIGGER, silent=True)
		if self.__sched and self.__event:
			self.__sched.cancel(self.__event)
		self.task(params)
				
	def task(self, params=None):
		self.__backend.refresh()
		inter = -1
		sleep = False
		
		if self.__backend.is_interval_mult_enabled():
			try:
				inter = self.__backend.get_interval()
			except Exception:
				pass

			if inter > 0:
				inter -= 1
				self.__backend.save_interval(inter)
				self.__backend.log(self.__SERVICE_LOG_MULT, silent=True)			
			else:
				self.__backend.remove_interval()
				inter = -1
		
		if inter < 0 or params:
			if self.__backend.should_i_work_now() or (params and self.__backend.triggers_enabled()):
				self.__backend.log(self.__SERVICE_LOG_STARTING, silent=True)
				
				par = params if params != self.__backend.get_empty_params() else str()
				args = (self.__script + par.split()) if par else self.__script
				subprocess.Popen(args)
			else:		
				if self.__NUMBER_OF_NOTIF == 0: self.__backend.log(self.__SERVICE_LOG_SLEEPING, silent=True)
				self.__NUMBER_OF_NOTIF = (self.__NUMBER_OF_NOTIF + 1)%10
				sleep = True
		
		frameTime = self.__backend.get_slide_interval() if not sleep else self.__WAIT_EVENT_TIME
		self.__backend.update_time()
		if not sleep: self.__backend.log(self.__SERVICE_LOG_NEXT.format(self.__backend.next_time()), silent=True)
		self.__event = self.__sched.enter(frameTime, self.__EVENT_PRIORITY, self.task)	
			
if __name__ == "__main__":
	daemon = service('/tmp/ePiframe-service.pid', os.path.dirname(os.path.realpath(__file__)))

	if len(sys.argv) >= 2 and not '--help' in [x.lower() for x in sys.argv]:
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
			daemon.start('web' if 'web' in [x.lower() for x in sys.argv] else 'telegram' if 'telegram' in [x.lower() for x in sys.argv] else str(), '--debug' in [x.lower() for x in sys.argv])
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
		print ("usage: %s start|stop|restart [service]" % sys.argv[0])
		print ("	service  	start only particular service (i.e. web or telegram)")
		print ("			services must be enabled in configuration!")
		print ("			for web: any port number below 5000 needs root privilleges to be possible to assign (use sudo ./ePiframe_service.py ...")
		print ("")
		print ("")
		print ("Use --debug at the end for debugger info")
		sys.exit(2)