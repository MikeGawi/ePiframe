"""Smoke tests: run the real ePiframe entry points as processes.

They check that the modules work together (CLI flow, config migration, photo
index, ImageMagick conversion, WebUI start) in an isolated folder: the
configuration and data directories point to ``tmp_path`` and the processes run
there, so nothing in the repository or on the machine is touched.

Run them with ``uv run pytest -m smoke`` (they are excluded from the default run;
CI runs them in a separate job with ImageMagick installed).
"""

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image

from epiframe.config import paths

REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(paths.CONFIG_FILE_DEFAULT)
CONVERT = shutil.which("convert")
TIMEOUT = 180

needs_imagemagick = pytest.mark.skipif(CONVERT is None, reason="needs ImageMagick")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if Path(item.path).is_relative_to(Path(__file__).parent):
            item.add_marker(pytest.mark.smoke)


@dataclass
class Frame:
    """An ePiframe installation in ``directory`` (config, data and photos)."""

    directory: Path

    @property
    def config_file(self) -> Path:
        return self.directory / "config.cfg"

    @property
    def photos(self) -> Path:
        return self.directory / "photos"

    def configure(self, **entries: str) -> None:
        """Set config entries (the file is created from the default if missing)."""
        if not self.config_file.exists():
            shutil.copyfile(DEFAULT_CONFIG, self.config_file)
        text = self.config_file.read_text()
        for name, value in entries.items():
            text, count = re.subn(
                rf"^{name}=.*$", f"{name}={value}", text, flags=re.MULTILINE
            )
            assert count == 1, f"no {name} entry"
        self.config_file.write_text(text)

    def environment(self) -> dict[str, str]:
        return os.environ | {
            paths.CONFIG_DIR_ENV: str(self.directory),
            paths.DATA_DIR_ENV: str(self.directory),
        }

    def run(
        self, *arguments: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run ``ePiframe.py`` with ``arguments`` and extra ``env`` variables."""
        return subprocess.run(
            [sys.executable, str(REPOSITORY / "ePiframe.py"), *arguments],
            cwd=self.directory,
            env=self.environment() | (env or {}),
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )

    def add_photo(self, name: str, color: str, mtime: float) -> Path:
        path = self.photos / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 48), color).save(path)
        os.utime(path, (mtime, mtime))
        return path


def machine_independent_paths() -> dict[str, str]:
    """FILE entries that must exist: real ImageMagick, any file for the others."""
    return {
        "convert_bin_path": CONVERT or sys.executable,
        "rrdtool_bin_path": sys.executable,
        "fbi_bin_path": sys.executable,
    }


@pytest.fixture
def frame(tmp_path: Path) -> Frame:
    frame = Frame(tmp_path)
    frame.configure(**machine_independent_paths())
    return frame
