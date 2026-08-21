import assert from 'node:assert/strict';
import test from 'node:test';
import {
  DEFAULT_PATIENT_PREFERENCES,
  getPatientPreferences,
  sanitizePatientPreferences,
  setPatientPreferences,
  updatePatientPreference,
} from './patientPreferences.js';

const createStorage = () => {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  };
};

test('patient preferences fail closed for malformed and non-boolean values', () => {
  assert.deepEqual(sanitizePatientPreferences({ pushNotifications: true, shareLocation: 'yes' }), {
    ...DEFAULT_PATIENT_PREFERENCES,
    pushNotifications: true,
  });
});

test('patient preferences persist independently for each user', () => {
  globalThis.localStorage = createStorage();
  setPatientPreferences('patient-a', { pushNotifications: true });
  updatePatientPreference('patient-b', 'uploadWifiOnly', true);
  assert.equal(getPatientPreferences('patient-a').pushNotifications, true);
  assert.equal(getPatientPreferences('patient-a').uploadWifiOnly, false);
  assert.equal(getPatientPreferences('patient-b').pushNotifications, false);
  assert.equal(getPatientPreferences('patient-b').uploadWifiOnly, true);
  delete globalThis.localStorage;
});

test('unsupported preference keys are rejected', () => {
  globalThis.localStorage = createStorage();
  assert.throws(
    () => updatePatientPreference('patient-a', 'diagnosisMode', true),
    /unsupported_patient_preference/,
  );
  delete globalThis.localStorage;
});
