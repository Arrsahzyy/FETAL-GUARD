import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import {
  createGatewayTelemetryV2Value,
  createGatewayTimeSyncValue,
  getBluetoothScanErrorCode,
  validateTelemetryEnvelope,
} from './useBluetooth.js';

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

const goldenEnvelope = JSON.parse(fs.readFileSync(
  new URL('../../contracts/telemetry/v1/golden-esp32.json', import.meta.url),
  'utf8',
));

const goldenV2Envelope = JSON.parse(fs.readFileSync(
  new URL('../../contracts/telemetry/v2/golden-esp32-window.json', import.meta.url),
  'utf8',
));

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

test('gateway time sync fits the minimum BLE payload and contains epoch milliseconds', () => {
  const value = createGatewayTimeSyncValue(1786900000000);
  const command = new TextDecoder().decode(value);

  assert.equal(command, 'T1786900000000');
  assert.ok(value.byteLength <= 20);
});

test('native gateway v2 command respects negotiated MTU and firmware cap', () => {
  assert.equal(new TextDecoder().decode(createGatewayTelemetryV2Value(185)), 'V2:180');
  assert.equal(new TextDecoder().decode(createGatewayTelemetryV2Value(23)), 'V2:20');
  assert.equal(new TextDecoder().decode(createGatewayTelemetryV2Value(512)), 'V2:180');
});

test('web bluetooth scan errors retain an actionable cause', () => {
  assert.equal(getBluetoothScanErrorCode({ name: 'NotFoundError' }), 'scan_no_device_selected');
  assert.equal(getBluetoothScanErrorCode({ name: 'SecurityError' }), 'scan_permission_denied');
  assert.equal(getBluetoothScanErrorCode({ name: 'NotSupportedError' }), 'ble_unsupported');
  assert.equal(getBluetoothScanErrorCode({ name: 'NotReadableError' }), 'ble_adapter_unavailable');
  assert.equal(getBluetoothScanErrorCode(new Error('unknown')), 'scan_failed');
});

test('device packet signatures are carried through the gateway unchanged', () => {
  // The gateway cannot verify this HMAC -- only the backend holds the key -- so
  // the contract it must honour is that the value reaches the upload untouched.
  const v1 = validateTelemetryEnvelope(goldenEnvelope);
  const v2 = validateTelemetryEnvelope(goldenV2Envelope);

  assert.equal(v1.packetSignature, goldenEnvelope.packet_signature);
  assert.equal(v2.packetSignature, goldenV2Envelope.packet_signature);
  assert.match(v1.packetSignature, /^[0-9a-f]{64}$/);
});

test('an unprovisioned device omitting a signature still parses', () => {
  const packet = validateTelemetryEnvelope(validEnvelope());

  assert.equal(packet.packetSignature, null);
});

test('a malformed packet signature is rejected instead of forwarded', () => {
  for (const signature of ['not-hex', '', 'ab'.repeat(31), 'ab'.repeat(33), 'g'.repeat(64), 123]) {
    assert.throws(
      () => validateTelemetryEnvelope({ ...validEnvelope(), packet_signature: signature }),
      /invalid_packet_signature/,
      `expected rejection for ${JSON.stringify(signature)}`,
    );
  }
});

test('signature casing is normalized so it still matches the backend digest', () => {
  const packet = validateTelemetryEnvelope({
    ...validEnvelope(),
    packet_signature: `  ${'AB'.repeat(32)}  `,
  });

  assert.equal(packet.packetSignature, 'ab'.repeat(32));
});

test('telemetry v2 preserves per-modality sample rates and four-channel layout', () => {
  const packet = validateTelemetryEnvelope(goldenV2Envelope);

  assert.deepEqual(packet.sampleRatesHz, { p: 200, fsr: 50, hr_ir: 100, hr_red: 100 });
  assert.equal(packet.channelLayout.p, 4);
  assert.equal(packet.sampleRateHz, null);
});

test('shared ESP32 golden packet satisfies the browser gateway contract', () => {
  const packet = validateTelemetryEnvelope(goldenEnvelope);

  assert.equal(packet.deviceUid, 'FETAL-GUARD-001');
  assert.equal(packet.sequenceNumber, 0);
  assert.equal(packet.fhr, 142);
  assert.equal(packet.motherHR, 82);
  assert.equal(packet.spo2, 97);
  assert.equal(packet.contractionLevel, 28);
  assert.equal(packet.signalQuality, 76);
  assert.deepEqual(packet.rawChannels.p, [2048, 2051, 2046, 2053]);
});

test('patient monitoring fields fail closed when a device sends out-of-range values', () => {
  const envelope = validEnvelope();
  envelope.telemetry.contractionLevel = 101;

  assert.throws(
    () => validateTelemetryEnvelope(envelope),
    /invalid_contraction_level/,
  );
});
