from datetime import datetime, timedelta, timezone
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from api.dependencies import get_current_user
from core.config import settings
from core.device_auth import build_signing_message, verify_packet_signature
from core.realtime import enqueue_realtime_event
from services.ai_pipeline import enqueue_ready_window
from services.alerting import evaluate_session_alerts
from services.vitals_derivation import derive_session_vitals
from db.database import get_db
from models.device import Device
from models.device_assignment import DeviceAssignment
from models.patient import Patient
from models.sensor_data import SensorDataChunk
from models.session import MonitoringSession
from models.session_sensor_summary import SessionSensorSummary
from models.user import User
from schemas.sensor_data import SensorDataChunkCreate, SensorDataChunkResponse
from schemas.session import SessionCreate, SessionResponse, SessionUpdate

router = APIRouter()
logger = logging.getLogger(__name__)

REGISTERED_TRANSPORT_SOURCES = frozenset({"device", "ble", "mqtt"})


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


def get_owned_session(
    db: Session,
    session_id: str,
    patient_id: str,
    organization_id: str,
) -> MonitoringSession:
    monitoring_session = (
        db.query(MonitoringSession)
        .filter(
            MonitoringSession.id == session_id,
            MonitoringSession.patient_id == patient_id,
            MonitoringSession.organization_id == organization_id,
        )
        .with_for_update()
        .first()
    )
    if monitoring_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitoring session not found",
        )
    return monitoring_session


def get_active_device_assignment_for_patient(
    db: Session,
    device: Device,
    patient: Patient,
) -> DeviceAssignment:
    assignment = (
        db.query(DeviceAssignment)
        .filter(
            DeviceAssignment.device_id == device.id,
            DeviceAssignment.organization_id == patient.organization_id,
            DeviceAssignment.ends_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if assignment is None or assignment.patient_id != patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not assigned to this patient",
        )
    if device.patient_id != assignment.patient_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DEVICE_ASSIGNMENT_CACHE_CONFLICT",
                "message": "Device registry ownership does not match its active assignment",
            },
        )
    return assignment


def get_device_for_upload(
    db: Session,
    patient: Patient,
    chunk_in: SensorDataChunkCreate,
) -> tuple[Device | None, DeviceAssignment | None]:
    if not chunk_in.device_uid:
        return None, None

    device = (
        db.query(Device)
        .filter(
            Device.device_uid == chunk_in.device_uid,
            Device.organization_id == patient.organization_id,
        )
        .with_for_update()
        .first()
    )
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not registered",
        )
    assignment = get_active_device_assignment_for_patient(db, device, patient)
    if device.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not active",
        )
    return device, assignment


def get_active_patient_device(
    db: Session,
    patient: Patient,
    device_uid: str,
) -> tuple[Device, DeviceAssignment]:
    device = (
        db.query(Device)
        .filter(
            Device.device_uid == device_uid,
            Device.organization_id == patient.organization_id,
        )
        .with_for_update()
        .first()
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not registered")
    assignment = get_active_device_assignment_for_patient(db, device, patient)
    if device.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device is not active")
    return device, assignment


def enforce_production_ingestion_policy(chunk_in: SensorDataChunkCreate) -> None:
    if settings.ENVIRONMENT != "production":
        return
    if chunk_in.source not in REGISTERED_TRANSPORT_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Production sensor ingestion requires registered-device transport metadata",
        )
    if chunk_in.is_simulated is True or chunk_in.summary is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Simulated or client-derived sensor summaries are disabled in production",
        )
    payload_timestamp_ms = chunk_in.payload.t
    if payload_timestamp_ms is None or chunk_in.captured_at is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Production device packets require capture timestamps",
        )
    captured_timestamp_ms = int(chunk_in.captured_at.timestamp() * 1000)
    if abs(payload_timestamp_ms - captured_timestamp_ms) > 5000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="payload.t does not match captured_at",
        )


