/**
 * Shared models and helpers for Clinician Dashboard
 */
import {
  formatRelativeTime,
  formatDateTime,
  formatDuration,
} from './formatters.js';

export const RISK_PRIORITY = Object.freeze({ low: 0, medium: 1, high: 2, unknown: 3 });

const CLINICIAN_COPY = {
  id: {
    dataUnavailable: 'Belum tersedia dari sistem',
    unknownPatient: 'Pasien tidak diketahui',
    noSession: 'Belum ada sesi',
    activeSession: 'Sedang berlangsung',
    alertUnit: 'alert',
    ageUnit: 'tahun',
    ageShort: 'th',
    weekUnit: 'minggu',
    weekShort: 'mg',
    estimatedFhr: 'Estimasi DJJ',
    maternalHr: 'Nadi ibu',
    signalQualityPercent: 'Kualitas sinyal',
    contraction: {
      unknown: 'Belum tersedia dari sistem',
      none: 'Tidak tampak pola kontraksi',
      mild: 'Indikator ringan',
      regular: 'Pola teratur terdeteksi',
      strong: 'Indikator kuat',
    },
    monitoringStatus: {
      active: 'Aktif',
      finished: 'Selesai',
      empty: 'Belum ada sesi',
    },
    risk: {
      low: {
        label: 'Pemantauan Rutin',
        shortLabel: 'Rendah',
        className: 'low',
        description: 'Tidak ada alert sedang atau tinggi pada sesi yang tersedia.',
      },
      medium: {
        label: 'Perlu Observasi',
        shortLabel: 'Sedang',
        className: 'medium',
        description: 'Ada indikasi awal yang perlu dipantau ulang oleh nakes.',
      },
      high: {
        label: 'Segera Tinjau',
        shortLabel: 'Tinggi',
        className: 'high',
        description: 'Ada alert prioritas tinggi yang perlu ditinjau nakes.',
      },
      unknown: {
        label: 'Data Perlu Diverifikasi',
        shortLabel: 'Tidak dikenali',
        className: 'unknown',
        description: 'Status risiko tidak dikenali sistem dan perlu verifikasi data oleh nakes.',
      },
    },
    filters: [
      { key: 'all', label: 'Semua' },
      { key: 'alerts', label: 'Ada Alert' },
      { key: 'high', label: 'Segera Tinjau' },
      { key: 'medium', label: 'Perlu Observasi' },
      { key: 'low', label: 'Rutin' },
    ],
    statusFilters: [
      { key: 'all', label: 'Semua Status' },
      { key: 'active', label: 'Sedang Dipantau' },
      { key: 'inactive', label: 'Tidak Aktif' },
    ],
    alertStatus: {
      open: 'Belum ditangani',
      acknowledged: 'Ditandai ditangani',
      in_review: 'Sedang ditinjau',
      resolved: 'Selesai',
      false_positive: 'Bukan alert aktif',
      archived: 'Diarsipkan',
    },
    csvHeaders: ['Kode Pasien', 'Nama', 'Usia', 'Gestasi', 'Sesi', 'Status Risiko', 'Alert Aktif', 'Kualitas Sinyal'],
    csvPrefix: 'Pasien_FetalGuard',
  },
  en: {
    dataUnavailable: 'Not available from system',
    unknownPatient: 'Unknown patient',
    noSession: 'No session yet',
    activeSession: 'In progress',
    alertUnit: 'alert',
    ageUnit: 'years',
    ageShort: 'yr',
    weekUnit: 'weeks',
    weekShort: 'wk',
    estimatedFhr: 'Estimated FHR',
    maternalHr: 'Maternal pulse',
    signalQualityPercent: 'Signal quality',
    contraction: {
      unknown: 'Not available from system',
      none: 'No contraction pattern shown',
      mild: 'Mild indicator',
      regular: 'Regular pattern detected',
      strong: 'Strong indicator',
    },
    monitoringStatus: {
      active: 'Active',
      finished: 'Completed',
      empty: 'No session yet',
    },
    risk: {
      low: {
        label: 'Routine Monitoring',
        shortLabel: 'Low',
        className: 'low',
        description: 'No medium or high alert is present in the available sessions.',
      },
      medium: {
        label: 'Needs Observation',
        shortLabel: 'Medium',
        className: 'medium',
        description: 'An early indication needs repeat review by the clinician.',
      },
      high: {
        label: 'Review Soon',
        shortLabel: 'High',
        className: 'high',
        description: 'A high-priority alert needs clinician review.',
      },
      unknown: {
        label: 'Verify Data',
        shortLabel: 'Unrecognized',
        className: 'unknown',
        description: 'The risk status is not recognized and needs clinician data verification.',
      },
    },
    filters: [
      { key: 'all', label: 'All' },
      { key: 'alerts', label: 'Has Alert' },
      { key: 'high', label: 'Review Soon' },
      { key: 'medium', label: 'Needs Observation' },
      { key: 'low', label: 'Routine' },
    ],
    statusFilters: [
      { key: 'all', label: 'All Statuses' },
      { key: 'active', label: 'Being Monitored' },
      { key: 'inactive', label: 'Inactive' },
    ],
    alertStatus: {
      open: 'Open',
      acknowledged: 'Marked handled',
      in_review: 'In review',
      resolved: 'Resolved',
      false_positive: 'Not an active alert',
      archived: 'Archived',
    },
    csvHeaders: ['Patient Code', 'Name', 'Age', 'Gestation', 'Session', 'Risk Status', 'Active Alerts', 'Signal Quality'],
    csvPrefix: 'FetalGuard_Patients',
  },
};

