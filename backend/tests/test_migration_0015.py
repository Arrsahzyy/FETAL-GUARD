from __future__ import annotations

import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_COMMAND = (sys.executable, "-m", "alembic")
REVISION_0014 = "20260809_0014"
REVISION_0015 = "20260809_0015"
DEFAULT_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"


def _database_uri(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _run_alembic(path: Path, *arguments: str, success: bool = True) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["SQLALCHEMY_DATABASE_URI"] = _database_uri(path)
    environment["AUTO_CREATE_DB"] = "false"
    result = subprocess.run(
        [*ALEMBIC_COMMAND, *arguments],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = result.stdout + result.stderr
    if success:
        assert result.returncode == 0, output
    else:
        assert result.returncode != 0, output
    return result


@pytest.fixture(scope="session")
def legacy_0014_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    database_path = tmp_path_factory.mktemp("migration-0015") / "legacy-0014.sqlite"
    _run_alembic(database_path, "upgrade", REVISION_0014)
    return database_path


def _copy_legacy_database(source: Path, destination: Path) -> Path:
    shutil.copy2(source, destination)
    return destination


def _insert_user(
    connection: sqlite3.Connection,
    *,
    user_id: str,
    email: str,
    role: str,
) -> None:
    connection.execute(
        "INSERT INTO users "
        "(id, email, hashed_password, role, created_at) VALUES (?, ?, 'unused', ?, ?)",
        (user_id, email, role, "2026-01-01T00:00:00+00:00"),
    )


def _insert_patient(
    connection: sqlite3.Connection,
    *,
    patient_id: str,
    user_id: str,
    organization_id: str,
    code: str,
) -> None:
    connection.execute(
        "INSERT INTO patients "
        "(id, user_id, name, age, gestational_age_weeks, created_at, "
        "organization_id, patient_code) VALUES (?, ?, ?, 30, 28, ?, ?, ?)",
        (
            patient_id,
            user_id,
            f"Patient {code}",
            "2026-01-01T00:00:00+00:00",
            organization_id,
            code,
        ),
    )


def _seed_reassignment_history(connection: sqlite3.Connection) -> dict[str, str]:
    ids = {
        "patient_user_1": "10000000-0000-0000-0000-000000000001",
        "patient_user_2": "10000000-0000-0000-0000-000000000002",
        "clinician_user": "10000000-0000-0000-0000-000000000003",
        "patient_1": "20000000-0000-0000-0000-000000000001",
        "patient_2": "20000000-0000-0000-0000-000000000002",
        "membership": "30000000-0000-0000-0000-000000000001",
        "device": "40000000-0000-0000-0000-000000000001",
        "session_old_patient_1": "50000000-0000-0000-0000-000000000001",
        "session_patient_2": "50000000-0000-0000-0000-000000000002",
        "session_current_completed": "50000000-0000-0000-0000-000000000003",
        "session_current_active": "50000000-0000-0000-0000-000000000004",
    }
    _insert_user(
        connection,
        user_id=ids["patient_user_1"],
        email="migration-p1@example.test",
        role="patient",
    )
    _insert_user(
        connection,
        user_id=ids["patient_user_2"],
        email="migration-p2@example.test",
        role="patient",
    )
    _insert_user(
        connection,
        user_id=ids["clinician_user"],
        email="migration-clinician@example.test",
        role="clinician",
    )
    _insert_patient(
        connection,
        patient_id=ids["patient_1"],
        user_id=ids["patient_user_1"],
        organization_id=DEFAULT_ORGANIZATION_ID,
        code="FG-MIG-P1",
    )
    _insert_patient(
        connection,
        patient_id=ids["patient_2"],
        user_id=ids["patient_user_2"],
        organization_id=DEFAULT_ORGANIZATION_ID,
        code="FG-MIG-P2",
    )
    connection.execute(
        "INSERT INTO organization_memberships "
        "(id, organization_id, user_id, role, created_at) VALUES (?, ?, ?, 'clinician', ?)",
        (
            ids["membership"],
            DEFAULT_ORGANIZATION_ID,
            ids["clinician_user"],
            "2026-01-01T00:00:00+00:00",
        ),
    )
    connection.execute(
        "INSERT INTO devices "
        "(id, device_uid, patient_id, display_name, status, registered_at, assigned_at) "
        "VALUES (?, 'FG-MIGRATION-UNIT', ?, 'Migration unit', 'active', ?, ?)",
        (
            ids["device"],
            ids["patient_1"],
            "2025-12-31T08:00:00+00:00",
            "2026-01-05T08:00:00+00:00",
        ),
    )
    sessions = (
        (
            ids["session_old_patient_1"],
            ids["patient_1"],
            "2026-01-01T09:00:00+00:00",
            "2026-01-01T10:00:00+00:00",
            "completed",
            "legacy-old-p1",
        ),
        (
            ids["session_patient_2"],
            ids["patient_2"],
            "2026-01-02T09:00:00+00:00",
            "2026-01-02T10:00:00+00:00",
            "completed",
            "legacy-p2",
        ),
        (
            ids["session_current_completed"],
            ids["patient_1"],
            "2026-01-06T09:00:00+00:00",
            "2026-01-06T10:00:00+00:00",
            "completed",
            "legacy-current-completed",
        ),
        (
            ids["session_current_active"],
            ids["patient_1"],
            "2026-01-07T09:00:00+00:00",
            None,
            "active",
            "legacy-current-active",
        ),
    )
    connection.executemany(
        "INSERT INTO sessions "
        "(id, patient_id, start_time, end_time, status, device_id, client_session_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(*row[:5], ids["device"], row[5]) for row in sessions],
    )
    connection.execute(
        "INSERT INTO session_data_chunks "
        "(id, session_id, timestamp, payload, device_id, ingestion_id, boot_id, "
        "sequence_number, captured_at) VALUES (?, ?, ?, '{}', ?, 'ingestion-1', "
        "'boot-1', 1, ?)",
        (
            "60000000-0000-0000-0000-000000000001",
            ids["session_current_active"],
            "2026-01-07T09:01:00+00:00",
            ids["device"],
            "2026-01-07T09:01:00+00:00",
        ),
    )
    connection.execute(
        "INSERT INTO session_sensor_summaries "
        "(id, session_id, device_id, contraction_indicator, sample_count, source, "
        "is_simulated, created_at, updated_at) VALUES (?, ?, ?, 'unknown', 1, "
        "'device', 0, ?, ?)",
        (
            "70000000-0000-0000-0000-000000000001",
            ids["session_current_active"],
            ids["device"],
            "2026-01-07T09:01:00+00:00",
            "2026-01-07T09:01:00+00:00",
        ),
    )
    connection.execute(
        "INSERT INTO notifications "
        "(id, session_id, message, risk_level, created_at, status, version, updated_at, "
        "resolved_by_user_id, resolved_at) VALUES (?, ?, 'Legacy resolved alert', "
        "'medium', ?, 'resolved', 2, ?, ?, ?)",
        (
            "80000000-0000-0000-0000-000000000001",
            ids["session_old_patient_1"],
            "2026-01-01T09:30:00+00:00",
            "2026-01-01T10:00:00+00:00",
            ids["clinician_user"],
            "2026-01-01T10:00:00+00:00",
        ),
    )
    connection.execute(
        "INSERT INTO access_audit_events "
        "(id, organization_id, actor_user_id, actor_membership_id, patient_id, "
        "action, resource_type, outcome, created_at) VALUES (?, NULL, ?, ?, ?, "
        "'patient.view', 'patient', 'success', ?)",
        (
            "90000000-0000-0000-0000-000000000001",
            ids["clinician_user"],
            ids["membership"],
            ids["patient_1"],
            "2026-01-07T09:00:00+00:00",
        ),
    )
    connection.commit()
    return ids


def test_fresh_upgrade_schema_and_empty_downgrade(
    legacy_0014_database: Path,
    tmp_path: Path,
) -> None:
    database_path = _copy_legacy_database(
        legacy_0014_database,
        tmp_path / "fresh-upgrade.sqlite",
    )

    _run_alembic(database_path, "upgrade", REVISION_0015)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        session_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
        }
        assert {"organization_id", "device_assignment_id"} <= session_columns

    _run_alembic(database_path, "downgrade", REVISION_0014)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            REVISION_0014,
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'table' AND name = 'device_assignments'"
        ).fetchone() == (0,)


