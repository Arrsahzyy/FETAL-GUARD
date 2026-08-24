"""
uterine.py — FSR 408 TIDAK dipakai sebagai threshold absolut. Wajib
dikalibrasi ke baseline individual dulu (lihat poin 7-10 dokumen Anda).
"""
import numpy as np
from scipy.signal import find_peaks


class UterineBaseline:
    """Kalibrasi baseline per sesi monitoring (per pasien), bukan konstanta global."""

    def __init__(self, calibration_range: float = 500.0):
        self.baseline = None
        self.calibration_range = calibration_range  # dipakai untuk normalisasi 0-1

    def calibrate(self, initial_samples):
        """Panggil sekali di awal sesi (mis. 10-30 detik pertama, saat rileks)."""
        self.baseline = float(np.mean(initial_samples))
        return self.baseline

    def is_calibrated(self) -> bool:
        return self.baseline is not None

    def normalize(self, raw_fsr):
        """raw_fsr bisa skalar atau array. Return delta & normalized (0-1-an)."""
        if self.baseline is None:
            raise RuntimeError("Baseline belum dikalibrasi. Panggil calibrate() dulu.")
        raw = np.asarray(raw_fsr, dtype=np.float64)
        delta = raw - self.baseline
        normalized = np.clip(delta / self.calibration_range, 0, 1.5)  # izinkan sedikit overshoot
        return delta, normalized


def extract_uc_features(delta_signal, fs=10.0):
    """
    Fitur kontraksi dari sinyal delta (bukan raw FSR) dalam satu window.
    delta_signal: array hasil UterineBaseline.normalize()[0] (ΔFSR).
    """
    delta_signal = np.asarray(delta_signal, dtype=np.float64)
    peaks, props = find_peaks(delta_signal, height=np.std(delta_signal) * 0.5, distance=fs)

    max_amp = float(delta_signal.max()) if len(delta_signal) else 0.0
    mean_amp = float(delta_signal.mean()) if len(delta_signal) else 0.0

    rise_time, fall_time, duration = 0.0, 0.0, 0.0
    if len(peaks):
        p = peaks[np.argmax(delta_signal[peaks])]
        left = p
        while left > 0 and delta_signal[left] > delta_signal[left - 1]:
            left -= 1
        right = p
        while right < len(delta_signal) - 1 and delta_signal[right] > delta_signal[right + 1]:
            right += 1
        rise_time = (p - left) / fs
        fall_time = (right - p) / fs
        duration = (right - left) / fs

    return {
        "max_amplitude": round(max_amp, 2),
        "mean_amplitude": round(mean_amp, 2),
        "rise_time_sec": round(rise_time, 2),
        "fall_time_sec": round(fall_time, 2),
        "duration_sec": round(duration, 2),
        "peak_count": int(len(peaks)),
    }


def estimate_uc_rate(delta_signal, fs, window_sec, min_gap_sec=45):
    """Hitung jumlah kontraksi lalu ekstrapolasi ke 'per 10 menit'
    (satuan yang dipakai ambang klinis di app/uc.py).

    Dua penjagaan penting supaya tidak salah hitung noise sebagai kontraksi:
    1. Smoothing (moving average) dulu — kontraksi asli itu naik-turun
       LAMBAT (puluhan detik), bukan lonjakan sesaat seperti noise sensor.
    2. Jarak minimum antar-peak = min_gap_sec (default 45 detik) — secara
       fisiologis kontraksi tidak mungkin terjadi lebih rapat dari itu.
    """
    from scipy.signal import find_peaks
    delta_signal = np.asarray(delta_signal, dtype=np.float64)
    if delta_signal.std() < 1e-6 or window_sec < min_gap_sec:
        return 0.0

    kernel_len = max(int(fs * 3), 1)  # smoothing ~3 detik
    smooth = np.convolve(delta_signal, np.ones(kernel_len) / kernel_len, mode="same")

    peaks, _ = find_peaks(smooth, height=smooth.std() * 0.8, distance=int(fs * min_gap_sec))
    peak_count = len(peaks)
    return float(peak_count * (600.0 / window_sec))  # extrapolasi ke /10menit
