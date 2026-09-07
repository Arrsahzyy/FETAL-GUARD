/**
 * Shared models and helpers for the admin Devices panel.
 *
 * Pure: no React, no network. Mirrors src/utils/clinicianModels.js so the
 * display logic is unit-testable and the component stays thin.
 */
import { formatRelativeTime } from './formatters.js';

/** Selectable device states, matching the backend DeviceStatus enum. */
export const DEVICE_STATUS_OPTIONS = Object.freeze([
  { value: 'registered', label: 'Terdaftar' },
  { value: 'active', label: 'Aktif' },
  { value: 'maintenance', label: 'Perawatan' },
  { value: 'retired', label: 'Dipensiunkan' },
  { value: 'lost', label: 'Hilang' },
]);

const STATUS_META = Object.freeze({
  registered: { label: 'Terdaftar', tone: 'info' },
  active: { label: 'Aktif', tone: 'ready' },
  maintenance: { label: 'Perawatan', tone: 'warning' },
  retired: { label: 'Dipensiunkan', tone: 'muted' },
  lost: { label: 'Hilang', tone: 'danger' },
});

const TONE_CLASS = Object.freeze({
  info: '',
  ready: 'admin-status--ready',
  warning: 'admin-status--warning',
  muted: 'admin-status--inactive',
  danger: 'admin-status--danger',
});

/**
 * Human label + tone for a device status. An unrecognised contract value stays
 * visible (labelled with the raw value) rather than being hidden or throwing —
 * same principle as normalizeRiskLevel in clinicianModels.
 */
export function describeDeviceStatus(status) {
  const known = STATUS_META[status];
  if (known) return known;
  return { label: status ? String(status) : 'Tidak diketahui', tone: 'info' };
}

/** `class` attribute for the status pill, e.g. "admin-status admin-status--ready". */
export function deviceStatusClassName(status) {
  const { tone } = describeDeviceStatus(status);
  const modifier = TONE_CLASS[tone] || '';
  return modifier ? `admin-status ${modifier}` : 'admin-status';
}

/** Build an id -> patient map for assignment name resolution. */
export function buildPatientLookup(patients) {
  const map = new Map();
  for (const patient of patients || []) {
    if (patient && patient.id) map.set(patient.id, patient);
  }
  return map;
}

/**
 * Name of the patient a device is assigned to. The device list response carries
 * only `patient_id`, and the admin patient list is paginated, so a device can be
 * bound to a patient who is not on the current page.
 */
export function describeDeviceAssignment(device, patientLookup) {
  const patientId = device?.patient_id;
  if (!patientId) return 'Belum di-assign';
  const patient = patientLookup?.get?.(patientId);
  return patient?.name || 'Terpasang (pasien di luar halaman)';
}

/** Relative "last seen", or a plain label when the device has never reported. */
export function formatLastSeen(value, locale = 'id') {
  if (!value) return 'Belum pernah';
  return formatRelativeTime(value, locale);
}

/** Button label reflects whether a key already exists (issue vs rotate). */
export function signingKeyActionLabel(device) {
  return device?.packet_secret_provisioned_at
    ? 'Rotasi signing key'
    : 'Terbitkan signing key';
}

export function claimCodeActionLabel(device) {
  return device?.claim_code_set_at
    ? 'Terbitkan ulang claim code'
    : 'Terbitkan claim code';
}
