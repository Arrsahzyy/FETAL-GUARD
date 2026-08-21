import assert from 'node:assert/strict';
import test from 'node:test';

import { createWebBluetoothClient } from './webBluetoothClient.js';

const SERVICE_UUID = '0000ffe0-0000-1000-8000-00805f9b34fb';
const CHARACTERISTIC_UUID = '0000ffe1-0000-1000-8000-00805f9b34fb';

test('web bluetooth adapter selects, connects, receives, and writes gateway data', async () => {
  const characteristicListeners = new Map();
  let writtenValue = null;
  const characteristic = {
    addEventListener(type, handler) { characteristicListeners.set(type, handler); },
    removeEventListener(type) { characteristicListeners.delete(type); },
    async startNotifications() {},
    async stopNotifications() {},
    async writeValueWithResponse(value) {
      writtenValue = new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    },
  };
  const server = {
    async getPrimaryService(uuid) {
      assert.equal(uuid, SERVICE_UUID);
      return {
        async getCharacteristic(characteristicUuid) {
          assert.equal(characteristicUuid, CHARACTERISTIC_UUID);
          return characteristic;
        },
      };
    },
  };
  const deviceListeners = new Map();
  const device = {
    id: 'browser-device-1',
    name: 'FETAL-GUARD-001',
    addEventListener(type, handler) { deviceListeners.set(type, handler); },
    removeEventListener(type) { deviceListeners.delete(type); },
    gatt: {
      connected: false,
      async connect() {
        this.connected = true;
        return server;
      },
      disconnect() { this.connected = false; },
      getPrimaryService: server.getPrimaryService,
    },
  };
  let requestOptions = null;
  const client = createWebBluetoothClient({
    async requestDevice(options) {
      requestOptions = options;
      return device;
    },
  });

  await client.initialize();
  let discovered = null;
  await client.requestLEScan(
    { namePrefix: 'FETAL-GUARD', optionalServices: [SERVICE_UUID] },
    (result) => { discovered = result; },
  );
  assert.deepEqual(requestOptions.filters, [{ namePrefix: 'FETAL-GUARD' }]);
  assert.equal(discovered.device.name, 'FETAL-GUARD-001');

  await client.connect(device.id, () => undefined);
  let notification = null;
  await client.startNotifications(
    device.id,
    SERVICE_UUID,
    CHARACTERISTIC_UUID,
    (value) => { notification = value; },
  );
  const notificationBytes = new TextEncoder().encode('{"ok":true}\n');
  characteristicListeners.get('characteristicvaluechanged')({
    target: { value: new DataView(notificationBytes.buffer) },
  });
  assert.equal(new TextDecoder().decode(notification), '{"ok":true}\n');

  const syncBytes = new TextEncoder().encode('T1786900000000');
  await client.write(
    device.id,
    SERVICE_UUID,
    CHARACTERISTIC_UUID,
    new DataView(syncBytes.buffer),
  );
  assert.equal(new TextDecoder().decode(writtenValue), 'T1786900000000');
});
