import tempfile
import unittest
from pathlib import Path

from bsense_dataset_studio.acquisition.recorder import Recorder, _State


class RecorderTests(unittest.TestCase):
    def test_zero_timestamps_are_preserved_in_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recorder = Recorder(Path(directory) / "unused.xdf")
            recorder._states = [
                _State(
                    kind="eeg",
                    inlet=object(),
                    stream_id=1,
                    channel_count=2,
                    channel_format=1,
                    count=1,
                    first=0.0,
                    last=0.0,
                )
            ]

            summary = recorder.summary()["eeg"]

        self.assertEqual(summary["first_timestamp"], 0.0)
        self.assertEqual(summary["last_timestamp"], 0.0)


if __name__ == "__main__":
    unittest.main()
