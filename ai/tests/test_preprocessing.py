import unittest

import numpy as np

from ai.src.fetal_guard_ai.features import signal_quality_index
from ai.src.fetal_guard_ai.preprocessing import (
    WindowConfig,
    interpolate_missing,
    make_sliding_windows,
    prepare_ctg_matrix,
    resample_uniform,
    robust_zscore,
)


class PreprocessingTests(unittest.TestCase):
    def test_interpolate_missing_handles_nan(self):
        values = np.asarray([1.0, np.nan, 3.0], dtype=np.float32)
        result = interpolate_missing(values)
        self.assertTrue(np.allclose(result, [1.0, 2.0, 3.0]))

    def test_make_sliding_windows_shape(self):
        values = np.arange(40, dtype=np.float32).reshape(20, 2)
        windows, starts = make_sliding_windows(
            values,
            WindowConfig(sampling_hz=2, window_seconds=5, stride_seconds=2.5),
        )
        self.assertEqual(windows.shape, (3, 10, 2))
        self.assertTrue(np.array_equal(starts, [0, 5, 10]))

    def test_robust_zscore_is_finite(self):
        values = np.asarray([[1.0, 2.0], [1.0, 5.0], [1.0, 8.0]], dtype=np.float32)
        result = robust_zscore(values)
        self.assertTrue(np.isfinite(result).all())

    def test_resample_uniform_changes_length(self):
        values = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
        result = resample_uniform(values, source_hz=1.0, target_hz=2.0)
        self.assertEqual(result.shape[0], 5)

    def test_prepare_ctg_matrix_two_channels(self):
        fhr = np.asarray([120.0, 121.0, np.nan, 123.0], dtype=np.float32)
        uc = np.asarray([10.0, 11.0, 12.0, 13.0], dtype=np.float32)
        result = prepare_ctg_matrix(fhr, uc)
        self.assertEqual(result.shape, (4, 2))

    def test_signal_quality_index_range(self):
        summary = signal_quality_index(np.asarray([1.0, 2.0, np.nan, 4.0], dtype=np.float32))
        self.assertGreaterEqual(summary.score, 0.0)
        self.assertLessEqual(summary.score, 1.0)


if __name__ == "__main__":
    unittest.main()
