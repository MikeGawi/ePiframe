#!/usr/bin/env python3

import sys, os, signal, glob
import atexit, shutil

from misc.constants import constants
from misc.logs import logs
from misc.connection import connection
from modules.configmanager import configmanager
from modules.pidmanager import pidmanager
from modules.oauthmanager import oauthmanager
from modules.albummanager import albummanager
from modules.weathermanager import weathermanager
from modules.weatherstampmanager import weatherstampmanager
from modules.indexmanager import indexmanager
from modules.randommanager import randommanager
from modules.convertmanager import convertmanager
from modules.photomanager import photomanager
from modules.filteringmanager import filteringmanager
from modules.displaymanager import displaymanager
from modules.intervalmanager import intervalmanager
from modules.databasemanager import databasemanager
from modules.usersmanager import usersmanager
from modules.localsourcemanager import localsourcemanager
from modules.pluginsmanager import pluginsmanager

def main():
	if sys.version_info[0] < constants.MINIMAL_PYTHON_VERSION:
		raise Exception("Must be using Python {}!".format(constants.MINIMAL_PYTHON_VERSION))

	print ("ePiframe - e-Paper Raspberry Pi Photo Frame")

	if '--help' in [x.lower() for x in sys.argv]:
		print ("Command line options:")
		print ("--check-config		checks configuration file")
		print ("--test			tests credentials, pickle file and downloads photo")
		print ("			without sending it to the display")
		print ("--test-display [file]	displays the photo file on attached display")
		print ("			with current ePiframe configuration")
		print ("--test-convert [file]	converts the photo file to configured")
		print ("			photo_convert_filename current ePiframe configuration")
		print ("--no-skip		like --test but is not skipping to another photo")
		print ("--users			manage users")
		print ("--help			this help")
	else: 	
		startTime = logs.start_time()

		try:
			config = configmanager(constants.CONFIG_FILE, constants.CONFIG_FILE_DEFAULT)
		except Exception as e:
			logs.show_log("Error loading {} configuration file! {}".format(constants.CONFIG_FILE ,e))
			raise

		logging = logs(config.get('log_files'))
		logging.log("Verifying configuration...")

		try:
			config.verify()
		except Warning as e:
			logging.log("Warning verifying configuration file! {}".format(e))
			pass
		except Exception as e:
			logging.log("Error verifying configuration file! {}".format(e))
			raise

		pidman = pidmanager(config.get('pid_file'))

		pluginsman = pluginsmanager(os.path.dirname(os.path.realpath(__file__)), pidman, logging, config)

		if len(pluginsman.get_enabled()) > 0:
			logging.log("Verifying plugins configuration...")

			for plug in pluginsman.get_enabled():
				try:
					plug.config.verify()
				except Warning as e:
					logging.log("Warning verifying configuration file for '{}' plugin! {}".format(plug.name, e))
					pass
				except Exception as e:
					logging.log("Error verifying configuration file for '{}' plugin! {}".format(plug.name, e))
					raise

		logging.log("OK!")

		if '--check-config' in [x.lower() for x in sys.argv]: exit()

		if '--users' in [x.lower() for x in sys.argv]:
			logging.log (constants.USERS_ACTIONS_TAG + "Starting database management module...")
			try:
				dbman = databasemanager()
				logging.log (constants.USERS_ACTIONS_TAG + "Success!")
			except Exception as exc:
				logging.log (constants.USERS_ACTIONS_TAG + "Fail! {}".format(str(exc)))
				raise

			logging.log (constants.USERS_ACTIONS_TAG + "Starting users management module...")
			try:
				usersman = usersmanager(dbman)
				logging.log (constants.USERS_ACTIONS_TAG + "Success!")
			except Exception as exc:
				logging.log (constants.USERS_ACTIONS_TAG + "Fail! {}".format(str(exc)))
				raise

			usersman.manage(logging)
			exit()

		if not '--test' in [x.lower() for x in sys.argv] and not '--test-convert' in [x.lower() for x in sys.argv] and not '--no-skip' in [x.lower() for x in sys.argv] and not displaymanager.is_hdmi(config.get('display_type')):
			try:
				if not config.check_system():
					raise Exception("SPI is disabled on system!")
			except Exception as e:
				logging.log("Error on checking system configuration - SPI is not enabled! {}".format(e))
				raise

		try:
			lastPid = pidman.read()
			if int(lastPid) > 0:
				try:
					if os.path.basename(__file__) in get_pid_name(lastPid):
						os.kill(int(lastPid), signal.SIGKILL)
				except Exception: 
					pass
				pidman.remove()

			pidman.save()	
			atexit.register(pidman.remove)
		except Exception as e:
			logging.log("Error! {}".format(e))
			raise

		if not '--test-display' in [x.lower() for x in sys.argv] and not '--test-convert' in [x.lower() for x in sys.argv] and not '--users' in [x.lower() for x in sys.argv]:

			logging.log ("Checking sources...")

			if not bool(config.getint('use_google_photos')) and not bool(config.getint('use_local')):
				logging.log ("No photo sources picked! Check the configuration!")
				raise Exception ("No photo sources picked! Check the configuration!")

			logging.log ("OK!")

			photoman = photomanager()
			photos = None

			if bool(config.getint('use_google_photos')):
				logging.log ("Getting data from Google Photos source...")
				logging.log ("Checking connection...")

				conn = connection.check_internet(constants.SCOPES[0], constants.CHECK_CONNECTION_TIMEOUT)
				if conn:
					logging.log("Error! {} - No connection to the Internet".format(conn))
					if not bool(config.getint('use_local')):
						raise Exception ("Error! {} - No connection to the Internet".format(conn))
					else:
						logging.log("Continuing with local source...")
				else:								
					logging.log ("OK!")

					logging.log ("Loading credentials...")

					try:
						authmanager = oauthmanager()
						authmanager.manage_pickle(config.get('pickle_file'), config.get('cred_file'), constants.SCOPES)
					except Exception as e:
						logging.log("Error! {}".format(e))
						raise

					logging.log ("Success!")

					logging.log ("Trying to build service with given credentials...")

					error = None

					try:
						authmanager.build_service(constants.SERVICE_NAME, constants.SERVICE_VERSION)
					except Exception as exc:
						error = str(exc)

					if error:
						logging.log ("Fail! {}".format(error))
						raise
					else:
						logging.log ("Success!")

						logging.log ("Getting all albums...")

						try:
							authmanager.get(constants.GOOGLE_PHOTOS_PAGESIZE, bool(constants.GOOGLE_PHOTOS_EXCLUDENONAPPCREATEDDATA), \
										   constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_RESPONSE)
						except Exception as exc:
							error = str(exc)

						if error:
							logging.log ("Fail! {}".format(error))
							raise Exception ("Fail! {}".format(error))
						else:
							logging.log ("Success!")

							logging.log ("Getting desired album(s)...")

							album = albummanager(authmanager.get_response(), \
												 config.get('album_names'), constants.GOOGLE_PHOTOS_ALBUMS_TITLE_HEADER)

							if album.get_albums().empty:
								logging.log ("Fail! Can't find album {}".format(config.get('album_names')))
								raise Exception ("Fail! Can't find album {}".format(config.get('album_names')))
							else:	
								logging.log ("Success!")

								logging.log ("Fetching albums data...")

								error = None

								try:
									for index, albumId in album.get_albums()[constants.GOOGLE_PHOTOS_ALBUMS_ID_HEADER].iteritems():	
										items = authmanager.get_items(constants.GOOGLE_PHOTOS_ALBUMS_ALBUMID_HEADER, albumId, \
																	  constants.GOOGLE_PHOTOS_ALBUMS_MEDIAITEMS_HEADER, \
																	  constants.GOOGLE_PHOTOS_PAGESIZE, \
																	  constants.GOOGLE_PHOTOS_PAGESIZE_HEADER, \
																	  constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_HEADER, \
																	  constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER)
										album.append_data(items)					
								except Exception as exc:
									error = str(exc)

								if error:
									logging.log ("Fail! {}".format(error))
									raise
								elif album.get_data().empty:
									logging.log ("Fail! Couldn't retrieve albums!")
									raise
								else:
									photos = photoman.set_photos(album, constants.GOOGLE_PHOTOS_ALBUMS_MEDIAMETADATA_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_HEADER, \
																constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER, constants.IMAGE_MIMETYPE_STARTING_STRING,\
																constants.PHOTOS_SOURCE_LABEL, constants.GOOGLE_PHOTOS_SOURCE)
									logging.log ("Success!")

			if bool(config.getint('use_local')):
				logging.log ("Getting data from local source...")
				localman = localsourcemanager(config.get('local_path'), bool(config.getint('local_subfolders')), constants.EXTENSIONS)
				localphotos = localman.get_local_photos(constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER,\
														constants.PHOTOS_SOURCE_LABEL, constants.LOCAL_SOURCE)
				photos = photoman.append_photos(photos, localphotos)
				logging.log ("Success!")			

			for plug in pluginsman.plugin_source():
				try:
					logging.log ("Getting data from plugin '{}' source...".format(plug.name))
					plugphotos = plug.add_photo_source(constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER, constants.PHOTOS_SOURCE_LABEL, photoman)
					photos = photoman.append_photos(photos, plugphotos)
					logging.log ("Success!")
				except Exception as exc:
					logging.log ("Error: {}".format(exc))
					raise

			#get number of photos available from the album
			totalNum = photoman.get_num_of_photos(photos) if photos is not None else 0
			logging.log ("Found {} photos".format(totalNum))

			#exit if no photos
			if totalNum == 0:
				logging.log ("No photos in albums!")
			else:
				logging.log ("Reading last photo index file...")

				#read index from file to change after each run
				try:
					indmanager = indexmanager(config.get('photo_index_file'))
				except IOError as e:
					logging.log ("Error opening file {}: {}".format(config.get('photo_index_file'), e))
					raise

				logging.log ("Success!")		

				logging.log ("Filtering photos...")

				#filter photos by from date
				if config.get('photos_from'):
					try:
						photos = filteringmanager.filter_by_from_date(photos, config.get('photos_from'), \
																	  constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER)
					except Exception as exc:
						logging.log ("Error parsing configured time photos_from: {}".format(exc))
						raise

				#filter photos by to date
				if config.get('photos_to'):
					try:
						photos = filteringmanager.filter_by_to_date(photos, config.get('photos_to'), \
																	constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER)
					except Exception as exc:
						logging.log ("Error parsing configured time photos_to: {}".format(exc))
						raise

				#filter photos by number
				if config.get('no_photos'):
					try:
						photos = filteringmanager.filter_by_number(photos, config.getint('no_photos'))							
					except Exception as exc:
						logging.log ("Error parsing configured time no_photos: {}".format(exc))
						raise

				logging.log ("and sorting ...")
				#photos sorting
				photos = filteringmanager.sort(photos, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER, photos[constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER], config.get('sorting'))
				#update index
				photos = photoman.reset_index(photos)

				for plug in pluginsman.plugin_photos_list():
					try:
						logging.log ("Changing photo list by plugin '{}'...".format(plug.name))
						photos = plug.change_photos_list(constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER, constants.PHOTOS_SOURCE_LABEL, photos,\
														photoman, indmanager, filteringmanager)
						logging.log ("Success!")
					except Exception as exc:
						logging.log ("Error: {}".format(exc))
						raise

				#get number of photos available from the album
				filterNum = photoman.get_num_of_photos(photos)
				logging.log ("Filtered {} photos".format(filterNum))

				#exit if no photos
				if filterNum == 0:
					logging.log ("No photos after filtering!")
				else:
					if not bool(config.getint('randomize')):
						#find previous photo	
						dbid = next(iter(photos[photoman.get_photos_attribute(photos, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER) == indmanager.get_id()].index), \
									constants.NOMATCH_INDICATOR_STRING)

						if dbid != constants.NOMATCH_INDICATOR_STRING:
							indmanager.set_index(dbid + 1)
						else:
							indmanager.set_index(indmanager.get_index() + 1)

						#don't go above the number of photos
						indmanager.check_index(filterNum)
					else:
						#get random photo
						randomman = randommanager(config.get('photo_list_file'), photos, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER)
						indmanager.set_index(randomman.get_random(indmanager.get_id(), '--no-skip' in [x.lower() for x in sys.argv]))

					#get filename + extension, download url and download file
					photo = photoman.get_photo_by_index(photos, indmanager.get_index())
					logging.log ("Photo to show:\n{}".format(photo))

					indmanager.set_id(photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER))	

					if bool(config.getint('interval_mult')):
						#if photo comment contains hotword then multiply interval by it's value and photo will be displayed longer
						intervalman = intervalmanager(config.get('interval_mult_file'))
						if not '--no-skip' in [x.lower() for x in sys.argv]:
							intervalman.remove()
						try:
							if not '--no-skip' in [x.lower() for x in sys.argv]:
								if photo[constants.PHOTOS_SOURCE_LABEL] == constants.GOOGLE_PHOTOS_SOURCE:							
									comment = str(photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_DESCRIPTION_HEADER))
								else:
									err, comment = convertmanager().get_image_comment(config.get('convert_bin_path'), photo[constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER])
								intervalman.save_interval(comment, config.get('interval_mult_hotword'), config.getint('interval_max_mult'))
						except Exception:
							pass

					for oldfile in glob.glob(os.path.join(config.get('photo_convert_path'), config.get('photo_download_name')) + '.*'): os.remove(oldfile)

					logging.log ("Getting next photo...")
					if photo[constants.PHOTOS_SOURCE_LABEL] == constants.GOOGLE_PHOTOS_SOURCE:
						filename = config.get('photo_download_name') + "." \
											  + constants.TYPE_TO_EXTENSION[photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER)]

						downloadUrl = photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_BASEURL_HEADER) + constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_GET_DETAILS

						try:
							ret = connection.download_file(downloadUrl, config.get('photo_convert_path'), filename, constants.OK_STATUS_ERRORCODE, constants.CHECK_CONNECTION_TIMEOUT)
						except Exception as exc:
							ret = str(exc)

						if ret != constants.OK_STATUS_ERRORCODE: logging.log ("Fail! Server error: {}".format(str(ret)))
					else:
						plug_with_source = next((x for x in pluginsman.get_plugin_source() if x.SOURCE == photo[constants.PHOTOS_SOURCE_LABEL]), None)

						if plug_with_source and pluginsman.plugin_source_get_file(plug_with_source):
							filename = plug_with_source.add_photo_source_get_file(photo, config.get('photo_convert_path'), config.get('photo_download_name'),\
																	   constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER, constants.PHOTOS_SOURCE_LABEL, photoman)
						else:
							sourceFile = photo[constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER]					
							err, imagetype = convertmanager().get_image_format(config.get('convert_bin_path'), sourceFile, constants.FIRST_FRAME_GIF)

							filename = config.get('photo_download_name') + "." + str(sourceFile).rsplit('.')[-1].lower()
							if not err and imagetype:
								try:
									filename = config.get('photo_download_name') + "." + constants.TYPE_TO_EXTENSION[constants.MIME_START + imagetype.lower()]
								except Exception:
									pass

							filename = os.path.join(config.get('photo_convert_path'), filename)
							try: 
								shutil.copy(sourceFile, filename)
							except Exception:
								pass

					if not os.path.exists(filename):
						logging.log ("Fail! File was not retrieved! : {}".format(str(ret)))
					else:
						logging.log ("Success!")

						#save index of current photo for next run
						try:
							if not '--no-skip' in [x.lower() for x in sys.argv]:
								indmanager.save()
						except IOError as e:
							logging.log ("Error saving file {}: {}".format(config.get('photo_index_file'), e))
							raise

						targetFilename = os.path.join(config.get('photo_convert_path'), config.get('photo_convert_filename'))					

						if convert (filename, targetFilename, config, pluginsman, logging, photo):
							if not '--test' in [x.lower() for x in sys.argv] and not '--no-skip' in [x.lower() for x in sys.argv]:
								logging.log ("Sending to display...")

								displayman = displaymanager(config.get('display'), config.get('display_type'), config.get('fbi_bin_path'), config.get('tty'))

								try:
									displayman.show_image(targetFilename)
								except Exception as exc:
									logging.log ("Error sending photo to display: {}".format(exc))
									raise
						else: logging.log ("Fail!")

		if '--test-convert' in [x.lower() for x in sys.argv]:
			filename = os.path.join(config.get('photo_convert_path'), config.get('photo_download_name'))	
			targetFilename = os.path.join(config.get('photo_convert_path'), config.get('photo_convert_filename'))

			fil = next((x for x in [y.lower() for y in sys.argv[1:]] if not '--' in x), '')

			if fil:
				filename = fil
			else:
				files = glob.glob('{}.*'.format(filename))
				if not files: raise Exception("No file: {}.*!".format(filename))
				fil = max(files, key=os.path.getctime)
				filename = fil

			if not os.path.exists(filename):
				raise Exception("No file: {}!".format(filename))

			err, imagetype = convertmanager().get_image_format(config.get('convert_bin_path'), filename, constants.FIRST_FRAME_GIF)
			source = config.get('photo_download_name') + "." + str(filename).rsplit('.')[-1].lower()
			if not err and imagetype:
				try:
					source = config.get('photo_download_name') + "." + constants.TYPE_TO_EXTENSION[constants.MIME_START + imagetype.lower()]
				except Exception as exc:
					ret = str(exc)

			try: 
				shutil.copy(filename, source)
			except Exception:
				pass

			if not os.path.exists(source):
				logging.log ("Fail! File was not retrieved! : {}".format(str(ret)))
			else:
				import pandas as pand
				if not convert (source, targetFilename, config, pluginsman, logging, pand.DataFrame()):
					logging.log ("Fail!")

		if '--test-display' in [x.lower() for x in sys.argv]:
			targetFilename = os.path.join(config.get('photo_convert_path'), config.get('photo_convert_filename'))	

			fil = next((x for x in [y.lower() for y in sys.argv[1:]] if not '--' in x), '')

			if fil:
				targetFilename = fil

			if not os.path.exists(targetFilename):
				raise Exception("No file: {}!".format(targetFilename))

			logging.log ("Sending to display...")
			displayman = displaymanager(config.get('display'), config.get('display_type'), config.get('fbi_bin_path'), config.get('tty'))

			try:
				displayman.show_image(targetFilename)
			except Exception as exc:
				logging.log ("Error sending photo to display: {}".format(exc))
				raise		

		endTime = logs.end_time()
		logging.log ("Done in{}".format(logs.execution_time(startTime,endTime)))

