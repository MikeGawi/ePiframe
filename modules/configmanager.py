import subprocess
from modules.filteringmanager import filteringmanager
from modules.timermanager import timermanager
from modules.weathermanager import weathermanager
from modules.weatherstampmanager import weatherstampmanager
from modules.telebotmanager import telebotmanager
from modules.convertmanager import convertmanager
from modules.localsourcemanager import localsourcemanager
from modules.displaymanager import displaymanager
from modules.base.configbase import configbase
from misc.configprop import configprop
from misc.connection import connection

class configmanager(configbase):
	
	__SPI_CHECK1 = 'ls -l /dev/spidev*'
	__SPI_CHECK2 = 'lsmod | grep spi_'
	
	def load_settings(self):
		self.SETTINGS = [
			configprop('use_google_photos', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('cred_file', self, prop_type=configprop.FILE_TYPE, dependency='use_google_photos'),
			configprop('pickle_file', self, prop_type=configprop.FILE_TYPE, dependency='use_google_photos'),
			configprop('album_names', self, notempty=False, dependency='use_google_photos'),
			configprop('use_local', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('local_path', self, prop_type=configprop.FILE_TYPE, dependency='use_local', convert=localsourcemanager.create_dir),
			configprop('local_subfolders', self, prop_type=configprop.BOOLEAN_TYPE, dependency='use_local'),
			configprop('units', self, possible=weathermanager.get_units()),
			configprop('photo_convert_path', self, prop_type=configprop.FILE_TYPE),
			configprop('log_files', self, notempty=False),
			configprop('convert_bin_path', self, prop_type=configprop.FILE_TYPE),
			configprop('rrdtool_bin_path', self, prop_type=configprop.FILE_TYPE),
			configprop('fbi_bin_path', self, prop_type=configprop.FILE_TYPE),
			configprop('display_type', self, possible=displaymanager.get_displays()),
			configprop('display', self, dependency=['display_type', displaymanager.get_spi()]),
			configprop('tty', self, minvalue=0, prop_type=configprop.INTEGER_TYPE, dependency=['display_type', displaymanager.get_hdmi()]),			
			configprop('slide_interval', self, minvalue=180, prop_type=configprop.FLOAT_TYPE),
			configprop('interval_mult', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('interval_mult_hotword', self, dependency='interval_mult'),
			configprop('interval_max_mult', self, dependency='interval_mult', minvalue=1, prop_type=configprop.INTEGER_TYPE),
			configprop('start_times', self, delimiter=',', prop_type=configprop.STRINGLIST_TYPE, length=7, special=configprop.special(timermanager.verify, ['start_times', 'stop_times'])),
			configprop('stop_times', self, delimiter=',', prop_type=configprop.STRINGLIST_TYPE, length=7, special=configprop.special(timermanager.verify, ['start_times', 'stop_times'])),
			configprop('control_display_power', self, prop_type=configprop.BOOLEAN_TYPE, dependency=['display_type', displaymanager.get_hdmi()]),
			configprop('allow_triggers', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('convert_option', self, prop_type=configprop.INTEGER_TYPE, possible=convertmanager.get_convert_options(), dependency=['display_type', displaymanager.get_spi()]),
			configprop('image_width', self, minvalue=1, prop_type=configprop.INTEGER_TYPE),
			configprop('image_height', self, minvalue=1, prop_type=configprop.INTEGER_TYPE),
			configprop('invert_colors', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('grayscale', self, prop_type=configprop.BOOLEAN_TYPE, dependency=['display_type', displaymanager.get_hdmi()]),
			configprop('colors_num', self, minvalue=1, notempty=False, prop_type=configprop.INTEGER_TYPE, dependency=['display_type', displaymanager.get_hdmi()]),
			configprop('horizontal', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('auto_orientation', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('turned', self, prop_type=configprop.BOOLEAN_TYPE, dependency='horizontal'),
			configprop('rotation', self, prop_type=configprop.INTEGER_TYPE, dependency=['horizontal', '0'], possible=convertmanager.get_rotation()),
			configprop('auto_gamma', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('auto_level', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('normalize', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('brightness', self, minvalue=-100, maxvalue=100, prop_type=configprop.INTEGER_TYPE),
			configprop('contrast', self, minvalue=-100, maxvalue=100, prop_type=configprop.INTEGER_TYPE),
			configprop('background_color', self, possible=convertmanager.get_background_colors()),
			configprop('randomize', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('photos_from', self, notempty=False, convert=filteringmanager.convert, checkfunction=filteringmanager.verify, special=configprop.special(filteringmanager.verify_times, ['photos_from', 'photos_to'])),
			configprop('photos_to', self, notempty=False, convert=filteringmanager.convert, checkfunction=filteringmanager.verify, special=configprop.special(filteringmanager.verify_times, ['photos_from', 'photos_to'])),
			configprop('no_photos', self, minvalue=1, notempty=False, prop_type=configprop.INTEGER_TYPE),
			configprop('sorting', self, possible=filteringmanager.get_sorting()),
			configprop('show_weather', self, prop_type=configprop.BOOLEAN_TYPE),
			configprop('apikey', self, dependency='show_weather'),
			configprop('lat', self, dependency='show_weather'),
			configprop('lon', self, dependency='show_weather'),
			configprop('position', self, dependency='show_weather', prop_type=configprop.INTEGER_TYPE, possible=weatherstampmanager.get_positions()),
			configprop('font', self, dependency='show_weather', minvalue=8, prop_type=configprop.INTEGER_TYPE),
			configprop('font_color', self, dependency='show_weather', possible=weatherstampmanager.get_colors()),
			configprop('use_telebot', self, prop_type=configprop.BOOLEAN_TYPE, resetneeded=True),
			configprop('token', self, dependency='use_telebot', checkfunction=telebotmanager.check_token),
			configprop('chat_id', self, notempty=False, dependency='use_telebot', delimiter=',', prop_type=configprop.INTLIST_TYPE),
			configprop('use_web', self, prop_type=configprop.BOOLEAN_TYPE, resetneeded=True),
			configprop('web_host', self, dependency='use_web', checkfunction=connection.is_ip),
			configprop('web_port', self, minvalue=1, maxvalue=65535, dependency='use_web', prop_type=configprop.INTEGER_TYPE),
			configprop('show_stats', self, dependency='use_web', prop_type=configprop.BOOLEAN_TYPE),
			configprop('dark_theme', self, dependency='use_web', prop_type=configprop.BOOLEAN_TYPE)
		]
	
	def legacy_convert(self):
		#legacy exceptional backward handling for converting one property to another property under different name
		#and the ones that misc.configprop.convert could not handle
		legacy = [
			type("", (), {"old" : ['Album settings', 'sort_desc'], "new" : ['Filtering', 'sorting'], "convert" : filteringmanager.get_descending})
		]
		
		for sett in legacy:
			try:
				if not self.config.has_section(sett.new[0]): self.config.add_section(sett.new[0])
				val = self.config.get(sett.old[0], sett.old[1])
				self.config.set(sett.new[0], sett.new[1], sett.convert(val))
			except Exception:
				pass
		#end
		
	def check_system (self):
		ret = False;
		
		process = subprocess.Popen(self.__SPI_CHECK1, shell=True, stdout=subprocess.PIPE)
		process.wait()
		out, err = process.communicate()
		
		process = subprocess.Popen(self.__SPI_CHECK2, shell=True, stdout=subprocess.PIPE)
		process.wait()
		out2, err2 = process.communicate()
		
		if not err and out2:
			ret = True

		return ret