"""Cryptographic packet authentication for registered FETAL-GUARD devices.

A device UID and the BLE advertised name are both public labels: any peripheral in
range can reproduce them, so UID matching alone never proves that a telemetry
packet came from the physical belt provisioned for a patient. Each device
therefore carries a symmetric secret that is generated here, flashed into firmware
once during provisioning, and afterwards only ever leaves the database to verify a
signature. Firmware signs its identity tuple together with a digest of the raw
samples, and the API recomputes that signature before storing anything.

The signed message is assembled from parsed values rather than from JSON text, so
it survives re-serialisation by the phone gateway and does not depend on key
ordering, whitespace, or float formatting anywhere along the path:

    FGSIG1|<device_uid>|<boot_id>|<sequence_number>|<captured_at_ms>|<schema_version>|<payload_digest>

`captured_at` is signed as integer milliseconds since the Unix epoch because that
is the value firmware actually holds; deriving it from an ISO string on either
side would make the signature depend on formatting choices.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_ONE_MILLISECOND = timedelta(milliseconds=1)

# Ordered so both firmware and backend walk the channels identically.
SIGNED_CHANNEL_ORDER = ("p", "fsr", "hr_ir", "hr_red")
SIGNATURE_PREFIX = "FGSIG1"
DEVICE_SECRET_BYTES = 32
# hex(HMAC-SHA256) is always 64 characters.
SIGNATURE_LENGTH = 64


def generate_device_secret() -> str:
    """Return a new device secret as lowercase hex, shown to an admin only once."""
    return secrets.token_hex(DEVICE_SECRET_BYTES)


def captured_at_to_epoch_ms(captured_at: datetime) -> int:
    """Normalise a timezone-aware timestamp to the integer milliseconds firmware signs.

    Derived with exact timedelta arithmetic rather than ``timestamp() * 1000``:
    that float round-trip lands a millisecond low often enough to break otherwise
    valid signatures at random.
    """
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware to be signed")
    return (captured_at.astimezone(timezone.utc) - _UNIX_EPOCH) // _ONE_MILLISECOND


def compute_payload_digest(channels: dict[str, list[int] | None]) -> str:
    """Hash the raw sample values so a signature also binds the packet contents.

    Absent channels are folded in as empty so that dropping a channel changes the
    digest instead of producing the same hash as a packet that never carried it.
    """
    parts: list[str] = []
    for name in SIGNED_CHANNEL_ORDER:
        values = channels.get(name) or []
        parts.append(f"{name}:" + ",".join(str(int(value)) for value in values))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_signing_message(
    *,
    device_uid: str,
    boot_id: str,
    sequence_number: int,
    captured_at: datetime,
    schema_version: int,
    channels: dict[str, list[int] | None],
) -> str:
    """Build the exact string firmware signs for one telemetry packet."""
    return "|".join(
        (
            SIGNATURE_PREFIX,
            device_uid,
            boot_id,
            str(sequence_number),
            str(captured_at_to_epoch_ms(captured_at)),
            str(schema_version),
            compute_payload_digest(channels),
        )
    )


def sign_packet(secret: str, message: str) -> str:
    """Return the lowercase hex HMAC-SHA256 a device is expected to transmit."""
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_packet_signature(secret: str, signature: str, message: str) -> bool:
    """Constant-time comparison of a received signature against the expected one."""
    if not secret or not signature:
        return False
    candidate = signature.strip().lower()
    if len(candidate) != SIGNATURE_LENGTH:
        return False
    return hmac.compare_digest(candidate, sign_packet(secret, message))
