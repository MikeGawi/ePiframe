"""Tests of install.sh: its functions run in bash (the script is sourced).

Nothing here needs root, apt or the network: commands that would are replaced by
shell functions defined before the call (e.g. ``function as_user { "$@"; }``), and
git repositories are local.
"""

import getpass
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from epiframe.core import system

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "install.sh"
GIT = (
    "git",
    "-c",
    "user.name=Test",
    "-c",
    "user.email=test@example.com",
    "-c",
    "init.defaultBranch=main",
    "-c",
    "advice.detachedHead=false",
)
# run as the current user instead of sudo -u (no braces: the scripts are formatted)
AS_USER = 'as_user() ( "$@" ); EPI_USER=$(id -un);'
NO_SERVICE = "function installed_service_dir { :; };"

Bash = Callable[..., subprocess.CompletedProcess[str]]


def run_bash(
    script: str, stdin: str = "", env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        # $0 must not be install.sh, otherwise the sourced script runs main
        ["bash", "-c", f'source "$1"\n{script}', "bash", str(INSTALL)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, **(env or {})},
    )


@pytest.fixture
def bash() -> Bash:
    return run_bash


def git(*arguments: str | Path) -> str:
    return subprocess.run(
        [*GIT, *map(str, arguments)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout.strip()


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    """A repository with release tags and a v2 branch."""
    repository = tmp_path / "origin"
    repository.mkdir()
    git("-C", repository, "init", "-q")
    (repository / "src" / "epiframe").mkdir(parents=True)
    (repository / "src" / "epiframe" / "__init__.py").write_text("")
    for tag in ("v1.9.6", "v2.0.0-alpha.3", "v2.0.0", "v2.1.0", "v2.2.0-beta.1"):
        (repository / "version").write_text(tag)
        git("-C", repository, "add", "-A")
        git("-C", repository, "commit", "-qm", tag)
        git("-C", repository, "tag", tag)
    git("-C", repository, "branch", "v2")
    return repository


@pytest.fixture
def checkout(tmp_path: Path, origin: Path) -> Path:
    folder = tmp_path / "ePiframe"
    git("clone", "-q", origin, folder)
    git("-C", folder, "checkout", "-q", "v2.0.0")
    return folder


def test_help_and_next_steps_run_without_root() -> None:
    for option, text in (("--help", "--update"), ("--next-steps", "check-config")):
        result = subprocess.run(
            ["bash", str(INSTALL), option],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert result.returncode == 0
        assert text in result.stdout


def test_parse_arguments(bash: Bash) -> None:
    result = bash(
        "parse_arguments --update --path /opt/frame --user frame --branch v2"
        " --repo /tmp/repo --yes --no-hardware\n"
        'echo "$ACTION|$INSTALL_DIR|$EPI_USER|$REF|$REPO_URL|$ASSUME_YES|$HARDWARE"'
    )

    assert result.stdout == "update|/opt/frame|frame|v2|/tmp/repo|1|0\n"


def test_parse_arguments_defaults(bash: Bash) -> None:
    result = bash(
        'parse_arguments; echo "$ACTION|$INSTALL_DIR|$REF|$ASSUME_YES|$HARDWARE"'
    )

    assert result.stdout == "install|||0|1\n"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [("--what", "Unknown option --what"), ("--path", "--path needs a value")],
)
def test_parse_arguments_errors(bash: Bash, arguments: str, message: str) -> None:
    result = bash(f"parse_arguments {arguments}; echo continued")

    assert result.returncode == 1
    assert message in result.stderr
    assert "continued" not in result.stdout


@pytest.mark.parametrize(
    ("machine", "target"),
    [
        ("armv6l", "arm-unknown-linux-musleabihf"),
        ("armv7l", "armv7-unknown-linux-gnueabihf"),
        ("aarch64", "aarch64-unknown-linux-gnu"),
        ("x86_64", "x86_64-unknown-linux-gnu"),
    ],
)
def test_uv_target(bash: Bash, machine: str, target: str) -> None:
    assert bash(f"uv_target {machine}").stdout == f"{target}\n"


def test_uv_target_unknown(bash: Bash) -> None:
    assert bash("uv_target mips").returncode == 1


@pytest.mark.parametrize(
    ("version", "minimum", "result"),
    [
        ("0.11.19", "0.11.19", 0),
        ("0.11.20", "0.11.19", 0),
        ("0.12.0", "0.11.19", 0),
        ("0.11.9", "0.11.19", 1),
        ("0.9.30", "0.11.19", 1),
    ],
)
def test_version_at_least(bash: Bash, version: str, minimum: str, result: int) -> None:
    assert bash(f"version_at_least {version} {minimum}").returncode == result


def test_find_uv(bash: Bash, tmp_path: Path) -> None:
    uv = tmp_path / "uv"
    uv.write_text('#!/bin/sh\necho "uv $VERSION (x)"\n')
    uv.chmod(0o755)

    found = bash(f"BIN_DIR={tmp_path}; find_uv", env={"VERSION": "0.12.1"})
    old = bash(
        f"BIN_DIR={tmp_path}; PATH=/usr/bin:/bin; find_uv", env={"VERSION": "0.1.0"}
    )

    assert found.stdout == f"{uv}\n"
    assert old.returncode == 1


def test_latest_tag_skips_pre_releases_and_1x(bash: Bash, origin: Path) -> None:
    assert bash(f"latest_tag {origin}").stdout == "v2.1.0\n"


def test_latest_tag_without_releases(bash: Bash, origin: Path) -> None:
    for tag in ("v2.0.0", "v2.1.0"):
        git("-C", origin, "tag", "-d", tag)

    assert bash(f"latest_tag {origin}").stdout == ""
    assert bash(f"latest_tag {origin.parent / 'missing'}").stdout == ""


@pytest.mark.parametrize("folder", ["/home/pi/ePiframe", "/opt/e-Pi_frame.2"])
def test_check_install_dir_accepts(bash: Bash, folder: str) -> None:
    assert bash(f"check_install_dir {folder}").returncode == 0


@pytest.mark.parametrize(
    "folder", ["relative/ePiframe", "'/home/pi/my frame'", "'/a|b'"]
)
def test_check_install_dir_refuses(bash: Bash, folder: str) -> None:
    result = bash(f"check_install_dir {folder}")

    assert result.returncode == 1
    assert "must be an absolute path" in result.stderr


def test_check_user(bash: Bash) -> None:
    assert "Run the installer with sudo" in bash("EPI_USER=; check_user").stderr
    assert "There is no user" in bash("EPI_USER=no-such-user-x; check_user").stderr
    assert bash(f"EPI_USER={getpass.getuser()}; check_user").returncode == 0


@pytest.mark.parametrize(
    ("machine", "hardware", "message"),
    [
        ("x86_64", 1, "This is not a Raspberry Pi (x86_64)"),
        ("mips", 0, "Unsupported architecture mips"),
    ],
)
def test_check_machine_refuses(
    bash: Bash, machine: str, hardware: int, message: str
) -> None:
    result = bash(
        f"function machine {{ echo {machine}; }}; HARDWARE={hardware}; check_machine"
    )

    assert result.returncode == 1
    assert message in result.stderr


@pytest.mark.parametrize("machine", ["x86_64", "armv6l", "aarch64"])
def test_check_machine_without_hardware(bash: Bash, machine: str) -> None:
    result = bash(f"function machine {{ echo {machine}; }}; HARDWARE=0; check_machine")

    assert result.returncode == 0


def test_check_python(bash: Bash) -> None:
    assert bash(f"SYSTEM_PYTHON={sys.executable}; check_python").returncode == 0
    missing = bash("SYSTEM_PYTHON=/no/python; check_python")
    assert "There is no /no/python" in missing.stderr


def test_check_python_too_old(bash: Bash, tmp_path: Path) -> None:
    python = tmp_path / "python3"
    python.write_text('#!/bin/sh\n[ "$1" = -V ] && echo "Python 3.9.2"\nexit 1\n')
    python.chmod(0o755)

    result = bash(f"SYSTEM_PYTHON={python}; check_python")

    assert result.returncode == 1
    assert "needs Python 3.11 or newer (Python 3.9.2)" in result.stderr


@pytest.mark.parametrize(
    ("machine", "hardware", "pi", "build"),
    [
        ("armv6l", 1, True, False),
        ("aarch64", 1, True, True),
        ("aarch64", 0, False, False),
        ("x86_64", 0, False, False),
    ],
)
def test_apt_packages(
    bash: Bash, machine: str, hardware: int, pi: bool, build: bool
) -> None:
    packages = bash(
        f"function machine {{ echo {machine}; }}; HARDWARE={hardware}; apt_packages"
    ).stdout.split()

    assert packages[:3] == ["git", "ca-certificates", "curl"]
    assert {"imagemagick", "fbi", "dcraw", "webp", "python3"} <= set(packages)
    assert ("liblgpio1" in packages) is pi
    assert ("swig" in packages) is build
    assert ("liblgpio-dev" in packages) is build


def test_python_modules(bash: Bash) -> None:
    assert "lgpio" in bash("HARDWARE=1; python_modules").stdout.split()
    modules = bash("HARDWARE=0; python_modules").stdout.split()
    assert "epiframe.cli" in modules
    assert "lgpio" not in modules


def test_python_modules_are_importable_in_the_dev_environment() -> None:
    modules = run_bash("HARDWARE=0; python_modules").stdout.split()

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib, sys; [importlib.import_module(m) for m in sys.argv[1:]]",
            *modules,
        ],
        check=True,
        timeout=60,
    )


