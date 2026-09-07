import React, {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import api, { getApiErrorMessage, isRequestCanceled } from '../../../services/api';
import { formatDateTime } from '../../../utils/formatters';
import {
  DEVICE_STATUS_OPTIONS,
  buildPatientLookup,
  claimCodeActionLabel,
  describeDeviceAssignment,
  deviceStatusClassName,
  describeDeviceStatus,
  formatLastSeen,
  signingKeyActionLabel,
} from '../../../utils/deviceModels';

const DEVICE_PAGE_SIZE = 10;

const STATUS_FILTERS = [
  { value: 'all', label: 'Semua status' },
  ...DEVICE_STATUS_OPTIONS,
];

const INITIAL_REGISTER_FORM = {
  deviceUid: '',
  displayName: '',
  patientId: '',
  status: 'registered',
};

const SECRET_COPY = {
  'claim-code': {
    title: 'Claim code',
    warning:
      'Cetak pada perangkat sekarang. Kode ini hanya ditampilkan sekali dan tidak dapat dilihat lagi. Menerbitkan ulang membatalkan kode sebelumnya.',
  },
  'signing-key': {
    title: 'Signing key (HMAC)',
    warning:
      'Tempel ke firmware lalu flash perangkat sekarang. Kunci ini hanya ditampilkan sekali. Rotasi kunci membuat perangkat wajib di-flash ulang sebelum bisa mengirim data.',
  },
};

function DevicesPanel({ patients, patientsLoading, organizationId }) {
  const [devicePage, setDevicePage] = useState({
    items: [],
    total: 0,
    limit: DEVICE_PAGE_SIZE,
    offset: 0,
  });
  const [searchTerm, setSearchTerm] = useState('');
  const deferredSearchTerm = useDeferredValue(searchTerm.trim());
  const [statusFilter, setStatusFilter] = useState('all');
  const [pageIndex, setPageIndex] = useState(0);
  const [registerForm, setRegisterForm] = useState(INITIAL_REGISTER_FORM);
  const [isLoading, setIsLoading] = useState(true);
  const [isRegistering, setIsRegistering] = useState(false);
  const [busyDeviceId, setBusyDeviceId] = useState('');
  const [error, setError] = useState('');
  const [issuedSecret, setIssuedSecret] = useState(null);
  const [copyState, setCopyState] = useState('');

  const abortControllerRef = useRef(null);
  const generationRef = useRef(0);

  const devices = devicePage.items;
  const patientLookup = useMemo(() => buildPatientLookup(patients), [patients]);
  const totalPages = Math.max(1, Math.ceil(devicePage.total / DEVICE_PAGE_SIZE));
  const currentPage = Math.min(pageIndex + 1, totalPages);
  const assignablePatients = patients || [];

  const loadDevices = useCallback(async ({ clearError = true } = {}) => {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const generation = generationRef.current + 1;
    generationRef.current = generation;
    setIsLoading(true);

    try {
      const data = await api.admin.listDevices({
        q: deferredSearchTerm || undefined,
        status: statusFilter,
        limit: DEVICE_PAGE_SIZE,
        offset: pageIndex * DEVICE_PAGE_SIZE,
        signal: controller.signal,
      });
      if (generationRef.current !== generation) return;
      setDevicePage({
        items: data.items || [],
        total: data.total || 0,
        limit: data.limit || DEVICE_PAGE_SIZE,
        offset: data.offset || 0,
      });
      // Refreshing after a failed mutation must not wipe the error explaining why.
      if (clearError) setError('');
    } catch (loadError) {
      if (!isRequestCanceled(loadError) && generationRef.current === generation) {
        setError(getApiErrorMessage(loadError));
      }
    } finally {
      if (generationRef.current === generation) setIsLoading(false);
    }
  }, [deferredSearchTerm, statusFilter, pageIndex]);

  useEffect(() => {
    void loadDevices();
  }, [loadDevices, organizationId]);

  useEffect(() => {
    // Facility switch: drop filters so the operator starts from a clean view.
    setSearchTerm('');
    setStatusFilter('all');
    setPageIndex(0);
    setRegisterForm(INITIAL_REGISTER_FORM);
    setIssuedSecret(null);
  }, [organizationId]);

  useEffect(
    () => () => {
      generationRef.current += 1;
      abortControllerRef.current?.abort();
    },
    [],
  );

  const handleSearchChange = (event) => {
    setSearchTerm(event.target.value);
    setPageIndex(0);
  };

  const handleStatusFilterChange = (event) => {
    setStatusFilter(event.target.value);
    setPageIndex(0);
  };

  const handleRegisterChange = (event) => {
    const { name, value } = event.target;
    setRegisterForm((current) => ({ ...current, [name]: value }));
  };

  const handleRegisterSubmit = async (event) => {
    event.preventDefault();
    setIsRegistering(true);
    setError('');

    const payload = {
      device_uid: registerForm.deviceUid.trim(),
      status: registerForm.status,
    };
    if (registerForm.displayName.trim()) payload.display_name = registerForm.displayName.trim();
    if (registerForm.patientId) payload.patient_id = registerForm.patientId;

    try {
      await api.admin.registerDevice(payload);
      setRegisterForm(INITIAL_REGISTER_FORM);
      setPageIndex(0);
      await loadDevices();
    } catch (registerError) {
      setError(getApiErrorMessage(registerError));
    } finally {
      setIsRegistering(false);
    }
  };

  const runDeviceAction = useCallback(
    async (deviceId, action) => {
      setBusyDeviceId(deviceId);
      setError('');
      try {
        await action();
        await loadDevices();
        return true;
      } catch (actionError) {
        const message = getApiErrorMessage(actionError);
        // Reload first (reverts the optimistic select), then show why it failed.
        await loadDevices({ clearError: false });
        setError(message);
        return false;
      } finally {
        setBusyDeviceId('');
      }
    },
    [loadDevices],
  );

  const handleReassign = async (device, nextPatientId) => {
    if (nextPatientId === (device.patient_id || '')) return;
    const nextName = nextPatientId
      ? patientLookup.get(nextPatientId)?.name || 'pasien lain'
      : null;
    const confirmed = window.confirm(
      nextPatientId
        ? `Pindahkan ${device.device_uid} ke ${nextName}?`
        : `Lepas ${device.device_uid} dari pasien saat ini?`,
    );
    if (!confirmed) return;
    await runDeviceAction(device.id, () =>
      api.admin.updateDevice(device.id, { patient_id: nextPatientId || null }),
    );
  };

  const handleStatusChange = async (device, nextStatus) => {
    if (nextStatus === device.status) return;
    if (
      (nextStatus === 'retired' || nextStatus === 'lost')
      && !window.confirm(
        `Ubah status ${device.device_uid} menjadi "${describeDeviceStatus(nextStatus).label}"? Perangkat tidak akan bisa dipakai untuk sesi baru.`,
      )
    ) {
      return;
    }
    await runDeviceAction(device.id, () =>
      api.admin.updateDevice(device.id, { status: nextStatus }),
    );
  };

  const handleIssueClaimCode = async (device) => {
    if (device.claim_code_set_at && !window.confirm(
      `Terbitkan claim code baru untuk ${device.device_uid}? Kode lama akan batal.`,
    )) {
      return;
    }
    setCopyState('');
    await runDeviceAction(device.id, async () => {
      const result = await api.admin.provisionDeviceClaimCode(device.id);
      setIssuedSecret({
        kind: 'claim-code',
        deviceUid: result.device_uid,
        value: result.claim_code,
        at: result.claim_code_set_at,
      });
    });
  };

  const handleIssueSigningKey = async (device) => {
    const rotating = Boolean(device.packet_secret_provisioned_at);
    if (
      rotating
      && !window.confirm(
        `Rotasi signing key ${device.device_uid}? Perangkat WAJIB di-flash ulang dengan kunci baru sebelum bisa mengirim data lagi. Ditolak bila ada sesi monitoring aktif.`,
      )
    ) {
      return;
    }
    setCopyState('');
    await runDeviceAction(device.id, async () => {
      const result = await api.admin.provisionDeviceSigningKey(device.id);
      setIssuedSecret({
        kind: 'signing-key',
        deviceUid: result.device_uid,
        value: result.packet_secret,
        at: result.packet_secret_provisioned_at,
      });
    });
  };

  const copySecret = async () => {
    if (!issuedSecret) return;
    try {
      await navigator.clipboard.writeText(issuedSecret.value);
      setCopyState('Disalin ke clipboard.');
    } catch {
      setCopyState('Salin manual dari kotak di atas.');
    }
  };

  const dismissSecret = () => {
    setIssuedSecret(null);
    setCopyState('');
  };

  const secretMeta = issuedSecret ? SECRET_COPY[issuedSecret.kind] : null;

  return (
    <section className="admin-panel admin-devices-panel">
      <div className="admin-panel__header">
        <h2>Perangkat</h2>
        <p>
          Daftarkan belt, terbitkan claim code dan signing key, tautkan ke pasien, dan atur
          statusnya. Semua tanpa akses shell.
        </p>
      </div>

      <form className="admin-devices-panel__register" onSubmit={handleRegisterSubmit}>
        <label className="admin-form__field">
          <span>UID perangkat</span>
          <input
            name="deviceUid"
            value={registerForm.deviceUid}
            onChange={handleRegisterChange}
            minLength={3}
            maxLength={80}
            placeholder="mis. FG-BENCH-01"
            autoComplete="off"
            required
          />
        </label>
        <label className="admin-form__field">
          <span>Nama tampilan <small>(opsional)</small></span>
          <input
            name="displayName"
            value={registerForm.displayName}
            onChange={handleRegisterChange}
            maxLength={120}
            placeholder="FETAL-GUARD Belt"
            autoComplete="off"
          />
        </label>
        <label className="admin-form__field">
          <span>Tautkan ke pasien <small>(opsional)</small></span>
          <select
            name="patientId"
            value={registerForm.patientId}
            onChange={handleRegisterChange}
            disabled={patientsLoading || assignablePatients.length === 0}
          >
            <option value="">Belum ditautkan</option>
            {assignablePatients.map((patient) => (
              <option key={patient.id} value={patient.id}>
                {patient.name}
              </option>
            ))}
          </select>
        </label>
        <label className="admin-form__field">
          <span>Status awal</span>
          <select name="status" value={registerForm.status} onChange={handleRegisterChange}>
            {DEVICE_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          className="admin-form__submit"
          disabled={isRegistering || registerForm.deviceUid.trim().length < 3}
        >
          {isRegistering ? 'Mendaftarkan...' : 'Daftarkan perangkat'}
        </button>
      </form>

      {error && <div className="admin-alert" role="alert">{error}</div>}

      {issuedSecret && secretMeta && (
        <div className="admin-credential__box" aria-live="polite">
          <span>{secretMeta.title} &middot; {issuedSecret.deviceUid}</span>
          <strong>Tampil sekali — simpan sekarang</strong>
          <div className="admin-credential__list">
            <code>{issuedSecret.value}</code>
          </div>
          <p className="admin-devices-panel__secret-warning">{secretMeta.warning}</p>
          <div className="admin-credential__actions">
            <button type="button" onClick={copySecret}>Salin</button>
            <button type="button" className="admin-credential__clear" onClick={dismissSecret}>
              Hapus tampilan
            </button>
          </div>
          {copyState && <p>{copyState}</p>}
        </div>
      )}

      <div className="admin-devices-panel__toolbar">
        <label className="admin-search">
          <span>Cari UID / nama</span>
          <input
            type="search"
            value={searchTerm}
            onChange={handleSearchChange}
            placeholder="Cari perangkat..."
          />
        </label>
        <label className="admin-search admin-search--compact">
          <span>Status</span>
          <select value={statusFilter} onChange={handleStatusFilterChange}>
            {STATUS_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="admin-table-panel__refresh"
          onClick={() => loadDevices()}
          disabled={isLoading}
        >
          {isLoading ? 'Memuat...' : 'Muat ulang'}
        </button>
      </div>

      {isLoading ? (
        <div className="admin-empty">Memuat daftar perangkat...</div>
      ) : devices.length === 0 ? (
        <div className="admin-empty">
          {deferredSearchTerm || statusFilter !== 'all'
            ? 'Tidak ada perangkat yang sesuai filter.'
            : 'Belum ada perangkat terdaftar.'}
        </div>
      ) : (
        <>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>UID</th>
                  <th>Status</th>
                  <th>Pasien</th>
                  <th>Firmware</th>
                  <th>Terakhir terlihat</th>
                  <th>Terdaftar</th>
                  <th>Aksi</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((device) => {
                  const rowBusy = busyDeviceId === device.id;
                  return (
                    <tr key={device.id}>
                      <td>
                        <strong>{device.device_uid}</strong>
                        {device.display_name && device.display_name !== device.device_uid && (
                          <div className="admin-devices-panel__subtle">{device.display_name}</div>
                        )}
                      </td>
                      <td>
                        <span className={deviceStatusClassName(device.status)}>
                          {describeDeviceStatus(device.status).label}
                        </span>
                      </td>
                      <td>{describeDeviceAssignment(device, patientLookup)}</td>
                      <td>{device.firmware_version || '--'}</td>
                      <td>{formatLastSeen(device.last_seen_at)}</td>
                      <td>{formatDateTime(device.registered_at)}</td>
                      <td>
                        <div className="admin-row-actions">
                          <label className="admin-devices-panel__inline-select">
                            <span className="admin-devices-panel__sr">Pasien perangkat {device.device_uid}</span>
                            <select
                              value={device.patient_id || ''}
                              disabled={rowBusy || patientsLoading}
                              onChange={(event) => handleReassign(device, event.target.value)}
                            >
                              <option value="">Lepas / belum ditautkan</option>
                              {assignablePatients.map((patient) => (
                                <option key={patient.id} value={patient.id}>
                                  {patient.name}
                                </option>
                              ))}
                              {device.patient_id && !patientLookup.has(device.patient_id) && (
                                <option value={device.patient_id}>Pasien di luar halaman</option>
                              )}
                            </select>
                          </label>
                          <label className="admin-devices-panel__inline-select">
                            <span className="admin-devices-panel__sr">Status perangkat {device.device_uid}</span>
                            <select
                              value={device.status}
                              disabled={rowBusy}
                              onChange={(event) => handleStatusChange(device, event.target.value)}
                            >
                              {DEVICE_STATUS_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <button
                            type="button"
                            className="admin-action-button"
                            disabled={rowBusy}
                            onClick={() => handleIssueClaimCode(device)}
                          >
                            {claimCodeActionLabel(device)}
                          </button>
                          <button
                            type="button"
                            className="admin-action-button"
                            disabled={rowBusy}
                            onClick={() => handleIssueSigningKey(device)}
                          >
                            {signingKeyActionLabel(device)}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="admin-pagination" aria-label="Navigasi daftar perangkat">
            <button
              type="button"
              disabled={pageIndex === 0}
              onClick={() => setPageIndex((current) => Math.max(0, current - 1))}
            >
              Sebelumnya
            </button>
            <span>Halaman {currentPage} dari {totalPages}</span>
            <button
              type="button"
              disabled={(pageIndex + 1) * DEVICE_PAGE_SIZE >= devicePage.total}
              onClick={() => setPageIndex((current) => current + 1)}
            >
              Berikutnya
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export default DevicesPanel;
