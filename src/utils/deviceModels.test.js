import assert from 'node:assert/strict';
import test from 'node:test';
import {
  DEVICE_STATUS_OPTIONS,
  buildPatientLookup,
  claimCodeActionLabel,
  describeDeviceAssignment,
  describeDeviceStatus,
  deviceStatusClassName,
  formatLastSeen,
  signingKeyActionLabel,
} from './deviceModels.js';

test('every known status has a label and a tone', () => {
  for (const { value } of DEVICE_STATUS_OPTIONS) {
    const meta = describeDeviceStatus(value);
    assert.ok(meta.label, `${value} has a label`);
    assert.ok(meta.tone, `${value} has a tone`);
  }
});

test('unknown status stays visible as data that needs verification', () => {
  const meta = describeDeviceStatus('decommissioned-2029');
  assert.equal(meta.label, 'decommissioned-2029');
  assert.equal(meta.tone, 'info');
  assert.equal(describeDeviceStatus(null).label, 'Tidak diketahui');
});

test('status class name maps tone to the shared admin-status modifiers', () => {
  assert.equal(deviceStatusClassName('active'), 'admin-status admin-status--ready');
  assert.equal(deviceStatusClassName('maintenance'), 'admin-status admin-status--warning');
  assert.equal(deviceStatusClassName('retired'), 'admin-status admin-status--inactive');
  assert.equal(deviceStatusClassName('lost'), 'admin-status admin-status--danger');
  // 'registered' / unknown -> base pill, no modifier
  assert.equal(deviceStatusClassName('registered'), 'admin-status');
  assert.equal(deviceStatusClassName('what'), 'admin-status');
});

test('assignment name resolves from the patient lookup, with honest fallbacks', () => {
  const lookup = buildPatientLookup([
    { id: 'p1', name: 'Siti' },
    { id: 'p2', name: 'Adit' },
    null,
    { name: 'no id ignored' },
  ]);
  assert.equal(lookup.size, 2);
  assert.equal(describeDeviceAssignment({ patient_id: 'p2' }, lookup), 'Adit');
  assert.equal(describeDeviceAssignment({ patient_id: null }, lookup), 'Belum di-assign');
  assert.equal(
    describeDeviceAssignment({ patient_id: 'p9' }, lookup),
    'Terpasang (pasien di luar halaman)',
  );
});

test('formatLastSeen distinguishes "never" from a real timestamp', () => {
  assert.equal(formatLastSeen(null), 'Belum pernah');
  assert.equal(formatLastSeen(undefined), 'Belum pernah');
  assert.equal(formatLastSeen(new Date().toISOString()), 'baru saja');
});

test('secret action labels reflect whether a secret already exists', () => {
  assert.equal(signingKeyActionLabel({}), 'Terbitkan signing key');
  assert.equal(
    signingKeyActionLabel({ packet_secret_provisioned_at: '2026-09-07T00:00:00Z' }),
    'Rotasi signing key',
  );
  assert.equal(claimCodeActionLabel({}), 'Terbitkan claim code');
  assert.equal(
    claimCodeActionLabel({ claim_code_set_at: '2026-09-07T00:00:00Z' }),
    'Terbitkan ulang claim code',
  );
});