def test_confirm(bash: Bash) -> None:
    script = 'confirm "Go?" {default} && echo yes || echo no'

    assert bash(script.format(default="Y"), stdin="\n").stdout.endswith("yes\n")
    assert bash(script.format(default="N"), stdin="\n").stdout.endswith("no\n")
    assert bash(script.format(default="N"), stdin="y\n").stdout.endswith("yes\n")
    assert bash(script.format(default="Y"), stdin="no\n").stdout.endswith("no\n")
    # end of the input
    assert bash(script.format(default="Y")).stdout.endswith("yes\n")
    assert bash("ASSUME_YES=1; " + script.format(default="N"), stdin="y\n").stdout == (
        "no\n"
    )


def test_step_success(bash: Bash, tmp_path: Path) -> None:
    log = tmp_path / "install.log"

    result = bash(f"LOG={log}; step 'Saying hello' echo hello; echo after")

    assert result.stdout.startswith("Saying hello:")
    assert "check!" in result.stdout
    assert result.stdout.endswith("after\n")
    assert log.read_text() == "hello\n"


def test_step_failure_shows_the_log(bash: Bash, tmp_path: Path) -> None:
    log = tmp_path / "install.log"

    result = bash(
        f"LOG={log}; step 'Failing' sh -c 'echo broken output; exit 3'; echo after"
    )

    assert result.returncode == 1
    assert "error!" in result.stdout
    assert "after" not in result.stdout
    assert "broken output" in result.stderr
    assert f"Failing failed, the full output is in {log}" in result.stderr


