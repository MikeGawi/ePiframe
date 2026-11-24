"""Records the samples: one every :data:`SAMPLE_INTERVAL`, written in batches.

A write is a transaction with an fsync; writing every sample (every 10 seconds)
would write about 38 KiB each time, some 330 MB a day, to the SD card. The
samples of a batch (a minute by default) are written at once: about 8.5 KiB per
sample, 75 MB a day (measured on a desktop SSD, 2026-11-24). The WebUI sees them
up to a minute later and a power cut loses at most that minute.
"""

import time

from epiframe.stats.metrics import SAMPLE_INTERVAL, Sample, Sampler
from epiframe.stats.store import MetricsStore

BATCH = 60 // SAMPLE_INTERVAL


class Recorder:
    def __init__(self, store: MetricsStore, sampler: Sampler, batch: int = BATCH):
        self._store = store
        self._sampler = sampler
        self._batch = batch
        self._pending: list[tuple[float, Sample]] = []

    def record(self, now: float | None = None) -> None:
        """Take a sample (at ``now``); write the batch when it is full."""
        moment = time.time() if now is None else now
        self._pending.append((moment, self._sampler.sample()))
        if len(self._pending) >= self._batch:
            self.flush()

    def flush(self) -> None:
        """Write the pending samples (dropped if that fails, it is logged by the
        caller)."""
        pending, self._pending = self._pending, []
        self._store.add_many(pending)