export const DATA_UNAVAILABLE = CLINICIAN_COPY.id.dataUnavailable;
export const UNKNOWN_PATIENT = CLINICIAN_COPY.id.unknownPatient;
export const RISK_META = CLINICIAN_COPY.id.risk;
export const FILTERS = CLINICIAN_COPY.id.filters;
export const STATUS_FILTERS = CLINICIAN_COPY.id.statusFilters;

export function normalizeRiskLevel(risk) {
  return Object.prototype.hasOwnProperty.call(RISK_PRIORITY, risk) ? risk : 'unknown';
}

export function getClinicianCopy(locale = 'id') {
  return CLINICIAN_COPY[locale] || CLINICIAN_COPY.id;
}

export function getRiskMeta(risk, locale = 'id') {
  const copy = getClinicianCopy(locale);
  return copy.risk[risk] || copy.risk.unknown;
}

export function getRiskFilters(locale = 'id') {
  return getClinicianCopy(locale).filters;
}

export function getStatusFilters(locale = 'id') {
  return getClinicianCopy(locale).statusFilters;
}

export function normalizeClinicianStatistics(statistics) {
  if (!statistics || typeof statistics !== 'object' || Array.isArray(statistics)) return null;

  const values = {
    total: statistics.total_patients,
    monitoring: statistics.active_monitoring,
    highRisk: statistics.high_priority_patients,
    alerts: statistics.open_alerts,
  };

  const hasValidCounts = Object.values(values).every(
    (value) => Number.isSafeInteger(value) && value >= 0,
  ) && values.monitoring <= values.total && values.highRisk <= values.total;

  return hasValidCounts ? values : null;
}

export function formatAggregateCount(value) {
  return Number.isSafeInteger(value) && value >= 0 ? String(value) : '—';
}

/**
 * Computes a real, honest sensor-data-availability ratio from the patient
 * rows already loaded on the dashboard (no fabricated/aggregate backend
 * value is assumed). Used by both the operations strip and the reports tab
 * so the two stay consistent.
 */
export function computeSensorCoverage(patientRows) {
  const total = patientRows.length;
  const ready = patientRows.filter((patient) => patient.hasSensorSummary).length;
  const percent = total > 0 ? Math.round((ready / total) * 100) : null;
  return { ready, total, percent };
}

export function getInitials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'FG';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

export function createPatientCode(id, assignedCode) {
  if (assignedCode) return String(assignedCode).toUpperCase();
  if (!id) return 'FG-BELUM-ADA';
  return `FG-${String(id).replace(/-/g, '').slice(0, 12).toUpperCase()}`;
}

export function dedupeSessions(patient) {
  const sessions = [
    ...(patient.active_sessions || []),
    patient.latest_session,
  ].filter(Boolean);

  const unique = new Map();
  sessions.forEach((session) => unique.set(session.id, session));

  return [...unique.values()].sort((a, b) => (
    new Date(b.start_time || 0).getTime() - new Date(a.start_time || 0).getTime()
  ));
}

export function formatSessionLabel(session, locale = 'id') {
  const copy = getClinicianCopy(locale);
  if (!session) return copy.noSession;
  if (session.status === 'active') return copy.activeSession;
  return formatRelativeTime(session.end_time || session.start_time, locale);
}

export function mapAlertsBySession(alerts) {
  return alerts.reduce((grouped, alert) => {
    const current = grouped.get(alert.session_id) || [];
    current.push(alert);
    grouped.set(alert.session_id, current);
    return grouped;
  }, new Map());
}

export function getHighestRiskForSessions(sessionIds, alertsBySession) {
  return sessionIds.reduce((highest, sessionId) => {
    const sessionAlerts = alertsBySession.get(sessionId) || [];
    return sessionAlerts.reduce((current, alert) => {
      const riskLevel = normalizeRiskLevel(alert.risk_level);
      return RISK_PRIORITY[riskLevel] > RISK_PRIORITY[current] ? riskLevel : current;
    }, highest);
  }, 'low');
}

export function countOpenAlertsForSessions(sessionIds, alertsBySession) {
  return sessionIds.reduce((total, sessionId) => {
    const sessionAlerts = alertsBySession.get(sessionId) || [];
    return total + sessionAlerts.filter((alert) => !alert.is_acknowledged).length;
  }, 0);
}

export function findPatientForSession(sessionId, patients) {
  return patients.find((item) => dedupeSessions(item).some((session) => session.id === sessionId)) || null;
}

