"""Tests of scripts/smoke_install.sh: its functions run in bash (the script is sourced).

systemctl, journalctl, systemd-analyze, curl and epiframe are shell functions that
record their calls; the installation is a folder in ``tmp_path`` with the default
configuration.
"""

import getpass
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from epiframe.config import paths

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "scripts" / "smoke_install.sh"

# the service and the tools it checks, driven by files and variables of the test
FAKES = r"""
as_user() ( "$@" )
function systemctl {
	echo "systemctl $*" >> "$CALLS"
	case $1 in
		show)
			case $3 in
				LoadState) echo "${FAKE_LOAD_STATE:-loaded}" ;;
				User) id -un ;;
				WorkingDirectory) echo "$DATA" ;;
				Environment) echo "${FAKE_ENVIRONMENT:-}" ;;
				FragmentPath) echo /lib/systemd/system/ePiframe.service ;;
				Result) echo "${FAKE_RESULT:-success}" ;;
			esac
			;;
		is-active) [[ -f $ACTIVE ]] ;;
		start) touch "$ACTIVE" ;;
		stop) rm -f "$ACTIVE" ;;
	esac
}
function journalctl { echo "journalctl $*" >> "$CALLS"; }
function systemd-analyze { echo "systemd-analyze $*" >> "$CALLS"; }
function curl {
	echo "curl $*" >> "$CALLS"
	(( $(grep -c '^curl' "$CALLS") > ${FAKE_CURL_FAILURES:-0} ))
}
function epiframe {
	echo "epiframe $* in $PWD" >> "$CALLS"
	[[ $1 != --version ]] || echo "ePiframe v2.0.0-test"
}
"""

Bash = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture
def data(tmp_path: Path) -> Path:
    """The frame folder of install.sh: config.cfg (default, mode 0600), a convert."""
    folder = tmp_path / "frame"
    folder.mkdir()
    convert = tmp_path / "convert"
    # writes its last argument, as ImageMagick does
    convert.write_text('#!/bin/sh\nfor last; do :; done\necho "$*" > "$last"\n')
    convert.chmod(0o755)
    config = folder / "config.cfg"
    text = Path(paths.CONFIG_FILE_DEFAULT).read_text()
    config.write_text(
        text.replace("convert_bin_path=/usr/bin/convert", f"convert_bin_path={convert}")
    )
    config.chmod(0o600)
    return folder


@pytest.fixture
def calls(tmp_path: Path) -> Path:
    return tmp_path / "calls"


