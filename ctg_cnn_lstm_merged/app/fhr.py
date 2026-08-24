"""fhr.py — ambang klinis FHR. Satu-satunya tempat definisi 110-160/dst,
biar training & backend selalu konsisten (tidak ada duplikasi logika)."""

FHR_CLASSES = ["Normal", "Bradycardia", "Tachycardia"]


def label_fhr(fhr_bpm: float) -> int:
    if fhr_bpm < 110:
        return 1  # Bradycardia
    if fhr_bpm > 160:
        return 2  # Tachycardia
    return 0      # Normal


def label_fhr_name(fhr_bpm: float) -> str:
    return FHR_CLASSES[label_fhr(fhr_bpm)]