def test_current_head_has_no_model_schema_drift(
    legacy_0014_database: Path,
    tmp_path: Path,
) -> None:
    database_path = _copy_legacy_database(
        legacy_0014_database,
        tmp_path / "current-head.sqlite",
    )
    _run_alembic(database_path, "upgrade", "head")
    _run_alembic(database_path, "check")
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_populated_reassignment_history_is_scoped_and_preserved(
    legacy_0014_database: Path,
    tmp_path: Path,
) -> None:
    database_path = _copy_legacy_database(
        legacy_0014_database,
        tmp_path / "populated-reassignment.sqlite",
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        ids = _seed_reassignment_history(connection)

    _run_alembic(database_path, "upgrade", REVISION_0015)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assignments = connection.execute(
            "SELECT patient_id, version, starts_at, ends_at "
            "FROM device_assignments ORDER BY starts_at"
        ).fetchall()
        assert [(row[0], row[1]) for row in assignments] == [
            (ids["patient_1"], 2),
            (ids["patient_2"], 2),
            (ids["patient_1"], 1),
        ]
        assert assignments[2][2].startswith("2026-01-05 08:00:00")
        assert assignments[2][3] is None

        session_snapshots = connection.execute(
            "SELECT s.id, s.patient_id, a.patient_id, s.organization_id, a.organization_id "
            "FROM sessions AS s JOIN device_assignments AS a "
            "ON a.id = s.device_assignment_id ORDER BY s.start_time"
        ).fetchall()
        assert len(session_snapshots) == 4
        assert all(row[1] == row[2] for row in session_snapshots)
        assert all(row[3] == DEFAULT_ORGANIZATION_ID == row[4] for row in session_snapshots)
        assert session_snapshots[2][0] == ids["session_current_completed"]
        assert session_snapshots[3][0] == ids["session_current_active"]
        current_snapshot_ids = connection.execute(
            "SELECT device_assignment_id FROM sessions "
            "WHERE id IN (?, ?) ORDER BY id",
            (ids["session_current_completed"], ids["session_current_active"]),
        ).fetchall()
        assert current_snapshot_ids[0][0] == current_snapshot_ids[1][0]

        for table_name in (
            "session_data_chunks",
            "session_sensor_summaries",
            "notifications",
            "alert_events",
            "access_audit_events",
        ):
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE organization_id IS NULL"
            ).fetchone() == (0,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT from_status, to_status, version FROM alert_events"
        ).fetchone() == (None, "resolved", 2)

    result = _run_alembic(database_path, "downgrade", REVISION_0014, success=False)
    assert "Downgrade would destroy immutable device assignment history" in (
        result.stdout + result.stderr
    )
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            REVISION_0015,
        )
        assert connection.execute("SELECT COUNT(*) FROM device_assignments").fetchone() == (3,)


