import socket
import subprocess
import sys
import time

import requests

from tests.smoke.conftest import REPOSITORY, Frame

# the service's web thread without the daemon (ePiframe_service.py kills other
# service processes on the machine, so it is not started here)
WEB_SERVER = """
import sys
sys.path.insert(0, sys.argv[1])
from epiframe.config import paths
from epiframe.service.frame import Frame
from modules.webuimanager import WebUIManager
WebUIManager(Frame(lambda trigger: None, paths.CONFIG_FILE, sys.argv[1])).start()
"""


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_for(url: str, timeout: float = 30) -> requests.Response:
    deadline = time.monotonic() + timeout
    while True:
        try:
            return requests.get(url, timeout=5)
        except requests.ConnectionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


def test_webui_starts_and_serves_pages(frame: Frame) -> None:
    port = free_port()
    frame.configure(use_web="1", web_host="127.0.0.1", web_port=str(port))
    server = subprocess.Popen(
        [sys.executable, "-c", WEB_SERVER, str(REPOSITORY)],
        cwd=frame.directory,
        env=frame.environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        home = wait_for(f"http://127.0.0.1:{port}/")
        status = requests.get(f"http://127.0.0.1:{port}/api/get_status", timeout=5)
        settings = requests.get(f"http://127.0.0.1:{port}/settings", timeout=5)
    finally:
        server.terminate()
        output, _ = server.communicate(timeout=30)

    assert home.status_code == 200, output
    assert "ePiframe" in home.text
    assert status.status_code == 200
    assert {"state", "update", "uptime"} <= status.json().keys()
    assert status.json()["state"] == "Idle"
    assert settings.status_code == 200
    assert "Use Local" in settings.text  # first section: Sources
