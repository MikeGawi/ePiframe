"""Tests of scripts/build_deb.sh: its functions run in bash (the script is sourced).

The display libraries come from local git repositories; the full build needs
dpkg-deb (Debian and Ubuntu, CI) and is skipped without it.
"""

import os
import shutil
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "scripts" / "build_deb.sh"
GIT = ("git", "-c", "user.name=Test", "-c", "user.email=test@example.com")

Bash = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture
def bash() -> Bash:
    def run(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            # $0 must not be build_deb.sh, otherwise the sourced script runs main
            ["bash", "-c", f'source "$1"\n{script}', "bash", str(BUILD)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    return run


def vendor_repository(folder: Path, path: str, file: str) -> str:
    """A git repository with ``file`` in ``path``; returns the commit."""
    (folder / path).mkdir(parents=True)
    (folder / path / file).write_text("# driver\n")
    (folder / "README.md").write_text("not packaged")
    subprocess.run([*GIT, "init", "-q", str(folder)], check=True, timeout=30)
    subprocess.run([*GIT, "-C", str(folder), "add", "-A"], check=True, timeout=30)
    subprocess.run(
        [*GIT, "-C", str(folder), "commit", "-qm", "driver"], check=True, timeout=30
    )
    return subprocess.run(
        ["git", "-C", str(folder), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("2.0.0a3", "2.0.0~a3"),
        ("2.0.0b1", "2.0.0~b1"),
        ("2.1.0rc2", "2.1.0~rc2"),
        ("2.0.0.dev4", "2.0.0~dev4"),
        ("2.0.0", "2.0.0"),
        ("2.0.1", "2.0.1"),
    ],
)
def test_deb_version(bash: Bash, version: str, expected: str) -> None:
    assert bash(f"deb_version {version}").stdout == f"{expected}\n"


def test_deb_versions_sort_like_the_releases() -> None:
    if shutil.which("dpkg") is None:
        pytest.skip("needs dpkg")
    for lower, higher in (("2.0.0~a3", "2.0.0~b1"), ("2.0.0~rc1", "2.0.0")):
        result = subprocess.run(
            ["dpkg", "--compare-versions", lower, "lt", higher],
            check=False,
            timeout=30,
        )
        assert result.returncode == 0


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v2.0.0-alpha.4", "2.0.0a4"),
        ("v2.0.0-beta.1", "2.0.0b1"),
        ("v2.1.0-rc.2", "2.1.0rc2"),
        ("v2.0.0", "2.0.0"),
        ("v2.0.1", "2.0.1"),
    ],
)
def test_tag_version(bash: Bash, tag: str, expected: str) -> None:
    assert bash(f"tag_version {tag}").stdout == f"{expected}\n"


def test_check_tag(bash: Bash) -> None:
    assert bash("check_tag v2.0.0-alpha.4 2.0.0a4").returncode == 0
    # no tag (CI builds of branches): nothing to check
    assert bash("check_tag '' 2.0.0a4").returncode == 0
    wrong = bash("check_tag v2.0.0-alpha.4 2.0.0a3; echo continued")
    assert wrong.returncode == 1
    assert "The tag v2.0.0-alpha.4 is not the version 2.0.0a3" in wrong.stderr
    assert "continued" not in wrong.stdout


def test_build_stops_on_a_wrong_tag(bash: Bash, tmp_path: Path) -> None:
    result = bash(f"build_main --check-tag v1.0.0 --out {tmp_path}/out")

    assert result.returncode == 1
    assert "The tag v1.0.0 is not the version" in result.stderr
    assert not (tmp_path / "out").exists()


def test_project_version(bash: Bash) -> None:
    version = bash("project_version").stdout.strip()

    assert version
    assert f'\nversion = "{version}"\n' in (ROOT / "pyproject.toml").read_text()


