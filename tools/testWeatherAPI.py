#!/usr/bin/env python3

import requests, json, sys

API_KEY = None
LAT_COORDS = 40.7127
LON_COORDS = -74.0060

print ("ePiframe - e-Paper Raspberry Pi Photo Frame - OpenWeather API check tool.")
print ("This tool will help test OpenWeather API call for ePiframe.")

if not '--help' in [x.lower() for x in sys.argv]:
	API_KEY = input("Enter API key from openweathermap.org: ")
	print ('API key = ' + str(API_KEY))
	
	LAT_COORDS = input("Enter latitude coordinates from https://www.maps.ie/coordinates.html [Leave empty for New York]:") or LAT_COORDS
	print ('Latitude = ' + str(LAT_COORDS))
	
	LON_COORDS = input("Enter longtitude coordinates from https://www.maps.ie/coordinates.html [Leave empty for New York]:") or LON_COORDS
	print ('Longtitude = ' + str(LON_COORDS))
	
	url = "https://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&units=metric&appid={}".format(LAT_COORDS,LON_COORDS,API_KEY)
	
	try:
		ret = requests.get(url, timeout=5)
		ret.raise_for_status()		
	except Exception as exc:
		print ("Couldn't retrieve weather data! {}".format(exc))
		ret = None
	
	if ret:
		print ("-=+*Success! Data retrieved with given credentials:")
		print(json.dumps(ret.json(), indent=2, sort_keys=True))