import errno
import socket
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from epiframe.config import paths
from epiframe.config.manager import ConfigManager
from epiframe.web.console import (
    WebTest,
    bind,
    bind_problem,
    network_address,
    url,
)
from tests.helpers.console import Answer, Console


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigManager:
    monkeypatch.chdir(tmp_path)
    return ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)


@dataclass
class Server:
    """``serve`` and ``bind`` recording the calls; ``bind`` raises ``error``."""

    error: OSError | None = None
    served: list[tuple[str, int]] = field(default_factory=list)
    bound: list[tuple[str, int]] = field(default_factory=list)

    def serve(self, host: str, port: int) -> None:
        self.served.append((host, port))

    def bind(self, host: str, port: int) -> None:
        self.bound.append((host, port))
        if self.error:
            raise self.error


def run(
    config: ConfigManager,
    server: Server,
    *answers: Answer,
    login_needed: bool = True,
    address: str | None = "192.168.1.20",
) -> tuple[int, Console]:
    console = Console(*answers)
    test = WebTest(
        config,
        server.serve,
        ask=console.ask,
        say=console.say,
        try_bind=server.bind,
        address=lambda: address,
    )
    return test.run(login_needed), console


def saved(tmp_path: Path) -> ConfigManager:
    return ConfigManager(tmp_path / "config.cfg", paths.CONFIG_FILE_DEFAULT)


def test_new_values_are_saved_and_served(config: ConfigManager, tmp_path: Path) -> None:
    server = Server()

    code, console = run(config, server, "127.0.0.1", "8080", "")

    assert code == 0
    assert console.prompts == [
        "WebUI address [0.0.0.0]: ",
        "WebUI port [80]: ",
        "Save them and enable the WebUI? [Y/n] ",
    ]
    assert server.bound == server.served == [("127.0.0.1", 8080)]
    stored = saved(tmp_path)
    assert (stored.get("use_web"), stored.get("web_host"), stored.get("web_port")) == (
        "1",
        "127.0.0.1",
        "8080",
    )
    assert "Open http://127.0.0.1:8080/" in console.lines
    assert console.lines[-1] == "\nWebUI stopped."


def test_configured_values_are_kept(config: ConfigManager, tmp_path: Path) -> None:
    config.set("use_web", "1")
    config.set("web_port", "8080")
    config.save()
    server = Server()

    code, console = run(config, server, "", "")

    assert code == 0
    assert len(console.prompts) == 2  # nothing to save
    assert server.served == [("0.0.0.0", 8080)]  # noqa: S104
    # all addresses: this machine and its network address
    assert "Open http://127.0.0.1:8080/ or http://192.168.1.20:8080/" in console.lines


def test_not_saved(config: ConfigManager, tmp_path: Path) -> None:
    server = Server()

    code, console = run(config, server, "::", "8080", "n")

    assert code == 0
    assert saved(tmp_path).get("web_port") == "80"
    assert server.served == [("::", 8080)]
    assert "Open http://127.0.0.1:8080/ or http://192.168.1.20:8080/" in console.lines
    assert "Saved" not in console.output


def test_without_network_address(config: ConfigManager) -> None:
    code, console = run(config, Server(), "", "8080", "n", address=None)

    assert code == 0
    assert "Open http://127.0.0.1:8080/" in console.lines


def test_wrong_values_are_asked_again(config: ConfigManager) -> None:
    server = Server()

    code, console = run(
        config, server, "frame.local", "::1", "http", "0", "70000", "8080", "n"
    )

    assert code == 0
    assert "Not a valid IP address! (0.0.0.0: all addresses," in console.output
    assert console.output.count("Please enter a number in the 1-65535 range") == 3
    assert server.served == [("::1", 8080)]


def test_port_that_can_not_be_used(config: ConfigManager, tmp_path: Path) -> None:
    server = Server(PermissionError(errno.EACCES, "Permission denied"))

    code, console = run(config, server, "", "")

    assert code == 1
    assert "Error: Port 80 needs root privileges" in console.output
    assert server.served == []
    assert saved(tmp_path).get("use_web") == "0"


def test_warning_without_users(config: ConfigManager) -> None:
    code, console = run(config, Server(), "", "8080", "n", login_needed=False)

    assert code == 0
    assert "No WebUI users: everybody who can open it controls the frame" in (
        console.lines
    )


@pytest.mark.parametrize("stop", [KeyboardInterrupt(), EOFError()])
def test_stopped_in_the_dialogue(config: ConfigManager, stop: BaseException) -> None:
    server = Server()

    code, console = run(config, server, "", stop)

    assert code == 1
    assert console.lines[-1] == "\nTest stopped, nothing saved."
    assert server.served == []


@pytest.mark.parametrize(
    ("error", "port", "message"),
    [
        (PermissionError(errno.EACCES, "denied"), 80, "Port 80 needs root privileges"),
        (PermissionError(errno.EACCES, "denied"), 8080, "denied"),
        (OSError(errno.EADDRINUSE, "in use"), 8080, "Port 8080 is already in use"),
        (OSError(errno.EADDRNOTAVAIL, "x"), 8080, "This machine has no such address"),
        (OSError(errno.EIO, "other"), 8080, "other"),
    ],
)
def test_bind_problem(error: OSError, port: int, message: str) -> None:
    assert message in bind_problem(error, port)


def test_url() -> None:
    assert url("10.0.0.2", 80) == "http://10.0.0.2:80/"
    assert url("::1", 8080) == "http://[::1]:8080/"


def test_bind_free_and_taken_port() -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        with pytest.raises(OSError, match="in use") as raised:
            bind("127.0.0.1", port)
    assert raised.value.errno == errno.EADDRINUSE
    bind("::1", 0)
    bind("127.0.0.1", 0)


def test_network_address(monkeypatch: pytest.MonkeyPatch) -> None:
    found = network_address()
    assert found is None or found.count(".") == 3

    def no_network(*arguments: object) -> None:
        raise OSError(errno.ENETUNREACH, "Network is unreachable")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    assert network_address() is None