def test_render_unit(bash: Bash) -> None:
    unit = bash(
        f"render_unit {ROOT / 'misc/ePiframe.service.org'} pi /home/pi/ePiframe"
    ).stdout

    assert "\nUser=pi\n" in unit
    assert "\nExecStart=/home/pi/ePiframe/.venv/bin/epiframe service\n" in unit
    assert "\nWorkingDirectory=/home/pi/ePiframe\n" in unit
    assert "@" not in unit


def test_sudoers_rules_match_the_service_commands(bash: Bash) -> None:
    rules = bash(
        "function systemctl_path { echo /usr/bin/systemctl; }; sudoers_rules pi"
    ).stdout

    assert rules.splitlines()[1] == (
        "pi ALL=(root) NOPASSWD: /usr/bin/systemctl reboot,"
        " /usr/bin/systemctl poweroff,"
        " /usr/bin/systemctl --no-block restart ePiframe.service"
    )


def test_sudoers_rules_follow_epiframe_core_system() -> None:
    # the exact argument lists epiframe.core.system runs with sudo -n
    assert system.SERVICE == "ePiframe.service"
    assert system.SYSTEMCTL == "systemctl"
    source = Path(system.__file__).read_text()
    for command in (
        '[SYSTEMCTL, "reboot"]',
        '[SYSTEMCTL, "poweroff"]',
        '[SYSTEMCTL, "--no-block", "restart", service]',
    ):
        assert command in source


