#!/usr/bin/env python3

import sys, os, signal
import atexit

from misc.constants import constants
from misc.logs import logs
from misc.connection import connection
from modules.configmanager import configmanager
from modules.pidmanager import pidmanager
from modules.oauthmanager import oauthmanager
from modules.albummanager import albummanager
from modules.indexmanager import indexmanager
from modules.randommanager import randommanager
from modules.convertmanager import convertmanager
from modules.photomanager import photomanager
from modules.filteringmanager import filteringmanager
from modules.displaymanager import displaymanager
from modules.intervalmanager import intervalmanager

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
	print ("--help			this help")
else: 	
	startTime = logs.start_time()

	try:
		config = configmanager(constants.CONFIG_FILE)
	except Exception as e:
		logs.show_log("Error loading {} configuration file! {}".format(constants.CONFIG_FILE ,e))
		raise

	logs.show_log ("Verifying configuration...")

	try:
		config.verify()
	except Exception as e:
		logs.show_log("Error verifying cofiguration file! {}".format(e))
		raise
		
	logs.show_log ("OK!")

	if '--check-config' in [x.lower() for x in sys.argv]: exit ()

	if not '--test' in [x.lower() for x in sys.argv] and not '--test-convert' in [x.lower() for x in sys.argv]:
		try:
			if not config.check_system():
				raise Exception("SPI is disabled on system!")
		except Exception as e:
			logs.show_log("Error on checking system configuration - SPI is not enabled! {}".format(e))
			raise

	try:
		pidman = pidmanager(config.get('pid_file'))
		
		lastPid = pidman.read()
		
		if int(lastPid) > 0:
			try:
				os.kill(int(lastPid), signal.SIGKILL)
			except Exception: 
				pass
			pidman.remove()
		
		pidman.save()	
		atexit.register(pidman.remove)
	except Exception as e:
		logs.show_log("Error! {}".format(e))
		raise
	
	if not '--test-display' in [x.lower() for x in sys.argv] and not '--test-convert' in [x.lower() for x in sys.argv]:
		logs.show_log ("Checking connection...")

		conn = connection.check_internet(constants.SCOPES[0], constants.CHECK_CONNECTION_TIMEOUT)
		if conn:
			logs.show_log("Error! {} - No connection to the Internet".format(conn))
			raise

		logs.show_log ("OK!")

		logs.show_log ("Loading credentials...")

		try:
			authmanager = oauthmanager()
			authmanager.manage_pickle(config.get('pickle_file'), config.get('cred_file'), constants.SCOPES)
		except Exception as e:
			logs.show_log("Error! {}".format(e))
			raise

		logs.show_log ("Success!")

		logs.show_log ("Trying to build service with given credentials...")

		error = None

		try:
			authmanager.build_service(constants.SERVICE_NAME, constants.SERVICE_VERSION)
		except Exception as exc:
			error = str(exc)

		if error:
			logs.show_log ("Fail! {}".format(error))
		else:
			logs.show_log ("Success!")

			logs.show_log ("Getting all albums...")

			try:
				authmanager.get(constants.GOOGLE_PHOTOS_PAGESIZE, bool(constants.GOOGLE_PHOTOS_EXCLUDENONAPPCREATEDDATA), \
							   constants.GOOGLE_PHOTOS_NEXTTOKENPAGE_RESPONSE_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_RESPONSE)
			except Exception as exc:
				error = str(exc)

			if error:
				logs.show_log ("Fail! {}".format(error))
			else:
				logs.show_log ("Success!")

				logs.show_log ("Getting desired album(s)...")

				album = albummanager(authmanager.get_response(), \
									 config.get('album_names'), constants.GOOGLE_PHOTOS_ALBUMS_TITLE_HEADER)

				if album.get_albums().empty:
					logs.show_log ("Fail! Can't find album {}".format(config.get('album_names')))
				else:	
					logs.show_log ("Success!")

					logs.show_log ("Fetching albums data...")

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
						logs.show_log ("Fail! {}".format(error))
					elif album.get_data().empty:
						logs.show_log ("Fail! Couldn't retrieve albums!")
					else:
						logs.show_log ("Success!")

						photoman = photomanager()
						photos = photoman.set_photos(album, constants.GOOGLE_PHOTOS_ALBUMS_MEDIAMETADATA_HEADER, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_HEADER, \
													constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER, constants.IMAGE_MIMETYPE_STARTING_STRING)

						#get number of photos available from the album
						totalNum = photoman.get_num_of_photos(photos)
						logs.show_log ("Found {} photos".format(totalNum))

						#exit if no photos
						if totalNum == 0:
							logs.show_log ("No photos in albums!")
						else:
							logs.show_log ("Reading last photo index file...")

							#read index from file to change after each run
							try:
								indmanager = indexmanager(config.get('photo_index_file'))
							except IOError as e:
								logs.show_log ("Error opening file {}: {}".format(config.get('photo_index_file'), e))
								raise

							logs.show_log ("Success!")		

							logs.show_log ("Filtering photos...")

							#filter photos by from date
							if config.get('photos_from'):
								try:
									photos = filteringmanager.filter_by_from_date(photos, config.get('photos_from'), \
																				  constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER)
								except Exception as exc:
									logs.show_log ("Error parsing configured time photos_from: {}".format(exc))
									raise

							#filter photos by to date
							if config.get('photos_to'):
								try:
									photos = filteringmanager.filter_by_to_date(photos, config.get('photos_to'), \
																				constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER)
								except Exception as exc:
									logs.show_log ("Error parsing configured time photos_to: {}".format(exc))
									raise

							#filter photos by number
							if config.get('no_photos'):
								try:
									photos = filteringmanager.filter_by_number(photos, config.getint('no_photos'))							
								except Exception as exc:
									logs.show_log ("Error parsing configured time no_photos: {}".format(exc))
									raise

							logs.show_log ("and sorting ...")
							#photos sorting
							if config.get('sort_desc'):
								try:
									photos = filteringmanager.sort(photos, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_CREATIONTIME_HEADER, photos.creationTime, \
																   bool(config.getint('sort_desc')))
								except Exception as exc:
									logs.show_log ("Error parsing configured time sort_desc: {}".format(exc))
									raise

							#update index
							photos = photoman.reset_index(photos)

							#get number of photos available from the album
							filterNum = photoman.get_num_of_photos(photos)
							logs.show_log ("Filtered {} photos".format(filterNum))

							#exit if no photos
							if filterNum == 0:
								logs.show_log ("No photos after filtering!")
							else:
								if config.getint('randomize') == 0:
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
									indmanager.set_index(randomman.get_random(indmanager.get_id()))

								#get filename + extension, download url and download file
								photo = photoman.get_photo_by_index(photos, indmanager.get_index())
								logs.show_log ("Photo to show:\n{}".format(photo))

								indmanager.set_id(photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_ID_HEADER))	
								downloadUrl = photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_BASEURL_HEADER) + \
																			constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_GET_DETAILS

								if config.getint('interval_mult') == 1:
									#if photo comment contains hotword then multiply interval by it's value and photo will be displayed longer
									intervalman = intervalmanager(config.get('interval_mult_file'))
									intervalman.remove()
									try:
										comment = str(photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_DESCRIPTION_HEADER))
										intervalman.save_interval(comment, config.get('interval_mult_hotword'), config.getint('interval_max_mult'))
									except Exception:
										pass

								filename = config.get('photo_download_name') + "." \
													  + constants.TYPE_TO_EXTENSION[photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_MIMETYPE_HEADER)]
								targetFilename = os.path.join(config.get('photo_convert_path'), \
															  config.get('photo_convert_filename'))				

								logs.show_log ("Downloading next photo...")	

								try:
									ret = connection.download_file(downloadUrl, config.get('photo_convert_path') , filename, constants.OK_STATUS_ERRORCODE)
								except Exception as exc:
									ret = str(exc)

								if ret != constants.OK_STATUS_ERRORCODE:
									logs.show_log ("Fail! Server error: {}".format(str(ret)))
								else:
									logs.show_log ("Success!")

									#save index of current photo for next run
									try:
										indmanager.save()
									except IOError as e:
										logs.show_log ("Error saving file {}: {}".format(config.get('photo_index_file'), e))
										raise

									logs.show_log ("Processing the photo...")

									origwidth = photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_WIDTH_HEADER)
									origheight = photoman.get_photo_attribute(photo, constants.GOOGLE_PHOTOS_ALBUMS_PHOTO_HEIGHT_HEADER)							

									#convert image
									if convertmanager().convert_image(origwidth, origheight, int(config.get('convert_option')), config.get('convert_bin_path'), \
																filename, config.getint('image_width'), config.getint('image_height'), config.getint('invert_colors'),\
																config.getint('horizontal'), config.get('background_color'), targetFilename)  != None:
										logs.show_log ("Fail! {}".format(str(err)))
									else:
										logs.show_log ("Success!")

										if not '--test' in [x.lower() for x in sys.argv]:
											logs.show_log ("Sending to display...")

											displayman = displaymanager(config.get('display'))

											try:
												displayman.show_image(targetFilename)
											except Exception as exc:
												logs.show_log ("Error sending photo to display: {}".format(exc))
												raise
	elif '--test-display' == sys.argv[1].lower():
		targetFilename = os.path.join(config.get('photo_convert_path'), config.get('photo_convert_filename'))	
		if sys.argv[2]:
			targetFilename = sys.argv[2]

		if not os.path.exists(targetFilename):
			raise Exception("No file: {}!".format(targetFilename))
			
		logs.show_log ("Sending to display...")
		displayman = displaymanager(config.get('display'))

		try:
			displayman.show_image(targetFilename)
		except Exception as exc:
			logs.show_log ("Error sending photo to display: {}".format(exc))
			raise																			
	elif '--test-convert' == sys.argv[1].lower():
		filename = os.path.join(config.get('photo_convert_path'), config.get('photo_download_name'))
		targetFilename = os.path.join(config.get('photo_convert_path'), config.get('photo_convert_filename'))
		if sys.argv[2]:
			filename = sys.argv[2]

		if not os.path.exists(filename):
			raise Exception("No file: {}!".format(filename))
		
		convertman = convertmanager()
		err, width, height = convertman.get_image_size(config.get('convert_bin_path'),filename)
		
		if err != None:
			logs.show_log ("Fail! {}".format(str(err)))
		else:
			if convertman.convert_image(width, height, int(config.get('convert_option')), config.get('convert_bin_path'), \
							filename, config.getint('image_width'), config.getint('image_height'), config.getint('invert_colors'),\
							config.getint('horizontal'), config.get('background_color'), targetFilename)  != None:
				logs.show_log ("Fail! {}".format(str(err)))
			else:
				logs.show_log ("Success!")
		
	endTime = logs.end_time()
	logs.show_log ("Done in{}".format(logs.execution_time(startTime,endTime)))