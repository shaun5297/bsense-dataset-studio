from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ..schemas.markers import Marker


class MarkerPublisher:
    def __init__(self, events_path: Path, outlet: Any | None = None) -> None:
        self.events_path = events_path
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        if outlet is None:
            from pylsl import StreamInfo, StreamOutlet, cf_string

            # Per-instance source_id: a stale outlet from a previous run must
            # never be mistaken for (or merged with) the current one.
            source_id = f"bsense-dataset-studio-{uuid.uuid4().hex[:8]}"
            info = StreamInfo("BSense Experiment Markers", "Markers", 1, 0, cf_string, source_id)
            outlet = StreamOutlet(info)
        self._outlet = outlet

    def publish(self, marker: Marker) -> None:
        if self._outlet is None:
            raise RuntimeError("Marker outlet 已关闭")
        payload = json.dumps(marker.to_dict(), ensure_ascii=False, separators=(",", ":"))
        self._outlet.push_sample([payload], marker.timestamp)
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(payload + "\n")

    def close(self) -> None:
        """Release the LSL outlet so later runs do not discover a stale stream."""
        outlet, self._outlet = self._outlet, None
        del outlet  # dropping the last reference destroys the outlet at once
