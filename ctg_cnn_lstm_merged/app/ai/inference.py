import os
import sys
import torch
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from app.ai.model import CTGCNNLSTM
from training.generate_sequences import FHR_CLASSES, MHR_CLASSES, UC_CLASSES, OVERALL_CLASSES, SEQ_LEN

BASE = os.path.join(os.path.dirname(__file__), "..", "..")


class CTGPredictor:
    def __init__(self, ckpt_path=os.path.join(BASE, "checkpoints", "best.pt")):
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        self.model = CTGCNNLSTM()
        self.model.load_state_dict(ckpt["model_state"])
        self.model.eval()
        self.mean = ckpt["scaler_mean"]
        self.std = ckpt["scaler_std"]

    def predict(self, window):
        """window: list/array shape (SEQ_LEN, 3) berisi [fhr_bpm, mhr_bpm, uc_per_10min]."""
        window = np.asarray(window, dtype=np.float32)
        assert window.shape == (SEQ_LEN, 3), f"window harus ({SEQ_LEN}, 3)"

        x = (window - self.mean) / self.std
        x = torch.tensor(x, dtype=torch.float32).unsqueeze(0)

        with torch.no_grad():
            out = self.model(x)

        def decode(logits, classes):
            probs = torch.softmax(logits[0], dim=0)
            idx = int(probs.argmax())
            return classes[idx], round(float(probs[idx]), 4)

        fhr_label, fhr_conf = decode(out["fhr"], FHR_CLASSES)
        mhr_label, mhr_conf = decode(out["mhr"], MHR_CLASSES)
        uc_label, uc_conf = decode(out["uc"], UC_CLASSES)
        overall_label, overall_conf = decode(out["overall"], OVERALL_CLASSES)

        return {
            "fhr_status": fhr_label, "fhr_confidence": fhr_conf,
            "mhr_status": mhr_label, "mhr_confidence": mhr_conf,
            "uc_status": uc_label, "uc_confidence": uc_conf,
            "overall_status": overall_label, "overall_confidence": overall_conf,
        }