@pytest.fixture
def bash(tmp_path: Path, data: Path, calls: Path) -> Bash:
    def run(
        script: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            # $0 must not be the script, otherwise the sourced script runs main
            ["bash", "-c", f'source "$1"\n{FAKES}\n{script}', "bash", str(SMOKE)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            cwd=tmp_path,
            env={
                **os.environ,
                "CALLS": str(calls),
                "DATA": str(data),
                "ACTIVE": str(tmp_path / "active"),
                **(env or {}),
            },
        )

    return run


def recorded(calls: Path) -> list[str]:
    return calls.read_text().splitlines() if calls.exists() else []


def config_value(config: Path, name: str) -> str:
    return next(
        line.split("=", 1)[1]
        for line in config.read_text().splitlines()
        if line.startswith(f"{name}=")
    )


# --------------------------------------------------------------------- arguments


def test_arguments(bash: Bash) -> None:
    port = bash('parse_smoke_arguments --port 9000; echo "$PORT"')
    default = bash('parse_smoke_arguments; echo "$PORT"')
    help_text = bash("parse_smoke_arguments --help; echo not here")

    assert port.stdout == "9000\n"
    assert default.stdout == "8080\n"
    assert help_text.returncode == 0
    assert "--port PORT" in help_text.stdout
    assert "not here" not in help_text.stdout


@pytest.mark.parametrize(
    ("arguments", "error"),
    [
        ("--port", "--port needs a number"),
        ("--port 80x", "--port needs a number"),
        ("--other", "Unknown option --other"),
    ],
)
def test_wrong_arguments(bash: Bash, arguments: str, error: str) -> None:
    result = bash(f"parse_smoke_arguments {arguments}")

    assert result.returncode == 1
    assert error in result.stderr


# ------------------------------------------------------------------ installation


def test_installation_of_install_sh(bash: Bash, data: Path) -> None:
    result = bash('find_installation; echo "$EPI_USER|$DATA_DIR|$CONFIG"')

    assert result.returncode == 0, result.stderr
    user, folder, config = result.stdout.strip().split("|")
    assert user == getpass.getuser()
    assert folder == str(data)
    assert config == str(data / "config.cfg")


def test_installation_of_the_deb_package(
    bash: Bash, data: Path, tmp_path: Path
) -> None:
    etc = tmp_path / "etc"
    etc.mkdir()
    shutil.move(data / "config.cfg", etc / "config.cfg")
    environment = (
        f"EPIFRAME_CONFIG_DIR={etc} EPIFRAME_DATA_DIR={data} "
        f"EPIFRAME_PLUGINS_DIR={data}/plugins"
    )

    result = bash(
        'find_installation; echo "$CONFIG"; unit_environment EPIFRAME_PLUGINS_DIR',
        env={"FAKE_ENVIRONMENT": environment},
    )

    assert result.stdout.splitlines() == [str(etc / "config.cfg"), f"{data}/plugins"]


def test_no_installation(bash: Bash, data: Path) -> None:
    missing = bash("find_installation", env={"FAKE_LOAD_STATE": "not-found"})
    (data / "config.cfg").unlink()
    no_config = bash("find_installation")
    no_folder = bash("find_installation", env={"DATA": str(data / "missing")})

    assert "ePiframe.service is not installed" in missing.stderr
    assert f"There is no {data}/config.cfg" in no_config.stderr
    assert "has no User or WorkingDirectory" in no_folder.stderr
    assert {missing.returncode, no_config.returncode, no_folder.returncode} == {1}


def test_config_values_and_paths(bash: Bash, data: Path) -> None:
    result = bash(
        "find_installation; config_value local_path; config_value missing; "
        "frame_path logs/a.log; frame_path /var/photos"
    )

    assert result.stdout.splitlines() == ["photos", f"{data}/logs/a.log", "/var/photos"]


def test_set_entries(bash: Bash, data: Path) -> None:
    config = data / "config.cfg"

    result = bash("find_installation; set_entries use_web=1 'start_times=-,-'")
    before = config.read_text()
    missing = bash("find_installation; set_entries use_web=0 no_such_entry=1")

    assert result.returncode == 0, result.stderr
    assert config_value(config, "use_web") == "1"
    assert config_value(config, "start_times") == "-,-"
    assert config.stat().st_mode & 0o777 == 0o600
    assert missing.returncode == 1
    assert config.read_text() == before


# ------------------------------------------------------------------------- state


def test_state_of_an_active_service(bash: Bash, data: Path, tmp_path: Path) -> None:
    (tmp_path / "active").touch()
    config = data / "config.cfg"
    original = config.read_text()
    photo = data / "photos" / "smoke.png"

    result = bash(
        f"""find_installation; save_state || exit 1
        [[ -f $ACTIVE ]] && echo still active
        stat -c %a "$WORK" "$WORK/config.cfg"
        set_entries use_web=1; mkdir -p {data}/photos; touch {photo}
        PHOTO_FILE={photo}; work=$WORK
        restore_state; [[ -e $work ]] && echo work kept; restore_state"""
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["755", "600"]
    assert config.read_text() == original
    assert config.stat().st_mode & 0o777 == 0o600
    assert not photo.exists()
    assert (tmp_path / "active").exists()


def test_state_of_a_stopped_service(bash: Bash, tmp_path: Path, calls: Path) -> None:
    result = bash("find_installation; save_state; restore_state")

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "active").exists()
    assert not any("systemctl start" in call for call in recorded(calls))


def test_finish_shows_the_journal_after_a_failure(bash: Bash, calls: Path) -> None:
    failed = bash("find_installation; save_state; trap finish EXIT; exit 3")
    journal = [call for call in recorded(calls) if call.startswith("journalctl")]
    passed = bash("find_installation; save_state; trap finish EXIT; true")

    assert failed.returncode == 3
    assert journal == ["journalctl -u ePiframe.service -n 40 --no-pager"]
    assert passed.returncode == 0
    assert len([c for c in recorded(calls) if c.startswith("journalctl")]) == 1


# ------------------------------------------------------------------------ checks


def test_check_unit(bash: Bash, calls: Path) -> None:
    result = bash("check_unit")

    assert result.returncode == 0
    assert (
        "systemd-analyze verify --man=no /lib/systemd/system/ePiframe.service"
        in recorded(calls)
    )


def test_photo_and_caller_file(bash: Bash, data: Path, calls: Path) -> None:
    result = bash(
        'find_installation; save_state; add_photo; convert_caller_file; echo "$WORK"'
    )

    assert result.returncode == 0, result.stderr
    work = result.stdout.strip()
    photo = data / "photos" / "epiframe-smoke.png"
    assert photo.read_text().startswith("-size 320x240 xc:red ")
    assert Path(work, "epiframe-smoke.png").read_text() == photo.read_text()
    assert f"epiframe test-convert epiframe-smoke.png in {work}" in recorded(calls)


def test_configure_service(bash: Bash, data: Path) -> None:
    result = bash("find_installation; PORT=8123; configure_service")

    config = data / "config.cfg"
    assert result.returncode == 0, result.stderr
    assert {
        name: config_value(config, name)
        for name in (
            "use_web",
            "web_host",
            "web_port",
            "start_times",
            "stop_times",
            "control_display_power",
        )
    } == {
        "use_web": "1",
        "web_host": "127.0.0.1",
        "web_port": "8123",
        "start_times": "-,-,-,-,-,-,-",
        "stop_times": "-,-,-,-,-,-,-",
        "control_display_power": "0",
    }


def test_wait_for_webui(bash: Bash, tmp_path: Path, calls: Path) -> None:
    (tmp_path / "active").touch()

    answered = bash("wait_for_webui", env={"FAKE_CURL_FAILURES": "2"})
    tries = [call for call in recorded(calls) if call.startswith("curl")]
    timeout = bash("WAIT=0; wait_for_webui", env={"FAKE_CURL_FAILURES": "99"})
    (tmp_path / "active").unlink()
    stopped = bash("wait_for_webui", env={"FAKE_CURL_FAILURES": "99"})

    assert answered.returncode == 0
    assert tries == ["curl -fsS -o /dev/null http://127.0.0.1:8080/"] * 3
    assert timeout.returncode == 1
    assert stopped.returncode == 1


def test_check_service_log(bash: Bash, data: Path) -> None:
    missing = bash("find_installation; check_service_log")
    (data / "logs").mkdir()
    (data / "logs" / "ePiframe.log").write_text("ePiframe Service: STARTED\n")
    found = bash("find_installation; check_service_log")
    bash("find_installation; set_entries log_files=")
    no_log = bash("find_installation; check_service_log")

    assert missing.returncode != 0
    assert found.returncode == 0
    assert no_log.returncode == 0


def test_stop_cleanly(bash: Bash) -> None:
    assert bash("stop_cleanly").returncode == 0
    assert bash("stop_cleanly", env={"FAKE_RESULT": "exit-code"}).returncode == 1


# ------------------------------------------------------------------------- main


def test_main_needs_root(bash: Bash) -> None:
    result = bash("function is_root { false; }; smoke_main")

    assert result.returncode == 1
    assert "Run the smoke test as root" in result.stderr


def test_main(bash: Bash, data: Path, tmp_path: Path, calls: Path) -> None:
    (data / "logs").mkdir()
    (data / "logs" / "ePiframe.log").write_text("ePiframe Service: STARTED\n")
    (tmp_path / "active").touch()
    original = (data / "config.cfg").read_text()

    result = bash("function is_root { :; }; smoke_main --port 8123")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Smoke test of ePiframe v2.0.0-test in" in result.stdout
    assert "The smoke test passed" in result.stdout
    assert "error!" not in result.stdout
    service = [
        call.removeprefix("systemctl ")
        for call in recorded(calls)
        if call.startswith("systemctl") and " show " not in f" {call} "
    ]
    assert service == [
        "is-active --quiet ePiframe.service",  # save_state: running
        "stop ePiframe.service",
        "start ePiframe.service",  # the WebUI answered at once
        "stop ePiframe.service",  # stop_cleanly
        "stop ePiframe.service",  # restore_state
        "start ePiframe.service",  # it was running
    ]
    commands = [
        call.split(" in ")[0] for call in recorded(calls) if call.startswith("epiframe")
    ]
    assert commands == [
        "epiframe --version",
        "epiframe --version",
        "epiframe check-config",
        "epiframe test --no-skip",
        "epiframe test-convert epiframe-smoke.png",
    ]
    assert "curl -fsS -o /dev/null http://127.0.0.1:8123/" in recorded(calls)
    assert (data / "config.cfg").read_text() == original
    assert not (data / "photos" / "epiframe-smoke.png").exists()
    assert (tmp_path / "active").exists()


def test_main_failure(bash: Bash, data: Path, calls: Path) -> None:
    original = (data / "config.cfg").read_text()

    # no service log: the check fails after the configuration was changed
    result = bash("function is_root { :; }; smoke_main")

    assert result.returncode == 1
    assert "Checking the service log failed" in result.stderr
    assert any(call.startswith("journalctl") for call in recorded(calls))
    assert (data / "config.cfg").read_text() == original