def test_parse_build_arguments(bash: Bash) -> None:
    result = bash(
        "parse_build_arguments --arch armhf --arch amd64 --out /tmp/packages"
        ' --check-tag v2.0.0\necho "${SELECTED[*]}|$OUT_DIR|$TAG"'
    )
    defaults = bash('parse_build_arguments; echo "${SELECTED[*]}|$OUT_DIR|$TAG"')

    assert result.stdout == "armhf amd64|/tmp/packages|v2.0.0\n"
    assert defaults.stdout == f"armhf arm64 amd64|{ROOT}/dist|\n"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ("--arch i386", "Unknown architecture i386"),
        ("--out", "--out needs a value"),
        ("--what", "Unknown option --what"),
    ],
)
def test_parse_build_arguments_errors(bash: Bash, arguments: str, message: str) -> None:
    result = bash(f"parse_build_arguments {arguments}; echo continued")

    assert result.returncode == 1
    assert message in result.stderr
    assert "continued" not in result.stdout


def test_help(bash: Bash) -> None:
    result = bash("parse_build_arguments --help; echo continued")

    assert result.returncode == 0
    assert "--arch ARCH" in result.stdout
    assert "continued" not in result.stdout


def test_depends(bash: Bash) -> None:
    armhf, arm64, amd64 = (
        bash(f"depends {architecture}").stdout.strip()
        for architecture in ("armhf", "arm64", "amd64")
    )

    assert amd64.startswith("adduser, ca-certificates, curl, dcraw, fbi, imagemagick,")
    assert "python3 (>= 3.11)" in amd64
    assert "libsqlite3-0 (>= 3.35)" in amd64
    assert "liblgpio1" not in amd64
    assert armhf.startswith(amd64 + ", liblgpio1, libopenblas0-pthread")
    assert armhf.endswith(", libavif16 | libavif15")
    assert arm64 == amd64 + ", liblgpio1, gcc, python3-dev, swig, liblgpio-dev"


def test_sudoers_rule_names_the_device_systemctl(bash: Bash) -> None:
    rules = bash("sudoers_rules epiframe").stdout

    assert "epiframe ALL=(root) NOPASSWD: /usr/bin/systemctl reboot," in rules


def test_copy_code_takes_only_runtime_files(bash: Bash, tmp_path: Path) -> None:
    result = bash(f"copy_code {tmp_path}/code")

    assert result.returncode == 0
    names = sorted(path.name for path in (tmp_path / "code").iterdir())
    assert names == [
        "LICENSE",
        "README.md",
        "install.sh",
        "pyproject.toml",
        "scripts",
        "src",
        "static",
        "templates",
        "uv.lock",
    ]
    assert [path.name for path in (tmp_path / "code" / "scripts").iterdir()] == [
        "piwheels_apt.py"
    ]
    assert (tmp_path / "code" / "src" / "epiframe" / "cli.py").is_file()
    assert not list((tmp_path / "code").rglob("__pycache__"))


def test_control(bash: Bash, tmp_path: Path) -> None:
    (tmp_path / "opt").mkdir()
    (tmp_path / "opt" / "file").write_bytes(b"x" * 10000)

    control = bash(f"control {tmp_path} armhf 2.0.0~a3").stdout

    lines = control.splitlines()
    assert lines[:3] == [
        "Package: epiframe",
        "Version: 2.0.0~a3",
        "Architecture: armhf",
    ]
    size = next(line for line in lines if line.startswith("Installed-Size: "))
    assert int(size.split()[1]) >= 10
    assert any(line.startswith("Depends: adduser, ") for line in lines)
    # the long description: indented lines, "." for an empty one
    description = lines[lines.index(next(x for x in lines if x.startswith("Desc"))) :]
    assert all(line.startswith(" ") for line in description[1:])
    assert " ." in description


