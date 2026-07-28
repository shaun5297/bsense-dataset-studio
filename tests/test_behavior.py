import unittest

from bsense_dataset_studio.behavior.sart import classify_trial, summarize_trials


class SartTests(unittest.TestCase):
    def test_summary_includes_extended_research_metrics(self) -> None:
        rows = [
            classify_trial(True, 0.40),
            classify_trial(True, 0.50),
            classify_trial(True, None),
            classify_trial(False, 0.30),
            classify_trial(False, None),
            classify_trial(True, 0.05),
        ]
        result = summarize_trials(rows)
        self.assertEqual(result["valid_trial_count"], 6)
        self.assertEqual(result["omission_count"], 1)
        self.assertEqual(result["commission_count"], 1)
        self.assertEqual(result["false_start_count"], 1)
        self.assertIn("slowest_10_percent_mean_s", result)
        self.assertIn("reaction_time_slope", result)

    def test_invalid_trials_are_excluded(self) -> None:
        rows = [classify_trial(True, 0.4), classify_trial(True, None, valid=False)]
        self.assertEqual(summarize_trials(rows)["valid_trial_count"], 1)


if __name__ == "__main__":
    unittest.main()
