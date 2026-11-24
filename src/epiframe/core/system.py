"""The system the frame runs on: information and power commands (no shell).

The information is read straight from ``/proc`` and ``/sys``; every reader returns
``None`` when it is not available (other OS, a missing or unreadable file), so
callers can show what they have.

The commands (reboot, power off, restart of the ePiframe service) run
``systemctl`` with an argument list. The service runs as root; any other user
needs ``sudo`` without a password (``sudo -n``, never asks), like the default
``pi`` user of Raspberry Pi OS.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from epiframe.core.logs import get_logger

PROC_DIR = Path("/proc")
THERMAL_FILE = Path("/sys/class/thermal/thermal_zone0/temp")

KIBIBYTE = 1024

SERVICE = "ePiframe.service"
SYSTEMCTL = "systemctl"
COMMAND_TIMEOUT = 30

log = get_logger("system")


@dataclass(frozen=True)
class Usage:
    """Used and total amount of memory or swap, in bytes."""

    used: int
    total: int

    @property
    def percent(self) -> int:
        return round(self.used * 100 / self.total) if self.total else 0


@dataclass(frozen=True)
class Memory:
    ram: Usage
    swap: Usage


@dataclass(frozen=True)
class CpuTimes:
    """Time the CPUs spent since boot (``/proc/stat``, clock ticks)."""

    busy: int
    total: int

    def percent_since(self, previous: "CpuTimes") -> float | None:
        """CPU usage between ``previous`` and these times, in percent."""
        total = self.total - previous.total
        if total <= 0:
            return None
        return (self.busy - previous.busy) * 100 / total


def _read(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def _meminfo(text: str) -> dict[str, int]:
    """``/proc/meminfo`` as ``{name: bytes}`` (values are in kB there)."""
    values = {}
    for line in text.splitlines():
        name, _, value = line.partition(":")
        fields = value.split()
        if fields and fields[0].isdigit():
            values[name] = int(fields[0]) * KIBIBYTE
    return values


def memory(proc: Path = PROC_DIR) -> Memory | None:
    """RAM (``MemTotal - MemAvailable`` used, as ``free``) and swap usage."""
    text = _read(proc / "meminfo")
    if text is None:
        return None
    values = _meminfo(text)
    try:
        ram = Usage(values["MemTotal"] - values["MemAvailable"], values["MemTotal"])
    except KeyError:
        return None
    swap_total = values.get("SwapTotal", 0)
    swap = Usage(swap_total - values.get("SwapFree", swap_total), swap_total)
    return Memory(ram, swap)


def uptime(proc: Path = PROC_DIR) -> timedelta | None:
    """Time since boot, in whole seconds."""
    text = _read(proc / "uptime")
    try:
        return timedelta(seconds=int(float((text or "").split()[0])))
    except (IndexError, ValueError):
        return None


def load_average(proc: Path = PROC_DIR) -> tuple[float, float, float] | None:
    """System load averaged over 1, 5 and 15 minutes."""
    text = _read(proc / "loadavg")
    try:
        one, five, fifteen = (float(value) for value in (text or "").split()[:3])
    except ValueError:
        return None
    return one, five, fifteen


def _cpu_ticks(text: str) -> list[int]:
    """user nice system idle iowait irq softirq steal of all CPUs (guest is in
    user); empty if ``text`` is not ``/proc/stat``."""
    fields = (text.splitlines() or [""])[0].split()
    if fields[:1] != ["cpu"]:
        return []
    try:
        return [int(value) for value in fields[1:9]]
    except ValueError:
        return []


def cpu_times(proc: Path = PROC_DIR) -> CpuTimes | None:
    """All CPUs together; idle and I/O wait count as not busy."""
    ticks = _cpu_ticks(_read(proc / "stat") or "")
    if not ticks:
        return None
    idle = sum(ticks[3:5])
    return CpuTimes(sum(ticks) - idle, sum(ticks))


def disk_usage(path: Path) -> Usage | None:
    """Used and total space of the file system holding ``path``."""
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return Usage(usage.used, usage.total)


def temperature(path: Path = THERMAL_FILE) -> float | None:
    """CPU temperature in degrees Celsius (the kernel reports millidegrees)."""
    text = _read(path)
    try:
        return int((text or "").strip()) / 1000
    except ValueError:
        return None


def fahrenheit(celsius: float) -> float:
    return celsius * 1.8 + 32


def _privileged(command: list[str]) -> list[str]:
    return command if os.geteuid() == 0 else ["sudo", "-n", *command]


def run(command: list[str]) -> bool:
    """Run ``command``; return whether it succeeded (a failure is logged)."""
    try:
        result = subprocess.run(  # noqa: S603 - argument list, no shell
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=COMMAND_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as error:
        log.error(f"Can't run {' '.join(command)}: {error}")
        return False
    if result.returncode:
        message = result.stderr.strip() or f"exit code {result.returncode}"
        log.error(f"{' '.join(command)} failed: {message}")
    return result.returncode == 0


def service_running(service: str = SERVICE) -> bool:
    """Return whether the systemd ``service`` is active."""
    command = [SYSTEMCTL, "is-active", "--quiet", service]
    try:
        result = subprocess.run(  # noqa: S603 - argument list, no shell
            command, capture_output=True, check=False, timeout=COMMAND_TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def reboot() -> bool:
    return run(_privileged([SYSTEMCTL, "reboot"]))


def power_off() -> bool:
    return run(_privileged([SYSTEMCTL, "poweroff"]))


def restart_service(service: str = SERVICE) -> bool:
    # --no-block: the service may restart itself (WebUI, Telegram bot), don't
    # wait for the job that stops this very process
    return run(_privileged([SYSTEMCTL, "--no-block", "restart", service]))
