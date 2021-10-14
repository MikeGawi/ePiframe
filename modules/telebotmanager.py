import telebot, requests
import os, re, glob,sys
from datetime import datetime, timedelta
import modules.intervalmanager as iman
import modules.timermanager as tman
import modules.configmanager as cman
from misc.telebotcmd import telebotcmd
from misc.constants import constants

class telebotmanager:

	__REBOOT_OS_CMD = "sudo reboot"
	__STATUS_OS_CMD = "/usr/bin/free --mega -t | /usr/bin/awk '{print (NR==1?\"Type\":\"\"), $1, $2, $3, (NR==1?\"\":$4)}' | column -t | /bin/sed 's/ \+/ /g' && /usr/bin/uptime | /bin/sed 's/ \+/ /g' | /bin/sed 's/^ //g' && vcgencmd measure_temp"
	
	__NEXT_TIME_FORMAT = "in {d} days {h} hours {m} mins {s} secs"
	__ERROR_CONF_FILE = "Error loading {} configuration file! {}"
	
	__REFRESH_PARAMS = "--test-convert --test-display"
	
	def __init__ (self, event, path):
		self.__event = event		
		self.__path = path
		self.__load_config()
		self.__bot = telebot.TeleBot(self.__config.get('token'), parse_mode = telebotcmd.TG_PARSE_MODE)
		user = self.__bot.get_me()
		self.__bot.set_update_listener(self.__handle_messages)
		self.update_time()
	
	@classmethod
	def check_token (self, token):
		bot = telebot.TeleBot(token, parse_mode = telebotcmd.TG_PARSE_MODE)
		user = bot.get_me()
	
	def __load_config (self):
		try:
			self.__config = cman.configmanager(os.path.join(self.__path, constants.CONFIG_FILE))
		except Exception as e:
			raise Exception(self.__ERROR_CONF_FILE.format(constants.CONFIG_FILE, e))
	
	def update_time (self):
		value = self.__config.getint('slide_interval')
		mult = 1
		
		try :
			interval = self.__config.get('interval_mult_file')
			mult = interval.read()
			if mult <= 0: mult = 1
		except Exception:
			pass
		
		timer = tman.timermanager(self.__config.get('start_times').split(','), self.__config.get('stop_times').split(','))
		
		if timer.should_i_work_now():
			self.__next_time = datetime.now(datetime.now().astimezone().tzinfo) + timedelta(seconds=(value * mult))
		else:
			self.__next_time = tman.timermanager.when_i_work_next()
	
	def start (self):
		self.__bot.infinity_polling()
		
	def fire_event (self, args=None):
		self.__remove_interval()
		self.__event(args)
	
	def __period(self, delta, pattern):
		d = {'d': delta.days}
		d['h'], rem = divmod(delta.seconds, 3600)
		d['m'], d['s'] = divmod(rem, 60)
		return pattern.format(**d)
	
	def __handle_messages (self, messages):
		self.__load_config()
		
		if messages:
			for msg in messages:
				chatId = msg.chat.id
				ids = [int(x) for x in self.__config.get('chat_id').split(',')] if self.__config.get('chat_id') else [ chatId ]
				if chatId in ids:
					if msg.content_type == telebotcmd.TEXT_TAG:
						command = re.sub(r'@.+ ', ' ', msg.text).split('@')[0]
						self.__process_command (chatId, command)
					elif msg.content_type == telebotcmd.PHOTO_TAG:
						self.__process_file (msg)
					else:
						self.__bot.send_message(chatId, telebotcmd.UNSUPPORTED_REP)
	
	def __process_file (self, msg):
		if os.path.exists(self.__config.get('pid_file')):
			self.__bot.send_message(chatId, '{}\n{}'.format(telebotcmd.PROGRESS_REP, telebotcmd.LATER_REP))
		else:
			file_info = self.__bot.get_file(msg.photo[-1].file_id)
			downloaded_file = self.__bot.download_file(file_info.file_path)
			try:
				with open(self.__config.get('photo_download_name') + telebotcmd.DOWNLOAD_PHOTO_EXT, telebotcmd.DOWNLOAD_PHOTO_PERM_TAG) as new_file:
					new_file.write(downloaded_file)

				self.fire_event(self.__REFRESH_PARAMS)
				self.__bot.reply_to(msg, telebotcmd.SENDING_REP)
			except Exception:
				self.__bot.reply_to(msg, telebotcmd.ERROR_REP)
	
	def __process_longer_command (self, chatId, cmd):

		if bool(self.__config.getint('interval_mult')):
			if len(cmd.split(" ")) == 1:
				self.__bot.send_message(chatId, telebotcmd.LONGER_REP)
			else:
				val = cmd.split(" ")[1]
				try :
					val = int(val)
					if val <= 0: raise
					interval = iman.intervalmanager(self.__config.get('interval_mult_file'))
					inter = 0
					try:
						inter = interval.read()
					except Exception:
						pass					
					val+=0 if inter < 0 else inter
					maxin = self.__config.getint('interval_max_mult')
					val = maxin if val > maxin else val
					interval.save(val)
					self.__bot.send_message(chatId, '{}\n{} ({} is max in configuration){}'.format(telebotcmd.OK_REP, telebotcmd.LONGER_MSG.format(val), maxin,\
										   telebotcmd.LONGER2_MSG if inter>0 else ''))
				except Exception:
					self.__bot.send_message(chatId, telebotcmd.VALUE_REP)
		else:
			self.__bot.send_message(chatId, telebotcmd.LONGER_OFF_REP)
	
	def __remove_interval (self):
		interval = iman.intervalmanager(self.__config.get('interval_mult_file'))
		interval.remove()
	
	def __process_command (self, chatId, cmd):
		if cmd == telebotcmd.CURRENT_CMD:
			self.__bot.send_chat_action(chatId, telebotcmd.UPLOAD_PHOTO_TAG)
			if os.path.exists(self.__config.get('photo_convert_filename')):
				self.__bot.send_photo(chatId, open(self.__config.get('photo_convert_filename'), telebotcmd.UPLOAD_PHOTO_PERM_TAG))
			else:
				self.__bot.send_message(chatId, telebotcmd.ERROR_REP)
		elif cmd == telebotcmd.NEXT_CMD:
			if os.path.exists(self.__config.get('pid_file')):
				self.__bot.send_message(chatId, telebotcmd.PROGRESS_REP)
			else:				
				self.fire_event()
				self.__bot.send_message(chatId, telebotcmd.OK_REP)
		elif cmd == telebotcmd.WHEN_CMD:	
			time = self.__next_time.isoformat().replace('T', ' at ').split('.')[0]
			now = datetime.now(datetime.now().astimezone().tzinfo)
			period = self.__period(self.__next_time - now, self.__NEXT_TIME_FORMAT)
			self.__bot.send_message(chatId, '{}\n{}\n{}'.format(telebotcmd.NEXT_UPDATE_MSG, time, period))			
		elif telebotcmd.LONGER_CMD.replace(telebotcmd.OPTION_IND, '') in cmd:
			self.__process_longer_command (chatId, cmd)
		elif cmd == telebotcmd.PING_CMD:
			self.__bot.send_message(chatId, telebotcmd.PING_REP)
		elif telebotcmd.ECHO_CMD.replace(telebotcmd.OPTION_IND, '') in cmd:
			if len(cmd.split(" ")) == 1:
				self.__bot.send_message(chatId, telebotcmd.ECHO_REP)
			else:
				text = " ".join(cmd.split()[1:])
				self.__bot.send_message(chatId, text)
		elif cmd == telebotcmd.ORIGINAL_CMD:
			files = glob.glob('{}.*'.format(self.__config.get('photo_download_name')))
			if files:						
				self.__bot.send_chat_action(chatId, telebotcmd.UPLOAD_PHOTO_TAG)
				self.__bot.send_photo(chatId, open(max(files, key=os.path.getctime), telebotcmd.UPLOAD_PHOTO_PERM_TAG))
			else:
				self.__bot.send_message(chatId, telebotcmd.ERROR_REP)
		elif cmd == telebotcmd.START_CMD or cmd == telebotcmd.HELP_CMD:
			self.__bot.send_message(chatId, '*{}*\n\n{}\n{}\n\n{}\n\n{}'.format(telebotcmd.HELLO_MSG, telebotcmd.COMMANDS_MSG, telebotcmd.DESCRIPTIONS, \
																				telebotcmd.UPLOAD_MSG, telebotcmd.ALL))
		elif cmd == telebotcmd.STATUS_CMD:
			result = os.popen(self.__STATUS_OS_CMD).read()
			if result: 
				self.__bot.send_message(chatId, result)
			else:
				self.__bot.send_message(chatId, telebotcmd.ERROR_REP)
		elif cmd == telebotcmd.REBOOT_CMD:
			self.__bot.send_message(chatId, telebotcmd.OK_REP)
			os.system(self.__REBOOT_OS_CMD)
		else:
			self.__bot.send_message(chatId, telebotcmd.UNKNOWN_REP)