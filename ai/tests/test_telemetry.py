import unittest

import numpy as np

from ai.src.fetal_guard_ai.telemetry import (
    TelemetryWindowError,
    prepare_stored_telemetry_window,
)


def chunk(sequence, *, include_ppg=True):
    samples = {
        "p": [1000, 1001, 1002, 1003, 1004, 1005, 1006, 1007],
        "fsr": [500, 510],
    }
    rates = {"p": 2, "fsr": 2}
    if include_ppg:
        samples.update({"hr_ir": [10000, 10100], "hr_red": [9000, 9100]})
        rates.update({"hr_ir": 2, "hr_red": 2})
    return {
        "schema_version": 2,
        "boot_id": "boot-test-0001",
        "sequence_number": sequence,
        "source": "ble",
        "is_simulated": False,
        "sample_rates_hz": rates,
        "channel_layout": {"p": 4},
        "samples": samples,
    }


class TelemetryAdapterTests(unittest.TestCase):
    def test_builds_native_multimodal_model_shapes(self):
        prepared = prepare_stored_telemetry_window(
            [chunk(1), chunk(2)],
            window_seconds=2,
            target_rates_hz={"piezo": 2, "fsr": 2, "maternal_ppg": 2},
        )

        self.assertEqual(prepared.inputs["piezo"].shape, (4, 4))
        self.assertEqual(prepared.inputs["fsr"].shape, (4, 1))
        self.assertEqual(prepared.inputs["maternal_ppg"].shape, (4, 2))
        self.assertTrue(all(np.isfinite(value).all() for value in prepared.inputs.values()))
        self.assertEqual(prepared.valid_ratios, {
            "piezo": 1.0,
            "fsr": 1.0,
            "maternal_ppg": 1.0,
        })

    def test_missing_ppg_is_masked_for_fail_closed_safety_gate(self):
        prepared = prepare_stored_telemetry_window(
            [chunk(1, include_ppg=False)],
            window_seconds=1,
            target_rates_hz={"piezo": 2, "fsr": 2, "maternal_ppg": 2},
        )

        self.assertEqual(prepared.valid_ratios["maternal_ppg"], 0.0)
        self.assertFalse(prepared.validity_masks["maternal_ppg"].any())

    def test_packet_gap_is_rejected(self):
        with self.assertRaisesRegex(TelemetryWindowError, "missing or reordered") as raised:
            prepare_stored_telemetry_window(
                [chunk(1), chunk(3)],
                window_seconds=2,
                target_rates_hz={"piezo": 2, "fsr": 2, "maternal_ppg": 2},
            )
        self.assertEqual(raised.exception.code, "packet_gap")

    def test_v1_or_simulated_data_never_enters_hardware_inference(self):
        invalid = chunk(1)
        invalid["schema_version"] = 1
        with self.assertRaises(TelemetryWindowError) as raised:
            prepare_stored_telemetry_window(
                [invalid],
                window_seconds=1,
                target_rates_hz={"piezo": 2, "fsr": 2, "maternal_ppg": 2},
            )
        self.assertEqual(raised.exception.code, "unsupported_telemetry_schema")


if __name__ == "__main__":
    unittest.main()