def convert (_filename, _targetFilename, _config, _plugins, _logging, _photo):
	ret = False
	filename_pre = os.path.join(os.path.split(_filename)[0], 'pre_'+os.path.split(_filename)[1])
	try: 
		shutil.copy(_filename, filename_pre)
	except Exception:
		pass

	for plug in _plugins.plugin_preprocess():
		try:
			_logging.log ("Preprocessing photo by plugin '{}'...".format(plug.name))
			plug.preprocess_photo(filename_pre, bool(_config.getint('horizontal')), convertmanager(), _photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER, constants.PHOTOS_SOURCE_LABEL)
			_logging.log ("Success!")
		except Exception as exc:
			_logging.log ("Error: {}".format(exc))
			raise

	err, width, height = convertmanager().get_image_size(_config.get('convert_bin_path'), filename_pre, constants.FIRST_FRAME_GIF)			
	
	_logging.log ("Processing the photo...")
	#convert image
	if err or convertmanager().convert_image(width, height, filename_pre + constants.FIRST_FRAME_GIF, _targetFilename, _config, displaymanager.is_hdmi(_config.get('display_type'))) != None:
		_logging.log ("Fail! {}".format(str(err)))
	else:
		_logging.log ("Success!")
		
		for plug in _plugins.plugin_postprocess():
			try:
				_logging.log ("Postprocessing photo by plugin '{}'...".format(plug.name))
				plug.postprocess_photo(_targetFilename, _config.getint('image_width'), _config.getint('image_height'), bool(_config.getint('horizontal')), convertmanager(), _photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER, constants.PHOTOS_SOURCE_LABEL)
				_logging.log ("Success!")
			except Exception as exc:
				_logging.log ("Error: {}".format(exc))
				raise
		
		if bool(_config.getint('show_weather')):
			_logging.log ("Getting weather data...")
			weatherman = weathermanager(_config.get('apikey'), _config.get('units'), _config.get('lat'), _config.get('lon'))

			try:
				weatherman.send_request(constants.WEATHER_BASE_URL, constants.CHECK_CONNECTION_TIMEOUT)
				if not weatherman.get_data(): raise Exception("Couldn't retrieve weather data!")
				_logging.log ("Success!")
				_logging.log ("Putting weather stamp...")
				weatherstampman = weatherstampmanager(_targetFilename, _config.getint('image_width'), _config.getint('image_height'),\
													  bool(_config.getint('horizontal')), _config.getint('font'),\
													  _config.get('font_color'), _config.getint('position'), _config.getint('rotation') )
				weatherstampman.compose(weatherman.get_temperature(constants.WEATHER_TEMP_MAINTAG, constants.WEATHER_TEMP_TAG),\
										_config.get('units'), weatherman.get_weathericon(constants.WEATHER_ICON_MAINTAG,\
																						constants.WEATHER_ICON_POSITION,\
																						constants.WEATHER_ICON_TAG))
				_logging.log ("Success!")
			except Exception as exc:
				_logging.log ("Fail! {}".format(str(exc)))
		ret = True
	return ret
		
if __name__ == '__main__':
	main()