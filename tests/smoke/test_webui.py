import signal
import socket
import subprocess
import sys
import time

import requests

from epiframe.stats.metrics import Sampler
from epiframe.stats.store import MetricsStore
from tests.smoke.conftest import REPOSITORY, Frame

# only the WebUI of the service (the whole service: test_service.py)
WEB_SERVER = """
import sys
sys.path.insert(0, sys.argv[1])
from epiframe.config import paths
from epiframe.service.frame import Frame
from epiframe.web.app import WebUI
WebUI(Frame(lambda trigger: None, paths.CONFIG_FILE, sys.argv[1])).start()
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
    # a sample as the service's stats thread takes it (default stats_db_file)
    MetricsStore(frame.directory / "stats.db").add(Sampler(frame.directory).sample())
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
        stats = requests.get(f"http://127.0.0.1:{port}/api/get_stats", timeout=5)
        stats_page = requests.get(f"http://127.0.0.1:{port}/stats", timeout=5)
        spec = requests.get(f"http://127.0.0.1:{port}/api/openapi.json", timeout=5)
        missing = requests.get(f"http://127.0.0.1:{port}/api/action=", timeout=5)
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
    assert stats.status_code == 200
    assert len(stats.json()["time"]) == 1
    assert stats_page.status_code == 200
    assert "Temperature" in stats_page.text
    assert spec.status_code == 200
    assert "/api/get_status" in spec.json()["paths"]
    assert missing.status_code == 404
    assert missing.json() == {"error": "Not Found"}
    # the session key of this installation, in the data directory
    assert len((frame.directory / "secret.key").read_text().strip()) == 64


def test_test_web_serves_until_ctrl_c(frame: Frame) -> None:
    port = free_port()
    frame.configure()  # the default configuration
    answers = frame.directory / "answers.txt"
    answers.write_text(f"127.0.0.1\n{port}\ny\n")
    with answers.open() as stdin:
        tool = subprocess.Popen(
            [sys.executable, str(REPOSITORY / "ePiframe.py"), "--test-web"],
            cwd=frame.directory,
            env=frame.environment(),
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    try:
        home = wait_for(f"http://127.0.0.1:{port}/")
        spec = requests.get(f"http://127.0.0.1:{port}/api/openapi.json", timeout=5)
    finally:
        tool.send_signal(signal.SIGINT)  # Ctrl+C
        output, _ = tool.communicate(timeout=30)

    assert tool.returncode == 0, output
    assert home.status_code == 200
    assert "/api/get_status" in spec.json()["paths"]
    assert f"Open http://127.0.0.1:{port}/" in output
    assert "WebUI stopped." in output
    assert f"web_port={port}" in frame.config_file.read_text()  # saved


def test_test_web_port_in_use(frame: Frame) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        result = frame.run("--test-web", answers=f"127.0.0.1\n{port}\n")

    assert result.returncode == 1
    assert f"Port {port} is already in use" in result.stdout
