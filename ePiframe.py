#!/usr/bin/env python3

import sys, os, signal, glob
import atexit

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
		config = configmanager(constants.CONFIG_FILE)
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
		
	logging.log("OK!")

	if '--check-config' in [x.lower() for x in sys.argv]: exit ()
		
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

	if not '--test' in [x.lower() for x in sys.argv] and not '--test-convert' in [x.lower() for x in sys.argv] and not '--no-skip' in [x.lower() for x in sys.argv]:
		try:
			if not config.check_system():
				raise Exception("SPI is disabled on system!")
		except Exception as e:
			logging.log("Error on checking system configuration - SPI is not enabled! {}".format(e))
			raise

	try:
		pidman = pidmanager(config.get('pid_file'))

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
		logging.log ("Checking connection...")

		conn = connection.check_internet(constants.SCOPES[0], constants.CHECK_CONNECTION_TIMEOUT)
		if conn:
			logging.log("Error! {} - No connection to the Internet".format(conn))
			raise

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
			else:
				logging.log ("Success!")

				logging.log ("Getting desired album(s)...")

				album = albummanager(authmanager.get_response(), \
									 config.get('album_names'), constants.GOOGLE_PHOTOS_ALBUMS_TITLE_HEADER)

				if album.get_albums().empty:
					logging.log ("Fail! Can't find album {}".format(config.get('album_names')))
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
					elif album.get_data().empty:
						logging.log ("Fail! Couldn't retrieve albums!")
					else:
						logging.log ("Success!")

						photoman = photomanager()
						photos = photoman.set_photos(album, constants.GOOGLE_PHOTOS_ALBUMS_MEDIAMETADATA_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_HEADER, \
													constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER, constants.IMAGE_MIMETYPE_STARTING_STRING)

						#get number of photos available from the album
						totalNum = photoman.get_num_of_photos(photos)
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
							if config.get('sort_desc'):
								try:
									photos = filteringmanager.sort(photos, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER, photos.creationTime, \
																   bool(config.getint('sort_desc')))
								except Exception as exc:
									logging.log ("Error parsing configured time sort_desc: {}".format(exc))
									raise

							#update index
							photos = photoman.reset_index(photos)

							#get number of photos available from the album
							filterNum = photoman.get_num_of_photos(photos)
							logging.log ("Filtered {} photos".format(filterNum))

							#exit if no photos
							if filterNum == 0:
								logging.log ("No photos after filtering!")
							else:
								if not bool(config.getint('randomize')):
									#find previous photo	
									dbid = next(iter(photos[photoman.get_photos_attribute(photos, constants.GOOGLE_PHOTOS_ALBUMS_ID_HEADER) == indmanager.get_id()].index), \
												constants.NOMATCH_INDICATOR_STRING)

									if dbid != constants.NOMATCH_INDICATOR_STRING:
										dbid += 1
										indmanager.set_index(dbid)
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
								downloadUrl = photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_BASEURL_HEADER) + \
																			constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_GET_DETAILS

								if bool(config.getint('interval_mult')):
									#if photo comment contains hotword then multiply interval by it's value and photo will be displayed longer
									intervalman = intervalmanager(config.get('interval_mult_file'))
									if not '--no-skip' in [x.lower() for x in sys.argv]:
										intervalman.remove()
									try:
										if not '--no-skip' in [x.lower() for x in sys.argv]:
											comment = str(photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_DESCRIPTION_HEADER))
											intervalman.save_interval(comment, config.get('interval_mult_hotword'), config.getint('interval_max_mult'))
									except Exception:
										pass

								filename = config.get('photo_download_name') + "." \
													  + constants.TYPE_TO_EXTENSION[photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER)]
								targetFilename = os.path.join(config.get('photo_convert_path'), \
															  config.get('photo_convert_filename'))				

								logging.log ("Downloading next photo...")	

								try:
									ret = connection.download_file(downloadUrl, config.get('photo_convert_path') , filename, constants.OK_STATUS_ERRORCODE, constants.CHECK_CONNECTION_TIMEOUT)
								except Exception as exc:
									ret = str(exc)
									
								if not os.path.exists(filename):
									ret = "File was not downloaded!"

								if ret != constants.OK_STATUS_ERRORCODE:
									logging.log ("Fail! Server error: {}".format(str(ret)))
								else:
									logging.log ("Success!")

									#save index of current photo for next run
									try:
										if not '--no-skip' in [x.lower() for x in sys.argv]:
											indmanager.save()
									except IOError as e:
										logging.log ("Error saving file {}: {}".format(config.get('photo_index_file'), e))
										raise

									logging.log ("Processing the photo...")

									origwidth = photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_WIDTH_HEADER)
									origheight = photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_HEIGHT_HEADER)							

									#convert image
									if convertmanager().convert_image(origwidth, origheight, int(config.get('convert_option')), config.get('convert_bin_path'), \
																filename, config.getint('image_width'), config.getint('image_height'), config.getint('invert_colors'),\
																config.getint('horizontal'), config.get('background_color'), targetFilename,\
																os.path.join(config.get('photo_convert_path'), \
															    config.get('thumb_photo_download_name')), os.path.join(config.get('photo_convert_path'), \
															  	config.get('thumb_photo_convert_filename'))	)  != None:
										logging.log ("Fail! {}".format(str(err)))
									else:
										logging.log ("Success!")
										
										if bool(config.getint('show_weather')):
											logging.log ("Getting weather data...")
											weatherman = weathermanager(config.get('apikey'), config.get('units'), config.get('lat'), config.get('lon'))
											
											try:
												weatherman.send_request(constants.WEATHER_BASE_URL, constants.CHECK_CONNECTION_TIMEOUT)
												if not weatherman.get_data(): raise Exception("Couldn't retrieve weather data!")
												logging.log ("Success!")
												logging.log ("Putting weather stamp...")
												weatherstampman = weatherstampmanager(targetFilename, config.getint('image_width'), config.getint('image_height'),\
																					  bool(config.getint('horizontal')), config.getint('font'),\
																					  config.get('font_color'), config.getint('position'))
												weatherstampman.compose(weatherman.get_temperature(constants.WEATHER_TEMP_MAINTAG, constants.WEATHER_TEMP_TAG),\
																		config.get('units'), weatherman.get_weathericon(constants.WEATHER_ICON_MAINTAG,\
																														constants.WEATHER_ICON_POSITION,\
																														constants.WEATHER_ICON_TAG))
												logging.log ("Success!")
											except Exception as exc:
												logging.log ("Fail! {}".format(str(exc)))										
										
										if not '--test' in [x.lower() for x in sys.argv] and not '--no-skip' in [x.lower() for x in sys.argv]:
											logging.log ("Sending to display...")

											displayman = displaymanager(config.get('display'))

											try:
												displayman.show_image(targetFilename)
											except Exception as exc:
												logging.log ("Error sending photo to display: {}".format(exc))
												raise
												
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
		
		convertman = convertmanager()
		err, width, height = convertman.get_image_size(config.get('convert_bin_path'), filename)
		
		if err != None:
			logging.log ("Fail! {}".format(str(err)))
		else:
			logging.log ("Processing the photo...")
			if convertman.convert_image(width, height, int(config.get('convert_option')), config.get('convert_bin_path'), \
							filename, config.getint('image_width'), config.getint('image_height'), config.getint('invert_colors'),\
							config.getint('horizontal'), config.get('background_color'), targetFilename,\
							os.path.join(config.get('photo_convert_path'), \
							config.get('thumb_photo_download_name')), os.path.join(config.get('photo_convert_path'), \
							config.get('thumb_photo_convert_filename'))	)  != None:
				logging.log ("Fail! {}".format(str(err)))
			else:
				logging.log ("Success!")
		
				if bool(config.getint('show_weather')):
					logging.log ("Getting weather data...")
					weatherman = weathermanager(config.get('apikey'), config.get('units'), config.get('lat'), config.get('lon'))

					try:
						weatherman.send_request(constants.WEATHER_BASE_URL, constants.CHECK_CONNECTION_TIMEOUT)
						if not weatherman.get_data(): raise Exception("Couldn't retrieve weather data!")
						logging.log ("Success!")
						logging.log ("Putting weather stamp...")
						weatherstampman = weatherstampmanager(targetFilename, config.getint('image_width'), config.getint('image_height'),\
															  bool(config.getint('horizontal')), config.getint('font'),\
															  config.get('font_color'), config.getint('position'))
						weatherstampman.compose(weatherman.get_temperature(constants.WEATHER_TEMP_MAINTAG, constants.WEATHER_TEMP_TAG),\
												config.get('units'), weatherman.get_weathericon(constants.WEATHER_ICON_MAINTAG,\
																								constants.WEATHER_ICON_POSITION,\
																								constants.WEATHER_ICON_TAG))
						logging.log ("Success!")
					except Exception as exc:
						logging.log ("Fail! {}".format(str(exc)))
			
	if '--test-display' in [x.lower() for x in sys.argv]:
		targetFilename = os.path.join(config.get('photo_convert_path'), config.get('photo_convert_filename'))	
		
		fil = next((x for x in [y.lower() for y in sys.argv[1:]] if not '--' in x), '')

		if fil:
			filename = fil
	
		if not os.path.exists(targetFilename):
			raise Exception("No file: {}!".format(targetFilename))
			
		logging.log ("Sending to display...")
		displayman = displaymanager(config.get('display'))

		try:
			displayman.show_image(targetFilename)
		except Exception as exc:
			logging.log ("Error sending photo to display: {}".format(exc))
			raise		
		
	endTime = logs.end_time()
	logging.log ("Done in{}".format(logs.execution_time(startTime,endTime)))