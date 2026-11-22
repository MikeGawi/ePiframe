from pathlib import Path

import pytest

from epiframe.display.system import spi_enabled

LSMOD = "spidev 16384 0 - Live 0x0\nspi_bcm2835 20480 0 - Live 0x0\n"


@pytest.fixture
def dev_dir(tmp_path: Path) -> Path:
    path = tmp_path / "dev"
    path.mkdir()
    return path


@pytest.fixture
def modules(tmp_path: Path) -> Path:
    path = tmp_path / "modules"
    path.write_text(LSMOD)
    return path


def test_enabled(dev_dir: Path, modules: Path) -> None:
    (dev_dir / "spidev0.0").touch()

    assert spi_enabled(dev_dir, modules) is True


def test_no_device(dev_dir: Path, modules: Path) -> None:
    (dev_dir / "i2c-1").touch()

    assert spi_enabled(dev_dir, modules) is False


def test_no_module(dev_dir: Path, modules: Path) -> None:
    (dev_dir / "spidev0.0").touch()
    modules.write_text("spidev 16384 0 - Live 0x0\n")

    assert spi_enabled(dev_dir, modules) is False


def test_unreadable_modules(dev_dir: Path, tmp_path: Path) -> None:
    (dev_dir / "spidev0.0").touch()

    assert spi_enabled(dev_dir, tmp_path / "missing") is False
