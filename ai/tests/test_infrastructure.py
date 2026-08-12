import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ai.src.fetal_guard_ai.artifact import ModelArtifactManifest
from ai.src.fetal_guard_ai.contracts import (
    ChannelContract,
    ModelValidationStatus,
    WindowContract,
)
from ai.src.fetal_guard_ai.model import HybridCNNLSTMConfig, build_hybrid_cnn_lstm
from ai.src.fetal_guard_ai.inference import (
    apply_safety_layer,
    predict_preprocessed_window,
)
from ai.src.fetal_guard_ai.preprocessing import (
    WindowConfig,
    make_masked_sliding_windows,
    robust_zscore,
)
from ai.src.fetal_guard_ai.training_data import (
    group_holdout_split,
    load_hybrid_training_npz,
)


class InfrastructureTests(unittest.TestCase):
    @staticmethod
    def _write_hybrid_dataset(path: Path, *, low_validity: bool = False) -> None:
        sample_count = 6
        arrays = {
            "piezo": np.zeros((sample_count, 20, 4), dtype=np.float32),
            "fsr": np.zeros((sample_count, 8, 1), dtype=np.float32),
            "maternal_ppg": np.zeros((sample_count, 12, 2), dtype=np.float32),
        }
        masks = {name: np.ones_like(values, dtype=bool) for name, values in arrays.items()}
        if low_validity:
            masks["piezo"][0, :10, :] = False
        np.savez_compressed(
            path,
            **arrays,
            **{f"{name}_validity_mask": mask for name, mask in masks.items()},
            screening_labels=np.asarray([0, 1, 2, 0, 1, 2], dtype=np.int64),
            quality_targets=np.asarray([1, 0.8, 0.9, 1, 0.7, 0.95], dtype=np.float32),
            measurement_targets=np.full((sample_count, 2), np.nan, dtype=np.float32),
            contraction_targets=np.full((sample_count,), np.nan, dtype=np.float32),
            group_ids=np.asarray(["g1", "g2", "g3", "g4", "g5", "g6"]),
            dataset_kind=np.asarray("synthetic_smoke_test"),
            preprocessing_version=np.asarray("test-v1"),
            input_schema_version=np.asarray(2, dtype=np.int64),
        )

    def test_window_contract_rejects_duplicate_modalities(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            WindowContract(
                modalities=(
                    ChannelContract("piezo", 4, 250, "adc_count"),
                    ChannelContract("piezo", 1, 50, "adc_count"),
                )
            )

    def test_masked_window_rejects_data_hidden_by_normalization(self):
        raw = np.arange(20, dtype=np.float32).reshape(10, 2)
        raw[:6, :] = np.nan
        original_mask = np.isfinite(raw)
        normalized = robust_zscore(raw)

        windows, masks, starts = make_masked_sliding_windows(
            normalized,
            WindowConfig(
                sampling_hz=1,
                window_seconds=10,
                stride_seconds=10,
                min_valid_ratio=0.8,
            ),
            validity_mask=original_mask,
        )

        self.assertEqual(windows.shape[0], 0)
        self.assertEqual(masks.shape[0], 0)
        self.assertEqual(starts.shape[0], 0)

    def test_artifact_manifest_verifies_hash_and_gates_deployment(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifact = root / "model.pt"
            artifact.write_bytes(b"reviewed-test-artifact")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "model_name": "fetal-guard-hybrid",
                        "model_version": "0.1.0",
                        "architecture": "cnn_lstm_multitask",
                        "preprocessing_version": "0.1.0",
                        "artifact_file": "model.pt",
                        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                        "validation_status": "analytical_validated",
                        "input_schema_version": 2,
                        "created_at": "2026-08-11T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )

            manifest = ModelArtifactManifest.load(manifest_path)
            self.assertEqual(manifest.verify(manifest_path), artifact)
            manifest.assert_allowed_for("shadow")
            with self.assertRaisesRegex(RuntimeError, "not allowed"):
                manifest.assert_allowed_for("patient")

    def test_model_config_rejects_noncanonical_class_count(self):
        with self.assertRaisesRegex(ValueError, "three learned classes"):
            HybridCNNLSTMConfig(screening_classes=2)

    def test_model_builder_fails_with_actionable_error_without_torch(self):
        try:
            import torch  # noqa: F401
        except ImportError:
            with self.assertRaisesRegex(RuntimeError, "PyTorch is required"):
                build_hybrid_cnn_lstm()
        else:
            model = build_hybrid_cnn_lstm()
            self.assertGreater(sum(parameter.numel() for parameter in model.parameters()), 0)

    def test_hybrid_dataset_contract_and_group_split_prevent_leakage(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "hybrid.npz"
            self._write_hybrid_dataset(path)
            dataset = load_hybrid_training_npz(path)
            split = group_holdout_split(dataset.group_ids, seed=7)

            train_groups = set(dataset.group_ids[split.train])
            validation_groups = set(dataset.group_ids[split.validation])
            test_groups = set(dataset.group_ids[split.test])
            self.assertFalse(train_groups & validation_groups)
            self.assertFalse(train_groups & test_groups)
            self.assertFalse(validation_groups & test_groups)
            self.assertEqual(
                sorted(np.concatenate((split.train, split.validation, split.test)).tolist()),
                list(range(dataset.sample_count)),
            )

    def test_hybrid_dataset_rejects_windows_below_validity_gate(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "hybrid-low-validity.npz"
            self._write_hybrid_dataset(path, low_validity=True)
            with self.assertRaisesRegex(ValueError, "below min_valid_ratio"):
                load_hybrid_training_npz(path)

    def test_safety_layer_suppresses_classification_for_limited_signal(self):
        result = apply_safety_layer(
            quality_probability=0.7,
            screening_probabilities=(0.05, 0.1, 0.85),
            fhr_bpm=145,
            maternal_hr_bpm=82,
            contraction_probability=0.2,
            model_version="test-v1",
            preprocessing_version="test-preprocessing-v1",
        )

        self.assertEqual(result.quality_status.value, "limited")
        self.assertEqual(result.screening_status.value, "insufficient_signal")
        self.assertIn("limited_signal_quality", result.reasons)

    def test_safety_layer_rejects_out_of_range_measurement(self):
        result = apply_safety_layer(
            quality_probability=0.95,
            screening_probabilities=(0.9, 0.05, 0.05),
            fhr_bpm=999,
            maternal_hr_bpm=82,
            contraction_probability=None,
            model_version="test-v1",
            preprocessing_version="test-preprocessing-v1",
        )

        self.assertIsNone(result.fhr_bpm)
        self.assertEqual(result.screening_status.value, "insufficient_signal")
        self.assertIn("invalid_fhr_output", result.reasons)

    def test_inference_rejects_incomplete_window_before_loading_torch(self):
        class FakeModel:
            config = HybridCNNLSTMConfig()

        manifest = ModelArtifactManifest(
            model_name="fetal-guard-hybrid",
            model_version="test-v1",
            architecture="cnn_lstm_multitask",
            preprocessing_version="test-preprocessing-v1",
            artifact_file="model.pt",
            artifact_sha256="a" * 64,
            validation_status=ModelValidationStatus.experimental,
            input_schema_version=2,
            created_at="2026-08-11T00:00:00Z",
        )
        inputs = {
            "piezo": np.zeros((20, 4), dtype=np.float32),
            "fsr": np.zeros((8, 1), dtype=np.float32),
            "maternal_ppg": np.zeros((12, 2), dtype=np.float32),
        }
        masks = {name: np.ones_like(values, dtype=bool) for name, values in inputs.items()}
        masks["piezo"][:10, :] = False

        result = predict_preprocessed_window(
            FakeModel(),
            manifest,
            inputs=inputs,
            validity_masks=masks,
        )

        self.assertEqual(result.screening_status.value, "insufficient_signal")
        self.assertEqual(result.quality_status.value, "unusable")
        self.assertIn("low_valid_piezo", result.reasons)


if __name__ == "__main__":
    unittest.main()
