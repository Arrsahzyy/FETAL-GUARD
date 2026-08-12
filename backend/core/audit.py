import json
from collections.abc import Mapping
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from models.access_audit_event import AccessAuditEvent


_FORBIDDEN_DETAIL_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "authorization",
        "password",
        "temporary_password",
        "national_id",
        "medical_history",
        "sensor_payload",
        "raw_data",
    }
)
_FORBIDDEN_COMPACT_DETAIL_KEYS = frozenset(key.replace("_", "") for key in _FORBIDDEN_DETAIL_KEYS)

_MAX_DETAIL_DEPTH = 4
_MAX_DETAIL_ITEMS = 50
_MAX_DETAIL_STRING_LENGTH = 500
_MAX_SERIALIZED_DETAIL_LENGTH = 4000


def _normalized_key(value: object) -> str:
    return "_".join(
        part for part in "".join(
            character.lower() if character.isalnum() else " "
            for character in str(value)
        ).split()
        if part
    )


def _sanitize_value(value: Any, *, depth: int) -> Any:
    if depth > _MAX_DETAIL_DEPTH:
        return "[TRUNCATED]"
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for index, (key, nested_value) in enumerate(value.items()):
            if index >= _MAX_DETAIL_ITEMS:
                sanitized["_truncated"] = True
                break
            normalized = _normalized_key(key)
            sanitized[str(key)] = (
                "[REDACTED]"
                if (
                    normalized in _FORBIDDEN_DETAIL_KEYS
                    or normalized.replace("_", "") in _FORBIDDEN_COMPACT_DETAIL_KEYS
                )
                else _sanitize_value(nested_value, depth=depth + 1)
            )
        return sanitized
    if isinstance(value, (list, tuple, set, frozenset)):
        values = list(value)
        sanitized_values = [
            _sanitize_value(item, depth=depth + 1)
            for item in values[:_MAX_DETAIL_ITEMS]
        ]
        if len(values) > _MAX_DETAIL_ITEMS:
            sanitized_values.append("[TRUNCATED]")
        return sanitized_values
    if isinstance(value, str):
        return value[:_MAX_DETAIL_STRING_LENGTH]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:_MAX_DETAIL_STRING_LENGTH]


def _sanitize_details(details: Mapping[str, Any] | None) -> str | None:
    if not details:
        return None
    serialized = json.dumps(_sanitize_value(details, depth=0), sort_keys=True, default=str)
    return serialized[:_MAX_SERIALIZED_DETAIL_LENGTH]


def add_access_audit_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    outcome: str,
    actor_user_id: str | None = None,
    actor_membership_id: str | None = None,
    organization_id: str | None = None,
    patient_id: str | None = None,
    resource_id: str | None = None,
    purpose: str | None = None,
    request: Request | None = None,
    details: Mapping[str, Any] | None = None,
) -> AccessAuditEvent:
    request_id = None
    client_ip = None
    user_agent = None
    if request is not None:
        request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")

    event = AccessAuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_membership_id=actor_membership_id,
        patient_id=patient_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        purpose=purpose,
        outcome=outcome,
        request_id=request_id,
        client_ip=client_ip,
        user_agent=user_agent[:500] if user_agent else None,
        details=_sanitize_details(details),
    )
    db.add(event)
    return event
