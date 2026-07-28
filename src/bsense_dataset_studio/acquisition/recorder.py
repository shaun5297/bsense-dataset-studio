from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .discovery import discover, select_unique
from .xdf_writer import XDFWriter

REQUIRED_KINDS = (
    "eeg",
    "fnirs",
    "motion",
    "metric",
    "heart_rate",
    "biomultilite_marker",
    "general_metric",
    "experiment_marker",
)


@dataclass
class _State:
    kind: str
    inlet: Any
    stream_id: int
    channel_count: int
    channel_format: int
    count: int = 0
    first: float = 0.0
    last: float = 0.0
    next_clock_offset_at: float = 0.0
    clock_offset_count: int = 0


class Recorder:
    def __init__(self, output: Path, *, required_kinds: tuple[str, ...] = REQUIRED_KINDS) -> None:
        self.output = output
        self.required_kinds = required_kinds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._states: list[_State] = []
        self.error: Exception | None = None

    def start(self, *, timeout: float = 5.0) -> None:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("recorder already running")
        selected = select_unique(discover(timeout), self.required_kinds)
        from pylsl import StreamInlet, local_clock

        states: list[_State] = []
        writer = XDFWriter(self.output)
        try:
            for stream_id, kind in enumerate(self.required_kinds, 1):
                info, descriptor = selected[kind]
                writer.write_stream_header(stream_id, info.as_xml())
                inlet = StreamInlet(info, max_buflen=60)
                inlet.open_stream(timeout=timeout)
                states.append(
                    _State(
                        kind,
                        inlet,
                        stream_id,
                        descriptor.channel_count,
                        int(info.channel_format()),
                        next_clock_offset_at=time.monotonic(),
                    )
                )
        except Exception:
            for state in states:
                try:
                    state.inlet.close_stream()
                except Exception:
                    pass
            writer.close()
            raise

        def run() -> None:
            try:
                while not self._stop.is_set():
                    received = False
                    for state in states:
                        monotonic_now = time.monotonic()
                        if monotonic_now >= state.next_clock_offset_at:
                            try:
                                offset = float(state.inlet.time_correction(timeout=0.0))
                                writer.write_clock_offset(
                                    state.stream_id,
                                    float(local_clock()),
                                    offset,
                                )
                                state.clock_offset_count += 1
                            except Exception:
                                pass
                            state.next_clock_offset_at = monotonic_now + 5.0
                        samples, timestamps = state.inlet.pull_chunk(timeout=0.0, max_samples=1024)
                        if timestamps:
                            received = True
                            writer.write_samples(
                                state.stream_id,
                                timestamps,
                                samples,
                                state.channel_count,
                                state.channel_format,
                            )
                            state.count += len(timestamps)
                            state.first = state.first or float(timestamps[0])
                            state.last = float(timestamps[-1])
                    if not received:
                        time.sleep(0.005)
            except Exception as exc:
                self.error = exc
            finally:
                for state in states:
                    writer.write_stream_footer(state.stream_id, state.first, state.last, state.count)
                    try:
                        state.inlet.close_stream()
                    except Exception:
                        pass
                writer.close()

        self._stop.clear()
        self._states = states
        self._thread = threading.Thread(target=run, name="bsense-xdf-recorder", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise TimeoutError("recorder did not stop")
        if self.error:
            raise RuntimeError("recorder failed") from self.error

    def summary(self) -> dict[str, object]:
        return {
            state.kind: {
                "sample_count": state.count,
                "first_timestamp": state.first or None,
                "last_timestamp": state.last or None,
                "clock_offset_count": state.clock_offset_count,
            }
            for state in self._states
        }
