"""Application version, read from the installed package metadata (pyproject.toml)."""

import re
from importlib import metadata

DISTRIBUTION = "epiframe"
UNKNOWN_VERSION = "0.0.0"

_PRE_RELEASES = {"a": "alpha", "b": "beta", "rc": "rc"}
_PEP440 = re.compile(r"^(?P<release>\d+(?:\.\d+)*)(?:(?P<pre>a|b|rc)(?P<number>\d+))?$")


def package_version() -> str:
    """Return the PEP 440 version of the installed distribution, e.g. ``2.0.0a1``."""
    try:
        return metadata.version(DISTRIBUTION)
    except metadata.PackageNotFoundError:
        return UNKNOWN_VERSION


def display_version(version: str) -> str:
    """Convert a PEP 440 version to the ``v``-prefixed SemVer display string.

    ``2.0.0a1`` -> ``v2.0.0-alpha.1``, ``1.9.6`` -> ``v1.9.6``. Versions in any other
    format are only prefixed with ``v``.
    """
    match = _PEP440.match(version)
    if not match or not match["pre"]:
        return f"v{version}"
    return f"v{match['release']}-{_PRE_RELEASES[match['pre']]}.{match['number']}"


__version__ = package_version()
VERSION = display_version(__version__)
