#!/usr/bin/env python3

import requests
import json
import sys

API_KEY = None
LAT_CORDS = 40.7127
LON_CORDS = -74.0060

print("ePiframe - e-Paper Raspberry Pi Photo Frame - OpenWeather API check tool.")
print("This tool will help test OpenWeather API call for ePiframe.")

if "--help" not in [argument.lower() for argument in sys.argv]:
    API_KEY = input("Enter API key from openweathermap.org: ")
    print("API key = " + str(API_KEY))

    LAT_CORDS = (
        input(
            "Enter latitude coordinates from https://www.maps.ie/coordinates.html [Leave empty for New York]:"
        )
        or LAT_CORDS
    )
    print("Latitude = " + str(LAT_CORDS))

    LON_CORDS = (
        input(
            "Enter longitude coordinates from https://www.maps.ie/coordinates.html [Leave empty for New York]:"
        )
        or LON_CORDS
    )
    print("Longitude = " + str(LON_CORDS))

    url = "https://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&units=metric&appid={}".format(
        LAT_CORDS, LON_CORDS, API_KEY
    )

    try:
        return_value = requests.get(url, timeout=5)
        return_value.raise_for_status()
    except Exception as exception:
        print(f"Couldn't retrieve weather data! {exception}")
        return_value = None

    if return_value:
        print("-=+*Success! Data retrieved with given credentials:")
        print(json.dumps(return_value.json(), indent=2, sort_keys=True))
