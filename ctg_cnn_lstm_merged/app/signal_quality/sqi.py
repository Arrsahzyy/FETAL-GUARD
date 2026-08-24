"""
sqi.py — Signal Quality Index multi-kriteria per sensor piezo, sesuai
rekomendasi: jangan pilih sensor cuma dari amplitudo terbesar.
"""
import numpy as np
from scipy.stats import entropy as scipy_entropy
from scipy.signal import find_peaks

WEIGHTS = {"snr": 0.35, "peak": 0.30, "rms": 0.15, "variance": 0.10, "entropy": 0.10}


def _snr(signal):
    """Estimasi SNR sederhana: rasio energi sinyal vs energi residual (noise)
    setelah smoothing (moving average) dianggap sebagai 'sinyal bersih'."""
    kernel = np.ones(5) / 5
    smooth = np.convolve(signal, kernel, mode="same")
    noise = signal - smooth
    p_signal = np.mean(smooth ** 2)
    p_noise = np.mean(noise ** 2) + 1e-8
    snr_db = 10 * np.log10(p_signal / p_noise + 1e-8)
    return max(snr_db, 0.0)


def _peak_consistency(signal, fs=50):
    """Semakin teratur jarak antar-puncak, semakin tinggi skor (fisiologis
    cenderung periodik; noise/motion artifact cenderung acak)."""
    peaks, _ = find_peaks(signal, distance=max(int(fs * 0.3), 1))
    if len(peaks) < 3:
        return 0.0
    intervals = np.diff(peaks)
    cv = intervals.std() / (intervals.mean() + 1e-8)  # coefficient of variation
    return float(np.clip(1 - cv, 0, 1))


def _entropy_score(signal, bins=20):
    """Entropy tinggi = sinyal terlalu acak (mendekati noise) -> skor DIBALIK
    (semakin rendah entropy relatif, semakin baik untuk deteksi periodik)."""
    hist, _ = np.histogram(signal, bins=bins, density=True)
    hist = hist[hist > 0]
    e = scipy_entropy(hist)
    e_norm = e / np.log(bins)  # normalisasi ke 0-1
    return float(np.clip(1 - e_norm, 0, 1))


def _minmax_scale(values):
    values = np.array(values, dtype=np.float64)
    lo, hi = values.min(), values.max()
    if hi - lo < 1e-8:
        return np.ones_like(values) * 0.5
    return (values - lo) / (hi - lo)


def calculate_sqi(sensor_windows: dict) -> dict:
    """
    sensor_windows: {"piezo_1": np.array(...), "piezo_2": np.array(...), ...}
    Return: {"piezo_1": {"snr":.., "rms":.., "peak":.., "variance":.., "entropy":.., "sqi": 0.71}, ...}
    """
    names = list(sensor_windows.keys())
    snr_raw, rms_raw, peak_raw, var_raw, ent_raw = [], [], [], [], []

    for name in names:
        sig = np.asarray(sensor_windows[name], dtype=np.float64)
        snr_raw.append(_snr(sig))
        rms_raw.append(np.sqrt(np.mean(sig ** 2)))
        peak_raw.append(_peak_consistency(sig))
        var_raw.append(sig.var())
        ent_raw.append(_entropy_score(sig))

    snr_s = _minmax_scale(snr_raw)
    rms_s = _minmax_scale(rms_raw)
    var_s = _minmax_scale(var_raw)
    # peak & entropy sudah 0-1 secara alami, tidak perlu di-scale ulang

    result = {}
    for i, name in enumerate(names):
        sqi = (
            WEIGHTS["snr"] * snr_s[i]
            + WEIGHTS["peak"] * peak_raw[i]
            + WEIGHTS["rms"] * rms_s[i]
            + WEIGHTS["variance"] * var_s[i]
            + WEIGHTS["entropy"] * ent_raw[i]
        )
        result[name] = {
            "snr": round(float(snr_raw[i]), 3),
            "rms": round(float(rms_raw[i]), 3),
            "peak_consistency": round(float(peak_raw[i]), 3),
            "variance": round(float(var_raw[i]), 3),
            "entropy": round(float(ent_raw[i]), 3),
            "sqi": round(float(sqi), 4),
        }
    return result


class SensorSelector:
    """Memilih sensor terbaik antar-window, dengan HYSTERESIS supaya tidak
    lompat-lompat ganti sensor tiap window (lihat rekomendasi poin 6)."""

    def __init__(self, switch_threshold: float = 0.08):
        self.switch_threshold = switch_threshold
        self.current_sensor = None

    def select(self, sqi_scores: dict) -> str:
        ranked = sorted(sqi_scores.items(), key=lambda kv: kv[1]["sqi"], reverse=True)
        best_name, best = ranked[0]

        if self.current_sensor is None or self.current_sensor not in sqi_scores:
            self.current_sensor = best_name
            return best_name

        current_sqi = sqi_scores[self.current_sensor]["sqi"]
        if best["sqi"] > current_sqi + self.switch_threshold:
            self.current_sensor = best_name

        return self.current_sensor