def enforce_device_packet_authentication(
    device: Device | None,
    chunk_in: SensorDataChunkCreate,
) -> None:
    """Reject telemetry that cannot be proven to come from the provisioned belt.

    A device UID travels in the clear and is reproducible by any BLE peripheral, so
    it establishes which device a packet *claims* to be, never which device sent
    it. Once a device has a provisioned secret, every packet must carry a matching
    HMAC regardless of environment: silently accepting unsigned packets from a
    device known to be capable of signing would defeat the control entirely.
    """
    if device is None:
        return

    secret = device.packet_secret
    if not secret:
        if settings.REQUIRE_DEVICE_PACKET_SIGNATURE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device has no provisioned signing key; re-provision the device before uploading",
            )
        return

    if not chunk_in.packet_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telemetry from a provisioned device must be signed",
        )
    if chunk_in.boot_id is None or chunk_in.sequence_number is None or chunk_in.captured_at is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Signed telemetry requires boot_id, sequence_number, and captured_at",
        )

    message = build_signing_message(
        device_uid=device.device_uid,
        boot_id=chunk_in.boot_id,
        sequence_number=chunk_in.sequence_number,
        captured_at=chunk_in.captured_at,
        schema_version=chunk_in.schema_version,
        channels=chunk_in.payload.model_dump(exclude_none=True),
    )
    if not verify_packet_signature(secret, chunk_in.packet_signature, message):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telemetry signature did not match the registered device key",
        )


def duplicate_chunk_response(chunk: SensorDataChunk) -> dict:
    return {
        "id": chunk.id,
        "organization_id": chunk.organization_id,
        "session_id": chunk.session_id,
        "timestamp": chunk.timestamp,
        "device_id": chunk.device_id,
        "ingestion_id": chunk.ingestion_id,
        "boot_id": chunk.boot_id,
        "sequence_number": chunk.sequence_number,
        "schema_version": chunk.schema_version,
        "captured_at": chunk.captured_at,
        "was_duplicate": True,
    }


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_device_packet_timeline(
    db: Session,
    device: Device | None,
    chunk_in: SensorDataChunkCreate,
) -> None:
    if (
        device is None
        or chunk_in.boot_id is None
        or chunk_in.sequence_number is None
        or chunk_in.captured_at is None
    ):
        return

    base_query = db.query(SensorDataChunk).filter(
        SensorDataChunk.device_id == device.id,
        SensorDataChunk.boot_id == chunk_in.boot_id,
        SensorDataChunk.captured_at.is_not(None),
    )
    previous = (
        base_query.filter(SensorDataChunk.sequence_number < chunk_in.sequence_number)
        .order_by(SensorDataChunk.sequence_number.desc())
        .first()
    )
    following = (
        base_query.filter(SensorDataChunk.sequence_number > chunk_in.sequence_number)
        .order_by(SensorDataChunk.sequence_number.asc())
        .first()
    )
    captured_at = normalize_utc(chunk_in.captured_at)
    if previous and previous.captured_at and captured_at < normalize_utc(previous.captured_at):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Packet captured_at is older than the preceding device sequence",
        )
    if following and following.captured_at and captured_at > normalize_utc(following.captured_at):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Packet captured_at is newer than the following device sequence",
        )


