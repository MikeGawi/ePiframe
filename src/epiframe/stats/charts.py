"""Chart data of the statistics: the query of the endpoint and its JSON answer.

Query: ``period`` (``day``, the default, ``week``, ``month`` or ``year``) and
``metrics`` (comma separated names, all by default). Answer::

    {"period": "day", "step": 10, "time": [1732442400, ...],
     "metrics": [{"name": "load1", "label": "Load 1 min", "unit": "",
                  "values": [0.52, null, ...]}, ...]}

``time`` is Unix time in seconds (the start of the period for averages), a
``null`` value was not measured. The temperature is in the configured unit.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from epiframe.core.system import fahrenheit
from epiframe.stats.metrics import (
    FAHRENHEIT,
    METRIC_NAMES,
    METRICS_BY_NAME,
    TEMPERATURE,
)
from epiframe.stats.store import Period, Series

DECIMALS = 2


@dataclass(frozen=True)
class Query:
    period: Period
    names: tuple[str, ...]


def parse_query(arguments: Mapping[str, str]) -> Query:
    """The query from the request ``arguments``; raises ``ValueError`` with a
    message for the user."""
    return Query(_period(arguments.get("period")), _names(arguments.get("metrics")))


def _period(text: str | None) -> Period:
    try:
        return Period(text or Period.DAY)
    except ValueError:
        choices = ", ".join(Period)
        raise ValueError(f"Unknown period {text!r}, use one of: {choices}") from None


def _split(text: str | None) -> list[str]:
    return [name.strip() for name in (text or "").split(",") if name.strip()]


def _names(text: str | None) -> tuple[str, ...]:
    names = _split(text)
    unknown = [name for name in names if name not in METRICS_BY_NAME]
    if unknown:
        raise ValueError(f"Unknown metrics: {', '.join(unknown)}")
    return tuple(dict.fromkeys(names)) or METRIC_NAMES


def _values(
    name: str, values: Sequence[float | None], metric: bool
) -> list[float | None]:
    convert = name == TEMPERATURE and not metric
    return [
        None
        if value is None
        else round(fahrenheit(value) if convert else value, DECIMALS)
        for value in values
    ]


def chart_data(series: Series, period: Period, metric: bool) -> dict[str, Any]:
    """The JSON answer for ``series``; ``metric`` is the unit setting."""
    metrics = []
    for name, values in series.values.items():
        definition = METRICS_BY_NAME[name]
        unit = FAHRENHEIT if name == TEMPERATURE and not metric else definition.unit
        metrics.append(
            {
                "name": name,
                "label": definition.label,
                "unit": unit,
                "values": _values(name, values, metric),
            }
        )
    return {
        "period": str(period),
        "step": series.step,
        "time": series.times,
        "metrics": metrics,
    }
