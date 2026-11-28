"""Tests of the DEB package files in packaging/deb.

postinst runs in bash with install.sh of the checkout (it is sourced); commands
that need root are replaced by shell functions. prerm, postrm and the epiframe
command use fixed system paths, so they run as copies with those paths moved
into ``tmp_path``.
"""

import configparser
import getpass
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGING = ROOT / "packaging" / "deb"
POSTINST = PACKAGING / "postinst"
USER = getpass.getuser()
# root-only parts of postinst replaced (no braces: the scripts are formatted)
AS_ME = f'SERVICE_USER="{USER}";'

Bash = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture
def bash() -> Bash:
    def run(
        script: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            # $0 must not be postinst, otherwise the sourced script runs main
            ["bash", "-c", f'source "$1"\n{script}', "bash", str(POSTINST)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={
                **os.environ,
                "EPIFRAME_INSTALLER": str(ROOT / "install.sh"),
                **(env or {}),
            },
        )

    return run


def executable(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)
    return path


# ---------------------------------------------------------------------- postinst


def test_postinst_needs_install_sh(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(POSTINST), "configure"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "EPIFRAME_INSTALLER": str(tmp_path / "missing.sh")},
    )

    assert result.returncode == 1


def test_postinst_main(bash: Bash) -> None:
    configured = bash(
        'function configure { echo "configure $1"; }; main configure 2.0.0~a3'
    )
    first = bash('function configure { echo "configure [$1]"; }; main configure')
    aborted = bash("main abort-upgrade 2.0.0; echo done")
    unknown = bash("main triggered; echo continued")

    assert configured.stdout == "configure 2.0.0~a3\n"
    assert first.stdout == "configure []\n"
    assert aborted.stdout == "done\n"
    assert unknown.returncode == 1
    assert "unknown argument: triggered" in unknown.stderr
    assert "continued" not in unknown.stdout


def test_as_user_runs_as_the_caller(bash: Bash) -> None:
    # postinst runs as root, so its files (code, venv, uv) belong to root
    assert bash("as_user id -un").stdout == f"{USER}\n"


@pytest.mark.parametrize(
    ("model", "expected"),
    [("Raspberry Pi Zero W Rev 1.1\0", 0), ("QEMU Virtual Machine\0", 1), (None, 1)],
)
def test_is_raspberry_pi(
    bash: Bash, tmp_path: Path, model: str | None, expected: int
) -> None:
    if model is not None:
        (tmp_path / "model").write_text(model)

    assert bash(f"MODEL_FILE={tmp_path}/model; is_raspberry_pi").returncode == expected


def test_create_user(bash: Bash, tmp_path: Path) -> None:
    calls = tmp_path / "calls"
    fake = f'function adduser {{ echo "$*" > {calls}; }};'

    existing = bash(f"{fake} SERVICE_USER={USER}; create_user")
    assert existing.returncode == 0
    assert not calls.exists()

    created = bash(f"{fake} SERVICE_USER=no-such-user-epiframe; create_user")
    assert created.returncode == 0
    assert calls.read_text() == (
        "--system --group --quiet --home /var/lib/epiframe --no-create-home"
        " no-such-user-epiframe\n"
    )


def test_create_folders(bash: Bash, tmp_path: Path) -> None:
    result = bash(
        f"{AS_ME} CONFIG_DIR={tmp_path}/etc; DATA_DIR={tmp_path}/var;"
        f" CACHE_DIR={tmp_path}/cache; BIN_DIR={tmp_path}/opt/bin; create_folders"
    )

    assert result.returncode == 0
    modes = {
        "etc": 0o750,
        "var": 0o750,
        "var/plugins": 0o755,
        "cache": 0o755,
        "opt/bin": 0o755,
    }
    for name, mode in modes.items():
        assert (tmp_path / name).stat().st_mode & 0o777 == mode, name