def bind_session_to_device(
    db: Session,
    monitoring_session: MonitoringSession,
    device: Device | None,
    assignment: DeviceAssignment | None,
) -> None:
    if device is None:
        if monitoring_session.device_id is None and monitoring_session.device_assignment_id is None:
            return
        if monitoring_session.device_id is None or monitoring_session.device_assignment_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Monitoring session has an incomplete device assignment binding",
            )
        bound_assignment = (
            db.query(DeviceAssignment.id)
            .filter(
                DeviceAssignment.id == monitoring_session.device_assignment_id,
                DeviceAssignment.device_id == monitoring_session.device_id,
                DeviceAssignment.patient_id == monitoring_session.patient_id,
                DeviceAssignment.organization_id == monitoring_session.organization_id,
                DeviceAssignment.ends_at.is_(None),
            )
            .first()
        )
        if bound_assignment is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Monitoring session device assignment is no longer active",
            )
        return
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device has no active patient assignment",
        )
    if (
        assignment.device_id != device.id
        or assignment.patient_id != monitoring_session.patient_id
        or assignment.organization_id != monitoring_session.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device assignment does not match this monitoring session",
        )
    if monitoring_session.device_id is not None:
        if (
            monitoring_session.device_id != device.id
            or monitoring_session.device_assignment_id != assignment.id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Monitoring session is bound to a different device",
            )
        return

    conflicting_session = (
        db.query(MonitoringSession.id)
        .filter(
            MonitoringSession.device_id == device.id,
            MonitoringSession.status == "active",
            MonitoringSession.id != monitoring_session.id,
        )
        .first()
    )
    if conflicting_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device already has an active monitoring session",
        )

    monitoring_session.device_id = device.id
    monitoring_session.device_assignment_id = assignment.id
    db.add(monitoring_session)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device already has an active monitoring session",
        )


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
            organization_id=monitoring_session.organization_id,
            session_id=monitoring_session.id,
            source=chunk_in.source or ("device" if device else "manual"),
            is_simulated=bool(chunk_in.is_simulated),
        )
        db.add(summary)

    incoming_source = chunk_in.source or ("device" if device else "manual")
    if device:
        summary.device_id = device.id
        device.last_seen_at = now
    summary.sample_count = max(0, summary.sample_count or 0) + count_sensor_samples(stored_payload)
    if summary.sample_count > count_sensor_samples(stored_payload) and summary.source != incoming_source:
        summary.source = "mixed"
    else:
        summary.source = incoming_source
    summary.is_simulated = bool(summary.is_simulated or chunk_in.is_simulated)
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
        return

    # Device uploads cannot supply a summary at all (the schema rejects it), so
    # their clinical values come from the server's own reading of the raw
    # channels rather than from anything the phone computed.
    db.flush()
    rederived = derive_session_vitals(db, monitoring_session, summary)
    # Alerts are raised only from those server-derived values, never from a
    # client-supplied summary, and never for simulated sessions. Evaluating only
    # on a fresh derivation keeps the dedup lookups off the packets in between,
    # which change nothing the rules read.
    if rederived and not summary.is_simulated:
        evaluate_session_alerts(db, monitoring_session, summary)


@router.get("/active", response_model=SessionResponse)
def get_active_monitoring_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = get_patient_profile_for_user(db, current_user)
    monitoring_session = (
        db.query(MonitoringSession)
        .options(joinedload(MonitoringSession.sensor_summary))
        .filter(
            MonitoringSession.patient_id == patient.id,
            MonitoringSession.organization_id == patient.organization_id,
            MonitoringSession.status == "active",
        )
        .first()
    )
    if monitoring_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active monitoring session not found",
        )
    return monitoring_session


