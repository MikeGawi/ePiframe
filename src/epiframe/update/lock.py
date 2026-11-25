"""PID file of a running update (``pid_file`` setting).

While the file exists the WebUI and the Telegram bot show "Busy". A new update
stops a previous one that still runs (hangs, e.g. on a stuck display driver).
"""

import os
import signal
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from epiframe.core.logs import get_logger
from epiframe.core.pidfile import PROC_DIR, PidFile, process_command

# how an update is started: ePiframe.py, the epiframe console script, python -m epiframe
UPDATE_NAMES = frozenset({"ePiframe.py", "epiframe"})
SERVICE_WORD = "service"  # epiframe service: never stopped

log = get_logger("update")


def is_update(command: str) -> bool:
    """Whether the command line ``command`` runs an ePiframe update."""
    words = command.split()
    names = {os.path.basename(word) for word in words}
    return not names.isdisjoint(UPDATE_NAMES) and SERVICE_WORD not in words


def stop_previous(pid: int, proc_dir: Path = PROC_DIR) -> None:
    """Kill process ``pid`` if it is another ePiframe update (the PID of a
    finished one may belong to another program by now)."""
    command = process_command(pid, proc_dir)
    if pid == os.getpid() or command is None or not is_update(command):
        return
    log.warning(f"Warning! Stopping previous ePiframe run (PID {pid})")
    with suppress(OSError):
        os.kill(pid, signal.SIGKILL)


@contextmanager
def update_lock(
    path: str | os.PathLike[str], proc_dir: Path = PROC_DIR
) -> Iterator[None]:
    """Hold the PID file at ``path`` while the block runs."""
    pid_file = PidFile(path)
    previous = pid_file.read()
    if previous is not None:
        stop_previous(previous, proc_dir)
    pid_file.write()
    try:
        yield
    finally:
        # a newer update that stopped this one owns the file now
        if pid_file.read() == pid_file.pid:
            pid_file.remove()
