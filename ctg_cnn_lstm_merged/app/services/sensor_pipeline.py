"""
sensor_pipeline.py — Langkah 2-5: gabungkan 4 piezo (FHR), MAX30102 (MHR),
FSR 408 (UC) jadi tiga angka: fhr_bpm, mhr_bpm, uc_per_10min. Ini yang
dipanggil SEBELUM data masuk ke CNN-LSTM (lihat ctg_service.py).
"""
from collections import deque
from app.signal_processing.filters import preprocess_channel
from app.signal_processing.bpm import estimate_bpm
from app.signal_quality.sqi import calculate_sqi, SensorSelector
from app.ctg.uterine import UterineBaseline, estimate_uc_rate

PIEZO_KEYS = ["piezo_1", "piezo_2", "piezo_3", "piezo_4"]
UC_HISTORY_SEC = 300  # akumulasi 5 menit FSR sebelum diekstrapolasi ke /10menit
                       # (window sesaat 4 detik terlalu pendek -> noise kecil bisa
                       # meledak jadi angka besar kalau langsung diekstrapolasi)


class SensorPipeline:
    """Satu instance = satu sesi/device (state hysteresis piezo & baseline
    FSR harus konsisten sepanjang sesi, sama seperti ctg_ai_backend)."""

    def __init__(self, fs_piezo=50.0, fs_max30102=50.0, fs_fsr=10.0, calibration_range=500.0):
        self.fs_piezo = fs_piezo
        self.fs_max30102 = fs_max30102
        self.fs_fsr = fs_fsr
        self.piezo_selector = SensorSelector(switch_threshold=0.08)
        self.uc_baseline = UterineBaseline(calibration_range=calibration_range)
        self.fsr_history = deque(maxlen=int(UC_HISTORY_SEC * fs_fsr))

    def calibrate_uc(self, initial_fsr_samples):
        return self.uc_baseline.calibrate(initial_fsr_samples)

    def process(self, raw_window: dict) -> dict:
        """
        raw_window = {
            "piezo_1": [...], "piezo_2": [...], "piezo_3": [...], "piezo_4": [...],  # 4️⃣
            "max30102": [...],                                                        # 2️⃣
            "fsr": [...],                                                             # 3️⃣
        }
        """
        # 4️⃣ FHR dari piezo terbaik (SQI + hysteresis)
        filtered_piezo = {k: preprocess_channel(raw_window[k], fs=self.fs_piezo) for k in PIEZO_KEYS}
        sqi_scores = calculate_sqi(filtered_piezo)
        best_piezo = self.piezo_selector.select(sqi_scores)
        fhr_bpm = estimate_bpm(filtered_piezo[best_piezo], fs=self.fs_piezo)

        # 2️⃣ MHR dari MAX30102 (sensor tunggal, tidak perlu seleksi)
        filtered_mhr = preprocess_channel(raw_window["max30102"], fs=self.fs_max30102)
        mhr_bpm = estimate_bpm(filtered_mhr, fs=self.fs_max30102)

        # 3️⃣ UC dari FSR (baseline individual + akumulasi 5 menit, bukan
        # ekstrapolasi dari window sesaat yang gampang meledak oleh noise)
        if not self.uc_baseline.is_calibrated():
            raise RuntimeError("Baseline UC belum dikalibrasi. Panggil calibrate_uc() dulu.")
        self.fsr_history.extend(raw_window["fsr"])
        history_duration_sec = len(self.fsr_history) / self.fs_fsr
        delta, _ = self.uc_baseline.normalize(list(self.fsr_history))
        uc_per_10min = estimate_uc_rate(delta, fs=self.fs_fsr, window_sec=history_duration_sec)

        return {
            "fhr_bpm": fhr_bpm,
            "mhr_bpm": mhr_bpm,
            "uc_per_10min": uc_per_10min,
            "audit": {  # 5️⃣ tetap simpan jejak, bisa dicek kalau hasil aneh
                "selected_piezo": best_piezo,
                "sqi_scores": sqi_scores,
                "uc_baseline": self.uc_baseline.baseline,
                "uc_history_sec": round(history_duration_sec, 1),
            },
        }
