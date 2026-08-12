import unittest

from ai.src.fetal_guard_ai.labels import SafeScreeningLabel, ph_regression_target, screening_label_from_ph


class LabelTests(unittest.TestCase):
    def test_ph_regression_target_parses_numeric_value(self):
        self.assertEqual(ph_regression_target({"pH": "7.21"}), 7.21)

    def test_screening_label_requires_reviewed_cutoff(self):
        self.assertIsNone(screening_label_from_ph({"pH": "7.01"}, observation_cutoff=None))

    def test_screening_label_uses_explicit_cutoff(self):
        label = screening_label_from_ph({"pH": "7.01"}, observation_cutoff=7.05)
        self.assertEqual(label, SafeScreeningLabel.needs_observation)


if __name__ == "__main__":
    unittest.main()
