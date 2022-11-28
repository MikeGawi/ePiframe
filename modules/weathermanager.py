from typing import Any, List
import requests


class WeatherManager:

    __UNITS_VALUES = ["metric", "imperial"]

    def __init__(self, apikey, units, lat, lon):
        self.__apikey = apikey
        self.__units = units
        self.__lat = lat
        self.__lon = lon
        self.__data = None

    @staticmethod
    def get_response_json(url: str, timeout: int) -> Any:
        try:
            return_value = requests.get(url, timeout=timeout)
            return_value.raise_for_status()
        except requests.ConnectionError:
            return_value = None

        return return_value.json() if return_value else None

    def send_request(self, base_url: str, timeout: int):
        url = base_url.format(self.__lat, self.__lon, self.__units, self.__apikey)
        self.__data = self.get_response_json(url, timeout)

    def get_data(self) -> Any:
        return self.__data

    def get_weather_icon(self, main_tag: str, position: str, icon_tag: str) -> str:
        return self.__data[main_tag][position][icon_tag]

    def get_temperature(self, main_tag: str, temp_tag: str) -> str:
        return self.__data[main_tag][temp_tag]

    @classmethod
    def verify_units(cls, value: str):
        if value not in cls.__UNITS_VALUES:
            raise Exception(
                f"Configuration units should be one of {cls.__UNITS_VALUES}"
            )

    @classmethod
    def get_units(cls) -> List[str]:
        return cls.__UNITS_VALUES

    @classmethod
    def is_metric(cls, value: str) -> bool:
        return value == cls.__UNITS_VALUES[0]
