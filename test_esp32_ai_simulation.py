import sys
import time
from pathlib import Path

# ============================================================
# FETAL GUARD
# TEST 4 - SIMULASI ESP32 -> AI
# ============================================================

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
CTG_ROOT = ROOT / "ctg_cnn_lstm_merged"

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(CTG_ROOT))

from services.ctg_cnn_lstm_adapter import predict_from_payload


# ============================================================
# SIMULATED ESP32 DATA
# ============================================================

ESP32_READINGS = [
    {"fhr_bpm": 140, "mhr_bpm": 82, "uc_per_10min": 2},
    {"fhr_bpm": 141, "mhr_bpm": 83, "uc_per_10min": 2},
    {"fhr_bpm": 142, "mhr_bpm": 82, "uc_per_10min": 3},
    {"fhr_bpm": 140, "mhr_bpm": 84, "uc_per_10min": 2},
    {"fhr_bpm": 139, "mhr_bpm": 83, "uc_per_10min": 2},
    {"fhr_bpm": 141, "mhr_bpm": 82, "uc_per_10min": 3},
    {"fhr_bpm": 143, "mhr_bpm": 84, "uc_per_10min": 3},
    {"fhr_bpm": 142, "mhr_bpm": 83, "uc_per_10min": 2},
    {"fhr_bpm": 140, "mhr_bpm": 82, "uc_per_10min": 2},
    {"fhr_bpm": 139, "mhr_bpm": 81, "uc_per_10min": 3},
    {"fhr_bpm": 141, "mhr_bpm": 82, "uc_per_10min": 2},
    {"fhr_bpm": 142, "mhr_bpm": 83, "uc_per_10min": 3},
    {"fhr_bpm": 140, "mhr_bpm": 84, "uc_per_10min": 2},
    {"fhr_bpm": 139, "mhr_bpm": 82, "uc_per_10min": 2},
    {"fhr_bpm": 141, "mhr_bpm": 83, "uc_per_10min": 3},
]


def main():
    print()
    print("=" * 60)
    print(" FETAL GUARD - TEST 4")
    print(" SIMULASI ESP32 -> AI")
    print("=" * 60)

    print()
    print("ESP32: Bluetooth connection simulated")
    print("ESP32: Sending CTG readings...")
    print()

    window = []

    # ========================================================
    # SIMULATE ESP32 STREAM
    # ========================================================

    for i, reading in enumerate(ESP32_READINGS, start=1):

        print(
            f"[ESP32] Reading {i:02d}/15 | "
            f"FHR={reading['fhr_bpm']:3d} bpm | "
            f"MHR={reading['mhr_bpm']:3d} bpm | "
            f"UC={reading['uc_per_10min']}"
        )

        window.append(reading)

        # Simulate arrival interval
        time.sleep(0.1)

    print()
    print("-" * 60)
    print("ESP32: 15 readings received")
    print("ESP32: CTG window ready")
    print("-" * 60)

    # ========================================================
    # SEND WINDOW TO BACKEND AI ADAPTER
    # ========================================================

    payload = {
        "readings": window
    }

    print()
    print("BACKEND: Receiving ESP32 payload...")
    print("BACKEND: Running CTG CNN-LSTM...")
    print()

    result = predict_from_payload(payload)

    # ========================================================
    # AI RESULT
    # ========================================================

    print("=" * 60)
    print(" FETAL GUARD AI RESULT")
    print("=" * 60)

    print()
    print(
        f"FHR      : {result['fhr']['status']}"
        f" | confidence = {result['fhr']['confidence']}"
    )

    print(
        f"MHR      : {result['mhr']['status']}"
        f" | confidence = {result['mhr']['confidence']}"
    )

    print(
        f"UC       : {result['uc']['status']}"
        f" | confidence = {result['uc']['confidence']}"
    )

    print()
    print("-" * 60)

    print(
        f"OVERALL  : {result['overall']['status']}"
        f" | confidence = {result['overall']['confidence']}"
    )

    print("-" * 60)

    # ========================================================
    # VALIDATION
    # ========================================================

    assert set(result.keys()) == {
        "fhr",
        "mhr",
        "uc",
        "overall",
    }

    for channel in ["fhr", "mhr", "uc", "overall"]:

        assert "status" in result[channel]
        assert "confidence" in result[channel]

        confidence = result[channel]["confidence"]

        assert 0.0 <= confidence <= 1.0

    print()
    print("=" * 60)
    print(" TEST 4 PASSED")
    print(" ESP32 simulation -> AI inference berhasil")
    print("=" * 60)


if __name__ == "__main__":
    main()