def test_command_script_runs_epiframe_in_its_folder(bash: Bash, tmp_path: Path) -> None:
    frame = tmp_path / "frame"
    (frame / ".venv" / "bin").mkdir(parents=True)
    epiframe = frame / ".venv" / "bin" / "epiframe"
    epiframe.write_text('#!/bin/sh\necho "$(pwd) $*"\n')
    epiframe.chmod(0o755)
    command = tmp_path / "epiframe"
    command.write_text(bash(f"command_script {getpass.getuser()} {frame}").stdout)
    command.chmod(0o755)

    result = subprocess.run(
        [str(command), "test", "--no-skip"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
        cwd=tmp_path,
    )

    assert result.stdout == f"{frame} test --no-skip\n"


def test_user_groups_only_existing(bash: Bash) -> None:
    script = (
        "USER_GROUPS=(root no-such-group-x); USER_PI_GROUPS=(root); HARDWARE={};"
        " user_groups"
    )

    assert bash(script.format(0)).stdout == "root\n"
    assert bash(script.format(1)).stdout == "root,root\n"


def test_check_new_install_dir(bash: Bash, tmp_path: Path, checkout: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    full = tmp_path / "full"
    full.mkdir()
    (full / "file").touch()

    assert (
        bash(f"INSTALL_DIR={tmp_path / 'new'}; check_new_install_dir").returncode == 0
    )
    assert bash(f"INSTALL_DIR={empty}; check_new_install_dir").returncode == 0
    assert (
        "use --update" in bash(f"INSTALL_DIR={checkout}; check_new_install_dir").stderr
    )
    assert "is not empty" in bash(f"INSTALL_DIR={full}; check_new_install_dir").stderr


def test_find_install_dir(bash: Bash, checkout: Path) -> None:
    script = (
        "function installed_service_dir {{ echo {service}; }}; INSTALL_DIR={path};"
        ' EPI_USER=; find_install_dir; echo "$INSTALL_DIR|$EPI_USER"'
    )

    from_service = bash(script.format(service=checkout, path=""))
    from_option = bash(script.format(service="", path=checkout))

    assert from_service.stdout == f"{checkout}|{getpass.getuser()}\n"
    assert from_option.stdout == from_service.stdout


def test_find_install_dir_refuses_1x(bash: Bash, tmp_path: Path) -> None:
    (tmp_path / "misc").mkdir()
    (tmp_path / "misc" / "constants.py").touch()

    result = bash(f"{NO_SERVICE} INSTALL_DIR={tmp_path}; find_install_dir")

    assert result.returncode == 1
    assert "is ePiframe 1.x" in result.stderr


def test_find_install_dir_without_installation(bash: Bash, tmp_path: Path) -> None:
    result = bash(f"{NO_SERVICE} INSTALL_DIR={tmp_path}; find_install_dir")

    assert result.returncode == 1
    assert f"There is no ePiframe installation in {tmp_path}" in result.stderr


def test_update_target(bash: Bash, checkout: Path) -> None:
    script = f"{AS_USER} INSTALL_DIR={checkout}; REF={{}}; update_target"

    assert bash(script.format("")).stdout == "v2.1.0\n"
    assert bash(script.format("v2.0.0")).stdout == "v2.0.0\n"
    git("-C", checkout, "checkout", "-q", "v2")
    assert bash(script.format("")).stdout == "v2\n"


def test_target_commit(bash: Bash, checkout: Path, origin: Path) -> None:
    script = f"{AS_USER} INSTALL_DIR={checkout}; target_commit {{}}"

    assert bash(script.format("v2")).stdout.strip() == git(
        "-C", origin, "rev-parse", "v2"
    )
    assert bash(script.format("v2.0.0")).stdout.strip() == git(
        "-C", origin, "rev-parse", "v2.0.0^{commit}"
    )
    assert bash(script.format("v9.9.9")).returncode != 0


def test_checkout_target_tag_and_branch(
    bash: Bash, checkout: Path, origin: Path
) -> None:
    script = f"{AS_USER} INSTALL_DIR={checkout}; checkout_target {{}}"

    assert bash(script.format("v2.1.0")).returncode == 0
    assert git("-C", checkout, "describe", "--tags") == "v2.1.0"

    assert bash(script.format("v2")).returncode == 0
    assert git("-C", checkout, "symbolic-ref", "--short", "HEAD") == "v2"
    # the branch moves on: --update fast-forwards it
    git("-C", origin, "checkout", "-q", "v2")
    (origin / "new").write_text("new")
    git("-C", origin, "add", "-A")
    git("-C", origin, "commit", "-qm", "new")
    git("-C", checkout, "fetch", "-q", "origin")
    assert bash(script.format("v2")).returncode == 0
    assert (checkout / "new").read_text() == "new"


def test_check_clean_checkout(bash: Bash, checkout: Path) -> None:
    script = f"{AS_USER} INSTALL_DIR={checkout}; check_clean_checkout"
    (checkout / "config.cfg").write_text("untracked files are fine")

    assert bash(script).returncode == 0
    (checkout / "version").write_text("changed")
    result = bash(script)
    assert result.returncode == 1
    assert "M version" in result.stderr


def test_backup_and_restore_config(bash: Bash, checkout: Path) -> None:
    (checkout / "config.cfg").write_text("[x]\n")
    (checkout / "misc").mkdir()
    (checkout / "misc" / "users.db").write_text("users")

    backup = Path(
        bash(f"{AS_USER} INSTALL_DIR={checkout}; backup_files").stdout.strip()
    )

    assert backup.parent == checkout / "backup"
    assert sorted(path.name for path in backup.iterdir()) == ["config.cfg", "users.db"]
    (checkout / "config.cfg").unlink()
    assert (
        bash(f"{AS_USER} INSTALL_DIR={checkout}; restore_config {backup}").returncode
        == 0
    )
    assert (checkout / "config.cfg").read_text() == "[x]\n"
    # an existing configuration is never replaced
    (checkout / "config.cfg").write_text("[new]\n")
    bash(f"{AS_USER} INSTALL_DIR={checkout}; restore_config {backup}")
    assert (checkout / "config.cfg").read_text() == "[new]\n"


def test_fetch_library(bash: Bash, tmp_path: Path) -> None:
    vendor = tmp_path / "vendor"
    (vendor / "python" / "lib" / "driver").mkdir(parents=True)
    (vendor / "python" / "lib" / "driver" / "epd.py").write_text("one")
    (vendor / "other.txt").write_text("not copied")
    git("-C", vendor, "init", "-q")
    git("-C", vendor, "add", "-A")
    git("-C", vendor, "commit", "-qm", "one")
    first = git("-C", vendor, "rev-parse", "HEAD")
    (vendor / "python" / "lib" / "driver" / "epd.py").write_text("two")
    git("-C", vendor, "commit", "-qam", "two")
    frame = tmp_path / "frame"
    frame.mkdir()
    script = (
        f"{AS_USER} INSTALL_DIR={frame};"
        f" fetch_library file://{vendor} {{}} python/lib/driver waveshare_epd"
    )

    assert bash(script.format(first)).returncode == 0
    assert (frame / "lib" / "waveshare_epd" / "epd.py").read_text() == "one"
    assert sorted(path.name for path in (frame / "lib").iterdir()) == [
        ".waveshare_epd.commit",
        "waveshare_epd",
    ]
    # the same commit again: nothing is downloaded
    assert (
        bash(script.format(first).replace("file://", "file:///missing")).returncode == 0
    )
    assert bash(script.format(git("-C", vendor, "rev-parse", "HEAD"))).returncode == 0
    assert (frame / "lib" / "waveshare_epd" / "epd.py").read_text() == "two"
    assert bash(script.format("0" * 40)).returncode != 0


def test_show_next_steps(bash: Bash) -> None:
    steps = bash("INSTALL_DIR=/home/pi/ePiframe; show_next_steps").stdout
    reboot = bash("INSTALL_DIR=/x; REBOOT_NEEDED=1; show_next_steps").stdout

    assert "1. Connect the display\n" in steps
    assert "Copy its config.cfg and misc/users.db into /home/pi/ePiframe" in steps
    assert "and reboot (SPI/I2C were enabled)" in reboot


def test_pinned_display_libraries_are_full_commits(bash: Bash) -> None:
    commits = bash('echo "$WAVESHARE_COMMIT $INKY_COMMIT"').stdout.split()

    assert [len(commit) for commit in commits] == [40, 40]
