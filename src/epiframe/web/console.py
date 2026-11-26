"""WebUI test (``ePiframe.py --test-web``).

Checks the WebUI address and port (valid, free, allowed for this user), offers
to save them and then serves the real WebUI of the frame until Ctrl+C, so the
pages and the REST API can be tried before the service runs it. Successor of
the 1.x ``tools/testWebUI.py`` (which only answered "Hello").
"""

import errno
import socket
from collections.abc import Callable

from epiframe.config.base import ConfigBase
from epiframe.core.console import Ask, Say, ask_yes
from epiframe.core.network import validate_ip

Serve = Callable[[str, int], None]  # host, port: serve until Ctrl+C
Bind = Callable[[str, int], None]  # raises OSError if the port can't be used
Probe = Callable[[], str | None]  # the address of this machine in the network

ANY_ADDRESSES = ("0.0.0.0", "::")  # noqa: S104 (all interfaces, on purpose)
PRIVILEGED_BELOW = 1024  # Linux: ip_unprivileged_port_start
SERVICE_HINT = "stop the ePiframe service first: sudo systemctl stop ePiframe.service"


def bind(host: str, port: int) -> None:
    """Try to listen on ``host``:``port`` (as the WebUI server does)."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))


def network_address() -> str | None:
    """The IPv4 address of the default route (nothing is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))  # TEST-NET-1, never routed anywhere
            return str(probe.getsockname()[0])
    except OSError:
        return None


def bind_problem(error: OSError, port: int) -> str:
    """What to tell the user about a failed ``bind``."""
    if isinstance(error, PermissionError) and port < PRIVILEGED_BELOW:
        return (
            f"Port {port} needs root privileges (ports below {PRIVILEGED_BELOW}):"
            " use e.g. 8080 or run ePiframe as root"
        )
    if error.errno == errno.EADDRINUSE:
        return (
            f"Port {port} is already in use (by the ePiframe service? {SERVICE_HINT})"
        )
    if error.errno == errno.EADDRNOTAVAIL:
        return "This machine has no such address (use 0.0.0.0 for all addresses)"
    return str(error)


def url(host: str, port: int) -> str:
    return f"http://[{host}]:{port}/" if ":" in host else f"http://{host}:{port}/"


class WebTest:
    """The test dialogue; ``ask``/``say`` are ``input``/``print`` by default."""

    def __init__(  # noqa: PLR0913 (injected for tests)
        self,
        config: ConfigBase,
        serve: Serve,
        *,
        ask: Ask = input,
        say: Say = print,
        try_bind: Bind = bind,
        address: Probe = network_address,
    ) -> None:
        self.config = config
        self.serve = serve
        self.ask = ask
        self.say = say
        self.try_bind = try_bind
        self.address = address

    def run(self, login_needed: bool) -> int:
        """Run the test; return the exit code (0 = served until stopped)."""
        try:
            self.say("ePiframe - WebUI test (Ctrl+C to stop)")
            host, port = self._host(), self._port()
            if not self._check(host, port):
                return 1
            self._offer_save(host, port)
        except (EOFError, KeyboardInterrupt):
            self.say("\nTest stopped, nothing saved.")
            return 1
        self._serve(host, port, login_needed)
        return 0

    def _host(self) -> str:
        current = self.config.get("web_host")
        while True:
            host = self.ask(f"WebUI address [{current}]: ").strip() or current
            try:
                validate_ip(host)
                return host
            except ValueError as error:
                self.say(f"{error} (0.0.0.0: all addresses, 127.0.0.1: this machine)")

    def _port(self) -> int:
        current = self.config.get("web_port")
        while True:
            text = self.ask(f"WebUI port [{current}]: ").strip() or current
            if text.isdigit() and 1 <= int(text) <= 65535:
                return int(text)
            self.say("Please enter a number in the 1-65535 range")

    def _check(self, host: str, port: int) -> bool:
        try:
            self.try_bind(host, port)
        except OSError as error:
            self.say(f"Error: {bind_problem(error, port)}")
            return False
        self.say(f"OK! {host} port {port} can be used.")
        return True

    def _offer_save(self, host: str, port: int) -> None:
        changed = (self.config.get("web_host"), self.config.get("web_port")) != (
            host,
            str(port),
        )
        if not changed and self.config.getint("use_web"):
            return
        if ask_yes(self.ask, "Save them and enable the WebUI?", True):
            self.config.set("use_web", "1")
            self.config.set("web_host", host)
            self.config.set("web_port", str(port))
            self.config.save()
            self.say(f"Saved to {self.config.path} (restart the service to use it).")

    def _urls(self, host: str, port: int) -> list[str]:
        if host not in ANY_ADDRESSES:
            return [url(host, port)]
        found = self.address()
        return [url("127.0.0.1", port)] + ([url(found, port)] if found else [])

    def _serve(self, host: str, port: int, login_needed: bool) -> None:
        if not login_needed:
            self.say("No WebUI users: everybody who can open it controls the frame")
            self.say("(add users with --users).")
        self.say("Open " + " or ".join(self._urls(host, port)))
        self.say("The API description: /api/openapi.json. Ctrl+C stops the WebUI.")
        self.serve(host, port)
        self.say("\nWebUI stopped.")