def test_unassigned_device_organization_is_inferred_from_unique_session_history(
    legacy_0014_database: Path,
    tmp_path: Path,
) -> None:
    database_path = _copy_legacy_database(
        legacy_0014_database,
        tmp_path / "unassigned-history.sqlite",
    )
    second_organization = "00000000-0000-0000-0000-000000000002"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO organizations (id, slug, name) VALUES (?, 'hospital-two', 'Hospital Two')",
            (second_organization,),
        )
        _insert_user(
            connection,
            user_id="11000000-0000-0000-0000-000000000001",
            email="historical@example.test",
            role="patient",
        )
        _insert_patient(
            connection,
            patient_id="21000000-0000-0000-0000-000000000001",
            user_id="11000000-0000-0000-0000-000000000001",
            organization_id=second_organization,
            code="FG-HIST",
        )
        connection.execute(
            "INSERT INTO devices "
            "(id, device_uid, patient_id, display_name, status, registered_at) "
            "VALUES ('41000000-0000-0000-0000-000000000001', 'FG-HISTORICAL', NULL, "
            "'Historical unit', 'registered', '2026-01-01T08:00:00+00:00')"
        )
        connection.execute(
            "INSERT INTO sessions "
            "(id, patient_id, start_time, end_time, status, device_id) VALUES "
            "('51000000-0000-0000-0000-000000000001', "
            "'21000000-0000-0000-0000-000000000001', '2026-01-02T09:00:00+00:00', "
            "'2026-01-02T10:00:00+00:00', 'completed', "
            "'41000000-0000-0000-0000-000000000001')"
        )
        connection.execute(
            "INSERT INTO access_audit_events "
            "(id, organization_id, action, resource_type, outcome, created_at) VALUES "
            "('91000000-0000-0000-0000-000000000001', ?, 'system.migration', "
            "'migration', 'success', '2026-01-02T10:00:00+00:00')",
            (second_organization,),
        )
        connection.commit()

    _run_alembic(database_path, "upgrade", REVISION_0015)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT organization_id FROM devices "
            "WHERE id = '41000000-0000-0000-0000-000000000001'"
        ).fetchone() == (second_organization,)
        assert connection.execute(
            "SELECT organization_id, version, ends_at FROM device_assignments"
        ).fetchone()[0:2] == (second_organization, 2)
        assert connection.execute(
            "SELECT organization_id FROM access_audit_events "
            "WHERE id = '91000000-0000-0000-0000-000000000001'"
        ).fetchone() == (second_organization,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_overlapping_legacy_device_sessions_fail_before_schema_changes(
    legacy_0014_database: Path,
    tmp_path: Path,
) -> None:
    database_path = _copy_legacy_database(
        legacy_0014_database,
        tmp_path / "ambiguous-overlap.sqlite",
    )
    with sqlite3.connect(database_path) as connection:
        _insert_user(
            connection,
            user_id="12000000-0000-0000-0000-000000000001",
            email="overlap@example.test",
            role="patient",
        )
        _insert_patient(
            connection,
            patient_id="22000000-0000-0000-0000-000000000001",
            user_id="12000000-0000-0000-0000-000000000001",
            organization_id=DEFAULT_ORGANIZATION_ID,
            code="FG-OVERLAP",
        )
        connection.execute(
            "INSERT INTO devices "
            "(id, device_uid, patient_id, display_name, status, registered_at, assigned_at) "
            "VALUES ('42000000-0000-0000-0000-000000000001', 'FG-OVERLAP', "
            "'22000000-0000-0000-0000-000000000001', 'Overlap unit', 'active', "
            "'2026-01-01T08:00:00+00:00', '2026-01-01T08:30:00+00:00')"
        )
        connection.executemany(
            "INSERT INTO sessions "
            "(id, patient_id, start_time, end_time, status, device_id) "
            "VALUES (?, '22000000-0000-0000-0000-000000000001', ?, ?, 'completed', "
            "'42000000-0000-0000-0000-000000000001')",
            (
                (
                    "52000000-0000-0000-0000-000000000001",
                    "2026-01-01T09:00:00+00:00",
                    "2026-01-01T10:00:00+00:00",
                ),
                (
                    "52000000-0000-0000-0000-000000000002",
                    "2026-01-01T09:30:00+00:00",
                    "2026-01-01T10:30:00+00:00",
                ),
            ),
        )
        connection.commit()

    result = _run_alembic(database_path, "upgrade", REVISION_0015, success=False)
    assert "Overlapping sessions make device assignment history ambiguous" in (
        result.stdout + result.stderr
    )
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            REVISION_0014,
        )
        device_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(devices)").fetchall()
        }
        assert "organization_id" not in device_columns


