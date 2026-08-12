import React, { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../../../context/useAuth';
import api, {
  clearStoredOrganizationId,
  getApiErrorMessage,
  getStoredOrganizationId,
  isRequestCanceled,
  setStoredOrganizationId,
} from '../../../services/api';
import './AdminPortal.css';

const PAGE_SIZE = 10;
const PATIENT_PAGE_SIZE = 25;

const INITIAL_FORM = {
  email: '',
  temporaryPassword: '',
  membershipRole: 'clinician',
};

const INITIAL_ASSIGNMENT_FORM = {
  patientId: '',
  clinicianId: '',
  careRole: 'primary',
};

function formatDate(value) {
  if (!value) return '--';
  return new Intl.DateTimeFormat('id-ID', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function formatAuditAction(action) {
  if (action === 'clinician.provisioned') return 'Provision akun nakes';
  if (action === 'clinician.deactivated') return 'Nonaktifkan akun nakes';
  if (action === 'clinician.activated') return 'Aktifkan ulang akun nakes';
  if (action === 'clinician.password_reset') return 'Reset password nakes';
  if (action === 'patient.assigned_to_clinician') return 'Assign pasien ke nakes';
  if (action === 'patient.unassigned_from_clinician') return 'Lepas assignment pasien';
  if (action === 'clinician.facility_access_revoked') return 'Cabut akses fasilitas nakes';
  return action;
}

function AdminIcon({ name }) {
  const props = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: '1.8',
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': 'true',
  };

  if (name === 'users') {
    return (
      <svg {...props}>
        <circle cx="9" cy="8" r="3" />
        <path d="M3.8 19a5.2 5.2 0 0 1 10.4 0" />
        <path d="M16 10.5a2.5 2.5 0 1 0-1.2-4.7" />
        <path d="M17 19a4.4 4.4 0 0 0-2.2-3.8" />
      </svg>
    );
  }

  if (name === 'shield') {
    return (
      <svg {...props}>
        <path d="M12 3.6 5.5 6v5.2c0 4.2 2.7 7.8 6.5 9.2 3.8-1.4 6.5-5 6.5-9.2V6L12 3.6Z" />
        <path d="m9.2 12 1.8 1.8 3.8-4" />
      </svg>
    );
  }

  if (name === 'key') {
    return (
      <svg {...props}>
        <circle cx="8" cy="14" r="4" />
        <path d="m11 11 8-8" />
        <path d="m16 6 2 2" />
        <path d="m14 8 2 2" />
      </svg>
    );
  }

  return (
    <svg {...props}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

const AdminPortal = () => {
  const { user, logout } = useAuth();
  const [clinicianPage, setClinicianPage] = useState({
    items: [],
    total: 0,
    limit: PAGE_SIZE,
    offset: 0,
  });
  const [patientPage, setPatientPage] = useState({
    items: [],
    total: 0,
    limit: PATIENT_PAGE_SIZE,
    offset: 0,
  });
  const [auditLogs, setAuditLogs] = useState([]);
  const [form, setForm] = useState(INITIAL_FORM);
  const [assignmentForm, setAssignmentForm] = useState(INITIAL_ASSIGNMENT_FORM);
  const [bulkEmails, setBulkEmails] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const deferredSearchTerm = useDeferredValue(searchTerm.trim());
  const [page, setPage] = useState(0);
  const [patientSearchTerm, setPatientSearchTerm] = useState('');
  const deferredPatientSearchTerm = useDeferredValue(patientSearchTerm.trim());
  const [patientPageIndex, setPatientPageIndex] = useState(0);
  const [createdCredentials, setCreatedCredentials] = useState([]);
  const [copyState, setCopyState] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isAuditLoading, setIsAuditLoading] = useState(true);
  const [isPatientLoading, setIsPatientLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isBulkSubmitting, setIsBulkSubmitting] = useState(false);
  const [isAssignmentSubmitting, setIsAssignmentSubmitting] = useState(false);
  const [busyClinicianId, setBusyClinicianId] = useState('');
  const [busyAssignmentId, setBusyAssignmentId] = useState('');
  const [error, setError] = useState('');
  const [organizationMemberships, setOrganizationMemberships] = useState([]);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState('');
  const [isOrganizationLoading, setIsOrganizationLoading] = useState(true);
  const adminDataAbortControllerRef = useRef(null);
  const adminDataGenerationRef = useRef(0);

  const clinicians = clinicianPage.items;
  const patients = patientPage.items;
  const totalClinicians = clinicianPage.total;
  const totalPages = Math.max(1, Math.ceil(totalClinicians / PAGE_SIZE));
  const currentPage = Math.min(page + 1, totalPages);
  const totalPatientPages = Math.max(1, Math.ceil(patientPage.total / PATIENT_PAGE_SIZE));
  const currentPatientPage = Math.min(patientPageIndex + 1, totalPatientPages);
  const latestClinician = useMemo(() => clinicians[0] || null, [clinicians]);
  const totalClinicianLabel = deferredSearchTerm ? 'Hasil pencarian' : 'Total nakes';
  const activeClinicians = useMemo(
    () => clinicians.filter(
      (clinician) => clinician.is_active !== false && clinician.membership_role === 'clinician',
    ),
    [clinicians],
  );
  const pendingResetCount = useMemo(
    () => clinicians.filter((clinician) => clinician.must_reset_password).length,
    [clinicians],
  );
  const inactiveCount = useMemo(
    () => clinicians.filter((clinician) => clinician.is_active === false).length,
    [clinicians],
  );
  const scopedPatientCount = useMemo(
    () => patients.filter((patient) => patient.assigned_clinicians?.length > 0).length,
    [patients],
  );

  const loadClinicians = useCallback(async ({ signal, generation }) => {
    setIsLoading(true);
    setError('');

    try {
      const data = await api.admin.listClinicians({
        q: deferredSearchTerm || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        signal,
      });
      if (adminDataGenerationRef.current !== generation) return;
      setClinicianPage({
        items: data.items || [],
        total: data.total || 0,
        limit: data.limit || PAGE_SIZE,
        offset: data.offset || 0,
      });
    } catch (loadError) {
      if (!isRequestCanceled(loadError) && adminDataGenerationRef.current === generation) {
        setError(getApiErrorMessage(loadError));
      }
    } finally {
      if (adminDataGenerationRef.current === generation) setIsLoading(false);
    }
  }, [deferredSearchTerm, page]);

  const loadAuditLogs = useCallback(async ({ signal, generation }) => {
    setIsAuditLoading(true);

    try {
      const data = await api.admin.listAuditLogs({ limit: 10, signal });
      if (adminDataGenerationRef.current !== generation) return;
      setAuditLogs(data);
    } catch (loadError) {
      if (!isRequestCanceled(loadError) && adminDataGenerationRef.current === generation) {
        setError(getApiErrorMessage(loadError));
      }
    } finally {
      if (adminDataGenerationRef.current === generation) setIsAuditLoading(false);
    }
  }, []);

  const loadPatients = useCallback(async ({ signal, generation }) => {
    setIsPatientLoading(true);

    try {
      const data = await api.admin.listPatients({
        q: deferredPatientSearchTerm || undefined,
        limit: PATIENT_PAGE_SIZE,
        offset: patientPageIndex * PATIENT_PAGE_SIZE,
        signal,
      });
      if (adminDataGenerationRef.current !== generation) return;
      setPatientPage({
        items: data.items || [],
        total: data.total || 0,
        limit: data.limit || PATIENT_PAGE_SIZE,
        offset: data.offset || 0,
      });
    } catch (loadError) {
      if (!isRequestCanceled(loadError) && adminDataGenerationRef.current === generation) {
        setError(getApiErrorMessage(loadError));
      }
    } finally {
      if (adminDataGenerationRef.current === generation) setIsPatientLoading(false);
    }
  }, [deferredPatientSearchTerm, patientPageIndex]);

  const refreshAdminData = useCallback(async () => {
    adminDataAbortControllerRef.current?.abort();
    const controller = new AbortController();
    adminDataAbortControllerRef.current = controller;
    const generation = adminDataGenerationRef.current + 1;
    adminDataGenerationRef.current = generation;
    await Promise.all([
      loadClinicians({ signal: controller.signal, generation }),
      loadAuditLogs({ signal: controller.signal, generation }),
      loadPatients({ signal: controller.signal, generation }),
    ]);
    if (adminDataAbortControllerRef.current === controller) {
      adminDataAbortControllerRef.current = null;
    }
  }, [loadAuditLogs, loadClinicians, loadPatients]);

  useEffect(() => {
    const controller = new AbortController();
    setIsOrganizationLoading(true);
    api.organizations.listMine({ signal: controller.signal })
      .then((response) => {
        const memberships = Array.isArray(response?.items)
          ? response.items.filter((membership) => membership.permissions?.includes('staff:manage'))
          : [];
        setOrganizationMemberships(memberships);
        const storedOrganizationId = getStoredOrganizationId();
        const selectedMembership = memberships.find(
          (membership) => membership.organization.id === storedOrganizationId,
        );
        const nextOrganizationId = selectedMembership?.organization.id
          || memberships[0]?.organization.id
          || '';
        if (nextOrganizationId) {
          setStoredOrganizationId(nextOrganizationId);
          setSelectedOrganizationId(nextOrganizationId);
        } else {
          clearStoredOrganizationId();
          setSelectedOrganizationId('');
          setError('Akun ini tidak memiliki akses admin fasilitas yang aktif.');
        }
      })
      .catch((loadError) => {
        if (!isRequestCanceled(loadError)) setError(getApiErrorMessage(loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsOrganizationLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (isOrganizationLoading || !selectedOrganizationId) return;
    void refreshAdminData();
  }, [isOrganizationLoading, refreshAdminData, selectedOrganizationId]);

  useEffect(() => () => {
    adminDataGenerationRef.current += 1;
    adminDataAbortControllerRef.current?.abort();
  }, []);

  const handleOrganizationChange = (event) => {
    const nextOrganizationId = event.target.value;
    if (!organizationMemberships.some(
      (membership) => membership.organization.id === nextOrganizationId,
    )) return;
    adminDataGenerationRef.current += 1;
    adminDataAbortControllerRef.current?.abort();
    setStoredOrganizationId(nextOrganizationId);
    setSelectedOrganizationId(nextOrganizationId);
    setPage(0);
    setPatientPageIndex(0);
    setSearchTerm('');
    setPatientSearchTerm('');
    setClinicianPage((current) => ({ ...current, items: [], total: 0, offset: 0 }));
    setPatientPage((current) => ({ ...current, items: [], total: 0, offset: 0 }));
    setAuditLogs([]);
    setAssignmentForm(INITIAL_ASSIGNMENT_FORM);
    setError('');
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleSearchChange = (event) => {
    setSearchTerm(event.target.value);
    setPage(0);
  };

  const handleAssignmentChange = (event) => {
    const { name, value } = event.target;
    setAssignmentForm((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError('');
    setCopyState('');

    const payload = {
      email: form.email,
      temporary_password: form.temporaryPassword.trim() || undefined,
      membership_role: form.membershipRole,
    };

    try {
      const response = await api.admin.provisionClinician(payload);
      setCreatedCredentials([response]);
      setForm(INITIAL_FORM);
      setPage(0);
      await refreshAdminData();
    } catch (submitError) {
      setError(getApiErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBulkSubmit = async (event) => {
    event.preventDefault();
    setIsBulkSubmitting(true);
    setError('');
    setCopyState('');

    const emails = bulkEmails
      .split(/[\n,;]+/)
      .map((item) => item.trim())
      .filter(Boolean);

    try {
      const response = await api.admin.bulkProvisionClinicians({ emails });
      setCreatedCredentials(response.clinicians);
      setBulkEmails('');
      setPage(0);
      await refreshAdminData();
    } catch (bulkError) {
      setError(getApiErrorMessage(bulkError));
    } finally {
      setIsBulkSubmitting(false);
    }
  };

  const handleAssignmentSubmit = async (event) => {
    event.preventDefault();
    setIsAssignmentSubmitting(true);
    setError('');

    try {
      await api.admin.assignPatientToClinician({
        patient_id: assignmentForm.patientId,
        clinician_id: assignmentForm.clinicianId,
        care_role: assignmentForm.careRole,
      });
      setAssignmentForm(INITIAL_ASSIGNMENT_FORM);
      await refreshAdminData();
    } catch (assignmentError) {
      setError(getApiErrorMessage(assignmentError));
    } finally {
      setIsAssignmentSubmitting(false);
    }
  };

  const copyTemporaryCredentials = async () => {
    if (createdCredentials.length === 0) return;

    const text = createdCredentials
      .map((item) => `${item.user.email},${item.temporary_password}`)
      .join('\n');

    try {
      await navigator.clipboard.writeText(text);
      setCopyState('Kredensial sementara disalin.');
    } catch {
      setCopyState('Salin manual dari daftar kredensial sementara.');
    }
  };

  const clearTemporaryCredentials = () => {
    setCreatedCredentials([]);
    setCopyState('');
  };

  const handleResetPassword = async (clinician) => {
    setBusyClinicianId(clinician.id);
    setError('');
    setCopyState('');

    try {
      const response = await api.admin.resetClinicianPassword(clinician.id);
      setCreatedCredentials([response]);
      await refreshAdminData();
      setCopyState('Password sementara baru dibuat. Salin dan bagikan melalui kanal internal yang aman.');
    } catch (actionError) {
      setError(getApiErrorMessage(actionError));
    } finally {
      setBusyClinicianId('');
    }
  };

  const handleToggleClinicianStatus = async (clinician) => {
    const willDeactivate = clinician.is_active !== false;
    const confirmed = willDeactivate
      ? window.confirm(`Nonaktifkan akses untuk ${clinician.email}? Akun tidak dapat login sampai diaktifkan ulang.`)
      : true;
    if (!confirmed) return;

    setBusyClinicianId(clinician.id);
    setError('');

    try {
      if (willDeactivate) {
        await api.admin.deactivateClinician(clinician.id);
      } else {
        await api.admin.activateClinician(clinician.id);
      }
      await refreshAdminData();
    } catch (actionError) {
      setError(getApiErrorMessage(actionError));
    } finally {
      setBusyClinicianId('');
    }
  };

  const handlePatientSearchChange = (event) => {
    setPatientSearchTerm(event.target.value);
    setPatientPageIndex(0);
    setAssignmentForm((current) => ({ ...current, patientId: '' }));
  };

  const handleRevokeFacilityAccess = async (clinician) => {
    const confirmed = window.confirm(
      `Cabut akses ${clinician.email} dari fasilitas ini? Seluruh assignment pasien aktif pada fasilitas ini juga akan ditutup.`,
    );
    if (!confirmed) return;

    setBusyClinicianId(clinician.id);
    setError('');
    try {
      await api.admin.revokeClinicianMembership(clinician.membership_id);
      await refreshAdminData();
    } catch (actionError) {
      setError(getApiErrorMessage(actionError));
    } finally {
      setBusyClinicianId('');
    }
  };

  const handleUnassignPatient = async (assignmentId, clinicianEmail, patientName) => {
    const confirmed = window.confirm(`Lepas akses ${clinicianEmail} dari pasien ${patientName}?`);
    if (!confirmed) return;

    setBusyAssignmentId(assignmentId);
    setError('');

    try {
      await api.admin.unassignPatientAssignment(assignmentId);
      await refreshAdminData();
    } catch (assignmentError) {
      setError(getApiErrorMessage(assignmentError));
    } finally {
      setBusyAssignmentId('');
    }
  };

  return (
    <main className="admin-portal">
      <header className="admin-portal__header">
        <div>
          <p className="admin-portal__eyebrow">Portal Admin</p>
          <h1>Provisioning akun nakes</h1>
          <p>
            Buat akun nakes secara terkontrol, pantau status reset password awal, dan simpan jejak
            tindakan admin tanpa membuka registrasi publik untuk akses klinis.
          </p>
        </div>
        <div className="admin-portal__account">
          {organizationMemberships.length > 0 && (
            <label className="admin-portal__facility">
              <span>Fasilitas</span>
              <select
                value={selectedOrganizationId}
                onChange={handleOrganizationChange}
                disabled={isOrganizationLoading || organizationMemberships.length === 1}
              >
                {organizationMemberships.map((membership) => (
                  <option key={membership.id} value={membership.organization.id}>
                    {membership.organization.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <span>{user?.email}</span>
          <button type="button" onClick={logout}>Keluar</button>
        </div>
      </header>

      <section className="admin-portal__stats" aria-label="Ringkasan provisioning">
        <article className="admin-stat">
          <span className="admin-stat__icon"><AdminIcon name="users" /></span>
          <small>{totalClinicianLabel}</small>
          <strong>{totalClinicians}</strong>
        </article>
        <article className="admin-stat">
          <span className="admin-stat__icon"><AdminIcon name="shield" /></span>
          <small>Wajib reset di halaman ini</small>
          <strong>{pendingResetCount}</strong>
        </article>
        <article className="admin-stat">
          <span className="admin-stat__icon"><AdminIcon name="key" /></span>
          <small>Terbaru di halaman ini</small>
          <strong>{latestClinician ? latestClinician.email : 'Belum ada'}</strong>
        </article>
        <article className="admin-stat">
          <span className="admin-stat__icon"><AdminIcon name="shield" /></span>
          <small>Nonaktif di halaman ini</small>
          <strong>{inactiveCount}</strong>
        </article>
        <article className="admin-stat">
          <span className="admin-stat__icon"><AdminIcon name="users" /></span>
          <small>Pasien scoped</small>
          <strong>{scopedPatientCount}/{patientPage.total}</strong>
        </article>
      </section>

      <section className="admin-portal__grid">
        <form className="admin-panel admin-form" onSubmit={handleSubmit}>
          <div className="admin-panel__header">
            <h2>Tambah nakes</h2>
            <p>
              Akun yang dibuat di sini langsung memiliki role nakes dan wajib mengganti password
              sementara pada login pertama.
            </p>
          </div>

          <label className="admin-form__field">
            <span>Email nakes</span>
            <input
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              autoComplete="email"
              placeholder="nama@fasilitas-kesehatan.id"
              required
            />
          </label>

          <label className="admin-form__field">
            <span>Password sementara <small>(opsional)</small></span>
            <input
              name="temporaryPassword"
              type="text"
              value={form.temporaryPassword}
              onChange={handleChange}
              autoComplete="off"
              minLength={8}
              placeholder="Kosongkan untuk dibuat otomatis"
            />
            <small>
              Bagikan melalui kanal internal yang aman. Sistem akan meminta nakes mengganti
              password ini sebelum masuk dashboard.
            </small>
          </label>

          {error && <div className="admin-alert" role="alert">{error}</div>}

          <button className="admin-form__submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Memproses...' : 'Provision akun nakes'}
          </button>

          <div className="admin-form__divider" />

          <div className="admin-panel__header">
            <h2>Tambah banyak nakes</h2>
            <p>Masukkan email dipisahkan baris baru, koma, atau titik koma. Maksimal 100 email per batch.</p>
          </div>

          <label className="admin-form__field">
            <span>Daftar email nakes</span>
            <textarea
              value={bulkEmails}
              onChange={(event) => setBulkEmails(event.target.value)}
              rows="5"
              placeholder={'nakes1@fasilitas.id\nnakes2@fasilitas.id'}
              required
            />
          </label>

          <button
            className="admin-form__submit admin-form__submit--secondary"
            type="button"
            onClick={handleBulkSubmit}
            disabled={isBulkSubmitting || !bulkEmails.trim()}
          >
            {isBulkSubmitting ? 'Memproses batch...' : 'Provision batch nakes'}
          </button>
        </form>

        <aside className="admin-panel admin-credential" aria-live="polite">
          <div className="admin-panel__header">
            <h2>Kredensial sementara</h2>
            <p>Password hanya ditampilkan setelah provisioning berhasil pada sesi admin ini.</p>
          </div>

          {createdCredentials.length > 0 ? (
            <div className="admin-credential__box">
              <span>Format</span>
              <strong>Email, password sementara</strong>
              <div className="admin-credential__list">
                {createdCredentials.map((credential) => (
                  <code key={credential.user.id}>
                    {credential.user.email},{credential.temporary_password}
                  </code>
                ))}
              </div>
              <div className="admin-credential__actions">
                <button type="button" onClick={copyTemporaryCredentials}>Salin semua</button>
                <button type="button" className="admin-credential__clear" onClick={clearTemporaryCredentials}>
                  Hapus tampilan
                </button>
              </div>
              {copyState && <p>{copyState}</p>}
            </div>
          ) : (
            <div className="admin-empty">
              <AdminIcon name="key" />
              <p>Belum ada akun nakes baru pada sesi ini.</p>
            </div>
          )}
        </aside>
      </section>

      <section className="admin-panel admin-scope-panel">
        <div className="admin-panel__header admin-panel__header--row">
          <div>
            <h2>Scope pasien-nakes</h2>
            <p>
              Tentukan nakes mana yang boleh melihat pasien tertentu. Dashboard nakes hanya
              menampilkan pasien dan alert yang sudah berada dalam scope ini.
            </p>
          </div>
          <label className="admin-search">
            <span>Cari nama pasien</span>
            <input
              type="search"
              value={patientSearchTerm}
              onChange={handlePatientSearchChange}
              placeholder="Cari pasien..."
            />
          </label>

          <label className="admin-form__field">
            <span>Hak akses fasilitas</span>
            <select
              name="membershipRole"
              value={form.membershipRole}
              onChange={handleChange}
              required
            >
              <option value="clinician">Nakes - hanya pasien yang ditugaskan</option>
              <option value="supervisor">Supervisor - seluruh pasien fasilitas</option>
            </select>
            <small>
              Berikan akses supervisor hanya kepada petugas yang memang berwenang meninjau
              seluruh pasien dalam fasilitas ini.
            </small>
          </label>
        </div>

        <form className="admin-assignment-form" onSubmit={handleAssignmentSubmit}>
          <label className="admin-form__field">
            <span>Pasien</span>
            <select
              name="patientId"
              value={assignmentForm.patientId}
              onChange={handleAssignmentChange}
              required
              disabled={isPatientLoading || patients.length === 0}
            >
              <option value="">Pilih pasien...</option>
              {patients.map((patient) => (
                <option key={patient.id} value={patient.id}>
                  {patient.name} - {patient.gestational_age_weeks} minggu
                </option>
              ))}
            </select>
          </label>

          <label className="admin-form__field">
            <span>Nakes</span>
            <select
              name="clinicianId"
              value={assignmentForm.clinicianId}
              onChange={handleAssignmentChange}
              required
              disabled={isLoading || activeClinicians.length === 0}
            >
              <option value="">Pilih nakes aktif...</option>
              {activeClinicians.map((clinician) => (
                <option key={clinician.id} value={clinician.id}>
                  {clinician.email}
                </option>
              ))}
            </select>
          </label>

          <label className="admin-form__field">
            <span>Peran pemantauan</span>
            <select
              name="careRole"
              value={assignmentForm.careRole}
              onChange={handleAssignmentChange}
              required
            >
              <option value="primary">Penanggung jawab utama</option>
              <option value="supporting">Nakes pendamping</option>
            </select>
            <small>Satu pasien hanya boleh memiliki satu penanggung jawab utama aktif.</small>
          </label>

          <button
            type="submit"
            className="admin-form__submit"
            disabled={isAssignmentSubmitting || !assignmentForm.patientId || !assignmentForm.clinicianId}
          >
            {isAssignmentSubmitting ? 'Menyimpan scope...' : 'Assign pasien'}
          </button>
        </form>

        {isPatientLoading ? (
          <div className="admin-empty">Memuat daftar pasien...</div>
        ) : patients.length === 0 ? (
          <div className="admin-empty">
            {deferredPatientSearchTerm
              ? 'Tidak ada pasien yang sesuai dengan pencarian.'
              : 'Belum ada profil pasien yang dapat di-assign.'}
          </div>
        ) : (
          <>
            <div className="admin-assignment-list">
              {patients.map((patient) => (
                <article key={patient.id} className="admin-assignment-item">
                  <div>
                    <strong>{patient.name}</strong>
                    <span>{patient.age} tahun - gestasi {patient.gestational_age_weeks} minggu</span>
                  </div>
                  <div className="admin-assignment-item__chips">
                    {patient.assigned_clinicians?.length > 0 ? (
                      patient.assigned_clinicians.map((clinician) => (
                        <span key={clinician.assignment_id} className="admin-assignment-chip">
                          {clinician.email} ({clinician.care_role === 'primary' ? 'utama' : 'pendamping'})
                          <button
                            type="button"
                            disabled={busyAssignmentId === clinician.assignment_id}
                            onClick={() => handleUnassignPatient(clinician.assignment_id, clinician.email, patient.name)}
                            aria-label={`Lepas assignment ${clinician.email} dari ${patient.name}`}
                          >
                            x
                          </button>
                        </span>
                      ))
                    ) : (
                      <span className="admin-assignment-empty">Belum ada nakes</span>
                    )}
                  </div>
                </article>
              ))}
            </div>
            <div className="admin-pagination" aria-label="Navigasi daftar pasien">
              <button
                type="button"
                disabled={patientPageIndex === 0}
                onClick={() => {
                  setAssignmentForm((current) => ({ ...current, patientId: '' }));
                  setPatientPageIndex((current) => Math.max(0, current - 1));
                }}
              >
                Sebelumnya
              </button>
              <span>Halaman {currentPatientPage} dari {totalPatientPages}</span>
              <button
                type="button"
                disabled={(patientPageIndex + 1) * PATIENT_PAGE_SIZE >= patientPage.total}
                onClick={() => {
                  setAssignmentForm((current) => ({ ...current, patientId: '' }));
                  setPatientPageIndex((current) => current + 1);
                }}
              >
                Berikutnya
              </button>
            </div>
          </>
        )}
      </section>

      <section className="admin-panel admin-table-panel">
        <div className="admin-panel__header admin-panel__header--row">
          <div>
            <h2>Daftar nakes</h2>
            <p>Akun yang sudah diprovisikan oleh admin.</p>
          </div>
          <div className="admin-table-panel__tools">
            <label className="admin-search">
              <span>Cari email nakes</span>
              <input
                type="search"
                value={searchTerm}
                onChange={handleSearchChange}
                placeholder="Cari email..."
              />
            </label>
            <button type="button" className="admin-table-panel__refresh" onClick={refreshAdminData} disabled={isLoading}>
              {isLoading ? 'Memuat...' : 'Muat ulang'}
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="admin-empty">Memuat daftar nakes...</div>
        ) : clinicians.length === 0 ? (
          <div className="admin-empty">Belum ada akun nakes yang sesuai.</div>
        ) : (
          <>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status akun</th>
                    <th>Status password</th>
                    <th>Dibuat</th>
                    <th>Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {clinicians.map((clinician) => (
                    <tr key={clinician.id}>
                      <td>{clinician.email}</td>
                      <td>
                        <span>
                          {clinician.membership_role === 'supervisor' ? 'Supervisor' : 'Nakes'}
                        </span>
                      </td>
                      <td>
                        <span className={clinician.is_active === false ? 'admin-status admin-status--inactive' : 'admin-status admin-status--ready'}>
                          {clinician.is_active === false ? 'Nonaktif' : 'Aktif'}
                        </span>
                      </td>
                      <td>
                        <span className={clinician.must_reset_password ? 'admin-status admin-status--pending' : 'admin-status admin-status--ready'}>
                          {clinician.must_reset_password ? 'Wajib reset' : 'Sudah aktif'}
                        </span>
                      </td>
                      <td>{formatDate(clinician.created_at)}</td>
                      <td>
                        <div className="admin-row-actions">
                          <button
                            type="button"
                            className="admin-action-button"
                            disabled={busyClinicianId === clinician.id}
                            onClick={() => handleResetPassword(clinician)}
                          >
                            Reset password
                          </button>
                          <button
                            type="button"
                            className={`admin-action-button ${clinician.is_active === false ? 'admin-action-button--activate' : 'admin-action-button--danger'}`}
                            disabled={busyClinicianId === clinician.id}
                            onClick={() => handleToggleClinicianStatus(clinician)}
                          >
                            {clinician.is_active === false ? 'Aktifkan' : 'Nonaktifkan'}
                          </button>
                          <button
                            type="button"
                            className="admin-action-button admin-action-button--danger"
                            disabled={busyClinicianId === clinician.id}
                            onClick={() => handleRevokeFacilityAccess(clinician)}
                          >
                            Cabut akses fasilitas
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="admin-pagination" aria-label="Navigasi daftar nakes">
              <button type="button" disabled={page === 0} onClick={() => setPage((current) => Math.max(0, current - 1))}>
                Sebelumnya
              </button>
              <span>Halaman {currentPage} dari {totalPages}</span>
              <button
                type="button"
                disabled={(page + 1) * PAGE_SIZE >= totalClinicians}
                onClick={() => setPage((current) => current + 1)}
              >
                Berikutnya
              </button>
            </div>
          </>
        )}
      </section>

      <section className="admin-panel admin-audit-panel">
        <div className="admin-panel__header">
          <h2>Audit provisioning</h2>
          <p>Jejak tindakan admin terbaru untuk pembuatan akun nakes.</p>
        </div>

        {isAuditLoading ? (
          <div className="admin-empty">Memuat audit log...</div>
        ) : auditLogs.length === 0 ? (
          <div className="admin-empty">Belum ada audit log provisioning.</div>
        ) : (
          <div className="admin-audit-list">
            {auditLogs.map((log) => (
              <article key={log.id} className="admin-audit-item">
                <div>
                  <strong>{formatAuditAction(log.action)}</strong>
                  <span>{log.target_email || 'Target tidak tersedia'}</span>
                </div>
                <time dateTime={log.created_at}>{formatDate(log.created_at)}</time>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
};

export default AdminPortal;
