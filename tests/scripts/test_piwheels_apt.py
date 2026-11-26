import io
import urllib.error
from importlib import metadata
from typing import Any

import pytest

from scripts import piwheels_apt

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
    """An installed distribution with the given name, version and WHEEL tags."""

    def __init__(self, name: str, version: str, *tags: str) -> None:
        self._metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
        self._wheel = "".join(f"Tag: {tag}\n" for tag in tags) if tags else None

    def read_text(self, filename: str) -> str | None:
        if filename == "METADATA":
            return self._metadata
        return self._wheel if filename == "WHEEL" else None

    def locate_file(self, path: Any) -> Any:  # pragma: no cover - unused
        raise NotImplementedError


def fetch(url: str) -> Any:
    projects = {
        piwheels_apt.PROJECT_URL.format(name="numpy"): NUMPY,
        piwheels_apt.PROJECT_URL.format(name="lgpio"): LGPIO,
    }
    if url not in projects:
        raise FileNotFoundError(url)
    return projects[url]


def test_wheel_of_an_arm_wheel_normalizes_the_name() -> None:
    distribution = Distribution(
        "Some.Package_name", "1.0", "cp311-abi3-linux_armv6l", "cp311-abi3-linux_armv7l"
    )

    assert piwheels_apt.wheel_of(distribution) == piwheels_apt.Wheel(
        "some-package-name",
        (
            "some_package_name-1.0-cp311-abi3-linux_armv6l.whl",
            "some_package_name-1.0-cp311-abi3-linux_armv7l.whl",
        ),
    )


@pytest.mark.parametrize(
    "tags",
    [(), ("py3-none-any",), ("cp311-cp311-manylinux_2_17_aarch64",)],
)
def test_wheel_of_other_distributions(tags: tuple[str, ...]) -> None:
    assert piwheels_apt.wheel_of(Distribution("x", "1.0", *tags)) is None


def test_arm_wheels_sorted_and_unique() -> None:
    wheels = piwheels_apt.arm_wheels(
        [
            Distribution("numpy", "2.4.6", "cp311-cp311-linux_armv6l"),
            Distribution("flask", "3.1.2", "py3-none-any"),
            Distribution("lgpio", "0.2.2.0", "cp311-cp311-linux_armv6l"),
            Distribution("numpy", "2.4.6", "cp311-cp311-linux_armv6l"),
        ]
    )

    assert [wheel.name for wheel in wheels] == ["lgpio", "numpy"]


def test_apt_dependencies_of_the_installed_file_only() -> None:
    wheel = piwheels_apt.Wheel("numpy", ("numpy-2.4.6-cp311-cp311-linux_armv6l.whl",))
    lgpio = piwheels_apt.Wheel("lgpio", ("LGPIO-0.2.2.0-cp311-cp311-linux_armv6l.whl",))

    assert piwheels_apt.apt_dependencies(wheel, fetch) == {
        "libopenblas0-pthread",
        "libgfortran5",
    }
    assert piwheels_apt.apt_dependencies(lgpio, fetch) == set()


def test_apt_dependencies_of_a_project_unknown_to_piwheels() -> None:
    wheel = piwheels_apt.Wheel("private", ("private-1.0-cp311-cp311-linux_armv7l.whl",))

    assert piwheels_apt.apt_dependencies(wheel, fetch) == set()


class Response(io.BytesIO):
    pass


def test_fetch_json() -> None:
    calls = []

    def urlopen(url: str, timeout: int) -> Response:
        calls.append((url, timeout))
        return Response(b'{"releases": {}}')

    assert piwheels_apt.fetch_json("https://x/json/", urlopen) == {"releases": {}}
    assert calls == [("https://x/json/", piwheels_apt.TIMEOUT)]


@pytest.mark.parametrize(
    ("code", "error"), [(404, FileNotFoundError), (500, urllib.error.HTTPError)]
)
def test_fetch_json_errors(code: int, error: type[Exception]) -> None:
    def urlopen(url: str, timeout: int) -> Response:
        raise urllib.error.HTTPError(url, code, "status", {}, None)  # type: ignore[arg-type]

    with pytest.raises(error):
        piwheels_apt.fetch_json("https://x/json/", urlopen)


def test_main_prints_sorted_packages(capsys: pytest.CaptureFixture[str]) -> None:
    distributions = [
        Distribution("numpy", "2.4.6", "cp311-cp311-linux_armv6l"),
        Distribution("lgpio", "0.2.2.0", "cp313-cp313-linux_armv6l"),
        Distribution("flask", "3.1.2", "py3-none-any"),
    ]

    code = piwheels_apt.main([], lambda: distributions, fetch)

    assert code == 0
    assert capsys.readouterr().out == "libgfortran5\nliblgpio1\nlibopenblas0-pthread\n"


def test_main_without_arm_wheels(capsys: pytest.CaptureFixture[str]) -> None:
    # the development machine: no 32-bit ARM wheels, no network access
    assert piwheels_apt.main([], fetch=pytest.fail) == 0
    assert capsys.readouterr().out == ""


def test_main_reports_network_errors(capsys: pytest.CaptureFixture[str]) -> None:
    def offline(url: str) -> Any:
        raise OSError("no network")

    distributions = [Distribution("numpy", "2.4.6", "cp311-cp311-linux_armv6l")]

    code = piwheels_apt.main([], lambda: distributions, offline)

    assert code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Can't read the piwheels data: no network\n"
