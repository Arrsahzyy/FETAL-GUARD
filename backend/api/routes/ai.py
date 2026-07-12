from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from api.dependencies import get_current_user
from db.database import get_db
from models.sensor_data import SensorDataChunk
from models.session import MonitoringSession
from models.user import User
from schemas.ai import AIPredictRequest, AIPredictResponse
from services.ai_stub import classify_screening_stub

router = APIRouter()


def get_accessible_sensor_chunk(db: Session, chunk_id: str, current_user: User) -> SensorDataChunk:
    chunk = (
        db.query(SensorDataChunk)
        .options(joinedload(SensorDataChunk.session).joinedload(MonitoringSession.patient))
        .filter(SensorDataChunk.id == chunk_id)
        .first()
    )
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor data chunk not found",
        )

    if current_user.role == "clinician":
        return chunk

    if current_user.role == "patient":
        patient = chunk.session.patient
        if patient.user_id == current_user.id:
            return chunk

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not enough permissions for this sensor data chunk",
    )


@router.post("/predict", response_model=AIPredictResponse)
def predict_screening_stub(
    request: AIPredictRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chunk = get_accessible_sensor_chunk(db, request.sensor_data_chunk_id, current_user)
    risk_score, classification = classify_screening_stub()

    return AIPredictResponse(
        sensor_data_chunk_id=chunk.id,
        risk_score=risk_score,
        classification=classification,
        message=(
            "Hasil ini adalah stub skrining awal FETAL-GUARD dan bukan penentu kondisi klinis. "
            "Gunakan untuk membantu pemantauan dan konsultasikan dengan tenaga kesehatan."
        ),
        is_stub=True,
    )
