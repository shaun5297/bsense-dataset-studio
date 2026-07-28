import tempfile
import unittest
from pathlib import Path

from bsense_dataset_studio.acquisition.xdf_writer import XDFWriter, encode_varlen_int
from bsense_dataset_studio.dataset.xdf_reader import read_xdf


class XDFTests(unittest.TestCase):
    def test_varlen_boundaries(self) -> None:
        self.assertEqual(encode_varlen_int(255)[0], 1)
        self.assertEqual(encode_varlen_int(256)[0], 4)
        self.assertEqual(encode_varlen_int(2**32)[0], 8)
        with self.assertRaises(ValueError):
            encode_varlen_int(-1)

    def test_writer_round_trips_through_pyxdf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roundtrip.xdf"
            xml = (
                '<?xml version="1.0"?><info><name>EEG</name><type>EEG</type>'
                "<channel_count>2</channel_count><nominal_srate>10</nominal_srate>"
                "<channel_format>float32</channel_format><source_id>test-eeg</source_id>"
                "<desc><channels><channel><label>C3</label></channel>"
                "<channel><label>C4</label></channel></channels></desc></info>"
            )
            timestamps = [1.0 + index * 0.1 for index in range(20)]
            samples = [
                [float(index), float(index + 1)]
                for index in range(20)
            ]
            with XDFWriter(path) as writer:
                writer.write_stream_header(1, xml)
                writer.write_clock_offset(1, 1.0, 0.0)
                writer.write_samples(1, timestamps, samples, 2, 1)
                writer.write_stream_footer(
                    1,
                    timestamps[0],
                    timestamps[-1],
                    len(timestamps),
                )
            streams, _header = read_xdf(path)
            self.assertEqual(len(streams), 1)
            self.assertEqual(streams[0]["info"]["name"][0], "EEG")
            self.assertEqual(len(streams[0]["time_stamps"]), 20)


if __name__ == "__main__":
    unittest.main()
