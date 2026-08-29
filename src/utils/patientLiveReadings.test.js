import assert from 'node:assert/strict';
import test from 'node:test';

import { getPatientLiveReadings } from './patientLiveReadings.js';

const telemetry = {
  fhr: 142,
  maternalHeartRate: 82,
  spo2: 97,
  signalQuality: 76,
  contractionLevel: 28,
};

test('returns all verified patient readings while telemetry is live', () => {
  assert.deepEqual(getPatientLiveReadings(telemetry, true), telemetry);
});

test('clears every patient reading when telemetry becomes stale', () => {
  assert.deepEqual(getPatientLiveReadings(telemetry, false), {
    fhr: null,
    maternalHeartRate: null,
    spo2: null,
    signalQuality: null,
    contractionLevel: null,
  });
});
