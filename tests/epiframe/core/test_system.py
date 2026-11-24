import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from epiframe.core import system
from epiframe.core.system import CpuTimes, Memory, Usage

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


STAT = """\
cpu  100 20 30 400 50 6 4 10 0 0
cpu0 50 10 15 200 25 3 2 5 0 0
intr 12345
"""


def test_cpu_times(proc: Path) -> None:
    (proc / "stat").write_text(STAT)

    # busy: user nice system irq softirq steal; idle + iowait are not busy
    assert system.cpu_times(proc) == CpuTimes(busy=170, total=620)


@pytest.mark.parametrize("content", ["", "intr 1 2 3\n", "cpu a b c d e f g h\n"])
def test_cpu_times_invalid(proc: Path, content: str) -> None:
    (proc / "stat").write_text(content)

    assert system.cpu_times(proc) is None


def test_cpu_times_missing(proc: Path) -> None:
    assert system.cpu_times(proc) is None


def test_cpu_percent_since() -> None:
    assert CpuTimes(150, 300).percent_since(CpuTimes(100, 200)) == 50
    assert CpuTimes(100, 200).percent_since(CpuTimes(100, 200)) is None
    # counters reset (another boot)
    assert CpuTimes(10, 20).percent_since(CpuTimes(100, 200)) is None


def test_disk_usage(tmp_path: Path) -> None:
    usage = system.disk_usage(tmp_path)

    assert usage is not None
    assert 0 < usage.used <= usage.total


def test_disk_usage_missing(tmp_path: Path) -> None:
    assert system.disk_usage(tmp_path / "missing") is None


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


# ------------------------------------------------------------------ commands


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record the commands; they succeed."""
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    return calls


@pytest.fixture
def root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 0)


@pytest.fixture
def user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 1000)


def test_fahrenheit() -> None:
    assert system.fahrenheit(0) == 32
    assert system.fahrenheit(100) == 212
    assert system.fahrenheit(-40) == -40


def test_run() -> None:
    assert system.run([sys.executable, "-c", "pass"]) is True


def test_run_failure(caplog: pytest.LogCaptureFixture) -> None:
    command = [sys.executable, "-c", "import sys; sys.exit('no permission')"]

    assert system.run(command) is False
    assert "failed: no permission" in caplog.text


def test_run_failure_without_message(caplog: pytest.LogCaptureFixture) -> None:
    assert system.run([sys.executable, "-c", "raise SystemExit(3)"]) is False
    assert "failed: exit code 3" in caplog.text


def test_run_missing_command(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    assert system.run([str(tmp_path / "missing"), "x"]) is False
    assert f"Can't run {tmp_path / 'missing'} x" in caplog.text


def test_run_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system, "COMMAND_TIMEOUT", 0.01)

    command = [sys.executable, "-c", "import time; time.sleep(5)"]

    assert system.run(command) is False


@pytest.mark.usefixtures("root")
def test_commands_as_root(commands: list[list[str]]) -> None:
    assert system.reboot() is True
    assert system.power_off() is True
    assert system.restart_service() is True

    assert commands == [
        ["systemctl", "reboot"],
        ["systemctl", "poweroff"],
        ["systemctl", "--no-block", "restart", "ePiframe.service"],
    ]


@pytest.mark.usefixtures("user")
def test_commands_as_user(commands: list[list[str]]) -> None:
    system.reboot()
    system.restart_service("other.service")

    assert commands == [
        ["sudo", "-n", "systemctl", "reboot"],
        ["sudo", "-n", "systemctl", "--no-block", "restart", "other.service"],
    ]


@pytest.mark.parametrize(("code", "running"), [(0, True), (3, False)])
def test_service_running(
    monkeypatch: pytest.MonkeyPatch, code: int, running: bool
) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        return subprocess.CompletedProcess(command, code)

    monkeypatch.setattr(subprocess, "run", run)

    assert system.service_running() is running
    assert calls == [["systemctl", "is-active", "--quiet", "ePiframe.service"]]


def test_service_running_without_systemctl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system, "SYSTEMCTL", "/nonexistent/systemctl")

    assert system.service_running() is False
