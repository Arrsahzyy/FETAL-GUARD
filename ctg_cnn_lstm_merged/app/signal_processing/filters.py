"""
filters.py — Band-pass & notch filter untuk sinyal piezo mentah, sebelum
dipakai untuk SQI atau model.
"""
import numpy as np
from scipy.signal import butter, filtfilt, iirnotch


def bandpass_filter(signal, fs, low=0.5, high=10.0, order=4):
    """Buang DC drift & noise frekuensi tinggi. fs = sampling rate (Hz)."""
    nyq = fs / 2
    b, a = butter(order, [low / nyq, high / nyq], btype="band")
    return filtfilt(b, a, signal)


def notch_filter(signal, fs, freq=50.0, q=30.0):
    """Buang interferensi listrik (mis. 50Hz Indonesia / 60Hz sebagian negara)."""
    nyq = fs / 2
    b, a = iirnotch(freq / nyq, q)
    return filtfilt(b, a, signal)


def normalize(signal):
    """Z-score normalization per window."""
    signal = np.asarray(signal, dtype=np.float64)
    std = signal.std()
    if std < 1e-8:
        return signal - signal.mean()
    return (signal - signal.mean()) / std


def preprocess_channel(raw_signal, fs, notch_freq=50.0):
    """Pipeline lengkap 1 channel: notch -> bandpass -> normalize.
    Notch dilewati otomatis kalau notch_freq >= Nyquist (fs terlalu rendah
    untuk memfilter frekuensi itu, mis. fs piezo < 100Hz)."""
    x = np.asarray(raw_signal, dtype=np.float64)
    if notch_freq < fs / 2:
        x = notch_filter(x, fs, freq=notch_freq)
    x = bandpass_filter(x, fs, high=min(10.0, fs / 2 - 0.5))
    return normalize(x)
