"""Local photo source: a folder (optionally with subfolders) on the frame.

Scanning hundreds of thousands of files on a Raspberry Pi Zero is slow, mostly
because of one ``stat`` call per file. The scan is therefore incremental: a
folder's modification time changes when files are added to it, removed from it
or renamed in it, so only the folders whose time changed are read file by file;
the others are just listed to find their subfolders. Folder times are kept in
the photo index (``source_state``).

A full scan (every file) is done on the first run, when the scan settings
change, and once every ``FULL_SCAN_INTERVAL`` as a safety net: it catches photos
edited in place and file systems that don't update folder times.

The id of a local photo is its path (as configured, e.g. ``photos/a.jpg``) and
its time is the file modification time.
"""

import os
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta

from epiframe.photos.index import PhotoIndex
from epiframe.photos.model import Photo

LOCAL_SOURCE = "Local"
FULL_SCAN_INTERVAL = timedelta(days=1)

# source_state keys: one per folder, plus the scan settings and the last full scan
FOLDER_KEY = "folder:"
SETTINGS_KEY = "scan:settings"
FULL_SCAN_KEY = "scan:full"


def create_directory(directory: str) -> str:
    """Config conversion of ``local_path``: create the folder if it is missing."""
    os.makedirs(directory, exist_ok=True)
    return directory


@dataclass(frozen=True)
class Folder:
    """A scanned folder: its modification time and its photo files."""

    path: str
    mtime_ns: int
    files: list[os.DirEntry[str]]


@dataclass(frozen=True)
class ScanResult:
    folders: int  # folders found
    scanned: int  # folders read file by file
    photos: int  # photos of the source after the scan
    full: bool


class LocalSource:
    """Photos with one of ``extensions`` in ``directory`` (and its subfolders)."""

    def __init__(
        self,
        directory: str,
        recursive: bool,
        extensions: Collection[str],
        full_scan_interval: timedelta = FULL_SCAN_INTERVAL,
    ) -> None:
        self.directory = os.path.normpath(directory)
        self.recursive = recursive
        self.extensions = frozenset(extension.lower() for extension in extensions)
        self.full_scan_interval = full_scan_interval

    @property
    def settings(self) -> str:
        """Scan settings; a change forces a full scan."""
        extensions = ",".join(sorted(self.extensions))
        return f"{self.directory}|{int(self.recursive)}|{extensions}"

    # -------------------------------------------------------------- file system

    def _is_photo(self, entry: os.DirEntry[str]) -> bool:
        extension = entry.name.rpartition(".")[2].lower()
        return extension in self.extensions and entry.is_file()

    def folders(self) -> Iterator[Folder]:
        """Folders in pre-order (sorted by name); hidden entries are skipped.

        Unreadable folders are skipped; symbolic links to folders are followed
        once (no loops).
        """
        pending = [self.directory]
        visited: set[tuple[int, int]] = set()
        while pending:
            path = pending.pop()
            folder = self._read_folder(path, visited)
            if folder is None:
                continue
            entries, mtime_ns = folder
            subfolders, files = self._split(entries)
            pending.extend(reversed(subfolders))
            yield Folder(path, mtime_ns, files)

    def _split(
        self, entries: list[os.DirEntry[str]]
    ) -> tuple[list[str], list[os.DirEntry[str]]]:
        """Subfolder paths (when recursive) and photo files of a folder."""
        visible = [entry for entry in entries if not entry.name.startswith(".")]
        folders = filter(os.DirEntry.is_dir, visible) if self.recursive else ()
        return [entry.path for entry in folders], list(filter(self._is_photo, visible))

    @staticmethod
    def _read_folder(
        path: str, visited: set[tuple[int, int]]
    ) -> tuple[list[os.DirEntry[str]], int] | None:
        try:
            status = os.stat(path)
            if (status.st_dev, status.st_ino) in visited:
                return None
            visited.add((status.st_dev, status.st_ino))
            with os.scandir(path) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError:
            return None
        return entries, status.st_mtime_ns

    @staticmethod
    def _photos(folder: Folder) -> Iterator[Photo]:
        for entry in folder.files:
            try:
                mtime = entry.stat().st_mtime
            except OSError:  # removed during the scan
                continue
            yield Photo(entry.path, LOCAL_SOURCE, datetime.fromtimestamp(mtime))

    def photos(self) -> Iterator[Photo]:
        """All photos (a full scan)."""
        for folder in self.folders():
            yield from self._photos(folder)

    # -------------------------------------------------------------------- index

    def sync(self, index: PhotoIndex, now: datetime | None = None) -> ScanResult:
        """Bring the photos of this source in ``index`` up to date."""
        now = now or datetime.now()
        state = index.source_state(LOCAL_SOURCE)
        known = {
            key.removeprefix(FOLDER_KEY): value
            for key, value in state.items()
            if key.startswith(FOLDER_KEY)
        }
        full = self._needs_full_scan(state, now)
        with index.batch():
            if full:
                folders = self._full_scan(index, known, now)
                scanned = folders
            else:
                folders, scanned = self._incremental_scan(index, known)
        return ScanResult(folders, scanned, index.count_source(LOCAL_SOURCE), full)

    def _needs_full_scan(self, state: dict[str, str], now: datetime) -> bool:
        last = state.get(FULL_SCAN_KEY)
        return (
            state.get(SETTINGS_KEY) != self.settings
            or last is None
            or now - datetime.fromisoformat(last) >= self.full_scan_interval
        )

    def _full_scan(
        self, index: PhotoIndex, known: dict[str, str], now: datetime
    ) -> int:
        times: dict[str, str] = {}

        def photos() -> Iterator[Photo]:
            for folder in self.folders():
                times[FOLDER_KEY + folder.path] = str(folder.mtime_ns)
                yield from self._photos(folder)

        index.replace_source(LOCAL_SOURCE, photos())
        index.remove_source_state(LOCAL_SOURCE, (FOLDER_KEY + path for path in known))
        index.set_source_state(
            LOCAL_SOURCE,
            times | {SETTINGS_KEY: self.settings, FULL_SCAN_KEY: now.isoformat()},
        )
        return len(times)

    def _incremental_scan(
        self, index: PhotoIndex, known: dict[str, str]
    ) -> tuple[int, int]:
        found: set[str] = set()
        scanned = 0
        for folder in self.folders():
            found.add(folder.path)
            if known.get(folder.path) != str(folder.mtime_ns):
                self._sync_folder(index, folder)
                scanned += 1
        gone = known.keys() - found
        for path in gone:
            index.remove_photos(LOCAL_SOURCE, index.child_ids(LOCAL_SOURCE, path + "/"))
        index.remove_source_state(LOCAL_SOURCE, (FOLDER_KEY + path for path in gone))
        return len(found), scanned

    def _sync_folder(self, index: PhotoIndex, folder: Folder) -> None:
        photos = list(self._photos(folder))
        index.add_photos(photos)
        removed = index.child_ids(LOCAL_SOURCE, folder.path + "/") - {
            photo.id for photo in photos
        }
        index.remove_photos(LOCAL_SOURCE, removed)
        index.set_source_state(
            LOCAL_SOURCE, {FOLDER_KEY + folder.path: str(folder.mtime_ns)}
        )
