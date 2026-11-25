"""The metrics the frame records and the sampler that reads them.

Every metric is read from ``/proc`` and ``/sys`` (see :mod:`epiframe.core.system`);
one that is not available (another OS, a missing file) is left out of the
sample. The temperature is always recorded in degrees Celsius: the unit setting
only changes how it is shown.
"""

from dataclasses import dataclass
from pathlib import Path

from epiframe.core import system

# seconds between two samples
SAMPLE_INTERVAL = 10

MEBIBYTE = 1024 * 1024
CELSIUS = "\N{DEGREE SIGN}C"
FAHRENHEIT = "\N{DEGREE SIGN}F"
TEMPERATURE = "temperature"

Sample = dict[str, float]


@dataclass(frozen=True)
class Metric:
    name: str
    label: str
    unit: str = ""


METRICS = (
    Metric("load1", "Load 1 min"),
    Metric("load5", "Load 5 min"),
    Metric("load15", "Load 15 min"),
    Metric("cpu", "CPU usage", "%"),
    Metric("memory_total", "Total memory", "MiB"),
    Metric("memory_used", "Used memory", "MiB"),
    Metric("swap_total", "Total swap", "MiB"),
    Metric("swap_used", "Used swap", "MiB"),
    Metric(TEMPERATURE, "Temperature", CELSIUS),
    Metric("disk", "Disk usage", "%"),
)
METRIC_NAMES = tuple(metric.name for metric in METRICS)
METRICS_BY_NAME = {metric.name: metric for metric in METRICS}

# metrics shown together on one chart
GROUPS = {
    "Load": ("load1", "load5", "load15"),
    "CPU": ("cpu",),
    "Memory": ("memory_total", "memory_used", "swap_total", "swap_used"),
    "Temperature": (TEMPERATURE,),
    "Disk": ("disk",),
}


def _load(proc: Path) -> Sample:
    load = system.load_average(proc)
    return dict(zip(("load1", "load5", "load15"), load, strict=True)) if load else {}


def _memory(proc: Path) -> Sample:
    memory = system.memory(proc)
    if memory is None:
        return {}
    return {
        "memory_total": memory.ram.total / MEBIBYTE,
        "memory_used": memory.ram.used / MEBIBYTE,
        "swap_total": memory.swap.total / MEBIBYTE,
        "swap_used": memory.swap.used / MEBIBYTE,
    }


def _temperature(thermal: Path) -> Sample:
    celsius = system.temperature(thermal)
    return {} if celsius is None else {TEMPERATURE: celsius}


def _disk(path: Path) -> Sample:
    usage = system.disk_usage(path)
    return {"disk": usage.used * 100 / usage.total} if usage and usage.total else {}


class Sampler:
    """Reads the metrics; the disk usage is the one of the file system holding
    ``disk``. The CPU usage is measured between two samples, so the first sample
    has none."""

    def __init__(
        self,
        disk: Path,
        proc: Path = system.PROC_DIR,
        thermal: Path = system.THERMAL_FILE,
    ):
        self._disk = disk
        self._proc = proc
        self._thermal = thermal
        self._cpu_times: system.CpuTimes | None = None

    def sample(self) -> Sample:
        return {
            **_load(self._proc),
            **self._cpu(),
            **_memory(self._proc),
            **_temperature(self._thermal),
            **_disk(self._disk),
        }

    def _cpu(self) -> Sample:
        previous, self._cpu_times = self._cpu_times, system.cpu_times(self._proc)
        if previous is None or self._cpu_times is None:
            return {}
        percent = self._cpu_times.percent_since(previous)
        return {} if percent is None else {"cpu": percent}
