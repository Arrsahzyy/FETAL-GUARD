"""
main.py — API dirapikan: response konsisten, ada schema eksplisit
(otomatis muncul di /docs), error handling jelas, dan endpoint
tambahan buat cek status buffer per device.
"""
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.services import ctg_service

app = FastAPI(
    title="CTG CNN-LSTM API",
    description="Menerima pembacaan FHR/MHR/UC dari ESP32, mengembalikan klasifikasi CNN-LSTM.",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_latest_by_device: dict = {}


class Reading(BaseModel):
    device_id: str = Field(..., examples=["esp32-ctg-01"])
    fhr_bpm: float = Field(..., ge=0, le=300)
    mhr_bpm: float = Field(..., ge=0, le=250)
    uc_per_10min: float = Field(..., ge=0, le=20)


class ParamResult(BaseModel):
    status: str
    confidence: float


class Prediction(BaseModel):
    fhr: ParamResult
    mhr: ParamResult
    uc: ParamResult
    overall: ParamResult


class IngestResponse(BaseModel):
    status: Literal["collecting", "predicted"]
    device_id: str
    timestamp: str
    buffer_count: Optional[int] = None
    buffer_needed: Optional[int] = None
    prediction: Optional[Prediction] = None


class HealthResponse(BaseModel):
    status: str
    active_devices: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.post("/api/ingest", response_model=IngestResponse)
def ingest(r: Reading):
    try:
        result = ctg_service.process_reading(r.device_id, r.fhr_bpm, r.mhr_bpm, r.uc_per_10min)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses pembacaan: {e}")

    if result["status"] == "collecting":
        return IngestResponse(
            status="collecting",
            device_id=r.device_id,
            timestamp=_now(),
            buffer_count=result["buffer_count"],
            buffer_needed=result["buffer_needed"],
        )

    prediction = Prediction(
        fhr=ParamResult(status=result["fhr_status"], confidence=result["fhr_confidence"]),
        mhr=ParamResult(status=result["mhr_status"], confidence=result["mhr_confidence"]),
        uc=ParamResult(status=result["uc_status"], confidence=result["uc_confidence"]),
        overall=ParamResult(status=result["overall_status"], confidence=result["overall_confidence"]),
    )
    resp = IngestResponse(status="predicted", device_id=r.device_id, timestamp=_now(), prediction=prediction)
    _latest_by_device[r.device_id] = resp.dict()
    return resp


@app.get("/api/buffer-status/{device_id}")
def buffer_status(device_id: str):
    win = ctg_service._windows.get(device_id)
    return {
        "device_id": device_id,
        "buffer_count": len(win.buf) if win else 0,
        "buffer_needed": win.seq_len if win else None,
        "ready": win.is_ready() if win else False,
    }


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", active_devices=len(ctg_service._windows))


# ---------------------------------------------------------------------------
# Endpoint baru: ESP32 kirim SENSOR MENTAH (4 piezo + MAX30102 + FSR),
# bukan bpm siap pakai. Langkah 1-6.
# ---------------------------------------------------------------------------

class RawWindow(BaseModel):
    device_id: str
    piezo_1: list[float]
    piezo_2: list[float]
    piezo_3: list[float]
    piezo_4: list[float]
    max30102: list[float]
    fsr: list[float]


@app.post("/api/ingest-raw")
def ingest_raw(w: RawWindow):
    raw = w.dict(exclude={"device_id"})
    try:
        result = ctg_service.process_raw_window(w.device_id, raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses sensor mentah: {e}")

    if result["status"] in ("collecting", "calibrating", "signal_too_weak"):
        return {"status": result["status"], "device_id": w.device_id, "timestamp": _now(), **{k: v for k, v in result.items() if k != "status"}}

    prediction = Prediction(
        fhr=ParamResult(status=result["fhr_status"], confidence=result["fhr_confidence"]),
        mhr=ParamResult(status=result["mhr_status"], confidence=result["mhr_confidence"]),
        uc=ParamResult(status=result["uc_status"], confidence=result["uc_confidence"]),
        overall=ParamResult(status=result["overall_status"], confidence=result["overall_confidence"]),
    )
    resp = {
        "status": "predicted", "device_id": w.device_id, "timestamp": _now(),
        "computed_bpm": result["computed_bpm"], "audit": result.get("audit"),
        "prediction": prediction.dict(),
    }
    _latest_by_device[w.device_id] = resp
    return resp


@app.get("/api/latest/{device_id}")
def latest(device_id: str):
    """7️⃣ Dipanggil website React buat polling hasil terakhir per device."""
    if device_id not in _latest_by_device:
        raise HTTPException(status_code=404, detail="Belum ada data untuk device ini.")
    return _latest_by_device[device_id]
