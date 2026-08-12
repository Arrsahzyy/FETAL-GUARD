from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import re
import uuid
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from models.realtime_event import RealtimeEvent, RealtimeEventCursor


_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,179}$")
_RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
_EVENT_METADATA_FIELDS = {
    "ai.analysis.updated": frozenset(
        {"quality_status", "screening_status", "visibility", "version"}
    ),
    "alert.created": frozenset({"risk_level", "status", "version"}),
    "alert.updated": frozenset({"risk_level", "status", "version"}),
    "care_assignment.updated": frozenset({"care_role", "state"}),
    "device.updated": frozenset({"assignment_state", "status"}),
    "session.completed": frozenset({"status"}),
    "session.started": frozenset({"has_device", "status"}),
    "telemetry.updated": frozenset(
        {"captured_at", "received_at", "sample_count", "source"}
    ),
}
_RESOURCE_TYPES_BY_EVENT = {
    "ai.analysis.updated": "ai_analysis",
    "alert.created": "alert",
    "alert.updated": "alert",
    "care_assignment.updated": "care_assignment",
    "device.updated": "device",
    "session.completed": "session",
    "session.started": "session",
    "telemetry.updated": "session",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_metadata_value(value: Any) -> str | int | float | bool | None:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat()
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str):
            return value.strip()[:120]
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Realtime event metadata must contain finite numbers")
        return value
    if hasattr(value, "value"):
        return _normalize_metadata_value(value.value)
    raise ValueError("Realtime event metadata must be scalar")


def sanitize_realtime_event_payload(event_type: str, payload: dict[str, Any] | None) -> dict:
    allowed_fields = _EVENT_METADATA_FIELDS.get(event_type)
    if allowed_fields is None:
        raise ValueError("Unsupported realtime event type")

    candidate = payload or {}
    unknown_fields = sorted(set(candidate) - allowed_fields)
    if unknown_fields:
        raise ValueError(
            "Unsupported realtime event metadata: " + ", ".join(unknown_fields)
        )
    sanitized = {
        key: _normalize_metadata_value(value)
        for key, value in candidate.items()
    }
    if len(json.dumps(sanitized, separators=(",", ":"), ensure_ascii=True)) > 2048:
        raise ValueError("Realtime event metadata exceeds the safe size limit")
    return sanitized


def _next_facility_cursor(db: Session, organization_id: str, now: datetime) -> int:
    values = {
        "organization_id": organization_id,
        "last_cursor": 1,
        "updated_at": now,
    }
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        statement = postgresql_insert(RealtimeEventCursor).values(**values)
    elif dialect_name == "sqlite":
        statement = sqlite_insert(RealtimeEventCursor).values(**values)
    else:
        cursor_state = (
            db.query(RealtimeEventCursor)
            .filter(RealtimeEventCursor.organization_id == organization_id)
            .with_for_update()
            .first()
        )
        if cursor_state is None:
            cursor_state = RealtimeEventCursor(**values)
            db.add(cursor_state)
        else:
            cursor_state.last_cursor += 1
            cursor_state.updated_at = now
        db.flush()
        return int(cursor_state.last_cursor)

    statement = statement.on_conflict_do_update(
        index_elements=[RealtimeEventCursor.organization_id],
        set_={
            "last_cursor": RealtimeEventCursor.last_cursor + 1,
            "updated_at": now,
        },
    ).returning(RealtimeEventCursor.last_cursor)
    return int(db.execute(statement).scalar_one())


def enqueue_realtime_event(
    db: Session,
    *,
    organization_id: str,
    patient_id: str,
    event_type: str,
    resource_id: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> RealtimeEvent:
    """Append one minimal event inside the caller's database transaction.

    The unique idempotency key makes retries safe. The caller remains
    responsible for committing or rolling back the surrounding domain change.
    """

    if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key):
        raise ValueError("Invalid realtime event idempotency key")
    if not _RESOURCE_ID_PATTERN.fullmatch(resource_id):
        raise ValueError("Invalid realtime event resource identifier")
    resource_type = _RESOURCE_TYPES_BY_EVENT.get(event_type)
    if resource_type is None:
        raise ValueError("Unsupported realtime event type")
    safe_payload = sanitize_realtime_event_payload(event_type, payload)

    existing = db.execute(
        select(RealtimeEvent).where(
            RealtimeEvent.organization_id == organization_id,
            RealtimeEvent.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    now = _utc_now()
    event_time = occurred_at or now
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    else:
        event_time = event_time.astimezone(timezone.utc)
    cursor = _next_facility_cursor(db, organization_id, now)
    realtime_event = RealtimeEvent(
        id=str(uuid.uuid4()),
        organization_id=organization_id,
        patient_id=patient_id,
        cursor=cursor,
        idempotency_key=idempotency_key,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=safe_payload,
        occurred_at=event_time,
        expires_at=event_time + timedelta(hours=settings.REALTIME_EVENT_RETENTION_HOURS),
        created_at=now,
    )
    try:
        with db.begin_nested():
            db.add(realtime_event)
            db.flush()
    except IntegrityError:
        # A concurrent retry can win after the initial lookup. Keep the caller's
        # transaction usable by containing the conflict in a savepoint.
        existing = db.execute(
            select(RealtimeEvent).where(
                RealtimeEvent.organization_id == organization_id,
                RealtimeEvent.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        raise
    return realtime_event


def purge_expired_realtime_events(
    db: Session,
    *,
    now: datetime | None = None,
    batch_size: int = 1000,
) -> int:
    """Delete one bounded batch of expired events for an external scheduler.

    This intentionally does not commit. Retention jobs can compose batches and
    own their transaction/retry policy. The cursor state is never reset.
    """

    if not 1 <= batch_size <= 10_000:
        raise ValueError("batch_size must be between 1 and 10000")
    cutoff = now or _utc_now()
    expired_ids = list(
        db.execute(
            select(RealtimeEvent.id)
            .where(RealtimeEvent.expires_at <= cutoff)
            .order_by(RealtimeEvent.expires_at.asc(), RealtimeEvent.cursor.asc())
            .limit(batch_size)
        ).scalars()
    )
    if not expired_ids:
        return 0
    if db.get_bind().dialect.name == "postgresql":
        # The append-only trigger and RLS policy permit only expired rows while
        # this transaction-local maintenance flag is set. It cannot authorize
        # updates or deletion of events still inside their retention window.
        db.execute(
            text(
                "SELECT set_config('app.realtime_retention_purge', 'on', true)"
            )
        )
    result = db.execute(delete(RealtimeEvent).where(RealtimeEvent.id.in_(expired_ids)))
    return int(result.rowcount or 0)
