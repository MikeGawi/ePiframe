from importlib import metadata
from pathlib import Path
from typing import Any

import pytest

from scripts import piwheels_apt

LOCK = """\
version = 1

[[package]]
name = "numpy"
version = "2.4.6"
source = { registry = "https://www.piwheels.org/simple" }

[[package]]
name = "numpy"
version = "2.4.6"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "lgpio"
version = "0.2.2.0"
source = { registry = "https://www.piwheels.org/simple" }

[[package]]
name = "flask"
version = "3.1.2"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "epiframe"
version = "2.0.0a3"
source = { editable = "." }
"""

NUMPY = {
    "releases": {
        "2.4.6": {
            "files": {
                "numpy-2.4.6-cp311-cp311-linux_armv6l.whl": {
                    "apt_dependencies": ["libopenblas0-pthread", "libgfortran5"]
                },
                "numpy-2.4.6-cp313-cp313-linux_armv6l.whl": {
                    "apt_dependencies": ["libstdc++6"]
                },
            }
        },
        "2.4.5": {"files": {}},
    }
}
LGPIO = {
    "releases": {
        "0.2.2.0": {
            "files": {
                "lgpio-0.2.2.0-cp311-cp311-linux_armv6l.whl": {
                    "apt_dependencies": None
                },
                "lgpio-0.2.2.0-cp313-cp313-linux_armv6l.whl": {
                    "apt_dependencies": ["liblgpio1"]
                },
            }
        }
    }
}


class Distribution(metadata.Distribution):
    """An installed distribution with the given version and WHEEL tags."""

    def __init__(self, version: str, *tags: str) -> None:
        self._metadata = f"Name: x\nVersion: {version}\n"
        self._wheel = "".join(f"Tag: {tag}\n" for tag in tags) if tags else None

    def read_text(self, filename: str) -> str | None:
        if filename == "METADATA":
            return self._metadata
        return self._wheel if filename == "WHEEL" else None

    def locate_file(self, path: str | Any) -> Any:  # pragma: no cover - unused
        raise NotImplementedError


@pytest.fixture
def lock(tmp_path: Path) -> Path:
    path = tmp_path / "uv.lock"
    path.write_text(LOCK)
    return path


def fetch(url: str) -> Any:
    return {
        piwheels_apt.PROJECT_URL.format(name="numpy"): NUMPY,
        piwheels_apt.PROJECT_URL.format(name="lgpio"): LGPIO,
    }[url]


def test_piwheels_packages(lock: Path) -> None:
    assert piwheels_apt.piwheels_packages(lock) == [
        ("numpy", "2.4.6"),
        ("lgpio", "0.2.2.0"),
    ]


def test_installed_finds_real_and_missing_distributions() -> None:
    found = piwheels_apt.installed("pytest")

    assert found is not None
    assert found.metadata["Name"] == "pytest"
    assert piwheels_apt.installed("no-such-distribution-here") is None


def test_wheel_filenames_normalizes_the_name() -> None:
    distribution = Distribution("1.0", "cp311-abi3-linux_armv6l", "py3-none-any")

    assert piwheels_apt.wheel_filenames("Some.Package-name", distribution) == [
        "some_package_name-1.0-cp311-abi3-linux_armv6l.whl",
        "some_package_name-1.0-py3-none-any.whl",
    ]
    assert piwheels_apt.wheel_filenames("x", Distribution("1.0")) == []


def test_installed_wheels_skips_missing_and_other_versions() -> None:
    distributions = {
        "numpy": Distribution("2.4.6", "cp313-cp313-linux_armv6l"),
        "lgpio": Distribution("0.2.1"),
    }

    wheels = piwheels_apt.installed_wheels(
        [("numpy", "2.4.6"), ("lgpio", "0.2.2.0"), ("gpiod", "2.6.0")],
        distributions.get,
    )

    assert wheels == [
        piwheels_apt.Wheel("numpy", ("numpy-2.4.6-cp313-cp313-linux_armv6l.whl",))
    ]


def test_apt_dependencies_of_the_installed_file_only() -> None:
    wheel = piwheels_apt.Wheel("numpy", ("numpy-2.4.6-cp311-cp311-linux_armv6l.whl",))

    assert piwheels_apt.apt_dependencies(wheel, fetch) == {
        "libopenblas0-pthread",
        "libgfortran5",
    }
    lgpio = piwheels_apt.Wheel("lgpio", ("LGPIO-0.2.2.0-cp311-cp311-linux_armv6l.whl",))
    assert piwheels_apt.apt_dependencies(lgpio, fetch) == set()


def test_main_prints_sorted_packages(
    lock: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    distributions = {
        "numpy": Distribution("2.4.6", "cp311-cp311-linux_armv6l"),
        "lgpio": Distribution("0.2.2.0", "cp313-cp313-linux_armv6l"),
    }

    code = piwheels_apt.main(["--lock", str(lock)], distributions.get, fetch)

    assert code == 0
    assert capsys.readouterr().out == "libgfortran5\nliblgpio1\nlibopenblas0-pthread\n"


def test_main_without_piwheels_packages(
    lock: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = piwheels_apt.main(["--lock", str(lock)], lambda _: None, fetch)

    assert code == 0
    assert capsys.readouterr().out == ""


def test_main_reports_network_errors(
    lock: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def offline(url: str) -> Any:
        raise OSError("no network")

    code = piwheels_apt.main(
        ["--lock", str(lock)], lambda _: Distribution("2.4.6"), offline
    )

    assert code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Can't read the piwheels data: no network\n"


def test_default_lock_is_the_project_lock() -> None:
    assert piwheels_apt.parse_arguments([]).lock == piwheels_apt.ROOT / "uv.lock"
    assert (piwheels_apt.ROOT / "uv.lock").is_file()
