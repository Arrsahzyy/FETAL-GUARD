import json

from core.audit import _sanitize_details


def test_access_audit_recursively_redacts_sensitive_values_and_bounds_payload():
    serialized = _sanitize_details(
        {
            "request": {
                "sensorPayload": {"p": [1, 2, 3]},
                "nested": {"medical-history": "sensitive"},
            },
            "safe": "x" * 800,
        }
    )

    assert serialized is not None
    assert len(serialized) <= 4000
    details = json.loads(serialized)
    assert details["request"]["sensorPayload"] == "[REDACTED]"
    assert details["request"]["nested"]["medical-history"] == "[REDACTED]"
    assert len(details["safe"]) == 500
