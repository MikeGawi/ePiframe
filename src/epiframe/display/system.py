"""Checks of the system setup needed by the displays."""

from pathlib import Path

DEV_DIR = Path("/dev")
KERNEL_MODULES = Path("/proc/modules")


def spi_enabled(dev_dir: Path = DEV_DIR, kernel_modules: Path = KERNEL_MODULES) -> bool:
    """Return whether SPI (needed by e-Paper displays) is enabled.

    Same check as 1.x (``ls /dev/spidev*`` and ``lsmod | grep spi_``), without
    running shell commands: a SPI device node exists and a SPI kernel module is
    loaded.
    """
    if not any(dev_dir.glob("spidev*")):
        return False
    try:
        modules = kernel_modules.read_text()
    except OSError:
        return False
    return any(line.startswith("spi_") for line in modules.splitlines())
