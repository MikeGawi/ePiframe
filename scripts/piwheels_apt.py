#!/usr/bin/env python3
"""Print the apt packages needed by the piwheels wheels installed in this venv.

piwheels (ARMv6/ARMv7 wheels for Raspberry Pi OS) builds wheels that link to
system libraries (e.g. numpy needs ``libopenblas0-pthread``) and publishes the
apt packages each wheel needs in its JSON API. ``install.sh`` runs this script
with the ePiframe venv Python after installing the Python packages (ePiframe's
and the plugins') and installs what it prints::

    .venv/bin/python scripts/piwheels_apt.py

Every installed distribution whose wheel was built for 32-bit ARM Linux
(``linux_armv6l`` / ``linux_armv7l``) is looked up in piwheels by its exact wheel
file name; wheels from elsewhere simply have no piwheels entry. Stdlib only. The
names are printed one per line, sorted.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from importlib import metadata
from typing import Any

PROJECT_URL = "https://www.piwheels.org/project/{name}/json/"
PLATFORMS = ("linux_armv6l", "linux_armv7l")
TIMEOUT = 30

Fetch = Callable[[str], Any]


@dataclass(frozen=True)
class Wheel:
    """An installed distribution and the file names of its wheel."""

    name: str
    filenames: tuple[str, ...]


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def wheel_tags(distribution: metadata.Distribution) -> list[str]:
    return [
        line.split(":", 1)[1].strip()
        for line in (distribution.read_text("WHEEL") or "").splitlines()
        if line.startswith("Tag:")
    ]


def wheel_of(distribution: metadata.Distribution) -> Wheel | None:
    """Return the wheel of ``distribution`` if it was built for 32-bit ARM."""
    tags = [tag for tag in wheel_tags(distribution) if tag.endswith(PLATFORMS)]
    if not tags:
        return None
    name = normalized(distribution.metadata["Name"])
    stem = name.replace("-", "_")
    version = distribution.version
    return Wheel(name, tuple(f"{stem}-{version}-{tag}.whl" for tag in tags))


def arm_wheels(distributions: Iterable[metadata.Distribution]) -> list[Wheel]:
    wheels = {}
    for distribution in distributions:
        wheel = wheel_of(distribution)
        if wheel is not None:
            wheels[wheel.name] = wheel
    return sorted(wheels.values(), key=lambda wheel: wheel.name)


def fetch_json(url: str, urlopen: Callable[..., Any] = urllib.request.urlopen) -> Any:
    """Return the JSON document at ``url``; a missing one is ``FileNotFoundError``."""
    try:
        with urlopen(url, timeout=TIMEOUT) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == HTTPStatus.NOT_FOUND:
            raise FileNotFoundError(url) from error
        raise


def project_files(project: Any) -> dict[str, list[str]]:
    """Map the (lower case) wheel file names of a piwheels project to apt packages."""
    return {
        filename.lower(): info.get("apt_dependencies") or []
        for release in project.get("releases", {}).values()
        for filename, info in release.get("files", {}).items()
    }


def apt_dependencies(wheel: Wheel, fetch: Fetch = fetch_json) -> set[str]:
    """Return the apt packages piwheels lists for ``wheel`` (none if unknown)."""
    try:
        project = fetch(PROJECT_URL.format(name=wheel.name))
    except FileNotFoundError:
        return set()
    files = project_files(project)
    return {
        package
        for filename in wheel.filenames
        for package in files.get(filename.lower(), [])
    }


def parse_arguments(arguments: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    return parser.parse_args(arguments)


def main(
    arguments: Sequence[str] | None = None,
    distributions: Callable[[], Iterable[metadata.Distribution]] = (
        metadata.distributions
    ),
    fetch: Fetch = fetch_json,
) -> int:
    parse_arguments(arguments)
    packages: set[str] = set()
    try:
        for wheel in arm_wheels(distributions()):
            packages |= apt_dependencies(wheel, fetch)
    except (OSError, ValueError) as error:
        print(f"Can't read the piwheels data: {error}", file=sys.stderr)
        return 1
    for package in sorted(packages):
        print(package)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
