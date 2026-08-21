import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getAIStatusTone,
  getPatientAIReadings,
  normalizeAIAnalysisPage,
  normalizeAIAnalysisResult,
} from './aiAnalysisModels.js';

const result = {
  id: 'result-1',
  patient_id: 'patient-1',
  session_id: 'session-1',
  device_id: 'device-1',
  window_started_at: '2026-08-17T10:00:00Z',
  window_ended_at: '2026-08-17T10:01:00Z',
  quality_status: 'usable',
  quality_score: 0.92,
  fhr_bpm: 142,
  maternal_hr_bpm: 82,
  contraction_probability: 0.2,
  screening_status: 'routine_monitoring',
  uncertainty: 0.12,
  reasons: ['screening_model_signal'],
  visibility: 'patient',
  is_simulated: false,
  model_version: 'clinical-001',
  preprocessing_version: 'pre-v2',
  created_at: '2026-08-17T10:01:02Z',
  review: {
    decision: 'confirmed',
    note: null,
    version: 1,
  },
};

test('normalizes a patient-visible AI result without exposing unbounded values', () => {
  const normalized = normalizeAIAnalysisResult(result);

  assert.equal(normalized.id, 'result-1');
  assert.equal(normalized.fhrBpm, 142);
  assert.equal(normalized.maternalHrBpm, 82);
  assert.equal(normalized.tone, 'success');
  assert.equal(normalized.review.version, 1);
});

test('rejects malformed result contracts and sorts valid pages newest first', () => {
  assert.equal(normalizeAIAnalysisResult({ ...result, quality_score: 4 }), null);
  assert.equal(normalizeAIAnalysisResult({ ...result, window_ended_at: 'invalid' }), null);

  const older = {
    ...result,
    id: 'result-older',
    window_started_at: '2026-08-17T09:59:00Z',
    window_ended_at: '2026-08-17T10:00:00Z',
  };
  assert.deepEqual(
    normalizeAIAnalysisPage({ items: [older, result] }).map((item) => item.id),
    ['result-1', 'result-older'],
  );
});

test('patient measurements fail closed for weak or simulated results', () => {
  const normalized = normalizeAIAnalysisResult(result);
  assert.deepEqual(getPatientAIReadings(normalized), { fhrBpm: 142, maternalHrBpm: 82 });
  assert.deepEqual(
    getPatientAIReadings({ ...normalized, qualityStatus: 'limited' }),
    { fhrBpm: null, maternalHrBpm: null },
  );
  assert.deepEqual(
    getPatientAIReadings({ ...normalized, isSimulated: true }),
    { fhrBpm: null, maternalHrBpm: null },
  );
  assert.equal(getAIStatusTone('review_with_clinician'), 'warning');
  assert.equal(getAIStatusTone('insufficient_signal'), 'info');
});
