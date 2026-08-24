"""
simulator.py — pengganti ESP32 fisik buat uji coba. Kirim pembacaan
FHR/MHR/UC ke /api/ingest, mensimulasikan skenario normal/abnormal.
"""
import argparse
import random
import time
import requests


def gen_normal():
    return {"fhr_bpm": round(random.uniform(115, 155), 1),
             "mhr_bpm": round(random.uniform(75, 105), 1),
             "uc_per_10min": round(random.uniform(2.2, 4.8), 1)}


def gen_abnormal():
    fhr = round(random.uniform(60, 105), 1) if random.random() < 0.5 else round(random.uniform(165, 200), 1)
    mhr = round(random.uniform(45, 68), 1) if random.random() < 0.5 else round(random.uniform(115, 150), 1)
    uc = round(random.uniform(0, 1.8), 1) if random.random() < 0.5 else round(random.uniform(5.2, 9), 1)
    return {"fhr_bpm": fhr, "mhr_bpm": mhr, "uc_per_10min": uc}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--device", default="esp32-ctg-01")
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--scenario", choices=["normal", "abnormal", "mixed"], default="mixed")
    args = p.parse_args()

    endpoint = f"{args.url}/api/ingest"
    print(f"Mengirim ke {endpoint} (device={args.device}, scenario={args.scenario}). Ctrl+C untuk berhenti.")

    i = 0
    try:
        while True:
            payload = gen_normal() if (args.scenario == "normal" or
                       (args.scenario == "mixed" and random.random() < 0.75)) else gen_abnormal()
            payload["device_id"] = args.device

            try:
                res = requests.post(endpoint, json=payload, timeout=5)
                res.raise_for_status()
                data = res.json()
                if data["status"] == "collecting":
                    print(f"[{i}] mengumpulkan {data['buffer_count']}/{data['buffer_needed']}")
                else:
                    pred = data["prediction"]
                    print(f"[{i}] FHR={payload['fhr_bpm']}({pred['fhr']['status']}) "
                          f"MHR={payload['mhr_bpm']}({pred['mhr']['status']}) "
                          f"UC={payload['uc_per_10min']}({pred['uc']['status']}) "
                          f"-> {pred['overall']['status']} ({pred['overall']['confidence']*100:.0f}%)")
            except requests.exceptions.RequestException as e:
                print(f"Error koneksi: {e}")

            i += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nSimulator dihentikan.")


if __name__ == "__main__":
    main()