def test_create_frame_config(bash: Bash, tmp_path: Path) -> None:
    script = f"{AS_ME} PACKAGE_DIR={ROOT}; CONFIG_DIR={tmp_path}; create_frame_config"

    assert bash(script).returncode == 0
    config = tmp_path / "config.cfg"
    assert (
        config.read_text() == (ROOT / "src/epiframe/config/config.default").read_text()
    )
    assert config.stat().st_mode & 0o777 == 0o600
    # an existing configuration stays
    config.write_text("[Mine]\n")
    assert bash(script).returncode == 0
    assert config.read_text() == "[Mine]\n"


def test_wheel_libraries_and_compile_code(bash: Bash, tmp_path: Path) -> None:
    package = tmp_path / "opt"
    (package / ".venv" / "bin").mkdir(parents=True)
    (package / ".venv" / "bin" / "python").symlink_to(sys.executable)
    executable(package / "scripts" / "piwheels_apt.py", "print('liblgpio1')\n")
    (package / "src" / "epiframe").mkdir(parents=True)
    (package / "src" / "epiframe" / "module.py").write_text("VALUE = 1\n")
    (package / "lib" / "inky").mkdir(parents=True)
    (package / "lib" / "inky" / "driver.py").write_text("VALUE = 2\n")

    libraries = bash(f"PACKAGE_DIR={package}; wheel_libraries")
    compiled = bash(f"PACKAGE_DIR={package}; compile_code")

    assert libraries.stdout == "liblgpio1\n"
    assert compiled.returncode == 0
    assert list((package / "src" / "epiframe" / "__pycache__").glob("module.*.pyc"))
    assert list((package / "lib" / "inky" / "__pycache__").glob("driver.*.pyc"))


def test_package_installed(bash: Bash) -> None:
    fake = "function dpkg-query {{ [[ $4 == bash ]] && echo {}; }};"

    assert bash(fake.format("installed") + " package_installed bash").returncode == 0
    assert bash(fake.format("config-files") + " package_installed bash").returncode == 1
    assert bash(fake.format("installed") + " package_installed other").returncode == 1


FAKE_LIBRARIES = (
    "function wheel_libraries {"
    " printf 'liblgpio1\\nlibopenblas0-pthread\\nlibavif16\\n'; };"
    " function package_installed { [[ $1 == libopenblas0-pthread ]]; };"
    " function apt_install { echo apt; };"
)


def test_install_wheel_libraries_reports_the_missing_ones(bash: Bash) -> None:
    # postinst replaces install.sh's apt install (apt can't run inside dpkg)
    result = bash(
        f"{FAKE_LIBRARIES} function machine {{ echo armv6l; }};"
        ' install_wheel_libraries_on_arm32; echo "[$MISSING_LIBRARIES]"'
    )

    assert result.returncode == 0
    assert result.stdout == "[liblgpio1 libavif16]\n"
    assert "sudo apt install liblgpio1 libavif16, then: sudo dpkg --configure -a" in (
        result.stderr
    )


def test_install_wheel_libraries_with_everything_installed(bash: Bash) -> None:
    result = bash(
        "function wheel_libraries { echo liblgpio1; };"
        " function package_installed { true; };"
        ' install_wheel_libraries; echo "[$MISSING_LIBRARIES]"'
    )

    assert result.stdout == "[]\n"
    assert result.stderr == ""


def test_install_wheel_libraries_when_piwheels_fails(bash: Bash) -> None:
    result = bash(
        "function wheel_libraries { return 1; }; install_wheel_libraries; echo $?"
    )

    assert result.stdout == "0\n"
    assert "Can't read the system libraries" in result.stderr


@pytest.fixture
def systemctl(tmp_path: Path) -> str:
    """Shell functions recording the systemctl calls in ``calls``."""
    return f'function systemctl {{ echo "$*" >> {tmp_path}/calls; }};'


@pytest.mark.parametrize(
    "case",
    [
        (True, "", ["daemon-reload", "enable --quiet ePiframe.service"]),
        (False, "", ["enable --quiet ePiframe.service"]),
        (True, "2.0.0~a3", ["daemon-reload", "try-restart ePiframe.service"]),
        (False, "2.0.0~a3", []),
    ],
)
def test_setup_service(
    bash: Bash, tmp_path: Path, systemctl: str, case: tuple[bool, str, list[str]]
) -> None:
    running, previous, expected = case

    result = bash(
        f"{systemctl} function systemd_running {{ {'true' if running else 'false'}; }};"
        f" setup_service '{previous}'"
    )

    assert result.returncode == 0
    assert calls(tmp_path) == expected


