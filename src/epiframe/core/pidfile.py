"""PID file of a running ePiframe process (``pid_file`` setting).

The file exists while a frame update runs: the WebUI and the Telegram bot show
"Busy" and a new update can find (and stop) a previous one that hangs.
"""

import os
from pathlib import Path

PROC_DIR = Path("/proc")


class PidFile:
    """PID file at ``path`` for the current process."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.pid = os.getpid()

    def read(self) -> int | None:
        """Return the PID stored in the file, ``None`` if there is no valid one.

        A corrupted file is removed.
        """
        try:
            text = self.path.read_text()
        except OSError:
            return None
        try:
            return int(text.strip())
        except ValueError:
            self.remove()
            return None

    def write(self) -> None:
        """Store the PID of the current process."""
        self.path.write_text(str(self.pid))

    def remove(self) -> None:
        self.path.unlink(missing_ok=True)


def process_command(pid: int, proc_dir: Path = PROC_DIR) -> str | None:
    """Return the command line of process ``pid`` (``None`` if it is not running).

    Arguments are separated by spaces (like ``ps -o cmd=``, which 1.x used).
    """
    try:
        raw = (proc_dir / str(pid) / "cmdline").read_bytes()
    except OSError:
        return None
    return raw.rstrip(b"\0").replace(b"\0", b" ").decode(errors="replace")
