import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ai.src.fetal_guard_ai.model import HybridCNNLSTMConfig
from ai.src.fetal_guard_ai.training_data import (
    group_holdout_split,
    load_hybrid_training_npz,
)

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make_synthetic_smoke_windows.py"
_spec = importlib.util.spec_from_file_location("make_synthetic_smoke_windows", _SCRIPT)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


class SyntheticSmokeGeneratorTests(unittest.TestCase):
    def test_dataset_matches_the_training_contract(self):
        data = gen.build_dataset(sessions=9, windows_per_session=6, window_seconds=8.0, seed=42)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "smoke.npz"
            np.savez_compressed(path, **data)
            dataset = load_hybrid_training_npz(path, config=HybridCNNLSTMConfig())

        self.assertEqual(dataset.dataset_kind, "synthetic_smoke_test")
        self.assertEqual(dataset.input_schema_version, 2)
        self.assertEqual(dataset.sample_count, 54)
        self.assertEqual(dataset.inputs["piezo"].shape, (54, 2000, 4))
        self.assertEqual(dataset.inputs["fsr"].shape, (54, 400, 1))
        self.assertEqual(dataset.inputs["maternal_ppg"].shape, (54, 800, 2))
        # all three screening classes present, and a leakage-safe split is possible
        self.assertEqual(set(np.unique(dataset.screening_labels).tolist()), {0, 1, 2})
        split = group_holdout_split(dataset.group_ids, seed=42)
        self.assertGreater(split.train.size, 0)
        self.assertGreater(split.validation.size, 0)
        self.assertGreater(split.test.size, 0)

    def test_labels_follow_the_threshold_rule(self):
        # FHR far out of range -> class 2; borderline -> class 1; normal -> class 0
        self.assertEqual(gen._screening_label(90.0, False), 2)
        self.assertEqual(gen._screening_label(180.0, False), 2)
        self.assertEqual(gen._screening_label(105.0, False), 1)
        self.assertEqual(gen._screening_label(165.0, False), 1)
        self.assertEqual(gen._screening_label(140.0, True), 1)
        self.assertEqual(gen._screening_label(140.0, False), 0)

    def test_windows_are_zscored_like_the_inference_path(self):
        data = gen.build_dataset(sessions=6, windows_per_session=4, window_seconds=8.0, seed=1)
        piezo = data["piezo"]
        self.assertTrue(np.isfinite(piezo).all())
        # robust_zscore output: per-window-channel median near 0, spread order ~1
        self.assertLess(abs(float(np.median(piezo))), 0.5)
        self.assertLess(float(np.abs(piezo).mean()), 5.0)


if __name__ == "__main__":
    unittest.main()