def test_check_other_installation(bash: Bash, tmp_path: Path) -> None:
    script = (
        f"UNIT_FILE={tmp_path}/unit; COMMAND_FILE={tmp_path}/command;"
        " check_other_installation"
    )

    assert bash(script).stderr == ""
    (tmp_path / "unit").touch()
    (tmp_path / "command").touch()
    warnings = bash(script)
    assert warnings.returncode == 0
    assert (
        f"{tmp_path}/unit (ePiframe installed with install.sh) replaces"
        in warnings.stderr
    )
    assert f"{tmp_path}/command (ePiframe installed with install.sh) comes before" in (
        warnings.stderr
    )


def test_show_package_next_steps(bash: Bash) -> None:
    steps = bash("show_package_next_steps").stdout
    reboot = bash("REBOOT_NEEDED=1; show_package_next_steps").stdout

    assert "1. Connect the display\n" in steps
    assert (
        "config.cfg into /etc/epiframe and misc/users.db into /var/lib/epiframe"
        in steps
    )
    assert "sudo dpkg-reconfigure epiframe" in steps
    assert "and reboot (SPI/I2C were enabled)" in reboot


CONFIGURE_STEPS = (
    "create_user",
    "add_user_groups",
    "create_folders",
    "create_frame_config",
    "install_uv",
    "install_python_environment",
    "enable_interfaces",
    "compile_code",
    "setup_service",
    "show_package_next_steps",
)


@pytest.fixture
def configure(
    bash: Bash, tmp_path: Path
) -> Callable[[str], subprocess.CompletedProcess[str]]:
    """Run configure with every step recording its name (and the settings)."""
    record = "".join(
        f'function {name} {{ echo "{name} $*" >> {tmp_path}/calls; }};'
        for name in CONFIGURE_STEPS
    )

    def run(arguments: str) -> subprocess.CompletedProcess[str]:
        return bash(
            f"{record} MODEL_FILE={tmp_path}/model; configure {arguments};"
            ' echo "$INSTALL_DIR|$EPI_USER|$BIN_DIR|$PLUGINS_DIR'
            '|${PLUGIN_UV_OPTIONS[*]}|$UV_CACHE_DIR|$HARDWARE|$LOG"'
        )

    return run


def test_configure_first_installation(
    configure: Callable[..., Any], tmp_path: Path
) -> None:
    result = configure("''")

    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    assert [call.split()[0] for call in calls] == list(CONFIGURE_STEPS)
    assert "setup_service " in calls
    settings, log = result.stdout.splitlines()[-1].rsplit("|", 1)
    assert settings == (
        "/opt/epiframe|epiframe|/opt/epiframe/bin|/var/lib/epiframe/plugins|--no-build"
        "|/var/cache/epiframe/uv|0"
    )
    assert not Path(log).exists()


def test_configure_upgrade_on_a_raspberry_pi(
    configure: Callable[..., Any], tmp_path: Path
) -> None:
    (tmp_path / "model").write_text("Raspberry Pi 4 Model B Rev 1.4\0")

    result = configure("2.0.0~a3")

    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    assert calls[-1] == "setup_service 2.0.0~a3"
    assert result.stdout.splitlines()[-1].split("|")[6] == "1"


def test_configure_stops_on_a_failed_step(bash: Bash, tmp_path: Path) -> None:
    record = "".join(f"function {name} {{ :; }};" for name in CONFIGURE_STEPS)

    result = bash(
        f"{record} function create_folders {{ return 1; }};"
        f" MODEL_FILE={tmp_path}/model; configure ''; echo continued"
    )

    assert result.returncode == 1
    assert "Creating the folders failed" in result.stderr
    assert "continued" not in result.stdout


