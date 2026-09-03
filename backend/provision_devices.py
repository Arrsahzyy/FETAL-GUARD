"""Provision a batch of belts: register them, issue signing keys and claim codes.

This is the manufacturing-side step of device onboarding. It runs once per unit
and produces the two secrets a belt needs:

* the packet signing key, which is flashed into firmware, and
* the claim code, which is printed on the belt so a patient can pair it
  themselves without an admin.

Both are disclosed exactly once, here. Nothing can read them back afterwards --
losing the output means re-provisioning the unit.

The CSV it writes therefore contains live secrets. Treat it as a credential file:
keep it off shared drives, hand it to whoever does the flashing and label
printing, and delete it once the batch is built.

Usage:
    python provision_devices.py --count 10 --prefix FG-BELT --out batch-01.csv
    python provision_devices.py --uids FG-BELT-001,FG-BELT-002 --out batch.csv

Options:
    --organization  Organization ID to register into (default: the default org)
    --hardware      hardware_revision to record, e.g. bench-demo
    --firmware      firmware_version to record
    --dry-run       Show what would be created without writing anything
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys

from sqlalchemy.exc import IntegrityError

from core.device_auth import generate_device_secret
from core.device_claim import generate_claim_code, hash_claim_code
from core.tenancy import DEFAULT_ORGANIZATION_ID, ensure_default_organization
from db.database import SessionLocal
# Every mapper has to be imported before the first query, or SQLAlchemy cannot
# resolve the relationship() strings between them.
from models.access_audit_event import AccessAuditEvent  # noqa: F401
from models.admin_audit_log import AdminAuditLog  # noqa: F401
from models.ai_analysis import (  # noqa: F401
    AIAnalysisResult,
    AIAnalysisReview,
    AIInferenceJob,
    AIModelVersion,
)
from models.alert_event import AlertEvent  # noqa: F401
from models.auth_login_attempt import AuthLoginAttempt  # noqa: F401
from models.auth_refresh_token import AuthRefreshToken  # noqa: F401
from models.device import Device
from models.device_assignment import DeviceAssignment  # noqa: F401
from models.device_claim_attempt import DeviceClaimAttempt  # noqa: F401
from models.notification import Notification  # noqa: F401
from models.organization import Organization  # noqa: F401
from models.organization_membership import OrganizationMembership  # noqa: F401
from models.patient import Patient  # noqa: F401
from models.patient_clinician_assignment import PatientClinicianAssignment  # noqa: F401
from models.realtime_event import RealtimeEvent, RealtimeEventCursor  # noqa: F401
from models.sensor_data import SensorDataChunk  # noqa: F401
from models.session import MonitoringSession  # noqa: F401
from models.session_sensor_summary import SessionSensorSummary  # noqa: F401
from models.user import User  # noqa: F401

CSV_COLUMNS = [
    "device_uid",
    "device_id",
    "claim_code",
    "packet_secret",
    "hardware_revision",
    "firmware_version",
    "provisioned_at",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, help="How many units to provision, with generated UIDs")
    parser.add_argument("--prefix", default="FG-BELT", help="UID prefix when using --count")
    parser.add_argument("--start", type=int, default=1, help="First sequence number when using --count")
    parser.add_argument("--uids", help="Comma-separated explicit device UIDs")
    parser.add_argument("--organization", default=None, help="Organization ID to register into")
    parser.add_argument("--hardware", default=None, help="hardware_revision to record")
    parser.add_argument("--firmware", default=None, help="firmware_version to record")
    parser.add_argument("--out", default=None, help="CSV path for the provisioning output")
    parser.add_argument("--dry-run", action="store_true", help="Do not write anything")
    return parser.parse_args()


def resolve_device_uids(arguments: argparse.Namespace) -> list[str]:
    if arguments.uids:
        uids = [uid.strip().upper() for uid in arguments.uids.split(",") if uid.strip()]
    elif arguments.count:
        uids = [
            f"{arguments.prefix}-{number:03d}".upper()
            for number in range(arguments.start, arguments.start + arguments.count)
        ]
    else:
        raise SystemExit("Provide either --count or --uids. See --help.")

    duplicates = {uid for uid in uids if uids.count(uid) > 1}
    if duplicates:
        raise SystemExit(f"Duplicate UIDs requested: {', '.join(sorted(duplicates))}")
    return uids


def main() -> int:
    arguments = parse_arguments()
    device_uids = resolve_device_uids(arguments)

    output_path = Path(arguments.out) if arguments.out else None
    if output_path and output_path.exists():
        raise SystemExit(
            f"{output_path} already exists. Refusing to overwrite a file that may hold "
            "secrets for a previous batch."
        )

    session = SessionLocal()
    provisioned: list[dict[str, str]] = []
    try:
        organization_id = arguments.organization
        if organization_id is None:
            ensure_default_organization(session)
            organization_id = DEFAULT_ORGANIZATION_ID

        existing = {
            device.device_uid
            for device in session.query(Device).filter(Device.device_uid.in_(device_uids)).all()
        }
        if existing:
            raise SystemExit(
                "These UIDs are already registered: " + ", ".join(sorted(existing))
                + "\nRe-provisioning an existing unit would invalidate its flashed key; "
                "rotate it through the API instead."
            )

        now = datetime.now(timezone.utc)
        for device_uid in device_uids:
            claim_code = generate_claim_code()
            packet_secret = generate_device_secret()
            device = Device(
                organization_id=organization_id,
                device_uid=device_uid,
                display_name="FETAL-GUARD Belt",
                hardware_revision=arguments.hardware,
                firmware_version=arguments.firmware,
                # Ships unassigned and unusable until a patient claims it.
                status="registered",
                packet_secret=packet_secret,
                packet_secret_provisioned_at=now,
                claim_code_hash=hash_claim_code(claim_code),
                claim_code_set_at=now,
            )
            session.add(device)
            session.flush()
            provisioned.append({
                "device_uid": device_uid,
                "device_id": device.id,
                "claim_code": claim_code,
                "packet_secret": packet_secret,
                "hardware_revision": arguments.hardware or "",
                "firmware_version": arguments.firmware or "",
                "provisioned_at": now.isoformat(),
            })

        if arguments.dry_run:
            session.rollback()
            print(f"Dry run: would provision {len(provisioned)} device(s).")
            for record in provisioned:
                print(f"  {record['device_uid']}")
            return 0

        session.commit()
    except IntegrityError as error:
        session.rollback()
        print(f"Provisioning failed, nothing was written: {error}", file=sys.stderr)
        return 1
    finally:
        session.close()

    print(f"Provisioned {len(provisioned)} device(s).")
    if output_path:
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(provisioned)
        print(f"Wrote {output_path}")
        print(
            "\nThis file contains signing keys and claim codes in clear text.\n"
            "Flash the keys, print the claim codes, then delete it."
        )
    else:
        print("\nNo --out given, so the secrets are shown once here only:\n")
        for record in provisioned:
            print(f"  {record['device_uid']}")
            print(f"    claim code    : {record['claim_code']}")
            print(f"    signing key   : {record['packet_secret']}")
        print("\nCopy these now. They cannot be read back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
