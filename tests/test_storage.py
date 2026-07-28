import json
import tempfile
import unittest
from pathlib import Path

from bsense_dataset_studio.storage import (
    default_dataset_root,
    load_dataset_root,
    plan_run_storage,
    prepare_run_storage,
    save_dataset_root,
)


class StorageTests(unittest.TestCase):
    def test_plan_uses_standard_dataset_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = plan_run_storage(
                directory,
                "P001",
                "01",
                "m6_readiness_study",
                "001",
            )
            relative = storage.xdf.relative_to(storage.dataset_root)
            self.assertEqual(
                str(relative),
                "raw/sub-P001/ses-01/sub-P001_ses-01_task-m6_readiness_study_run-001.xdf",
            )

    def test_prepare_creates_dataset_layout_and_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "dataset"
            storage = prepare_run_storage(
                plan_run_storage(root, "P001", "01", "deviceqc", "001")
            )
            self.assertTrue(storage.raw_directory.is_dir())
            for name in ("restricted", "quality", "annotations", "derived", "manifests"):
                self.assertTrue((root / name).is_dir())

    def test_selected_root_round_trips_through_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "data"
            config = base / "config" / "settings.json"
            save_dataset_root(root, config)
            self.assertEqual(load_dataset_root(config), root.resolve())

    def test_invalid_settings_fall_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "settings.json"
            config.write_text(json.dumps({"unexpected": True}), encoding="utf-8")
            self.assertEqual(load_dataset_root(config), default_dataset_root())


if __name__ == "__main__":
    unittest.main()