def test_multifacility_orphan_device_fails_closed(
    legacy_0014_database: Path,
    tmp_path: Path,
) -> None:
    database_path = _copy_legacy_database(
        legacy_0014_database,
        tmp_path / "ambiguous-orphan.sqlite",
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO organizations (id, slug, name) VALUES "
            "('00000000-0000-0000-0000-000000000002', 'hospital-two', 'Hospital Two')"
        )
        connection.execute(
            "INSERT INTO devices "
            "(id, device_uid, patient_id, display_name, status, registered_at) VALUES "
            "('43000000-0000-0000-0000-000000000001', 'FG-ORPHAN', NULL, "
            "'Orphan unit', 'registered', '2026-01-01T08:00:00+00:00')"
        )
        connection.commit()

    result = _run_alembic(database_path, "upgrade", REVISION_0015, success=False)
    assert "Unassigned devices without session provenance" in (result.stdout + result.stderr)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            REVISION_0014,
        )
        connection.execute(
            "DELETE FROM devices "
            "WHERE id = '43000000-0000-0000-0000-000000000001'"
        )
        connection.execute(
            "INSERT INTO access_audit_events "
            "(id, organization_id, action, resource_type, outcome, created_at) VALUES "
            "('94000000-0000-0000-0000-000000000001', NULL, 'legacy.unknown', "
            "'unknown', 'success', '2026-01-01T08:00:00+00:00')"
        )
        connection.commit()

    result = _run_alembic(database_path, "upgrade", REVISION_0015, success=False)
    assert "Unscoped access audit history cannot be assigned safely" in (
        result.stdout + result.stderr
    )
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            REVISION_0014,
        )


