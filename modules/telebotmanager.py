import telebot, re
from datetime import datetime, timedelta
from misc.telebotcmd import telebotcmd
from misc.connection import connection

class telebotmanager:

	__STATUS_OS_CMD = "/usr/bin/free --mega -t | /usr/bin/awk '{print (NR==1?\"Type\":\"\"), $1, $2, $3, (NR==1?\"\":$4)}' | column -t | /bin/sed 's/ \+/ /g' && /usr/bin/uptime | /bin/sed 's/ \+/ /g' | /bin/sed 's/^ //g' && vcgencmd measure_temp"
	__STATUS_OS_CMD_F = "/usr/bin/free --mega -t | /usr/bin/awk '{print (NR==1?\"Type\":\"\"), $1, $2, $3, (NR==1?\"\":$4)}' | column -t | /bin/sed 's/ \+/ /g' && /usr/bin/uptime | /bin/sed 's/ \+/ /g' | /bin/sed 's/^ //g' && echo \"temp=\"$(awk \"BEGIN {print `vcgencmd measure_temp | egrep -o '[0-9]*\.[0-9]*'`*1.8+32}\")\"\'F\""
		
	def __init__ (self, backend):
		self.__backend = backend
		self.__backend.refresh()
		self.__bot = self.check_token(self.__backend.get_token())
		self.__bot.set_update_listener(self.__handle_messages)
		self.__backend.update_time()
	
	@classmethod
	def check_token (self, token):
		ret = connection.check_internet('http://'+telebotcmd.API_URL, int(telebotcmd.API_CONNECTION_TIMEOUT))
		if ret:
			raise Exception(ret)
		bot = telebot.TeleBot(token, parse_mode = telebotcmd.TG_PARSE_MODE)
		user = bot.get_me()
		return bot
	
	def start (self):
		self.__bot.infinity_polling()
		
	def __handle_messages (self, messages):
		self.__backend.refresh()
		
		if messages:
			for msg in messages:
				chatId = msg.chat.id
				ids = [int(x) for x in self.__backend.get_chat_id().split(',')] if self.__backend.get_chat_id() else [ chatId ]
				if chatId in ids:
					if msg.content_type == telebotcmd.TEXT_TAG:
						command = re.sub(r'@.+ ', ' ', msg.text).split('@')[0]
						self.__process_command (chatId, command)
					elif msg.content_type == telebotcmd.PHOTO_TAG:
						self.__process_file (msg)
					else:
						self.__bot.send_message(chatId, telebotcmd.UNSUPPORTED_REP)
	
	def __process_file (self, msg):
		if self.__backend.pid_file_exists():
			self.__bot.send_message(chatId, '{}\n{}'.format(telebotcmd.PROGRESS_REP, telebotcmd.LATER_REP))
		else:
			file_info = self.__bot.get_file(msg.photo[-1].file_id)
			downloaded_file = self.__bot.download_file(file_info.file_path)
			try:
				with open(self.__backend.get_download_file() + telebotcmd.DOWNLOAD_PHOTO_EXT, telebotcmd.DOWNLOAD_PHOTO_PERM_TAG) as new_file:
					new_file.write(downloaded_file)

				self.__backend.refresh_frame()
				self.__bot.reply_to(msg, telebotcmd.SENDING_REP)
			except Exception:
				self.__bot.reply_to(msg, telebotcmd.ERROR_REP)
	
	def __process_longer_command (self, chatId, cmd):

		if self.__backend.is_interval_mult_enabled():
			if len(cmd.split(" ")) == 1:
				self.__bot.send_message(chatId, telebotcmd.LONGER_REP)
			else:
				val = cmd.split(" ")[1]
				try :
					val = int(val)
					if val <= 0: raise
					inter = 0
					try:
						inter =  self.__backend.get_interval()
					except Exception:
						pass					
					val+=0 if inter < 0 else inter
					maxin = self.__backend.get_max_interval()
					val = maxin if val > maxin else val
					self.__backend.save_interval(val)
					self.__bot.send_message(chatId, '{}\n{} ({} is max in configuration){}'.format(telebotcmd.OK_REP, telebotcmd.LONGER_MSG.format(val), maxin,\
										   telebotcmd.LONGER2_MSG if inter>0 else ''))
				except Exception:
					self.__bot.send_message(chatId, telebotcmd.VALUE_REP)
		else:
			self.__bot.send_message(chatId, telebotcmd.LONGER_OFF_REP)
	
	def __process_command (self, chatId, cmd):
		if cmd == telebotcmd.CURRENT_CMD:
			self.__bot.send_chat_action(chatId, telebotcmd.UPLOAD_PHOTO_TAG)
			if self.__backend.get_current_file():
				self.__bot.send_photo(chatId, open(self.__backend.get_current_file(), telebotcmd.UPLOAD_PHOTO_PERM_TAG))
			else:
				self.__bot.send_message(chatId, telebotcmd.ERROR_REP)
		elif cmd == telebotcmd.NEXT_CMD:
			if self.__backend.pid_file_exists():
				self.__bot.send_message(chatId, telebotcmd.PROGRESS_REP)
			else:				
				self.__backend.fire_event()
				self.__bot.send_message(chatId, telebotcmd.OK_REP)
		elif cmd == telebotcmd.WHEN_CMD:	
			self.__bot.send_message(chatId, '{}\n{}'.format(telebotcmd.NEXT_UPDATE_MSG, self.__backend.get_next_time()))
		elif telebotcmd.LONGER_CMD.replace(telebotcmd.OPTION_IND, '') in cmd:
			self.__process_longer_command (chatId, cmd)
		elif cmd == telebotcmd.PING_CMD:
			self.__bot.send_message(chatId, telebotcmd.PING_REP)
		elif telebotcmd.ECHO_CMD.replace(telebotcmd.OPTION_IND, '') in cmd:
			if len(cmd.split(" ")) == 1:
				self.__bot.send_message(chatId, telebotcmd.ECHO_REP)
			else:
				self.__bot.send_message(chatId, " ".join(cmd.split()[1:]))
		elif cmd == telebotcmd.ORIGINAL_CMD:
			if self.__backend.get_original_file():						
				self.__bot.send_chat_action(chatId, telebotcmd.UPLOAD_PHOTO_TAG)
				self.__bot.send_photo(chatId, open(self.__backend.get_original_file(), telebotcmd.UPLOAD_PHOTO_PERM_TAG))
			else:
				self.__bot.send_message(chatId, telebotcmd.ERROR_REP)
		elif cmd == telebotcmd.START_CMD or cmd == telebotcmd.HELP_CMD:
			self.__bot.send_message(chatId, '*{}*\n\n{}\n{}\n\n{}\n\n{}'.format(telebotcmd.HELLO_MSG, telebotcmd.COMMANDS_MSG, telebotcmd.DESCRIPTIONS, \
																				telebotcmd.UPLOAD_MSG, telebotcmd.ALL))
		elif cmd == telebotcmd.STATUS_CMD:
			result = self.__backend.start_sys_cmd(self.__STATUS_OS_CMD) if self.__backend.is_metric() else self.__backend.start_sys_cmd(self.__STATUS_OS_CMD_F)
			if result: 
				self.__bot.send_message(chatId, result)
			else:
				self.__bot.send_message(chatId, telebotcmd.ERROR_REP)
		elif cmd == telebotcmd.REBOOT_CMD:
			self.__bot.send_message(chatId, telebotcmd.OK_REP)
			self.__backend.reboot()
		else:
			self.__bot.send_message(chatId, telebotcmd.UNKNOWN_REP)