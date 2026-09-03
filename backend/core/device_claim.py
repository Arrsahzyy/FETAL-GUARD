"""Claim codes that let a patient bind a belt to themselves without an admin.

A device UID travels in BLE advertising data, so it proves nothing about who is
holding the belt: in a room with several identical belts, UID alone would let one
patient bind a belt strapped to someone else and route that pregnancy's readings
into the wrong record. The claim code is printed on the physical device, so
entering it demonstrates physical possession -- the same trust model as the WiFi
password on the back of a router.

The code is stored only as a bcrypt hash. It is disclosed once, at provisioning
time, and is never readable back through the API.

Encoding is Crockford Base32: the alphabet omits I, L, O and U, and decoding maps
the shapes people actually confuse (I and L to 1, O to 0), so a code read off a
sticker survives being typed by hand.
"""

from __future__ import annotations

import secrets

from core.security import get_password_hash, verify_password

CLAIM_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CLAIM_CODE_LENGTH = 8
CLAIM_CODE_GROUP_SIZE = 4
# Shapes a person is likely to transcribe wrongly, mapped to what the alphabet
# actually contains.
_CONFUSABLE_CHARACTERS = {"I": "1", "L": "1", "O": "0", "U": "V"}
_SEPARATORS = {"-", " ", "\t", "_"}


def generate_claim_code() -> str:
    """Return a new claim code, grouped for printing (e.g. ``4H7K-N2QP``)."""
    raw = "".join(secrets.choice(CLAIM_CODE_ALPHABET) for _ in range(CLAIM_CODE_LENGTH))
    groups = [
        raw[index : index + CLAIM_CODE_GROUP_SIZE]
        for index in range(0, CLAIM_CODE_LENGTH, CLAIM_CODE_GROUP_SIZE)
    ]
    return "-".join(groups)


def normalize_claim_code(value: str) -> str:
    """Fold a hand-typed code into its canonical form.

    Raises ``ValueError`` for anything that cannot be a claim code, so a
    malformed entry is rejected before it is ever compared against a hash.
    """
    if not isinstance(value, str):
        raise ValueError("Claim code must be text")

    normalized = "".join(
        _CONFUSABLE_CHARACTERS.get(character, character)
        for character in value.strip().upper()
        if character not in _SEPARATORS
    )
    if len(normalized) != CLAIM_CODE_LENGTH:
        raise ValueError(f"Claim code must be {CLAIM_CODE_LENGTH} characters")
    if any(character not in CLAIM_CODE_ALPHABET for character in normalized):
        raise ValueError("Claim code contains characters outside the code alphabet")
    return normalized


def hash_claim_code(code: str) -> str:
    """Hash a normalized claim code for storage."""
    return get_password_hash(normalize_claim_code(code))


def verify_claim_code(code: str, hashed_code: str | None) -> bool:
    """Check a submitted code against the stored hash, failing closed."""
    if not hashed_code:
        return False
    try:
        normalized = normalize_claim_code(code)
    except ValueError:
        return False
    return verify_password(normalized, hashed_code)
