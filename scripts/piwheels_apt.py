#!/usr/bin/env python3
"""Print the apt packages needed by the piwheels wheels installed in this venv.

piwheels (ARMv6/ARMv7 wheels for Raspberry Pi OS) builds wheels that link to
system libraries (e.g. numpy needs ``libopenblas0-pthread``) and publishes the
apt packages each wheel needs in its JSON API. ``install.sh`` runs this script
with the ePiframe venv Python after ``uv sync`` and installs what it prints::

    .venv/bin/python scripts/piwheels_apt.py [--lock uv.lock]

Only packages that ``uv.lock`` takes from piwheels and that are installed in
the running interpreter's environment are looked up (stdlib only, no network
access for anything else). The names are printed one per line, sorted.
"""

import argparse
import json
import re
import sys
import tomllib
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

PIWHEELS = "piwheels.org"
PROJECT_URL = "https://www.piwheels.org/project/{name}/json/"
TIMEOUT = 30
ROOT = Path(__file__).resolve().parent.parent

Fetch = Callable[[str], Any]
Installed = Callable[[str], metadata.Distribution | None]


@dataclass(frozen=True)
class Wheel:
    """An installed distribution and the file name of its wheel."""

    name: str
    filenames: tuple[str, ...]


def piwheels_packages(lock: Path) -> list[tuple[str, str]]:
    """Return ``(name, version)`` of the packages ``lock`` takes from piwheels."""
    packages = tomllib.loads(lock.read_text())["package"]
    return [
        (package["name"], package["version"])
        for package in packages
        if PIWHEELS in package.get("source", {}).get("registry", "")
    ]


def installed(name: str) -> metadata.Distribution | None:
    try:
        return metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return None


def wheel_filenames(name: str, distribution: metadata.Distribution) -> list[str]:
    """Return the possible wheel file names (one per tag of the ``WHEEL`` file)."""
    stem = re.sub(r"[-_.]+", "_", name).lower()
    version = distribution.version
    tags = [
        line.split(":", 1)[1].strip()
        for line in (distribution.read_text("WHEEL") or "").splitlines()
        if line.startswith("Tag:")
    ]
    return [f"{stem}-{version}-{tag}.whl" for tag in tags]


def installed_wheels(
    packages: Iterable[tuple[str, str]], find: Installed = installed
) -> list[Wheel]:
    """Return the locked piwheels packages installed in their locked version."""
    wheels = []
    for name, version in packages:
        distribution = find(name)
        if distribution is not None and distribution.version == version:
            wheels.append(Wheel(name, tuple(wheel_filenames(name, distribution))))
    return wheels


def fetch_json(url: str) -> Any:  # pragma: no cover - real network access
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:  # noqa: S310
        return json.load(response)


def project_files(project: Any) -> dict[str, list[str]]:
    """Map the (lower case) wheel file names of a piwheels project to apt packages."""
    return {
        filename.lower(): info.get("apt_dependencies") or []
        for release in project.get("releases", {}).values()
        for filename, info in release.get("files", {}).items()
    }


def apt_dependencies(wheel: Wheel, fetch: Fetch = fetch_json) -> set[str]:
    """Return the apt packages piwheels lists for ``wheel``."""
    files = project_files(fetch(PROJECT_URL.format(name=wheel.name)))
    return {
        package
        for filename in wheel.filenames
        for package in files.get(filename.lower(), [])
    }


def parse_arguments(arguments: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lock", type=Path, default=ROOT / "uv.lock")
    return parser.parse_args(arguments)


def main(
    arguments: Sequence[str] | None = None,
    find: Installed = installed,
    fetch: Fetch = fetch_json,
) -> int:
    options = parse_arguments(arguments)
    wheels = installed_wheels(piwheels_packages(options.lock), find)
    packages: set[str] = set()
    try:
        for wheel in wheels:
            packages |= apt_dependencies(wheel, fetch)
    except (OSError, ValueError) as error:
        print(f"Can't read the piwheels data: {error}", file=sys.stderr)
        return 1
    for package in sorted(packages):
        print(package)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
