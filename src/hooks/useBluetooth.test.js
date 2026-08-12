import assert from 'node:assert/strict';
import test from 'node:test';

import { validateTelemetryEnvelope } from './useBluetooth.js';

const validEnvelope = () => ({
  schema_version: 1,
  device_uid: 'fg-belt-test',
  boot_id: 'boot-test-0001',
  sequence_number: 1,
  captured_at: '2026-08-09T10:00:00+07:00',
  sample_rate_hz: 100,
  telemetry: {
    battery: 80,
    charging: false,
  },
  channels: { p: [1024] },
});

test('telemetry validation normalizes stable packet identity and timestamp', () => {
  const packet = validateTelemetryEnvelope(validEnvelope());

  assert.equal(packet.deviceUid, 'FG-BELT-TEST');
  assert.equal(packet.bootId, 'boot-test-0001');
  assert.equal(packet.capturedAt, '2026-08-09T03:00:00.000Z');
  assert.equal(packet.charging, false);
});

test('telemetry validation rejects string booleans instead of treating false as true', () => {
  const envelope = validEnvelope();
  envelope.telemetry.charging = 'false';

  assert.throws(
    () => validateTelemetryEnvelope(envelope),
    /invalid_charging/,
  );
});