# ----------------------------------------------------------- prerm, postrm, command


def moved(script: str, tmp_path: Path, user: str = "epiframe") -> str:
    """``script`` with its system paths moved into ``tmp_path``."""
    for path in (
        "/opt/epiframe",
        "/etc/epiframe",
        "/var/lib/epiframe",
        "/var/cache/epiframe",
    ):
        script = script.replace(path, f"{tmp_path}{path}")
    script = script.replace("/run/systemd/system", f"{tmp_path}/run/systemd/system")
    return script.replace("epiframe ]", f"{user} ]").replace(
        "-u epiframe", f"-u {user}"
    )


@pytest.fixture
def fake_bin(tmp_path: Path) -> dict[str, str]:
    """systemctl, sudo and runuser recording their arguments in ``calls``."""
    for name in ("systemctl", "sudo", "runuser"):
        executable(
            tmp_path / "bin" / name,
            f'#!/bin/sh\necho "{name} $*" >> {tmp_path}/calls\n',
        )
    return {"PATH": f"{tmp_path}/bin:{os.environ['PATH']}"}


def run_script(
    name: str,
    tmp_path: Path,
    env: dict[str, str],
    *arguments: str,
    user: str = "epiframe",
) -> subprocess.CompletedProcess[str]:
    script = executable(
        tmp_path / name, moved((PACKAGING / name).read_text(), tmp_path, user)
    )
    return subprocess.run(
        [str(script), *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, **env},
        cwd=tmp_path,
    )


def calls(tmp_path: Path) -> list[str]:
    recorded = tmp_path / "calls"
    return recorded.read_text().splitlines() if recorded.exists() else []


@pytest.fixture
def installed(tmp_path: Path) -> Path:
    """The package's code with compiled bytecode and a venv."""
    code = tmp_path / "opt" / "epiframe"
    for folder in (
        "src/epiframe/__pycache__",
        "lib/inky/__pycache__",
        ".venv/lib/x/__pycache__",
        "bin",
    ):
        (code / folder).mkdir(parents=True)
    (code / "src" / "epiframe" / "cli.py").write_text("")
    for folder in ("etc/epiframe", "var/lib/epiframe/photos", "var/cache/epiframe/uv"):
        (tmp_path / folder).mkdir(parents=True)
    return code


def test_prerm_remove(
    tmp_path: Path, installed: Path, fake_bin: dict[str, str]
) -> None:
    (tmp_path / "run" / "systemd" / "system").mkdir(parents=True)

    result = run_script("prerm", tmp_path, fake_bin, "remove")

    assert result.returncode == 0, result.stderr
    assert calls(tmp_path) == [
        "systemctl stop ePiframe.service",
        "systemctl disable --quiet ePiframe.service",
    ]
    assert not (installed / "src" / "epiframe" / "__pycache__").exists()
    assert not (installed / "lib" / "inky" / "__pycache__").exists()
    assert (installed / ".venv" / "lib" / "x" / "__pycache__").exists()
    assert (installed / "src" / "epiframe" / "cli.py").exists()


def test_prerm_upgrade_without_systemd(
    tmp_path: Path, installed: Path, fake_bin: dict[str, str]
) -> None:
    upgrade = run_script("prerm", tmp_path, fake_bin, "upgrade", "2.0.0")
    remove = run_script("prerm", tmp_path, fake_bin, "remove")

    assert upgrade.returncode == remove.returncode == 0
    assert calls(tmp_path) == ["systemctl disable --quiet ePiframe.service"]
    assert not (installed / "src" / "epiframe" / "__pycache__").exists()


def test_prerm_without_the_code(tmp_path: Path, fake_bin: dict[str, str]) -> None:
    assert run_script("prerm", tmp_path, fake_bin, "upgrade", "2.0.0").returncode == 0


