from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from .stream_schema import StreamDescriptor


@dataclass(frozen=True)
class DataWindow:
    descriptor: StreamDescriptor
    timestamps: tuple[float, ...]
    samples: tuple[tuple[float, ...], ...]
    total_samples_received: int
    last_received_monotonic: float | None

    @property
    def observed_srate(self) -> float | None:
        if len(self.timestamps) < 2 or self.timestamps[-1] <= self.timestamps[0]:
            return None
        return (len(self.timestamps) - 1) / (self.timestamps[-1] - self.timestamps[0])

    @property
    def is_live(self) -> bool:
        return self.last_received_monotonic is not None and time.monotonic() - self.last_received_monotonic < 2.5


class StreamBuffer:
    def __init__(self, descriptor: StreamDescriptor, buffer_seconds: float = 60.0) -> None:
        rate = descriptor.nominal_srate if descriptor.nominal_srate > 0 else 100.0
        capacity = min(max(math.ceil(rate * buffer_seconds * 1.25), 2048), 250_000)
        self.descriptor = descriptor
        self._timestamps: deque[float] = deque(maxlen=capacity)
        self._samples: deque[tuple[float, ...]] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._count = 0
        self._last: float | None = None

    def append_chunk(self, samples: Sequence[Sequence[float]], timestamps: Sequence[float]) -> int:
        rows = []
        for timestamp, sample in zip(timestamps, samples, strict=False):
            if len(sample) != self.descriptor.channel_count:
                continue
            try:
                rows.append((float(timestamp), tuple(float(value) for value in sample)))
            except (TypeError, ValueError):
                continue
        with self._lock:
            for timestamp, row in rows:
                self._timestamps.append(timestamp)
                self._samples.append(row)
            if rows:
                self._count += len(rows)
                self._last = time.monotonic()
        return len(rows)

    def window(self, seconds: float) -> DataWindow:
        if seconds <= 0:
            raise ValueError("seconds must be positive")
        with self._lock:
            timestamps = tuple(self._timestamps)
            samples = tuple(self._samples)
            count = self._count
            last = self._last
        if timestamps:
            cutoff = timestamps[-1] - seconds
            start = next((index for index, value in enumerate(timestamps) if value >= cutoff), len(timestamps))
            timestamps, samples = timestamps[start:], samples[start:]
        return DataWindow(self.descriptor, timestamps, samples, count, last)
