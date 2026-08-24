"""uc.py — ambang klinis kontraksi uterus (normal 2-5/10menit)."""

UC_CLASSES = ["Normal", "Hypocontraction", "Tachysystole"]


def label_uc(uc_per_10min: float) -> int:
    if uc_per_10min < 2:
        return 1  # Hypocontraction
    if uc_per_10min > 5:
        return 2  # Tachysystole
    return 0      # Normal


def label_uc_name(uc_per_10min: float) -> str:
    return UC_CLASSES[label_uc(uc_per_10min)]
