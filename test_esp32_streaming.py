import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
CTG_ROOT = ROOT / "ctg_cnn_lstm_merged"

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(CTG_ROOT))

from services.ctg_cnn_lstm_adapter import predict_from_payload


# ============================================================
# SIMULATED ESP32 BLE STREAM
# ============================================================

ESP32_STREAM = [
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

    # Packet 16-18 untuk menguji sliding window
    {"fhr_bpm": 140, "mhr_bpm": 82, "uc_per_10min": 2},
    {"fhr_bpm": 142, "mhr_bpm": 83, "uc_per_10min": 3},
    {"fhr_bpm": 141, "mhr_bpm": 84, "uc_per_10min": 2},
]


WINDOW_SIZE = 15


def run_ai(window, prediction_number):
    print()
    print("=" * 60)
    print(f" AI PREDICTION #{prediction_number}")
    print("=" * 60)

    result = predict_from_payload({
        "readings": window
    })

    print(
        f"FHR     : {result['fhr']['status']}"
        f" | confidence = {result['fhr']['confidence']}"
    )

    print(
        f"MHR     : {result['mhr']['status']}"
        f" | confidence = {result['mhr']['confidence']}"
    )

    print(
        f"UC      : {result['uc']['status']}"
        f" | confidence = {result['uc']['confidence']}"
    )

    print("-" * 60)

    print(
        f"OVERALL : {result['overall']['status']}"
        f" | confidence = {result['overall']['confidence']}"
    )

    # Validation
    for channel in ["fhr", "mhr", "uc", "overall"]:
        assert "status" in result[channel]
        assert "confidence" in result[channel]

        confidence = result[channel]["confidence"]

        assert 0.0 <= confidence <= 1.0

    return result


def main():

    print()
    print("=" * 60)
    print(" FETAL GUARD - TEST 5")
    print(" SIMULASI BLE STREAMING ESP32")
    print("=" * 60)

    print()
    print("[BLE] Connecting to simulated ESP32...")
    time.sleep(0.5)

    print("[BLE] Connected")
    print()

    buffer = []
    prediction_count = 0

    for packet_number, reading in enumerate(ESP32_STREAM, start=1):

        print(
            f"[BLE] Packet {packet_number:02d} received | "
            f"FHR={reading['fhr_bpm']} | "
            f"MHR={reading['mhr_bpm']} | "
            f"UC={reading['uc_per_10min']}"
        )

        buffer.append(reading)

        # Belum cukup untuk inference
        if len(buffer) < WINDOW_SIZE:
            print(
                f"      Buffer: {len(buffer)}/{WINDOW_SIZE}"
            )
            continue

        # Window pertama / sliding window
        window = buffer[-WINDOW_SIZE:]

        print(
            f"      Window ready: "
            f"{len(window)}/{WINDOW_SIZE}"
        )

        prediction_count += 1

        run_ai(
            window,
            prediction_count
        )

        # Simulasikan streaming:
        # setelah prediction pertama,
        # satu data lama keluar dan data baru masuk.
        print()
        print(
            "[WINDOW] Sliding window updated"
        )

        time.sleep(0.2)

    print()
    print("=" * 60)
    print(" TEST 5 SUMMARY")
    print("=" * 60)

    print(
        f"Total BLE packets received : "
        f"{len(ESP32_STREAM)}"
    )

    print(
        f"AI predictions performed   : "
        f"{prediction_count}"
    )

    assert len(ESP32_STREAM) == 18
    assert prediction_count == 4

    print()
    print("TEST 5 PASSED")
    print("BLE streaming simulation -> sliding window -> CNN-LSTM OK")
    print("=" * 60)


if __name__ == "__main__":
    main()