@pytest.fixture
def packages(bash: Bash, tmp_path: Path) -> Path:
    """The amd64 and armhf packages built with local display libraries."""
    if shutil.which("dpkg-deb") is None:
        pytest.skip("needs dpkg-deb")
    waveshare = vendor_repository(
        tmp_path / "waveshare",
        "RaspberryPi_JetsonNano/python/lib/waveshare_epd",
        "epd7in5_V2.py",
    )
    inky = vendor_repository(tmp_path / "inky", "inky", "inky_uc8159.py")
    out = tmp_path / "out"
    result = bash(
        f"WAVESHARE_REPO=file://{tmp_path}/waveshare; WAVESHARE_COMMIT={waveshare}\n"
        f"INKY_REPO=file://{tmp_path}/inky; INKY_COMMIT={inky}\n"
        f"build_main --arch amd64 --arch armhf --out {out}"
    )
    assert result.returncode == 0, result.stderr
    assert "Package for armhf:" in result.stdout
    return out


def package_field(package: Path, field: str) -> str:
    return subprocess.run(
        ["dpkg-deb", "--field", str(package), field],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()


def test_build(packages: Path, bash: Bash) -> None:
    version = bash("deb_version $(project_version)").stdout.strip()

    built = sorted(path.name for path in packages.iterdir())

    assert built == [f"epiframe_{version}_amd64.deb", f"epiframe_{version}_armhf.deb"]
    armhf = packages / built[1]
    assert package_field(armhf, "Version") == version
    assert package_field(armhf, "Architecture") == "armhf"
    assert "liblgpio1" in package_field(armhf, "Depends")
    assert "liblgpio1" not in package_field(packages / built[0], "Depends")


def test_built_files(packages: Path, tmp_path: Path) -> None:
    package = next(packages.glob("*_amd64.deb"))
    tree = tmp_path / "tree"
    subprocess.run(
        ["dpkg-deb", "--raw-extract", str(package), str(tree)], check=True, timeout=60
    )

    code = tree / "opt" / "epiframe"
    assert (code / "src" / "epiframe" / "cli.py").is_file()
    assert (code / "lib" / "waveshare_epd" / "epd7in5_V2.py").is_file()
    assert (code / "lib" / "inky" / "inky_uc8159.py").is_file()
    assert not (code / "tests").exists()
    assert not (code / "lib" / "README.md").exists()
    modes = {
        "usr/bin/epiframe": 0o755,
        "opt/epiframe/install.sh": 0o755,
        "DEBIAN/postinst": 0o755,
        "DEBIAN/prerm": 0o755,
        "DEBIAN/postrm": 0o755,
        "etc/sudoers.d/epiframe": 0o440,
        "usr/lib/systemd/system/ePiframe.service": 0o644,
        "usr/share/doc/epiframe/copyright": 0o644,
        "opt/epiframe/pyproject.toml": 0o644,
    }
    for name, mode in modes.items():
        assert stat.S_IMODE((tree / name).stat().st_mode) == mode, name
    assert (tree / "DEBIAN" / "conffiles").read_text() == "/etc/sudoers.d/epiframe\n"
    sudoers = (tree / "etc" / "sudoers.d" / "epiframe").read_text()
    assert sudoers.startswith("# ePiframe (DEB package): ")
    assert "\nepiframe ALL=(root) NOPASSWD: /usr/bin/systemctl reboot," in sudoers
    assert (tree / "usr" / "share" / "doc" / "epiframe" / "README.plugins.md").is_file()


def test_build_without_dpkg_deb_fails(bash: Bash, tmp_path: Path) -> None:
    (tmp_path / "stage" / "DEBIAN").mkdir(parents=True)
    path = f"{tmp_path}/bin:{os.environ['PATH']}"
    (tmp_path / "bin").mkdir()
    fake = tmp_path / "bin" / "dpkg-deb"
    fake.write_text("#!/bin/sh\nexit 2\n")
    fake.chmod(0o755)

    result = bash(
        f"PATH={path}; OUT_DIR={tmp_path}/out; build_package {tmp_path}/stage amd64 2"
    )

    assert result.returncode == 2
    assert result.stdout == ""
