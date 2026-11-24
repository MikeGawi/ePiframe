import pytest

from epiframe.stats.charts import Query, chart_data, parse_query
from epiframe.stats.metrics import METRIC_NAMES
from epiframe.stats.store import Period, Series


def test_default_query() -> None:
    assert parse_query({}) == Query(Period.DAY, METRIC_NAMES)
    assert parse_query({"period": "", "metrics": " , "}) == Query(
        Period.DAY, METRIC_NAMES
    )


def test_query() -> None:
    query = parse_query({"period": "year", "metrics": "cpu, load1,cpu"})

    assert query == Query(Period.YEAR, ("cpu", "load1"))


def test_unknown_period() -> None:
    with pytest.raises(ValueError, match="Unknown period 'hour', use one of: day,"):
        parse_query({"period": "hour"})


def test_unknown_metrics() -> None:
    with pytest.raises(ValueError, match=r"Unknown metrics: a, b$"):
        parse_query({"metrics": "load1,a,b"})


SERIES = Series(
    step=10,
    times=[100, 110],
    values={"load1": [0.123, None], "temperature": [50.0, 48.312]},
)


def test_chart_data_metric() -> None:
    assert chart_data(SERIES, Period.DAY, metric=True) == {
        "period": "day",
        "step": 10,
        "time": [100, 110],
        "metrics": [
            {
                "name": "load1",
                "label": "Load 1 min",
                "unit": "",
                "values": [0.12, None],
            },
            {
                "name": "temperature",
                "label": "Temperature",
                "unit": "\N{DEGREE SIGN}C",
                "values": [50.0, 48.31],
            },
        ],
    }


def test_chart_data_imperial() -> None:
    data = chart_data(SERIES, Period.WEEK, metric=False)

    assert data["period"] == "week"
    assert data["metrics"][0]["values"] == [0.12, None]
    assert data["metrics"][1]["unit"] == "\N{DEGREE SIGN}F"
    assert data["metrics"][1]["values"] == [122.0, 118.96]


def test_chart_data_empty() -> None:
    data = chart_data(Series(step=3600, values={"cpu": []}), Period.MONTH, True)

    assert data == {
        "period": "month",
        "step": 3600,
        "time": [],
        "metrics": [{"name": "cpu", "label": "CPU usage", "unit": "%", "values": []}],
    }
