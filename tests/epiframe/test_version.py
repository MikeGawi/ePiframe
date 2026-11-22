from importlib import metadata

import pytest
from pytest_mock import MockerFixture

from epiframe import version


@pytest.mark.parametrize(
    ("pep440", "expected"),
    [
        ("1.9.6", "v1.9.6"),
        ("2.0.0", "v2.0.0"),
        ("2.0.0a1", "v2.0.0-alpha.1"),
        ("2.0.0b12", "v2.0.0-beta.12"),
        ("2.0.0rc2", "v2.0.0-rc.2"),
        ("2.0.0.dev3", "v2.0.0.dev3"),
    ],
)
def test_display_version(pep440: str, expected: str) -> None:
    assert version.display_version(pep440) == expected


def test_package_version_matches_metadata() -> None:
    assert version.package_version() == metadata.version("epiframe")
    assert version.__version__ == version.package_version()
    assert version.display_version(version.__version__) == version.VERSION


def test_package_version_not_installed(mocker: MockerFixture) -> None:
    mocker.patch.object(
        metadata,
        "version",
        side_effect=metadata.PackageNotFoundError("epiframe"),
    )
    assert version.package_version() == version.UNKNOWN_VERSION