export function toPatientViewModel(patient, alertsBySession, locale = 'id') {
  const copy = getClinicianCopy(locale);
  const sessions = dedupeSessions(patient);
  const latestSession = sessions[0] || null;
  const sensorSummary = latestSession?.sensor_summary || null;
  const sessionIds = sessions.map((session) => session.id);
  const currentRisk = getHighestRiskForSessions(sessionIds, alertsBySession);
  const activeAlerts = countOpenAlertsForSessions(sessionIds, alertsBySession);
  const isActiveMonitoring = sessions.some((session) => session.status === 'active');
  const hasSession = Boolean(latestSession);
  const gestationalAge = patient.gestational_age_weeks;

  return {
    id: patient.id,
    patientCode: createPatientCode(patient.id, patient.patient_code),
    name: patient.name || copy.unknownPatient,
    age: patient.age,
    ageLabel: patient.age ? `${patient.age} ${copy.ageUnit}` : copy.dataUnavailable,
    initials: getInitials(patient.name),
    gestationalAge,
    gestationalAgeLabel: gestationalAge ? `${gestationalAge} ${copy.weekUnit}` : copy.dataUnavailable,
    lastSession: formatSessionLabel(latestSession, locale),
    lastSessionTime: formatDateTime(latestSession?.start_time, locale),
    lastSessionDuration: latestSession
      ? formatDuration(latestSession.start_time, latestSession.end_time, latestSession.status, locale)
      : copy.dataUnavailable,
    currentRisk,
    riskMeta: getRiskMeta(currentRisk, locale),
    activeAlerts,
    isActiveMonitoring,
    monitoringStatus: isActiveMonitoring
      ? copy.monitoringStatus.active
      : hasSession
        ? copy.monitoringStatus.finished
        : copy.monitoringStatus.empty,
    sessions,
    hasSensorSummary: Boolean(sensorSummary),
    fhrLabel: sensorSummary?.fhr_estimate_bpm ? `${sensorSummary.fhr_estimate_bpm} bpm` : copy.dataUnavailable,
    maternalHrLabel: sensorSummary?.maternal_hr_bpm ? `${sensorSummary.maternal_hr_bpm} bpm` : copy.dataUnavailable,
    signalLabel: typeof sensorSummary?.signal_quality_index === 'number'
      ? `${Math.round(sensorSummary.signal_quality_index * 100)}%`
      : copy.dataUnavailable,
    contractionLabel: sensorSummary
      ? copy.contraction[sensorSummary.contraction_indicator || 'unknown'] || copy.contraction.unknown
      : copy.dataUnavailable,
    sampleCount: sensorSummary?.sample_count || 0,
    sensorSource: sensorSummary?.source || null,
    isSensorSimulated: Boolean(sensorSummary?.is_simulated),
  };
}

export function toAlertViewModel(alert, patients, locale = 'id') {
  const copy = getClinicianCopy(locale);
  const patientFromId = alert.patient_id ? patients.find((patient) => patient.id === alert.patient_id) : null;
  const patientFromSession = findPatientForSession(alert.session_id, patients);
  const patient = patientFromId || patientFromSession;
  const patientId = alert.patient_id || patient?.id || null;
  const lifecycleStatus = alert.status || (alert.is_acknowledged ? 'acknowledged' : 'open');
  const riskLevel = normalizeRiskLevel(alert.risk_level);

  return {
    id: alert.id,
    patientId,
    patientName: patient?.name || copy.unknownPatient,
    patientCode: createPatientCode(patientId, patient?.patient_code),
    type: riskLevel === 'high' ? 'critical' : 'warning',
    riskLevel,
    riskMeta: getRiskMeta(riskLevel, locale),
    message: alert.message,
    timestamp: formatRelativeTime(alert.created_at, locale),
    absoluteTime: formatDateTime(alert.created_at, locale),
    sessionId: alert.session_id,
    status: lifecycleStatus,
    statusLabel: copy.alertStatus[lifecycleStatus] || copy.alertStatus.open,
    isAcknowledged: alert.is_acknowledged,
    acknowledgementNote: alert.acknowledgement_note || '',
    version: Number.isInteger(alert.version) ? alert.version : 1,
  };
}

export function csvEscape(value) {
  let stringValue = String(value ?? '');
  if (/^[=+\-@]/.test(stringValue.trimStart())) {
    stringValue = `'${stringValue}`;
  }
  if (/[",\r\n]/.test(stringValue)) {
    return `"${stringValue.replace(/"/g, '""')}"`;
  }
  return stringValue;
}

export function exportPatientCsv(rows, locale = 'id') {
  const copy = getClinicianCopy(locale);
  const body = rows.map((patient) => [
    patient.patientCode,
    patient.name,
    patient.age ? `${patient.age} ${copy.ageUnit}` : copy.dataUnavailable,
    patient.gestationalAge ? `${patient.gestationalAge} ${copy.weekUnit}` : copy.dataUnavailable,
    patient.lastSession,
    patient.riskMeta.label,
    patient.activeAlerts,
    patient.signalLabel,
  ]);
  const csv = [copy.csvHeaders, ...body].map((row) => row.map(csvEscape).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `${copy.csvPrefix}_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
