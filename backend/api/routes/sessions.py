from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from api.dependencies import get_current_user
from db.database import get_db
from models.device import Device
from models.patient import Patient
from models.sensor_data import SensorDataChunk
from models.session import MonitoringSession
from models.session_sensor_summary import SessionSensorSummary
from models.user import User
from schemas.sensor_data import SensorDataChunkCreate, SensorDataChunkResponse
from schemas.session import SessionCreate, SessionResponse, SessionUpdate

router = APIRouter()


def get_patient_profile_for_user(db: Session, current_user: User) -> Patient:
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patient users can manage monitoring sessions",
        )

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )
    return patient


def get_owned_session(db: Session, session_id: str, patient_id: str) -> MonitoringSession:
    monitoring_session = (
        db.query(MonitoringSession)
        .filter(MonitoringSession.id == session_id, MonitoringSession.patient_id == patient_id)
        .first()
    )
    if monitoring_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitoring session not found",
        )
    return monitoring_session


def get_device_for_upload(db: Session, patient_id: str, chunk_in: SensorDataChunkCreate) -> Device | None:
    if not chunk_in.device_uid:
        return None

    device = db.query(Device).filter(Device.device_uid == chunk_in.device_uid).first()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not registered",
        )
    if device.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not assigned to this patient",
        )
    if device.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not active",
        )
    return device


def count_sensor_samples(stored_payload: dict) -> int:
    samples = stored_payload.get("samples", stored_payload)
    if not isinstance(samples, dict):
        return 0

    total = 0
    for key in ("p", "fsr", "hr_ir", "hr_red"):
        channel = samples.get(key)
        if isinstance(channel, list):
            total += len(channel)
    return total


def upsert_session_sensor_summary(
    db: Session,
    monitoring_session: MonitoringSession,
    device: Device | None,
    chunk_in: SensorDataChunkCreate,
    stored_payload: dict,
) -> None:
    now = datetime.now(timezone.utc)
    summary = monitoring_session.sensor_summary
    if summary is None:
        summary = SessionSensorSummary(
            session_id=monitoring_session.id,
            source=chunk_in.source or ("device" if device else "manual"),
            is_simulated=bool(chunk_in.is_simulated),
        )
        db.add(summary)

    if device:
        summary.device_id = device.id
        device.last_seen_at = now
    summary.sample_count = max(0, summary.sample_count or 0) + count_sensor_samples(stored_payload)
    summary.source = chunk_in.source or summary.source or ("device" if device else "manual")
    summary.is_simulated = bool(chunk_in.is_simulated)
    summary.updated_at = now

    if chunk_in.summary:
        if chunk_in.summary.fhr_estimate_bpm is not None:
            summary.fhr_estimate_bpm = chunk_in.summary.fhr_estimate_bpm
        if chunk_in.summary.maternal_hr_bpm is not None:
            summary.maternal_hr_bpm = chunk_in.summary.maternal_hr_bpm
        if chunk_in.summary.signal_quality_index is not None:
            summary.signal_quality_index = chunk_in.summary.signal_quality_index
        if chunk_in.summary.contraction_indicator is not None:
            summary.contraction_indicator = chunk_in.summary.contraction_indicator.value


@router.get("", response_model=list[SessionResponse])
def list_monitoring_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = get_patient_profile_for_user(db, current_user)
    
    sessions = (
        db.query(MonitoringSession)
        .options(joinedload(MonitoringSession.sensor_summary))
        .filter(MonitoringSession.patient_id == patient.id)
        .order_by(MonitoringSession.start_time.desc())
        .all()
    )
    return sessions


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_monitoring_session(
    session_in: SessionCreate | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = session_in
    patient = get_patient_profile_for_user(db, current_user)

    active_session = (
        db.query(MonitoringSession)
        .filter(MonitoringSession.patient_id == patient.id, MonitoringSession.status == "active")
        .first()
    )
    if active_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active monitoring session already exists for this patient",
        )

    monitoring_session = MonitoringSession(patient_id=patient.id, status="active")

    db.add(monitoring_session)
    db.commit()
    db.refresh(monitoring_session)
    return monitoring_session


@router.patch("/{session_id}", response_model=SessionResponse)
def update_monitoring_session(
    session_id: str,
    session_update: SessionUpdate | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = get_patient_profile_for_user(db, current_user)
    monitoring_session = get_owned_session(db, session_id, patient.id)
    update_data = session_update or SessionUpdate()

    monitoring_session.status = update_data.status.value
    if monitoring_session.end_time is None:
        monitoring_session.end_time = datetime.now(timezone.utc)

    db.add(monitoring_session)
    db.commit()
    db.refresh(monitoring_session)
    return monitoring_session


@router.post("/{session_id}/data", response_model=SensorDataChunkResponse, status_code=status.HTTP_201_CREATED)
def create_sensor_data_chunk(
    session_id: str,
    chunk_in: SensorDataChunkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = get_patient_profile_for_user(db, current_user)
    monitoring_session = get_owned_session(db, session_id, patient.id)
    if monitoring_session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sensor data can only be uploaded to an active monitoring session",
        )

    device = get_device_for_upload(db, patient.id, chunk_in)
    stored_payload = chunk_in.to_stored_payload()
    chunk = SensorDataChunk(session_id=monitoring_session.id, payload=stored_payload)
    db.add(chunk)
    upsert_session_sensor_summary(db, monitoring_session, device, chunk_in, stored_payload)
    db.commit()
    db.refresh(chunk)
    return chunk
