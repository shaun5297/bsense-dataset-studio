import unittest

from bsense_dataset_studio.acquisition.discovery import describe, select_unique


class FakeStreamInfo:
    """Minimal stand-in for pylsl.StreamInfo."""

    def __init__(self, name: str, stream_type: str, source_id: str, hostname: str = "host-a") -> None:
        self._name = name
        self._type = stream_type
        self._source_id = source_id
        self._hostname = hostname

    def name(self) -> str:
        return self._name

    def type(self) -> str:
        return self._type

    def channel_count(self) -> int:
        return 4

    def nominal_srate(self) -> float:
        return 250.0

    def source_id(self) -> str:
        return self._source_id

    def hostname(self) -> str:
        return self._hostname

    def as_xml(self) -> str:
        return "<info />"


def _found(*infos: FakeStreamInfo):
    return [(info, describe(info)) for info in infos]


class DiscoveryTests(unittest.TestCase):
    def test_same_stream_seen_twice_on_lan_is_deduplicated(self) -> None:
        # One EEG stream resolved via two network paths yields two infos with
        # identical metadata; selection must not treat them as a conflict.
        first = FakeStreamInfo("BrainAmp", "EEG", source_id="serial-1")
        second = FakeStreamInfo("BrainAmp", "EEG", source_id="serial-1")
        selected = select_unique(_found(first, second), ["eeg"])
        self.assertIs(selected["eeg"][0], first)

    def test_distinct_devices_of_same_kind_still_raise(self) -> None:
        first = FakeStreamInfo("BrainAmp-1", "EEG", source_id="serial-1")
        second = FakeStreamInfo("BrainAmp-2", "EEG", source_id="serial-2")
        with self.assertRaisesRegex(RuntimeError, "重复流"):
            select_unique(_found(first, second), ["eeg"])

    def test_same_source_id_on_different_hosts_still_raise(self) -> None:
        first = FakeStreamInfo("BrainAmp", "EEG", source_id="serial-1", hostname="host-a")
        second = FakeStreamInfo("BrainAmp", "EEG", source_id="serial-1", hostname="host-b")
        with self.assertRaisesRegex(RuntimeError, "重复流"):
            select_unique(_found(first, second), ["eeg"])

    def test_missing_kind_still_raises(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "缺少流"):
            select_unique(_found(FakeStreamInfo("BrainAmp", "EEG", source_id="serial-1")), ["eeg", "fnirs"])

    def test_duplicate_error_lists_conflicting_stream_names(self) -> None:
        first = FakeStreamInfo("BrainAmp-1", "EEG", source_id="serial-1")
        second = FakeStreamInfo("BrainAmp-2", "EEG", source_id="serial-2")
        with self.assertRaisesRegex(RuntimeError, "BrainAmp-1 / BrainAmp-2"):
            select_unique(_found(first, second), ["eeg"])


if __name__ == "__main__":
    unittest.main()
