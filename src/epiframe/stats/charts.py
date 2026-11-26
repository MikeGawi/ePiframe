"""Chart data of the statistics: the query of the endpoint and its JSON answer.

Query: ``period`` (``day``, the default, ``week``, ``month`` or ``year``) and
``metrics`` (comma separated names, all by default). Answer::

    {"period": "day", "step": 10, "time": [1732442400, ...],
     "metrics": [{"name": "load1", "label": "Load 1 min", "unit": "",
                  "values": [0.52, null, ...]}, ...]}

``time`` is Unix time in seconds (the start of the period for averages), a
``null`` value was not measured. The temperature is in the configured unit.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from epiframe.core.system import fahrenheit
from epiframe.stats.metrics import (
    FAHRENHEIT,
    METRIC_NAMES,
    METRICS_BY_NAME,
    TEMPERATURE,
)
from epiframe.stats.store import Period, Series
from epiframe.web.api import doc

DECIMALS = 2


@dataclass(frozen=True)
class StatsQuery:
    period: Period = field(default=Period.DAY, metadata=doc("The period of the chart"))
    metrics: list[str] = field(
        default_factory=list,
        metadata=doc(
            f"Comma separated metrics (all by default): {', '.join(METRIC_NAMES)}"
        ),
    )


@dataclass(frozen=True)
class ChartMetric:
    name: str
    label: str
    unit: str
    values: list[float | None] = field(
        metadata=doc("One value per point of time, null: not measured")
    )


@dataclass(frozen=True)
class Chart:
    period: Period
    step: int = field(metadata=doc("Seconds between the points"))
    time: list[int] = field(metadata=doc("Unix times of the points"))
    metrics: list[ChartMetric]


def metric_names(names: Iterable[str]) -> tuple[str, ...]:
    """The requested metrics (all if none); raises ``ValueError`` for unknown names."""
    names = list(dict.fromkeys(names))
    unknown = [name for name in names if name not in METRICS_BY_NAME]
    if unknown:
        raise ValueError(f"Unknown metrics: {', '.join(unknown)}")
    return tuple(names) or METRIC_NAMES


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


def _metric(name: str, values: Sequence[float | None], metric: bool) -> ChartMetric:
    definition = METRICS_BY_NAME[name]
    unit = FAHRENHEIT if name == TEMPERATURE and not metric else definition.unit
    return ChartMetric(name, definition.label, unit, _values(name, values, metric))


def chart_data(series: Series, period: Period, metric: bool) -> Chart:
    """The answer for ``series``; ``metric`` is the unit setting."""
    return Chart(
        period=period,
        step=series.step,
        time=list(series.times),
        metrics=[
            _metric(name, values, metric) for name, values in series.values.items()
        ],
    )
