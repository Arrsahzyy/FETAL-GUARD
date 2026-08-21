import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getPatientHomeSessionReadings,
  normalizePatientHomeSession,
  normalizePatientHomeSessions,
} from './patientHomeSummary.js';

const session = {
  id: 'session-1',
  status: 'completed',
  start_time: '2026-08-20T10:00:00Z',
  end_time: '2026-08-20T10:20:00Z',
  last_data_at: '2026-08-20T10:19:59Z',
  sensor_summary: {
    fhr_estimate_bpm: 142,
    maternal_hr_bpm: 82,
    signal_quality_index: 0.91,
    contraction_indicator: 'mild',
    sample_count: 1200,
    source: 'device',
    is_simulated: false,
    updated_at: '2026-08-20T10:19:59Z',
  },
};

test('normalizes the stored session summary used by the patient home page', () => {
  const normalized = normalizePatientHomeSession(session);

  assert.equal(normalized.id, 'session-1');
  assert.equal(normalized.summary.fhrBpm, 142);
  assert.equal(normalized.summary.signalQuality, 0.91);
  assert.equal(normalized.summary.contractionIndicator, 'mild');
});

test('sorts sessions newest first and rejects malformed session contracts', () => {
  const newer = {
    ...session,
    id: 'session-2',
    start_time: '2026-08-21T10:00:00Z',
  };

  assert.deepEqual(
    normalizePatientHomeSessions([session, newer]).map((item) => item.id),
    ['session-2', 'session-1'],
  );
  assert.equal(normalizePatientHomeSession({ ...session, start_time: 'invalid' }), null);
  assert.equal(normalizePatientHomeSession({ ...session, status: 'unknown' }), null);
});

test('monitoring readings fail closed for simulated or out-of-contract values', () => {
  const normalized = normalizePatientHomeSession(session);
  assert.deepEqual(getPatientHomeSessionReadings(normalized), {
    fhrBpm: 142,
    maternalHrBpm: 82,
    signalQuality: 0.91,
    contractionIndicator: 'mild',
  });

  const simulated = normalizePatientHomeSession({
    ...session,
    sensor_summary: { ...session.sensor_summary, is_simulated: true },
  });
  assert.deepEqual(getPatientHomeSessionReadings(simulated), {
    fhrBpm: null,
    maternalHrBpm: null,
    signalQuality: null,
    contractionIndicator: 'unknown',
  });

  const invalid = normalizePatientHomeSession({
    ...session,
    sensor_summary: {
      ...session.sensor_summary,
      fhr_estimate_bpm: 500,
      signal_quality_index: 3,
    },
  });
  assert.equal(invalid.summary.fhrBpm, null);
  assert.equal(invalid.summary.signalQuality, null);
});
