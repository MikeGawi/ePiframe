"""The status of the frame (``/api/get_status``) with the 1.x texts."""

from dataclasses import dataclass, field
from datetime import timedelta

from epiframe.core import system
from epiframe.service.frame import Frame
from epiframe.version import VERSION
from epiframe.web.api import doc

NOTHING = "-"
UPTIME_UNITS = (("week", 604800), ("day", 86400), ("hour", 3600), ("minute", 60))


def memory_text(memory: system.Memory | None) -> str:
    return f"{memory.ram.percent}%" if memory else NOTHING


def load_text(load: tuple[float, float, float] | None) -> str:
    return " ".join(f"{value:.2f}" for value in load) if load else NOTHING


def _counts(seconds: int) -> list[tuple[int, str]]:
    counts = []
    for unit, size in UPTIME_UNITS:
        count, seconds = divmod(seconds, size)
        counts.append((count, unit))
    return counts


def uptime_text(uptime: timedelta | None) -> str:
    """As ``uptime --pretty`` (1.x): ``up 1 week, 1 day, 14 hours, 52 minutes``."""
    if uptime is None:
        return NOTHING
    counts = _counts(int(uptime.total_seconds()))
    parts = [f"{count} {unit}{'s' * (count > 1)}" for count, unit in counts if count]
    return "up " + ", ".join(parts or ["0 minutes"])


def temperature_text(celsius: float | None, metric: bool) -> str:
    if celsius is None:
        return NOTHING
    if metric:
        return f"{celsius:.1f}\N{DEGREE SIGN}C"
    return f"{system.fahrenheit(celsius):.1f}\N{DEGREE SIGN}F"


def service_text(running: bool) -> str:
    return "Running" if running else "Not running!"


@dataclass(frozen=True)
class Status:
    """The status of the frame."""

    converted: float = field(
        metadata=doc("Modification time of the displayed photo (Unix time, 0: none)")
    )
    original: float = field(
        metadata=doc("Modification time of the original photo (Unix time, 0: none)")
    )
    load: str = field(metadata=doc("System load of 1, 5 and 15 minutes"))
    mem: str = field(metadata=doc("Used memory, e.g. 21%"))
    service: str = field(metadata=doc("ePiframe service: Running or Not running!"))
    state: str = field(metadata=doc("Idle or Busy (changing the photo)"))
    temp: str = field(metadata=doc("CPU temperature in the configured units"))
    update: str = field(metadata=doc("When the photo changes next"))
    uptime: str = field(metadata=doc("Time since the system start"))
    version: str = field(metadata=doc("ePiframe version"))


def read_status(frame: Frame) -> Status:
    """The status now (``-`` for what can't be read)."""
    return Status(
        converted=frame.modified("thumb_photo_convert_filename"),
        original=frame.modified("thumb_photo_download_name"),
        load=load_text(system.load_average()),
        mem=memory_text(system.memory()),
        service=service_text(system.service_running()),
        state=frame.state,
        temp=temperature_text(system.temperature(), frame.metric),
        update=frame.next_update_text(),
        uptime=uptime_text(system.uptime()),
        version=VERSION,
    )
