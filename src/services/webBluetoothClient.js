const connectionKey = (deviceId, serviceUUID, characteristicUUID) => (
  `${deviceId}|${serviceUUID}|${characteristicUUID}`.toLowerCase()
);

const toDataView = (value) => {
  if (value instanceof DataView) return value;
  if (value instanceof ArrayBuffer) return new DataView(value);
  if (ArrayBuffer.isView(value)) {
    return new DataView(value.buffer, value.byteOffset, value.byteLength);
  }
  throw new TypeError('web_bluetooth_value_invalid');
};

export const createWebBluetoothClient = (bluetooth = globalThis.navigator?.bluetooth) => {
  const devices = new Map();
  const disconnectHandlers = new Map();
  const characteristics = new Map();
  const notificationHandlers = new Map();

  const getDevice = (deviceId) => {
    const device = devices.get(deviceId);
    if (!device) throw new Error('web_bluetooth_device_not_selected');
    return device;
  };

  const getCharacteristic = async (deviceId, serviceUUID, characteristicUUID) => {
    const key = connectionKey(deviceId, serviceUUID, characteristicUUID);
    if (characteristics.has(key)) return characteristics.get(key);

    const device = getDevice(deviceId);
    const server = device.gatt?.connected
      ? device.gatt
      : await device.gatt?.connect();
    if (!server) throw new Error('web_bluetooth_gatt_unavailable');
    const service = await server.getPrimaryService(serviceUUID);
    const characteristic = await service.getCharacteristic(characteristicUUID);
    characteristics.set(key, characteristic);
    return characteristic;
  };

  return {
    async initialize() {
      if (!bluetooth?.requestDevice) throw new Error('web_bluetooth_unavailable');
    },

    async requestLEScan(options, onResult) {
      if (!bluetooth?.requestDevice) throw new Error('web_bluetooth_unavailable');
      const requestOptions = {
        optionalServices: options?.optionalServices || [],
      };
      if (options?.namePrefix) {
        requestOptions.filters = [{ namePrefix: options.namePrefix }];
      } else {
        requestOptions.acceptAllDevices = true;
      }

      const device = await bluetooth.requestDevice(requestOptions);
      devices.set(device.id, device);
      onResult?.({
        device: { deviceId: device.id, name: device.name || null },
        localName: device.name || null,
        rssi: null,
      });
    },

    async stopLEScan() {
      // The browser chooser resolves one explicit user selection and has no
      // background scan to stop.
    },

    async connect(deviceId, onDisconnect) {
      const device = getDevice(deviceId);
      if (!device.gatt) throw new Error('web_bluetooth_gatt_unavailable');
      const previousHandler = disconnectHandlers.get(deviceId);
      if (previousHandler) {
        device.removeEventListener('gattserverdisconnected', previousHandler);
      }
      const handler = () => onDisconnect?.();
      disconnectHandlers.set(deviceId, handler);
      device.addEventListener('gattserverdisconnected', handler);
      await device.gatt.connect();
    },

    async disconnect(deviceId) {
      const device = devices.get(deviceId);
      if (!device) return;
      const handler = disconnectHandlers.get(deviceId);
      if (handler) device.removeEventListener('gattserverdisconnected', handler);
      disconnectHandlers.delete(deviceId);
      for (const key of characteristics.keys()) {
        if (key.startsWith(`${deviceId.toLowerCase()}|`)) characteristics.delete(key);
      }
      if (device.gatt?.connected) device.gatt.disconnect();
    },

    async startNotifications(deviceId, serviceUUID, characteristicUUID, onValue) {
      const characteristic = await getCharacteristic(
        deviceId,
        serviceUUID,
        characteristicUUID,
      );
      const key = connectionKey(deviceId, serviceUUID, characteristicUUID);
      const previousHandler = notificationHandlers.get(key);
      if (previousHandler) {
        characteristic.removeEventListener('characteristicvaluechanged', previousHandler);
      }
      const handler = (event) => {
        if (event.target?.value) onValue(event.target.value);
      };
      notificationHandlers.set(key, handler);
      characteristic.addEventListener('characteristicvaluechanged', handler);
      await characteristic.startNotifications();
    },

    async stopNotifications(deviceId, serviceUUID, characteristicUUID) {
      const key = connectionKey(deviceId, serviceUUID, characteristicUUID);
      const characteristic = characteristics.get(key);
      if (!characteristic) return;
      const handler = notificationHandlers.get(key);
      if (handler) {
        characteristic.removeEventListener('characteristicvaluechanged', handler);
      }
      notificationHandlers.delete(key);
      await characteristic.stopNotifications();
    },

    async write(deviceId, serviceUUID, characteristicUUID, value) {
      const characteristic = await getCharacteristic(
        deviceId,
        serviceUUID,
        characteristicUUID,
      );
      const data = toDataView(value);
      if (typeof characteristic.writeValueWithResponse === 'function') {
        await characteristic.writeValueWithResponse(data);
        return;
      }
      await characteristic.writeValue(data);
    },
  };
};

export default createWebBluetoothClient;
