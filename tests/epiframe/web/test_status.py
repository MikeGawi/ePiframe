from datetime import timedelta
from unittest.mock import patch

import pytest

from epiframe.core import system
from epiframe.service.frame import Frame
from epiframe.web.status import (
    NOTHING,
    load_text,
    memory_text,
    read_status,
    service_text,
    temperature_text,
    uptime_text,
)


@pytest.mark.parametrize(
    ("celsius", "metric", "expected"),
    [(50, True, "50.0°C"), (50, False, "122.0°F"), (None, False, "-")],
)
def test_temperature_text(celsius: float | None, metric: bool, expected: str) -> None:
    assert temperature_text(celsius, metric) == expected


@pytest.mark.parametrize(
    ("uptime", "expected"),
    [
        (
            timedelta(days=8, hours=14, minutes=52, seconds=7),
            "up 1 week, 1 day, 14 hours, 52 minutes",
        ),
        (timedelta(weeks=2, minutes=1), "up 2 weeks, 1 minute"),
        (timedelta(seconds=59), "up 0 minutes"),
        (None, "-"),
    ],
)
def test_uptime_text(uptime: timedelta | None, expected: str) -> None:
    assert uptime_text(uptime) == expected


def test_texts() -> None:
    assert load_text((1, 0.5, 0.125)) == "1.00 0.50 0.12"
    assert memory_text(system.Memory(system.Usage(1, 3), system.Usage(0, 0))) == "33%"
    assert service_text(True) == "Running"
    assert service_text(False) == "Not running!"


def test_nothing_available(frame: Frame) -> None:
    with (
        patch.object(system, "memory", return_value=None),
        patch.object(system, "load_average", return_value=None),
        patch.object(system, "uptime", return_value=None),
        patch.object(system, "temperature", return_value=None),
        patch.object(system, "service_running", return_value=False),
    ):
        status = read_status(frame)

    assert (status.mem, status.load, status.uptime, status.temp) == (NOTHING,) * 4
    assert (status.converted, status.original) == (0, 0)
    assert status.service == "Not running!"