@router.get("", response_model=list[SessionResponse])
def list_monitoring_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = get_patient_profile_for_user(db, current_user)
    
    sessions = (
        db.query(MonitoringSession)
        .options(joinedload(MonitoringSession.sensor_summary))
        .filter(
            MonitoringSession.patient_id == patient.id,
            MonitoringSession.organization_id == patient.organization_id,
        )
        .order_by(MonitoringSession.start_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return sessions


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_monitoring_session(
    session_in: SessionCreate | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request_data = session_in or SessionCreate()
    patient = get_patient_profile_for_user(db, current_user)

    if request_data.client_session_id:
        existing_request = (
            db.query(MonitoringSession)
            .options(joinedload(MonitoringSession.sensor_summary))
            .filter(
                MonitoringSession.patient_id == patient.id,
                MonitoringSession.organization_id == patient.organization_id,
                MonitoringSession.client_session_id == request_data.client_session_id,
            )
            .first()
        )
        if existing_request is not None:
            return existing_request

    device = None
    device_assignment = None
    if request_data.device_uid:
        device, device_assignment = get_active_patient_device(
            db,
            patient,
            request_data.device_uid,
        )
        if request_data.client_session_id:
            existing_request = (
                db.query(MonitoringSession)
                .options(joinedload(MonitoringSession.sensor_summary))
                .filter(
                    MonitoringSession.patient_id == patient.id,
                    MonitoringSession.organization_id == patient.organization_id,
                    MonitoringSession.client_session_id == request_data.client_session_id,
                )
                .first()
            )
            if existing_request is not None:
                return existing_request
        device_session = (
            db.query(MonitoringSession.id)
            .filter(
                MonitoringSession.device_id == device.id,
                MonitoringSession.organization_id == patient.organization_id,
                MonitoringSession.status == "active",
            )
            .first()
        )
        if device_session is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Device already has an active monitoring session",
            )

    active_session = (
        db.query(MonitoringSession)
        .filter(
            MonitoringSession.patient_id == patient.id,
            MonitoringSession.organization_id == patient.organization_id,
            MonitoringSession.status == "active",
        )
        .first()
    )
    if active_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active monitoring session already exists for this patient",
        )

    monitoring_session = MonitoringSession(
        organization_id=patient.organization_id,
        patient_id=patient.id,
        device_id=device.id if device else None,
        device_assignment_id=device_assignment.id if device_assignment else None,
        client_session_id=request_data.client_session_id,
        status="active",
    )

    db.add(monitoring_session)
    try:
        db.flush()
        enqueue_realtime_event(
            db,
            organization_id=patient.organization_id,
            patient_id=patient.id,
            event_type="session.started",
            resource_id=monitoring_session.id,
            idempotency_key=f"session.started:{monitoring_session.id}",
            payload={
                "status": monitoring_session.status,
                "has_device": device is not None,
            },
            occurred_at=monitoring_session.start_time,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        if request_data.client_session_id:
            existing_request = (
                db.query(MonitoringSession)
                .options(joinedload(MonitoringSession.sensor_summary))
                .filter(
                    MonitoringSession.patient_id == patient.id,
                    MonitoringSession.organization_id == patient.organization_id,
                    MonitoringSession.client_session_id == request_data.client_session_id,
                )
                .first()
            )
            if existing_request is not None:
                return existing_request
        if device is not None:
            device_session = (
                db.query(MonitoringSession.id)
                .filter(
                    MonitoringSession.device_id == device.id,
                    MonitoringSession.organization_id == patient.organization_id,
                    MonitoringSession.status == "active",
                )
                .first()
            )
            if device_session is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Device already has an active monitoring session",
                )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active monitoring session already exists for this patient",
        )
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
    monitoring_session = get_owned_session(
        db,
        session_id,
        patient.id,
        patient.organization_id,
    )
    update_data = session_update or SessionUpdate()

    if monitoring_session.status != "active":
        if monitoring_session.status == update_data.status.value:
            return monitoring_session
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A completed monitoring session cannot change status",
        )

    monitoring_session.status = update_data.status.value
    if monitoring_session.end_time is None:
        monitoring_session.end_time = datetime.now(timezone.utc)

    db.add(monitoring_session)
    enqueue_realtime_event(
        db,
        organization_id=monitoring_session.organization_id,
        patient_id=monitoring_session.patient_id,
        event_type="session.completed",
        resource_id=monitoring_session.id,
        idempotency_key=(
            f"session.completed:{monitoring_session.id}:{monitoring_session.status}"
        ),
        payload={"status": monitoring_session.status},
        occurred_at=monitoring_session.end_time,
    )
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
    enforce_production_ingestion_policy(chunk_in)
    # Lock the device before the session in every device-ingestion path. This
    # gives PostgreSQL a consistent lock order and serializes packets for one
    # physical device without relying on process-local locks.
    device, device_assignment = get_device_for_upload(db, patient, chunk_in)
    enforce_device_packet_authentication(device, chunk_in)
    monitoring_session = get_owned_session(
        db,
        session_id,
        patient.id,
        patient.organization_id,
    )
    if monitoring_session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sensor data can only be uploaded to an active monitoring session",
        )

    bind_session_to_device(db, monitoring_session, device, device_assignment)

    duplicate = (
        db.query(SensorDataChunk)
        .filter(
            SensorDataChunk.session_id == monitoring_session.id,
            SensorDataChunk.ingestion_id == chunk_in.ingestion_id,
        )
        .first()
    )
    if duplicate is not None:
        return duplicate_chunk_response(duplicate)

    if device and chunk_in.boot_id is not None and chunk_in.sequence_number is not None:
        replayed_packet = (
            db.query(SensorDataChunk)
            .filter(
                SensorDataChunk.device_id == device.id,
                SensorDataChunk.boot_id == chunk_in.boot_id,
                SensorDataChunk.sequence_number == chunk_in.sequence_number,
            )
            .first()
        )
        if replayed_packet is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Packet sequence was already ingested",
            )

    stored_payload = chunk_in.to_stored_payload()
    now = datetime.now(timezone.utc)
    if chunk_in.captured_at:
        session_started_at = monitoring_session.start_time
        if session_started_at.tzinfo is None:
            session_started_at = session_started_at.replace(tzinfo=timezone.utc)
        if chunk_in.captured_at > now + timedelta(minutes=5):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="captured_at is too far in the future",
            )
        if chunk_in.captured_at < session_started_at - timedelta(minutes=5):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="captured_at predates this monitoring session",
            )
    validate_device_packet_timeline(db, device, chunk_in)

    monitoring_session.last_data_at = now
    if chunk_in.captured_at is not None and (
        monitoring_session.last_captured_at is None
        or normalize_utc(chunk_in.captured_at) > normalize_utc(monitoring_session.last_captured_at)
    ):
        monitoring_session.last_captured_at = chunk_in.captured_at
    monitoring_session_id = monitoring_session.id
    device_id = device.id if device else None
    chunk = SensorDataChunk(
        organization_id=monitoring_session.organization_id,
        session_id=monitoring_session_id,
        device_id=device_id,
        ingestion_id=chunk_in.ingestion_id,
        boot_id=chunk_in.boot_id,
        sequence_number=chunk_in.sequence_number,
        schema_version=chunk_in.schema_version,
        captured_at=chunk_in.captured_at,
        timestamp=now,
        payload=stored_payload,
    )
    db.add(chunk)
    upsert_session_sensor_summary(db, monitoring_session, device, chunk_in, stored_payload)
    enqueue_realtime_event(
        db,
        organization_id=monitoring_session.organization_id,
        patient_id=monitoring_session.patient_id,
        event_type="telemetry.updated",
        resource_id=monitoring_session.id,
        idempotency_key=f"telemetry:{monitoring_session.id}:{chunk_in.ingestion_id}",
        payload={
            "captured_at": chunk_in.captured_at,
            "received_at": now,
            "sample_count": count_sensor_samples(stored_payload),
            "source": chunk_in.source or ("device" if device else "manual"),
        },
        occurred_at=now,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = (
            db.query(SensorDataChunk)
            .filter(
                SensorDataChunk.session_id == monitoring_session_id,
                SensorDataChunk.ingestion_id == chunk_in.ingestion_id,
            )
            .first()
        )
        if duplicate is None and device_id and chunk_in.boot_id is not None and chunk_in.sequence_number is not None:
            duplicate = (
                db.query(SensorDataChunk)
                .filter(
                    SensorDataChunk.device_id == device_id,
                    SensorDataChunk.boot_id == chunk_in.boot_id,
                    SensorDataChunk.sequence_number == chunk_in.sequence_number,
                )
                .first()
            )
        if duplicate is not None:
            return duplicate_chunk_response(duplicate)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sensor packet conflicted with the active device session",
        )
    try:
        job = enqueue_ready_window(
            db,
            monitoring_session=monitoring_session,
            latest_chunk=chunk,
        )
        if job is not None:
            db.commit()
    except Exception:
        # Telemetry is the source record and must remain durable even when the
        # derived AI queue is unavailable. Readiness/worker monitoring must
        # surface this failure; the next packet can idempotently retry the same
        # aligned window.
        db.rollback()
        logger.exception(
            "AI inference window could not be queued",
            extra={"session_id": monitoring_session_id, "ingestion_id": chunk_in.ingestion_id},
        )
    db.refresh(chunk)
    return chunk
