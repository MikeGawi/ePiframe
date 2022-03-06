import os, glob
from datetime import datetime, timedelta
import modules.intervalmanager as iterman
import modules.timermanager as timerman
import modules.configmanager as confman
from modules.weathermanager import weathermanager
import modules.pidmanager as pidman
import modules.pluginsmanager as pluginsman
from misc.constants import constants
from misc.logs import logs

class backendmanager:

	__REBOOT_OS_CMD = "sudo reboot"
	__POWEROFF_OS_CMD = "sudo poweroff"
	__RESTART_OS_CMD = "sudo systemctl restart ePiframe.service"
	__SERVICE_RUN_CMD = "systemctl is-active --quiet ePiframe.service && echo Running 2> /dev/null"
	__UPTIME_CMD = "uptime --pretty 2> /dev/null"
	__LOAD_CMD = "awk '{print $1\" \"$2\" \"$3}' /proc/loadavg 2> /dev/null"
	__MEM_CMD = "awk '/MemAvailable/{free=$2} /MemTotal/{total=$2} END{print int(100-(free*100)/total)}' /proc/meminfo 2> /dev/null"
	__TEMP_CMD = "vcgencmd measure_temp 2> /dev/null"
	__NEXT_TIME_FORMAT = "in {d} days {h} hours {m} mins {s} secs"
	
	__ERROR_CONF_FILE = "Error loading {} configuration file! {}"
	
	__IDLE_STATE = "Idle"
	__BUSY_STATE = "Busy"
	__NOT_RUNNING = "Not running!"
	__NOTHING = "-"
	
	__REFRESH_PARAMS = "--test-convert --test-display"
	__EMPTY_PARAMS = "NOPARAMS"

	def __init__ (self, event, path):
		self.__event = event		
		self.__path = path
		self.__lastdate = None
		self.__load_config()
		self.__interval = iterman.intervalmanager(self.__config.get('interval_mult_file'))
		self.__timer = timerman.timermanager(self.__config.get('start_times').split(','), self.__config.get('stop_times').split(','))
		self.remove_interval()
		self.update_time()
		self.__logging = logs(self.__config.get('log_files'))
		self.__plugins = pluginsman.pluginsmanager(self.__path, pidman.pidmanager(self.__config.get('pid_file')), self.__logging, self.__config)
	
	def get_last_date(self, file):
		ret = None
		try:
			ret = os.stat(os.path.join(self.__path, file)).st_mtime
		except Exception:
			pass
		return ret
	
	def get_path(self):
		return self.__path
	
	def get_plugins(self):
		return self.__plugins
	
	def __load_config (self):
		try:
			self.__config = confman.configmanager(os.path.join(self.__path, constants.CONFIG_FILE), os.path.join(self.__path, constants.CONFIG_FILE_DEFAULT))
			self.__lastdate = self.get_last_date(constants.CONFIG_FILE)			
		except Exception as e:
			raise Exception(self.__ERROR_CONF_FILE.format(constants.CONFIG_FILE, e))
	
	def log (self, text, silent):
		self.__logging.log(text, silent)
	
	def refresh (self):
		date = self.get_last_date(constants.CONFIG_FILE)

		if not date or not self.__lastdate or date != self.__lastdate:
			self.__load_config()
			self.__interval = iterman.intervalmanager(self.__config.get('interval_mult_file'))
			self.__timer = timerman.timermanager(self.__config.get('start_times').split(','), self.__config.get('stop_times').split(','))
	
	def get_config (self):
		return self.__config
	
	def next_time(self):
		nextUpdate = datetime.now(datetime.now().astimezone().tzinfo) + timedelta(seconds=self.__config.getint('slide_interval'))
		return nextUpdate.isoformat().replace('T', ' at ').split('.')[0]
	
	def update_time (self):
		value = self.get_slide_interval()
		mult = 1
		
		try :
			mult = self.get_interval()
			if mult <= 0: mult = 1
		except Exception:
			pass
		
		if self.should_i_work_now():
			self.__next_time = datetime.now(datetime.now().astimezone().tzinfo) + timedelta(seconds=(value * mult))
		else:
			self.__next_time = self.__timer.when_i_work_next()

	def should_i_work_now(self):
		return self.__timer.should_i_work_now()
			
	def get_update_time_formatted(self, formatted=False):
		ret = self.__next_time.isoformat().replace('T', ' at ').split('.')[0] if formatted else self.__next_time
		
		if formatted and datetime.now().date() == self.__next_time.date():
			ret = 'at ' + self.__next_time.isoformat().split('T')[1].split('.')[0]
		return ret
	
	def fire_event (self, args=None):
		self.remove_interval()
		self.__event(args)
		
	def next_photo (self):
		self.fire_event(self.__EMPTY_PARAMS)
	
	def get_empty_params(self):
		return self.__EMPTY_PARAMS
	
	def refresh_frame (self):
		self.fire_event(self.__REFRESH_PARAMS)
	
	def get_period(self, delta, pattern):
		d = {'d': delta.days if delta.days > 0 else 0 }
		d['h'], rem = divmod(delta.seconds, 3600)
		d['m'], d['s'] = divmod(rem, 60)
		return pattern.format(**d)
	
	def remove_interval (self):
		self.__interval.remove()
	
	def get_token (self):
		return self.__config.get('token')
	
	def get_interval (self):
		return self.__interval.read()
	
	def is_metric (self):
		return weathermanager.is_metric(self.__config.get('units'))	
	
	def save_interval (self, num):
		self.__interval.save(num)
	
	def get_max_interval (self):
		return self.__config.getint('interval_max_mult')
	
	def is_interval_mult_enabled (self):
		return bool(self.__config.getint('interval_mult'))
	
	def triggers_enabled(self):
		return bool(self.__config.getint('allow_triggers'))
			
	def pid_file_exists (self):
		return os.path.exists(self.__config.get('pid_file'))
	
	def get_download_file (self):
		return os.path.join(self.__config.get('photo_convert_path'), self.__config.get('photo_download_name'))
	
	def get_chat_id (self):
		return self.__config.get('chat_id')
	
	def get_original_file (self):
		ret = None
		files = glob.glob('{}.*'.format(os.path.join(self.__config.get('photo_convert_path'), self.__config.get('photo_download_name'))))
		if files:
			ret = max(files, key=os.path.getctime)			
		return ret
	
	def get_current_file (self):
		ret = None
		if os.path.exists(os.path.join(self.__config.get('photo_convert_path'), self.__config.get('photo_convert_filename'))):
			ret = os.path.join(self.__config.get('photo_convert_path'), self.__config.get('photo_convert_filename'))
		return ret
	
	def get_filename_if_exists(self, filename):
		return os.path.join(self.__config.get('photo_convert_path'), self.__config.get(filename)) if os.path.exists(os.path.join(self.__config.get('photo_convert_path'), self.__config.get(filename))) else str()
	
	def get_filename_modtime_if_exists(self, filename):
		file = os.path.join(self.__config.get('photo_convert_path'), self.__config.get(filename)) if os.path.exists(os.path.join(self.__config.get('photo_convert_path'), self.__config.get(filename))) else str()
		return os.stat(file).st_mtime if file else 0

	def get_slide_interval (self):
		return self.__config.getint('slide_interval')
	
	def is_telebot_enabled (self):
		return self.__config.getint('use_telebot')
	
	def is_web_enabled (self):
		return self.__config.getint('use_web')
	
	def stats_enabled (self):
		return self.__config.getint('show_stats')
	
	def get_state(self):
		return self.__BUSY_STATE if self.pid_file_exists() else self.__IDLE_STATE
	
	def get_service_state(self):
		return os.popen(self.__SERVICE_RUN_CMD).read().strip() or self.__NOT_RUNNING
	
	def get_uptime(self):
		return os.popen(self.__UPTIME_CMD).read().strip() or self.__NOTHING
	
	def get_load(self):
		return os.popen(self.__LOAD_CMD).read().strip() or self.__NOTHING
	
	def get_mem(self):
		return os.popen(self.__MEM_CMD).read().strip() or self.__NOTHING
	
	def get_temp(self):
		res =  os.popen(self.__TEMP_CMD).read().strip().replace("temp=", '').replace("'C", '') or self.__NOTHING
		
		if res:
			if self.is_metric(): 
				res += '\N{DEGREE SIGN}C'
			else:
				res = self.calc_to_f(res) + '\N{DEGREE SIGN}F'
		
		return res
	
	def calc_to_f(self, temp):
		res = self.__NOTHING
		try:
			res = str(round(float(temp) * 1.8 + 32, 1))
		except Exception:
			pass
		
		return res
	
	def get_next_time(self):
		time = self.get_update_time_formatted(True)
		delta = self.get_update_time_formatted() - datetime.now(datetime.now().astimezone().tzinfo)
		period = self.get_period(delta, self.__NEXT_TIME_FORMAT)
		
		if delta.days <= 0:
			per = period.split(' ')
			del per[1]
			del per[1]
			if divmod(delta.seconds, 3600)[0] == 0:
				del per[1]
				del per[1]
			period = ' '.join(per)
			
		return '{}\n{}'.format(time, period)																					 
	
	def reboot (self):
		os.system(self.__REBOOT_OS_CMD)
	
	def restart (self):
		os.system(self.__RESTART_OS_CMD)
	
	def poweroff (self):
		os.system(self.__POWEROFF_OS_CMD)
		
	def start_sys_cmd (self, cmd):
		return os.popen(cmd).read()