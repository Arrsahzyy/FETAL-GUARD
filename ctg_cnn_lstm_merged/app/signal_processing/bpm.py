"""bpm.py — hitung bpm dari sinyal periodik (piezo terpilih ATAU MAX30102),
lewat jarak antar-peak. Dipakai untuk FHR (dari piezo) dan MHR (dari MAX30102)."""
import numpy as np
from scipy.signal import find_peaks


def estimate_bpm(signal, fs, min_bpm=40, max_bpm=220):
    """signal: sinyal sudah difilter+normalize. fs: sampling rate (Hz)."""
    signal = np.asarray(signal, dtype=np.float64)
    min_distance = int(fs * 60 / max_bpm)  # jarak minimum antar-peak (batasi bpm maksimum)
    peaks, _ = find_peaks(signal, distance=max(min_distance, 1), height=np.std(signal) * 0.3)

    if len(peaks) < 2:
        return None  # sinyal tidak cukup jelas -> jangan paksa kasih angka ngawur

    intervals_sec = np.diff(peaks) / fs
    mean_interval = np.mean(intervals_sec)
    bpm = 60.0 / mean_interval
    return float(np.clip(bpm, min_bpm, max_bpm))
