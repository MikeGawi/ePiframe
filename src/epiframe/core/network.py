"""Network helpers: connectivity check, IP address validation and file download."""

import ipaddress
import os
import tempfile
from pathlib import Path

import requests

CHUNK_SIZE = 64 * 1024


def check_internet(url: str, timeout: float) -> str | None:
    """Return ``None`` if ``url`` answers, otherwise the error message.

    Any HTTP response counts as "connected"; only request failures (DNS, refused
    connection, timeout, ...) are reported.
    """
    try:
        requests.get(url, timeout=timeout)
    except requests.RequestException as exception:
        return str(exception)
    return None


def validate_ip(value: str) -> None:
    """Raise ``ValueError`` if ``value`` is not an IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise ValueError("Not a valid IP address!") from None


def download_file(
    url: str,
    destination: str | os.PathLike[str],
    timeout: float,
    session: requests.Session | None = None,
) -> Path:
    """Download ``url`` to ``destination`` and return its path.

    The body is streamed into a temporary file next to ``destination`` that is
    renamed only when the download is complete, so an interrupted download never
    leaves a truncated file behind. ``session`` allows authenticated requests (e.g.
    google-auth's ``AuthorizedSession``). Raises ``requests.HTTPError`` for error
    responses and any other ``requests.RequestException`` on failure.
    """
    target = Path(destination)
    get = session.get if session else requests.get
    with get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        handle, temporary = tempfile.mkstemp(
            dir=target.parent, prefix=f".{target.name}."
        )
        try:
            with os.fdopen(handle, "wb") as file:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    file.write(chunk)
            os.replace(temporary, target)
        except BaseException:
            os.remove(temporary)
            raise
    return target