def test_cross_facility_audit_history_fails_closed(
    legacy_0014_database: Path,
    tmp_path: Path,
) -> None:
    database_path = _copy_legacy_database(
        legacy_0014_database,
        tmp_path / "ambiguous-audit.sqlite",
    )
    second_organization = "00000000-0000-0000-0000-000000000002"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO organizations (id, slug, name) VALUES (?, 'hospital-two', 'Hospital Two')",
            (second_organization,),
        )
        _insert_user(
            connection,
            user_id="13000000-0000-0000-0000-000000000001",
            email="audit-patient@example.test",
            role="patient",
        )
        _insert_user(
            connection,
            user_id="13000000-0000-0000-0000-000000000002",
            email="audit-clinician@example.test",
            role="clinician",
        )
        _insert_patient(
            connection,
            patient_id="23000000-0000-0000-0000-000000000001",
            user_id="13000000-0000-0000-0000-000000000001",
            organization_id=second_organization,
            code="FG-AUDIT",
        )
        connection.execute(
            "INSERT INTO organization_memberships "
            "(id, organization_id, user_id, role, created_at) VALUES "
            "('33000000-0000-0000-0000-000000000001', ?, "
            "'13000000-0000-0000-0000-000000000002', 'clinician', ?)",
            (DEFAULT_ORGANIZATION_ID, "2026-01-01T00:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO access_audit_events "
            "(id, organization_id, actor_user_id, actor_membership_id, patient_id, "
            "action, resource_type, outcome, created_at) VALUES "
            "('93000000-0000-0000-0000-000000000001', NULL, "
            "'13000000-0000-0000-0000-000000000002', "
            "'33000000-0000-0000-0000-000000000001', "
            "'23000000-0000-0000-0000-000000000001', 'patient.view', 'patient', "
            "'success', '2026-01-01T00:00:00+00:00')"
        )
        connection.commit()

    result = _run_alembic(database_path, "upgrade", REVISION_0015, success=False)
    assert "Access audit history contains cross-organization identifiers" in (
        result.stdout + result.stderr
    )
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            REVISION_0014,
        )
