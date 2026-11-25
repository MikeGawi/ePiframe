from dataclasses import dataclass, field
from pathlib import Path

import pytest

from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.weather.console import WeatherTest
from epiframe.weather.openweather import Weather, WeatherError
from tests.helpers.console import Answer, Console

KEY = "secret-api-key"


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigManager:
    monkeypatch.chdir(tmp_path)
    return ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)


@dataclass
class FakeWeather:
    """``fetch_weather`` recording the requests; raises ``error`` if set."""

    error: WeatherError | None = None
    requests: list[tuple[str, str, str, str]] = field(default_factory=list)

    def __call__(
        self, api_key: str, latitude: str, longitude: str, units: str
    ) -> Weather:
        self.requests.append((api_key, latitude, longitude, units))
        if self.error:
            raise self.error
        return Weather(20.5, "10d")


def run(
    config: ConfigManager, fetch: FakeWeather, *answers: Answer
) -> tuple[int, Console]:
    console = Console(*answers)
    code = WeatherTest(
        config, console.ask, console.say, fetch, ask_secret=console.ask
    ).run()
    return code, console


def saved(tmp_path: Path) -> ConfigManager:
    return ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)


def test_new_values(config: ConfigManager, tmp_path: Path) -> None:
    fetch = FakeWeather()

    code, console = run(config, fetch, f" {KEY} ", "53.27", "7.77", "")

    assert code == 0
    assert console.prompts == [
        "OpenWeather API key: ",
        "Latitude: ",
        "Longitude: ",
        "Save them and enable the weather stamp? [Y/n] ",
    ]
    assert fetch.requests == [(KEY, "53.27", "7.77", "metric")]
    assert "OK! Temperature 21\N{DEGREE SIGN}C, weather icon 10d" in console.output
    assert KEY not in console.output
    config = saved(tmp_path)
    assert config.get("show_weather") == "1"
    assert (config.get("apikey"), config.get("lat"), config.get("lon")) == (
        KEY,
        "53.27",
        "7.77",
    )


def test_empty_value_asked_again(config: ConfigManager) -> None:
    fetch = FakeWeather()

    run(config, fetch, "", KEY, "", "1", "2", "n")

    assert fetch.requests == [(KEY, "1", "2", "metric")]


def test_configured_values(config: ConfigManager) -> None:
    for name, value in (("show_weather", "1"), ("apikey", KEY), ("lat", "1")):
        config.set(name, value)
    config.set("lon", "2")
    config.set("units", "imperial")
    fetch = FakeWeather()

    code, console = run(config, fetch, "", "", "")

    assert code == 0
    assert console.prompts == [
        "OpenWeather API key [from the configuration]: ",
        "Latitude [1]: ",
        "Longitude [2]: ",
    ]
    assert fetch.requests == [(KEY, "1", "2", "imperial")]
    assert "Temperature 21\N{DEGREE SIGN}F" in console.output
    assert "already has these values" in console.output


def test_changed_value_saved(config: ConfigManager, tmp_path: Path) -> None:
    for name, value in (("show_weather", "1"), ("apikey", KEY), ("lat", "1")):
        config.set(name, value)
    config.set("lon", "2")

    run(config, FakeWeather(), "", "3", "", "y")

    assert saved(tmp_path).get("lat") == "3"


def test_disabled_stamp_enabled(config: ConfigManager, tmp_path: Path) -> None:
    for name, value in (("apikey", KEY), ("lat", "1"), ("lon", "2")):
        config.set(name, value)

    run(config, FakeWeather(), "", "", "", "")

    assert saved(tmp_path).get("show_weather") == "1"


def test_nothing_saved(config: ConfigManager, tmp_path: Path) -> None:
    code, console = run(config, FakeWeather(), KEY, "1", "2", "n")

    assert code == 0
    assert "Nothing saved." in console.output
    assert saved(tmp_path).get("apikey") == ""


def test_error(config: ConfigManager, tmp_path: Path) -> None:
    fetch = FakeWeather(WeatherError("The weather API key was rejected (401)"))

    code, console = run(config, fetch, KEY, "1", "2")

    assert code == 1
    assert "Error: The weather API key was rejected (401)" in console.output
    assert saved(tmp_path).get("apikey") == ""


@pytest.mark.parametrize("stop", [KeyboardInterrupt(), EOFError()])
def test_stopped(config: ConfigManager, stop: BaseException) -> None:
    code, console = run(config, FakeWeather(), KEY, stop)

    assert code == 1
    assert "Test stopped, nothing saved." in console.output
