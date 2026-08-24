"""
generate_sequences.py
=======================
Beda dengan ctg_ai_backend (belajar dari bentuk gelombang piezo mentah),
modul ini bekerja LANGSUNG di atas nilai bpm/kontraksi aktual (FHR bpm,
MHR bpm, UC per 10 menit) — persis nilai yang ditampilkan ke user di
dashboard. Label ground truth dihitung dari AMBANG KLINIS EKSAK:

    FHR normal      : 110-160 bpm
    FHR bradikardia : < 110 bpm
    FHR takikardia  : > 160 bpm

    MHR normal (ACOG): 70-110 bpm
    MHR rendah        : < 70 bpm
    MHR tinggi         : > 110 bpm

    UC normal            : 2-5 kontraksi/10menit
    UC hypocontraction   : < 2
    UC tachysystole      : > 5

Setiap SAMPLE = satu window berisi SEQ_LEN pembacaan berurutan. Label
window = status pembacaan TERAKHIR di window itu (yaitu "kondisi saat
ini"), sedangkan sample-sample sebelumnya dipakai CNN-LSTM sebagai
KONTEKS supaya klasifikasi lebih tahan terhadap noise sensor sesaat.
"""
import numpy as np
import os

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

SEQ_LEN = 15  # jumlah pembacaan berurutan per window


import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.fhr import label_fhr, FHR_CLASSES
from app.mhr import label_mhr, MHR_CLASSES
from app.uc import label_uc, UC_CLASSES

OVERALL_CLASSES = ["Normal", "Abnormal"]


def _random_walk(base, n, step_std, lo, hi):
    walk = [base]
    for _ in range(n - 1):
        walk.append(walk[-1] + np.random.normal(0, step_std))
    return np.clip(np.array(walk), lo, hi)


def _generate_raw_series(n_points, dt_sec=15):
    """Bangkitkan deret waktu FHR/MHR/UC sepanjang n_points, dengan
    beberapa 'episode' abnormal yang realistis (bukan cuma noise acak)."""
    fhr = _random_walk(np.random.uniform(128, 145), n_points, 1.3, 60, 210)
    mhr = _random_walk(np.random.uniform(80, 95), n_points, 0.9, 45, 160)
    uc = np.clip(_random_walk(np.random.uniform(2.5, 4), n_points, 0.35, 0, 9), 0, None)

    n_episodes = np.random.randint(2, 6)
    for _ in range(n_episodes):
        kind = np.random.choice(["fhr_brady", "fhr_tachy", "mhr_low", "mhr_high", "uc_hypo", "uc_tachy"])
        start = np.random.randint(0, max(1, n_points - 20))
        length = np.random.randint(6, 18)
        end = min(start + length, n_points)
        if kind == "fhr_brady":
            fhr[start:end] -= np.random.uniform(30, 55)
        elif kind == "fhr_tachy":
            fhr[start:end] += np.random.uniform(30, 55)
        elif kind == "mhr_low":
            mhr[start:end] -= np.random.uniform(20, 35)
        elif kind == "mhr_high":
            mhr[start:end] += np.random.uniform(20, 35)
        elif kind == "uc_hypo":
            uc[start:end] = np.random.uniform(0, 1.8, end - start)
        elif kind == "uc_tachy":
            uc[start:end] = np.random.uniform(5.2, 8.5, end - start)

    fhr = np.clip(fhr, 40, 220)
    mhr = np.clip(mhr, 35, 200)
    uc = np.clip(uc, 0, 12)
    return fhr, mhr, uc


def build_dataset(n_sessions=250, session_len=120):
    """n_sessions sesi monitoring sintetis, tiap sesi punya session_len
    pembacaan berturut (dt_sec=15s -> ~30 menit per sesi). Window
    SEQ_LEN diambil overlapping dari tiap sesi."""
    X, y_fhr, y_mhr, y_uc, y_overall = [], [], [], [], []

    for _ in range(n_sessions):
        fhr, mhr, uc = _generate_raw_series(session_len)
        for start in range(0, session_len - SEQ_LEN + 1):
            end = start + SEQ_LEN
            window = np.stack([fhr[start:end], mhr[start:end], uc[start:end]], axis=1)  # (SEQ_LEN, 3)

            last_fhr, last_mhr, last_uc = fhr[end - 1], mhr[end - 1], uc[end - 1]
            lf, lm, lu = label_fhr(last_fhr), label_mhr(last_mhr), label_uc(last_uc)
            overall = 0 if (lf == 0 and lm == 0 and lu == 0) else 1

            X.append(window)
            y_fhr.append(lf)
            y_mhr.append(lm)
            y_uc.append(lu)
            y_overall.append(overall)

    return (
        np.array(X, dtype=np.float32),
        np.array(y_fhr, dtype=np.int64),
        np.array(y_mhr, dtype=np.int64),
        np.array(y_uc, dtype=np.int64),
        np.array(y_overall, dtype=np.int64),
    )


if __name__ == "__main__":
    X, y_fhr, y_mhr, y_uc, y_overall = build_dataset()
    out_path = os.path.join(os.path.dirname(__file__), "ctg_cnn_lstm_dataset.npz")
    np.savez(out_path, X=X, y_fhr=y_fhr, y_mhr=y_mhr, y_uc=y_uc, y_overall=y_overall)

    print(f"Dataset: {X.shape[0]} window, seq_len={SEQ_LEN}, fitur=3 (FHR,MHR,UC)")
    for name, arr, classes in [("FHR", y_fhr, FHR_CLASSES), ("MHR", y_mhr, MHR_CLASSES),
                                ("UC", y_uc, UC_CLASSES), ("Overall", y_overall, OVERALL_CLASSES)]:
        vals, counts = np.unique(arr, return_counts=True)
        dist = {classes[v]: int(c) for v, c in zip(vals, counts)}
        print(f"{name}: {dist}")
    print("Disimpan di:", os.path.abspath(out_path))
