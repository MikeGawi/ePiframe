"""Weather test (``ePiframe.py --test-weather``).

Checks the OpenWeather API key and the coordinates with the same request the frame
makes, before the weather stamp is configured; at the end it offers to save them.
"""

from collections.abc import Callable

from epiframe.config.base import ConfigBase
from epiframe.core.console import Ask, Say, ask_yes, read_secret
from epiframe.weather.openweather import Weather, WeatherError, fetch_weather
from epiframe.weather.stamp import temperature_text

Fetch = Callable[[str, str, str, str], Weather]

COORDINATES_HINT = "Coordinates of a place: https://www.maps.ie/coordinates.html"
KEY_HINT = "API key: https://home.openweathermap.org/api_keys"


class WeatherTest:
    """The test dialogue; ``ask``/``say`` are ``input``/``print`` by default."""

    def __init__(
        self,
        config: ConfigBase,
        ask: Ask = input,
        say: Say = print,
        fetch: Fetch = fetch_weather,
        ask_secret: Ask = read_secret,
    ) -> None:
        self.config = config
        self.ask = ask
        self.say = say
        self.fetch = fetch
        self.ask_secret = ask_secret

    def run(self) -> int:
        """Run the test; return the exit code (0 = the weather was retrieved)."""
        try:
            self.say("ePiframe - weather (OpenWeather) test (Ctrl+C to stop)")
            self.say(f"{KEY_HINT}\n{COORDINATES_HINT}")
            values = {
                "apikey": self._value("OpenWeather API key", "apikey", secret=True),
                "lat": self._value("Latitude", "lat"),
                "lon": self._value("Longitude", "lon"),
            }
            if not self._check(values):
                return 1
            self._offer_save(values)
        except (EOFError, KeyboardInterrupt):
            self.say("\nTest stopped, nothing saved.")
            return 1
        return 0

    def _value(self, label: str, name: str, secret: bool = False) -> str:
        """Ask for an entry (hidden if ``secret``); Enter keeps the configured value."""
        current = self.config.get(name)
        ask = self.ask_secret if secret else self.ask
        prompt = f"{label}{self._hint(current, secret)}: "
        while True:
            if answer := ask(prompt).strip() or current:
                return answer

    @staticmethod
    def _hint(current: str, secret: bool) -> str:
        if not current:
            return ""
        return " [from the configuration]" if secret else f" [{current}]"

    def _check(self, values: dict[str, str]) -> bool:
        self.say("Getting the weather...")
        units = self.config.get("units")
        try:
            weather = self.fetch(values["apikey"], values["lat"], values["lon"], units)
        except WeatherError as error:
            self.say(f"Error: {error}")
            return False
        self.say(
            f"OK! Temperature {temperature_text(weather.temperature, units)},"
            f" weather icon {weather.icon}"
        )
        return True

    def _offer_save(self, values: dict[str, str]) -> None:
        changed = any(self.config.get(name) != value for name, value in values.items())
        if not changed and self.config.getint("show_weather"):
            self.say("The configuration already has these values.")
        elif ask_yes(self.ask, "Save them and enable the weather stamp?", True):
            self._save(values)
        else:
            self.say("Nothing saved.")

    def _save(self, values: dict[str, str]) -> None:
        self.config.set("show_weather", "1")
        for name, value in values.items():
            self.config.set(name, value)
        self.config.save()
        self.say(f"Saved to {self.config.path}.")
