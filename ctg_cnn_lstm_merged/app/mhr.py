"""mhr.py — ambang klinis MHR (ACOG: normal 70-110 bpm)."""

MHR_CLASSES = ["Normal", "Low", "High"]


def label_mhr(mhr_bpm: float) -> int:
    if mhr_bpm < 70:
        return 1  # Low
    if mhr_bpm > 110:
        return 2  # High
    return 0      # Normal


def label_mhr_name(mhr_bpm: float) -> str:
    return MHR_CLASSES[label_mhr(mhr_bpm)]
