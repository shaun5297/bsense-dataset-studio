import unittest

from bsense_dataset_studio.acquisition.xdf_writer import encode_varlen_int


class XDFTests(unittest.TestCase):
    def test_varlen_boundaries(self) -> None:
        self.assertEqual(encode_varlen_int(255)[0], 1)
        self.assertEqual(encode_varlen_int(256)[0], 4)
        self.assertEqual(encode_varlen_int(2**32)[0], 8)
        with self.assertRaises(ValueError):
            encode_varlen_int(-1)


if __name__ == "__main__":
    unittest.main()