def test_postrm_remove(
    tmp_path: Path, installed: Path, fake_bin: dict[str, str]
) -> None:
    (tmp_path / "run" / "systemd" / "system").mkdir(parents=True)

    result = run_script("postrm", tmp_path, fake_bin, "remove")

    assert result.returncode == 0, result.stderr
    assert calls(tmp_path) == ["systemctl daemon-reload"]
    assert not (installed / ".venv").exists()
    assert not (installed / "bin").exists()
    # dpkg removed the package's files already in reality
    assert (installed / "src").exists()
    assert (tmp_path / "etc" / "epiframe").exists()
    assert (tmp_path / "var" / "lib" / "epiframe" / "photos").exists()


def test_postrm_purge(
    tmp_path: Path, installed: Path, fake_bin: dict[str, str]
) -> None:
    for folder in ("src", "lib"):
        subprocess.run(["rm", "-rf", str(installed / folder)], check=True, timeout=30)

    result = run_script("postrm", tmp_path, fake_bin, "purge")

    assert result.returncode == 0, result.stderr
    assert calls(tmp_path) == []
    assert not (tmp_path / "opt" / "epiframe").exists()
    for folder in ("etc/epiframe", "var/lib/epiframe", "var/cache/epiframe"):
        assert not (tmp_path / folder).exists(), folder


def test_postrm_upgrade_keeps_everything(
    tmp_path: Path, installed: Path, fake_bin: dict[str, str]
) -> None:
    assert run_script("postrm", tmp_path, fake_bin, "upgrade", "2.0.0").returncode == 0
    assert (installed / ".venv").exists()
    assert calls(tmp_path) == []


FAKE_EPIFRAME = """#!/bin/sh
echo "$(pwd)|$EPIFRAME_CONFIG_DIR|$EPIFRAME_DATA_DIR|$EPIFRAME_PLUGINS_DIR"
echo "$EPIFRAME_CALLER_DIR|$*"
"""


def test_command_runs_epiframe_as_the_service_user(tmp_path: Path) -> None:
    executable(
        tmp_path / "opt" / "epiframe" / ".venv" / "bin" / "epiframe", FAKE_EPIFRAME
    )
    (tmp_path / "var" / "lib" / "epiframe").mkdir(parents=True)

    result = run_script("epiframe", tmp_path, {}, "check-config", "--x", user=USER)

    data = f"{tmp_path}/var/lib/epiframe"
    assert result.stdout == (
        f"{data}|{tmp_path}/etc/epiframe|{data}|{data}/plugins\n"
        # file arguments are resolved against the folder the command started in
        f"{tmp_path}|check-config --x\n"
    )


def test_command_switches_to_the_service_user(
    tmp_path: Path, fake_bin: dict[str, str]
) -> None:
    result = run_script("epiframe", tmp_path, fake_bin, "test", user="no-such-user")

    assert result.returncode == 0
    command = "sudo" if os.getuid() else "runuser"
    assert calls(tmp_path) == [f"{command} -u no-such-user -- {tmp_path}/epiframe test"]


# ---------------------------------------------------------------- service unit


def test_unit_matches_the_command_and_postinst() -> None:
    unit = configparser.ConfigParser(strict=False, interpolation=None)
    unit.optionxform = str  # type: ignore[assignment,method-assign]
    text = (PACKAGING / "ePiframe.service").read_text()
    unit.read_string(text)
    service = unit["Service"]
    command = (PACKAGING / "epiframe").read_text()
    postinst = POSTINST.read_text()

    assert service["User"] == "epiframe"
    assert 'SERVICE_USER="epiframe"' in postinst
    assert f'DATA_DIR="{service["WorkingDirectory"]}"' in postinst
    assert f"cd {service['WorkingDirectory']} " in command
    assert service["ExecStart"] == "/opt/epiframe/.venv/bin/epiframe service"
    assert "exec /opt/epiframe/.venv/bin/epiframe " in command
    environment = [
        line.split("=", 1)[1]
        for line in text.splitlines()
        if line.startswith("Environment=")
    ]
    assert len(environment) == 3
    for variable in environment:
        assert f"\nexport {variable}\n" in command
    assert "EPIFRAME_CONFIG_DIR=/etc/epiframe" in environment
    assert 'CONFIG_DIR="/etc/epiframe"' in postinst
