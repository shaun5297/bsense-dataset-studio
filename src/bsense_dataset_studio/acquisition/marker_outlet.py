from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schemas.markers import Marker


class MarkerPublisher:
    def __init__(self, events_path: Path, outlet: Any | None = None) -> None:
        self.events_path = events_path
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        if outlet is None:
            from pylsl import StreamInfo, StreamOutlet, cf_string

            info = StreamInfo("BSense Experiment Markers", "Markers", 1, 0, cf_string, "bsense-dataset-studio")
            outlet = StreamOutlet(info)
        self._outlet = outlet

    def publish(self, marker: Marker) -> None:
        payload = json.dumps(marker.to_dict(), ensure_ascii=False, separators=(",", ":"))
        self._outlet.push_sample([payload], marker.timestamp)
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(payload + "\n")
