"""ctg_service.py — orchestrator lengkap: terima RAW WINDOW dari ESP32
(4 piezo + MAX30102 + FSR) -> sensor_pipeline (jadi fhr/mhr/uc bpm) ->
buffer per device -> CNN-LSTM begitu window CNN-LSTM penuh (6️⃣)."""
from app.signal_processing.windowing import RollingWindow
from app.services.sensor_pipeline import SensorPipeline
from app.ai.inference import CTGPredictor
from training.generate_sequences import SEQ_LEN

_predictor = None
_pipelines: dict[str, SensorPipeline] = {}
_windows: dict[str, RollingWindow] = {}
_calib_buffers: dict[str, list] = {}

CALIBRATION_SIZE = 100  # jumlah sample FSR awal untuk baseline UC


def _get_predictor() -> CTGPredictor:
    global _predictor
    if _predictor is None:
        _predictor = CTGPredictor()
    return _predictor


def process_raw_window(device_id: str, raw_window: dict) -> dict:
    """raw_window: {"piezo_1..4":[...], "max30102":[...], "fsr":[...]}"""
    pipeline = _pipelines.setdefault(device_id, SensorPipeline())

    # kalibrasi baseline UC otomatis di window pertama tiap device
    if not pipeline.uc_baseline.is_calibrated():
        buf = _calib_buffers.setdefault(device_id, [])
        buf.extend(raw_window["fsr"])
        if len(buf) < CALIBRATION_SIZE:
            return {"status": "calibrating", "calibration_progress": f"{len(buf)}/{CALIBRATION_SIZE}"}
        pipeline.calibrate_uc(buf[:CALIBRATION_SIZE])

    computed = pipeline.process(raw_window)
    if computed["fhr_bpm"] is None or computed["mhr_bpm"] is None:
        return {"status": "signal_too_weak", "detail": "Sinyal piezo/MAX30102 tidak cukup jelas untuk hitung bpm."}

    return process_reading(device_id, computed["fhr_bpm"], computed["mhr_bpm"], computed["uc_per_10min"],
                            audit=computed["audit"])


def process_reading(device_id: str, fhr_bpm: float, mhr_bpm: float, uc_per_10min: float, audit: dict = None) -> dict:
    """Tetap ada terpisah supaya endpoint lama (kirim bpm langsung, tanpa
    sensor mentah) masih bisa dipakai untuk uji cepat / simulator."""
    win = _windows.setdefault(device_id, RollingWindow(SEQ_LEN))
    win.push(fhr_bpm, mhr_bpm, uc_per_10min)

    if not win.is_ready():
        return {"status": "collecting", "buffer_count": len(win.buf), "buffer_needed": SEQ_LEN}

    result = _get_predictor().predict(win.as_list())
    out = {"status": "predicted", "computed_bpm": {"fhr_bpm": fhr_bpm, "mhr_bpm": mhr_bpm, "uc_per_10min": uc_per_10min}, **result}
    if audit:
        out["audit"] = audit
    return out
