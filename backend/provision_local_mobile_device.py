"""Assign one development device to an already registered local patient.

This helper is intentionally disabled in production. Patient credentials remain
managed by the normal registration and login API; this script only prepares the
device registry needed for an end-to-end hardware test.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import main  # noqa: F401  # Import all mapped models before querying relationships.
from core.config import settings
from db.database import SessionLocal
from models.device import Device
from models.device_assignment import DeviceAssignment
from models.patient import Patient
from models.user import User
from schemas.device import normalize_device_uid


def provision_device(patient_email: str, device_uid: str) -> None:
    if settings.ENVIRONMENT == "production":
        raise RuntimeError("Provisioning lokal dinonaktifkan di production.")

    normalized_email = patient_email.strip().lower()
    normalized_uid = normalize_device_uid(device_uid)
    if "@" not in normalized_email:
        raise RuntimeError("Email pasien tidak valid.")

    db = SessionLocal()
    try:
        patient = (
            db.query(Patient)
            .join(User, Patient.user_id == User.id)
            .filter(User.email == normalized_email, User.role == "patient")
            .first()
        )
        if patient is None:
            raise RuntimeError(
                "Profil pasien belum ada. Daftarkan akun pasien dari aplikasi terlebih dahulu."
            )

        device = db.query(Device).filter(Device.device_uid == normalized_uid).first()
        now = datetime.now(timezone.utc)
        if device is None:
            device = Device(
                organization_id=patient.organization_id,
                device_uid=normalized_uid,
                patient_id=patient.id,
                display_name="FETAL-GUARD Belt",
                firmware_version="local-test",
                status="active",
                assigned_at=now,
            )
            db.add(device)
            db.flush()
            db.add(
                DeviceAssignment(
                    organization_id=patient.organization_id,
                    device_id=device.id,
                    patient_id=patient.id,
                    assigned_by_user_id=None,
                    starts_at=now,
                )
            )
            db.commit()
            print(f"Perangkat {normalized_uid} dibuat dan diaktifkan untuk pasien {normalized_email}.")
            return

        if device.organization_id != patient.organization_id:
            raise RuntimeError("Perangkat terdaftar pada fasilitas lokal yang berbeda.")

        active_assignment = (
            db.query(DeviceAssignment)
            .filter(
                DeviceAssignment.device_id == device.id,
                DeviceAssignment.organization_id == device.organization_id,
                DeviceAssignment.ends_at.is_(None),
            )
            .first()
        )
        if active_assignment is not None and active_assignment.patient_id != patient.id:
            raise RuntimeError("Perangkat masih aktif untuk pasien lokal yang berbeda.")

        if active_assignment is None:
            db.add(
                DeviceAssignment(
                    organization_id=patient.organization_id,
                    device_id=device.id,
                    patient_id=patient.id,
                    assigned_by_user_id=None,
                    starts_at=now,
                )
            )

        device.patient_id = patient.id
        device.status = "active"
        device.assigned_at = device.assigned_at or now
        db.add(device)
        db.commit()
        print(f"Perangkat {normalized_uid} aktif untuk pasien {normalized_email}.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main_cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patient-email", required=True)
    parser.add_argument("--device-uid", default="FETAL-GUARD-001")
    args = parser.parse_args()
    provision_device(args.patient_email, args.device_uid)


if __name__ == "__main__":
    main_cli()
