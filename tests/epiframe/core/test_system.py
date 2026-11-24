from datetime import timedelta
from pathlib import Path

import pytest

from epiframe.core import system
from epiframe.core.system import Memory, Usage

MEMINFO = """\
MemTotal:        3906000 kB
MemFree:          900000 kB
MemAvailable:    2906000 kB
SwapTotal:        102400 kB
SwapFree:          51200 kB
HugePages_Total:       0
Not a value:     n/a
"""


@pytest.fixture
def proc(tmp_path: Path) -> Path:
    return tmp_path


def test_usage_percent() -> None:
    assert Usage(1, 3).percent == 33
    assert Usage(2, 3).percent == 67
    assert Usage(0, 0).percent == 0


def test_memory(proc: Path) -> None:
    (proc / "meminfo").write_text(MEMINFO)

    assert system.memory(proc) == Memory(
        ram=Usage(1_000_000 * 1024, 3_906_000 * 1024),
        swap=Usage(51_200 * 1024, 102_400 * 1024),
    )


def test_memory_without_swap(proc: Path) -> None:
    (proc / "meminfo").write_text("MemTotal: 2000 kB\nMemAvailable: 500 kB\n")

    assert system.memory(proc) == Memory(Usage(1500 * 1024, 2000 * 1024), Usage(0, 0))


def test_memory_without_available(proc: Path) -> None:
    # kernels older than 3.14 have no MemAvailable
    (proc / "meminfo").write_text("MemTotal: 2000 kB\nMemFree: 500 kB\n")

    assert system.memory(proc) is None


def test_memory_missing(proc: Path) -> None:
    assert system.memory(proc) is None


def test_uptime(proc: Path) -> None:
    (proc / "uptime").write_text("273906.75 1009238.48\n")

    assert system.uptime(proc) == timedelta(days=3, hours=4, minutes=5, seconds=6)


@pytest.mark.parametrize("content", ["", "x 1.0"])
def test_uptime_invalid(proc: Path, content: str) -> None:
    (proc / "uptime").write_text(content)

    assert system.uptime(proc) is None


def test_uptime_missing(proc: Path) -> None:
    assert system.uptime(proc) is None


def test_load_average(proc: Path) -> None:
    (proc / "loadavg").write_text("0.52 0.58 0.59 1/389 12345\n")

    assert system.load_average(proc) == (0.52, 0.58, 0.59)


@pytest.mark.parametrize("content", ["", "0.5 0.6", "a b c"])
def test_load_average_invalid(proc: Path, content: str) -> None:
    (proc / "loadavg").write_text(content)

    assert system.load_average(proc) is None


def test_load_average_missing(proc: Path) -> None:
    assert system.load_average(proc) is None


def test_temperature(tmp_path: Path) -> None:
    thermal = tmp_path / "temp"
    thermal.write_text("48312\n")

    assert system.temperature(thermal) == 48.312


def test_temperature_invalid(tmp_path: Path) -> None:
    thermal = tmp_path / "temp"
    thermal.write_text("")

    assert system.temperature(thermal) is None


def test_temperature_missing(tmp_path: Path) -> None:
    assert system.temperature(tmp_path / "temp") is None


def test_defaults() -> None:
    assert Path("/proc") == system.PROC_DIR
    assert Path("/sys/class/thermal/thermal_zone0/temp") == system.THERMAL_FILE
