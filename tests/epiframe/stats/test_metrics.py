from pathlib import Path

import pytest

from epiframe.core import system
from epiframe.stats import metrics
from epiframe.stats.metrics import GROUPS, METRIC_NAMES, METRICS_BY_NAME, Sampler

MEBIBYTE = 1024 * 1024
MEMINFO = """\
MemTotal:        2097152 kB
MemAvailable:    1048576 kB
SwapTotal:        102400 kB
SwapFree:          51200 kB
"""


def stat(busy: int, idle: int) -> str:
    return f"cpu  {busy} 0 0 {idle} 0 0 0 0 0 0\n"


@pytest.fixture
def proc(tmp_path: Path) -> Path:
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "loadavg").write_text("0.52 0.58 0.59 1/389 12345\n")
    (proc / "meminfo").write_text(MEMINFO)
    (proc / "stat").write_text(stat(100, 300))
    return proc


@pytest.fixture
def thermal(tmp_path: Path) -> Path:
    thermal = tmp_path / "temp"
    thermal.write_text("48312\n")
    return thermal


def test_sample(proc: Path, thermal: Path, tmp_path: Path) -> None:
    sampler = Sampler(tmp_path, proc, thermal)

    first = sampler.sample()
    (proc / "stat").write_text(stat(150, 350))
    second = sampler.sample()

    # no CPU usage in the first sample: it is measured between two samples
    assert "cpu" not in first
    assert second.pop("cpu") == 50
    assert first == second
    assert first["load1"] == 0.52
    assert first["load5"] == 0.58
    assert first["load15"] == 0.59
    assert first["memory_total"] == 2048
    assert first["memory_used"] == 1024
    assert first["swap_total"] == 100
    assert first["swap_used"] == 50
    assert first["temperature"] == 48.312
    assert 0 < first["disk"] < 100


def test_sample_nothing_available(tmp_path: Path) -> None:
    sampler = Sampler(tmp_path / "missing", tmp_path, tmp_path / "temp")

    assert sampler.sample() == {}
    assert sampler.sample() == {}


def test_cpu_counters_unchanged(proc: Path, thermal: Path, tmp_path: Path) -> None:
    sampler = Sampler(tmp_path, proc, thermal)

    sampler.sample()

    assert "cpu" not in sampler.sample()


def test_cpu_unreadable_later(proc: Path, thermal: Path, tmp_path: Path) -> None:
    sampler = Sampler(tmp_path, proc, thermal)
    sampler.sample()
    (proc / "stat").unlink()

    assert "cpu" not in sampler.sample()


def test_disk_of_empty_file_system(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(system, "disk_usage", lambda _: system.Usage(0, 0))

    assert "disk" not in Sampler(tmp_path, tmp_path, tmp_path / "temp").sample()


def test_defaults() -> None:
    sampler = Sampler(Path("/"))

    assert sampler._proc == system.PROC_DIR
    assert sampler._thermal == system.THERMAL_FILE
    assert metrics.SAMPLE_INTERVAL == 10


def test_definitions() -> None:
    grouped = [name for names in GROUPS.values() for name in names]

    # every metric is shown on exactly one chart
    assert sorted(grouped) == sorted(METRIC_NAMES)
    assert set(METRICS_BY_NAME) == set(METRIC_NAMES)
    assert METRICS_BY_NAME["temperature"].unit == "\N{DEGREE SIGN}C"
