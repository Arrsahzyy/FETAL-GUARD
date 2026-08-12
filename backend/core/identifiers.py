import secrets


def generate_patient_code() -> str:
    """Generate a non-clinical, human-readable patient directory code.

    The database unique constraint remains the final collision guard.
    """

    return f"FG-{secrets.token_hex(6).upper()}"
