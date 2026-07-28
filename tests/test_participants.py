import tempfile
import unittest
from pathlib import Path

from bsense_dataset_studio.participants.profile import save_profile


class ParticipantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = {
            "participant_id": "P001",
            "name": "受限姓名",
            "age": 30,
            "sex": "不愿透露",
            "education_years": 16,
            "dominant_hand": "右",
        }

    def test_conflicting_profile_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_profile(root, self.profile)
            changed = {**self.profile, "age": 31}
            with self.assertRaises(FileExistsError):
                save_profile(root, changed)


if __name__ == "__main__":
    unittest.main()
