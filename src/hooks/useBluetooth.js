import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Capacitor } from '@capacitor/core';
import { createWebBluetoothClient } from '../services/webBluetoothClient.js';

const DEFAULT_CONFIG = {
  deviceNamePrefix: 'FETAL-GUARD',
  serviceUUID: '0000ffe0-0000-1000-8000-00805f9b34fb',
  characteristicUUID: '0000ffe1-0000-1000-8000-00805f9b34fb',
  scanTimeout: 10000,
  maxReconnectAttempts: 5,
  reconnectBaseDelay: 1000,
};

const MAX_FRAME_BYTES = 64 * 1024;
const MAX_TRANSPORT_PACKET_QUEUE = 512;

export const getBluetoothScanErrorCode = (error) => {
  switch (error?.name) {
    case 'NotFoundError':
      return 'scan_no_device_selected';
    case 'SecurityError':
      return 'scan_permission_denied';
    case 'NotSupportedError':
      return 'ble_unsupported';
    case 'NotReadableError':
      return 'ble_adapter_unavailable';
    default:
      return 'scan_failed';
  }
};

export const createGatewayTimeSyncValue = (timestampMs = Date.now()) => {
  if (!Number.isSafeInteger(timestampMs) || timestampMs < 0) {
    throw new Error('invalid_time_sync');
  }
  const bytes = new TextEncoder().encode(`T${timestampMs}`);
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
};

export const createGatewayTelemetryV2Value = (mtu = 185) => {
  if (!Number.isInteger(mtu) || mtu < 23) throw new Error('invalid_mtu');
  // Leave three bytes for the ATT header and cap the application fragment so
  // the firmware does not depend on a controller accepting the maximum MTU.
  const chunkBytes = Math.max(20, Math.min(mtu - 3, 180));
  const bytes = new TextEncoder().encode(`V2:${chunkBytes}`);
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
};

const asFiniteNumber = (value, field, minimum, maximum) => {
  if (value === undefined || value === null) return null;
  const number = Number(value);
  if (!Number.isFinite(number) || number < minimum || number > maximum) {
    throw new Error(`invalid_${field}`);
  }
  return number;
};

const asBoolean = (value, field) => {
  if (value === undefined || value === null) return false;
  if (typeof value !== 'boolean') throw new Error(`invalid_${field}`);
  return value;
};

export const validateTelemetryEnvelope = (value) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('invalid_packet');
  }
  if (value.schema_version !== 1 && value.schema_version !== 2) {
    throw new Error('unsupported_schema');
  }
  if (typeof value.device_uid !== 'string' || value.device_uid.trim().length < 3) {
    throw new Error('missing_device_uid');
  }
  if (typeof value.boot_id !== 'string' || value.boot_id.trim().length < 8) {
    throw new Error('missing_boot_id');
  }
  if (!Number.isSafeInteger(value.sequence_number) || value.sequence_number < 0) {
    throw new Error('invalid_sequence');
  }

  const capturedAt = new Date(value.captured_at);
  if (!value.captured_at || Number.isNaN(capturedAt.getTime())) {
    throw new Error('invalid_timestamp');
  }

  const telemetry = value.telemetry && typeof value.telemetry === 'object'
    ? value.telemetry
    : value;

  const rawChannels = value.channels && typeof value.channels === 'object'
    && !Array.isArray(value.channels) ? value.channels : null;
  const sampleRatesHz = {};
  if (value.schema_version === 2) {
    if (!value.sample_rates_hz || typeof value.sample_rates_hz !== 'object') {
      throw new Error('missing_sample_rates');
    }
    for (const channel of ['p', 'fsr', 'hr_ir', 'hr_red']) {
      if (rawChannels?.[channel] === undefined) continue;
      sampleRatesHz[channel] = asFiniteNumber(
        value.sample_rates_hz[channel],
        `${channel}_sample_rate`,
        0.1,
        10000,
      );
      if (sampleRatesHz[channel] === null) throw new Error(`missing_${channel}_sample_rate`);
    }
    if (rawChannels?.p !== undefined && value.channel_layout?.p !== 4) {
      throw new Error('invalid_piezo_layout');
    }
  }

  return {
    deviceUid: value.device_uid.trim().toUpperCase(),
    bootId: value.boot_id.trim(),
    sequenceNumber: value.sequence_number,
    schemaVersion: value.schema_version,
    capturedAt: capturedAt.toISOString(),
    sampleRateHz: asFiniteNumber(value.sample_rate_hz, 'sample_rate', 0.1, 10000),
    sampleRatesHz: value.schema_version === 2 ? sampleRatesHz : null,
    channelLayout: value.schema_version === 2 ? { p: value.channel_layout?.p ?? null } : null,
    fhr: asFiniteNumber(telemetry.fhr, 'fhr', 30, 240),
    motherHR: asFiniteNumber(
      telemetry.motherHR ?? telemetry.maternal_heart_rate,
      'maternal_hr',
      30,
      220,
    ),
    spo2: asFiniteNumber(telemetry.spo2, 'spo2', 0, 100),
    signalQuality: asFiniteNumber(
      telemetry.signalQuality ?? telemetry.signal_quality,
      'signal_quality',
      0,
      100,
    ),
    contractionLevel: asFiniteNumber(
      telemetry.contractionLevel ?? telemetry.contraction_level,
      'contraction_level',
      0,
      100,
    ),
    battery: asFiniteNumber(
      telemetry.battery ?? telemetry.battery_percent,
      'battery',
      0,
      100,
    ),
    charging: asBoolean(telemetry.charging, 'charging'),
    rawChannels,
  };
};

export function useBluetooth(config = {}) {
  const {
    deviceNamePrefix = DEFAULT_CONFIG.deviceNamePrefix,
    serviceUUID = DEFAULT_CONFIG.serviceUUID,
    characteristicUUID = DEFAULT_CONFIG.characteristicUUID,
    scanTimeout = DEFAULT_CONFIG.scanTimeout,
    maxReconnectAttempts = DEFAULT_CONFIG.maxReconnectAttempts,
    reconnectBaseDelay = DEFAULT_CONFIG.reconnectBaseDelay,
  } = config;
  const cfg = useMemo(() => ({
    deviceNamePrefix,
    serviceUUID,
    characteristicUUID,
    scanTimeout,
    maxReconnectAttempts,
    reconnectBaseDelay,
  }), [
    characteristicUUID,
    deviceNamePrefix,
    maxReconnectAttempts,
    reconnectBaseDelay,
    scanTimeout,
    serviceUUID,
  ]);
  const [isScanning, setIsScanning] = useState(false);
  const [devices, setDevices] = useState([]);
  const [connectedDevice, setConnectedDevice] = useState(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [sensorData, setSensorData] = useState(null);
  const [error, setError] = useState(null);
  const [isAvailable, setIsAvailable] = useState(false);
  const [connectionState, setConnectionState] = useState('idle');
  const [lastPacketReceivedAt, setLastPacketReceivedAt] = useState(null);
  const [sensorPacketVersion, setSensorPacketVersion] = useState(0);
  const [transportDroppedPacketCount, setTransportDroppedPacketCount] = useState(0);

  const bleClientRef = useRef(null);
  const connectedDeviceRef = useRef(null);
  const configRef = useRef(cfg);
  const scanTimerRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const reconnectAttemptRef = useRef(0);
  const manualDisconnectRef = useRef(false);
  const mountedRef = useRef(true);
  const frameBufferRef = useRef('');
  const decoderRef = useRef(new TextDecoder());
  const connectRef = useRef(null);
  const connectAttemptRef = useRef(null);
  const connectionGenerationRef = useRef(0);
  const sensorPacketQueueRef = useRef([]);

  useEffect(() => {
    configRef.current = cfg;
  }, [cfg]);

  const clearScanTimer = useCallback(() => {
    if (scanTimerRef.current !== null) {
      window.clearTimeout(scanTimerRef.current);
      scanTimerRef.current = null;
    }
  }, []);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const stopScan = useCallback(async () => {
    clearScanTimer();
    const BleClient = bleClientRef.current;
    if (BleClient) {
      try {
        await BleClient.stopLEScan();
      } catch {
        // The native plugin may report that no scan is active; state is still safe to clear.
      }
    }
    if (mountedRef.current) setIsScanning(false);
  }, [clearScanTimer]);

  const scheduleReconnect = useCallback((deviceId) => {
    if (manualDisconnectRef.current || !mountedRef.current) return;
    const attempt = reconnectAttemptRef.current;
    if (attempt >= configRef.current.maxReconnectAttempts) {
      setConnectionState('error');
      setError('reconnect_failed');
      return;
    }

    clearReconnectTimer();
    const delay = Math.min(
      configRef.current.reconnectBaseDelay * (2 ** attempt),
      15000,
    );
    reconnectAttemptRef.current += 1;
    setConnectionState('reconnecting');
    reconnectTimerRef.current = window.setTimeout(() => {
      reconnectTimerRef.current = null;
      connectRef.current?.(deviceId, { reconnect: true }).catch(() => undefined);
    }, delay);
  }, [clearReconnectTimer]);

  const drainSensorPackets = useCallback(() => {
    if (sensorPacketQueueRef.current.length === 0) return [];
    return sensorPacketQueueRef.current.splice(0, sensorPacketQueueRef.current.length);
  }, []);

  const processNotification = useCallback((dataView) => {
    if (!mountedRef.current) return;
    try {
      const bytes = new Uint8Array(dataView.buffer, dataView.byteOffset, dataView.byteLength);
      frameBufferRef.current += decoderRef.current.decode(bytes, { stream: true });
      if (new TextEncoder().encode(frameBufferRef.current).byteLength > MAX_FRAME_BYTES) {
        throw new Error('frame_too_large');
      }

      const frames = frameBufferRef.current.split('\n');
      frameBufferRef.current = frames.pop() || '';

      if (frames.length === 0 && frameBufferRef.current.trim()) {
        try {
          const parsed = JSON.parse(frameBufferRef.current);
          frames.push(frameBufferRef.current);
          frameBufferRef.current = '';
          void parsed;
        } catch {
          return;
        }
      }

      let acceptedPacketCount = 0;
      let latestPacket = null;
      let latestReceivedAt = null;
      let frameError = null;
      for (const frame of frames) {
        if (!frame.trim()) continue;
        try {
          const receivedAtMs = Date.now();
          const packet = {
            ...validateTelemetryEnvelope(JSON.parse(frame)),
            receivedAtMs,
          };
          sensorPacketQueueRef.current.push(packet);
          if (sensorPacketQueueRef.current.length > MAX_TRANSPORT_PACKET_QUEUE) {
            const overflow = sensorPacketQueueRef.current.length - MAX_TRANSPORT_PACKET_QUEUE;
            sensorPacketQueueRef.current.splice(0, overflow);
            setTransportDroppedPacketCount((count) => count + overflow);
            frameError = new Error('transport_queue_overflow');
          }
          acceptedPacketCount += 1;
          latestPacket = packet;
          latestReceivedAt = receivedAtMs;
        } catch (packetError) {
          frameError = packetError;
        }
      }

      if (acceptedPacketCount > 0) {
        setSensorData(latestPacket);
        setLastPacketReceivedAt(latestReceivedAt);
        setSensorPacketVersion((version) => version + 1);
      }
      if (frameError) {
        setError(frameError.message || 'decode_failed');
      } else if (acceptedPacketCount > 0) {
        setError(null);
      }
    } catch (notificationError) {
      frameBufferRef.current = '';
      setError(notificationError.message || 'decode_failed');
    }
  }, []);

  const connect = useCallback((deviceId, options = {}) => {
    const BleClient = bleClientRef.current;
    if (!BleClient || !deviceId) {
      setError('ble_unavailable');
      return Promise.reject(new Error('ble_unavailable'));
    }

    const activeAttempt = connectAttemptRef.current;
    if (
      activeAttempt?.deviceId === deviceId
      && activeAttempt.generation === connectionGenerationRef.current
      && !manualDisconnectRef.current
    ) return activeAttempt.promise;
    if (connectedDeviceRef.current?.deviceId === deviceId && !options.reconnect) {
      return Promise.resolve(connectedDeviceRef.current);
    }

    const previousAttempt = activeAttempt?.promise || null;
    const generation = connectionGenerationRef.current + 1;
    connectionGenerationRef.current = generation;

    clearReconnectTimer();
    manualDisconnectRef.current = false;
    setIsConnecting(true);
    setConnectionState(options.reconnect ? 'reconnecting' : 'connecting');
    setError(null);

    const isCurrentAttempt = () => (
      mountedRef.current
      && !manualDisconnectRef.current
      && connectionGenerationRef.current === generation
    );
    const cleanupNativeConnection = async (targetDeviceId) => {
      try {
        await BleClient.stopNotifications(
          targetDeviceId,
          cfg.serviceUUID,
          cfg.characteristicUUID,
        );
      } catch {
        // Notification cleanup is idempotent across reconnect and device switches.
      }
      try {
        await BleClient.disconnect(targetDeviceId);
      } catch {
        // A failed or already-closed native connection is safe to ignore here.
      }
    };

    const operation = (async () => {
      let nativeConnectionOpened = false;
      let disconnectedDuringSetup = false;
      let suppressDisconnectCallback = false;
      try {
        await stopScan();
        if (previousAttempt) await previousAttempt.catch(() => undefined);
        if (!isCurrentAttempt()) throw new Error('connect_superseded');

        const previousDevice = connectedDeviceRef.current;
        if (previousDevice && previousDevice.deviceId !== deviceId) {
          await cleanupNativeConnection(previousDevice.deviceId);
          if (!isCurrentAttempt()) throw new Error('connect_superseded');
          if (connectedDeviceRef.current?.deviceId === previousDevice.deviceId) {
            connectedDeviceRef.current = null;
            setConnectedDevice(null);
          }
        }

        await BleClient.connect(deviceId, () => {
          if (!isCurrentAttempt() || suppressDisconnectCallback) return;
          disconnectedDuringSetup = true;
          if (connectedDeviceRef.current?.deviceId === deviceId) {
            connectedDeviceRef.current = null;
          }
          setConnectedDevice(null);
          setSensorData(null);
          setLastPacketReceivedAt(null);
          setConnectionState('disconnected');
          setError('unexpected_disconnect');
          scheduleReconnect(deviceId);
        });
        nativeConnectionOpened = true;
        if (!isCurrentAttempt() || disconnectedDuringSetup) {
          throw new Error('connect_superseded');
        }

        const device = devices.find((candidate) => candidate.deviceId === deviceId) || { deviceId };
        connectedDeviceRef.current = device;
        setConnectedDevice(device);
        frameBufferRef.current = '';
        decoderRef.current = new TextDecoder();
        if (!options.reconnect) {
          sensorPacketQueueRef.current = [];
          setTransportDroppedPacketCount(0);
        }

        const notificationHandler = (dataView) => {
          if (
            connectionGenerationRef.current !== generation
            || connectedDeviceRef.current?.deviceId !== deviceId
          ) return;
          processNotification(dataView);
        };
        await BleClient.startNotifications(
          deviceId,
          cfg.serviceUUID,
          cfg.characteristicUUID,
          notificationHandler,
        );
        await BleClient.write(
          deviceId,
          cfg.serviceUUID,
          cfg.characteristicUUID,
          createGatewayTimeSyncValue(),
        );
        if (Capacitor.isNativePlatform() && typeof BleClient.getMtu === 'function') {
          const negotiatedMtu = await BleClient.getMtu(deviceId);
          await BleClient.write(
            deviceId,
            cfg.serviceUUID,
            cfg.characteristicUUID,
            createGatewayTelemetryV2Value(negotiatedMtu),
          );
        }
        if (!isCurrentAttempt() || disconnectedDuringSetup) {
          throw new Error('connect_superseded');
        }

        reconnectAttemptRef.current = 0;
        setConnectionState('connected');
        return device;
      } catch (connectError) {
        suppressDisconnectCallback = true;
        if (nativeConnectionOpened) await cleanupNativeConnection(deviceId);
        const isSuperseded = !isCurrentAttempt() || connectError.message === 'connect_superseded';
        if (!isSuperseded) {
          if (connectedDeviceRef.current?.deviceId === deviceId) {
            connectedDeviceRef.current = null;
          }
          setConnectedDevice(null);
          setSensorData(null);
          setConnectionState(options.reconnect ? 'reconnecting' : 'error');
          setError(options.reconnect ? 'reconnect_failed' : 'connect_failed');
          if (options.reconnect) scheduleReconnect(deviceId);
        }
        throw connectError;
      } finally {
        if (connectionGenerationRef.current === generation && mountedRef.current) {
          setIsConnecting(false);
        }
      }
    })();

    connectAttemptRef.current = { deviceId, generation, promise: operation };
    const clearOperation = () => {
      if (connectAttemptRef.current?.promise === operation) {
        connectAttemptRef.current = null;
      }
    };
    void operation.then(clearOperation, clearOperation);
    return operation;
  }, [
    cfg.characteristicUUID,
    cfg.serviceUUID,
    clearReconnectTimer,
    devices,
    processNotification,
    scheduleReconnect,
    stopScan,
  ]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    const initialize = async () => {
      try {
        if (Capacitor.isNativePlatform()) {
          const { BleClient } = await import('@capacitor-community/bluetooth-le');
          await BleClient.initialize({ androidNeverForLocation: false });
          bleClientRef.current = BleClient;
        } else {
          const webClient = createWebBluetoothClient();
          await webClient.initialize();
          bleClientRef.current = webClient;
        }
        if (mountedRef.current) {
          setIsAvailable(true);
          setConnectionState('idle');
        }
      } catch {
        bleClientRef.current = null;
        if (mountedRef.current) {
          setIsAvailable(false);
          setConnectionState('unavailable');
        }
      }
    };
    void initialize();

    return () => {
      mountedRef.current = false;
      manualDisconnectRef.current = true;
      connectionGenerationRef.current += 1;
      sensorPacketQueueRef.current = [];
      clearScanTimer();
      clearReconnectTimer();
      const BleClient = bleClientRef.current;
      const device = connectedDeviceRef.current;
      connectedDeviceRef.current = null;
      if (BleClient) void BleClient.stopLEScan().catch(() => undefined);
      if (BleClient && device) {
        const current = configRef.current;
        void BleClient.stopNotifications(
          device.deviceId,
          current.serviceUUID,
          current.characteristicUUID,
        ).catch(() => undefined);
        void BleClient.disconnect(device.deviceId).catch(() => undefined);
      }
    };
  }, [clearReconnectTimer, clearScanTimer]);

  const scan = useCallback(async () => {
    const BleClient = bleClientRef.current;
    if (!BleClient) {
      setError('ble_unavailable');
      throw new Error('ble_unavailable');
    }

    // Web Bluetooth requestDevice() must be invoked while the original click
    // still has transient user activation. Awaiting even an idempotent web
    // stop call first can make Chrome reject the chooser with SecurityError.
    if (Capacitor.isNativePlatform()) {
      await stopScan();
    } else {
      clearScanTimer();
      if (mountedRef.current) setIsScanning(false);
    }
    setDevices([]);
    setError(null);
    setIsScanning(true);
    setConnectionState('scanning');

    try {
      await BleClient.requestLEScan(
        {
          namePrefix: cfg.deviceNamePrefix,
          optionalServices: [cfg.serviceUUID],
        },
        (result) => {
          if (!mountedRef.current) return;
          setDevices((current) => {
            const nextDevice = {
              deviceId: result.device.deviceId,
              name: result.device.name || result.localName || 'FETAL-GUARD',
              rssi: result.rssi ?? null,
            };
            const index = current.findIndex((item) => item.deviceId === nextDevice.deviceId);
            if (index < 0) return [...current, nextDevice];
            const next = [...current];
            next[index] = nextDevice;
            return next;
          });
        },
      );
      scanTimerRef.current = window.setTimeout(() => {
        void stopScan();
        if (mountedRef.current && !connectedDeviceRef.current) setConnectionState('idle');
      }, cfg.scanTimeout);
    } catch (scanError) {
      await stopScan();
      setConnectionState('error');
      setError(getBluetoothScanErrorCode(scanError));
      throw scanError;
    }
  }, [cfg.deviceNamePrefix, cfg.scanTimeout, cfg.serviceUUID, clearScanTimer, stopScan]);

  const disconnect = useCallback(async () => {
    manualDisconnectRef.current = true;
    const generation = connectionGenerationRef.current + 1;
    connectionGenerationRef.current = generation;
    clearReconnectTimer();
    const BleClient = bleClientRef.current;
    const device = connectedDeviceRef.current;
    connectedDeviceRef.current = null;
    if (BleClient && device) {
      try {
        await BleClient.stopNotifications(
          device.deviceId,
          cfg.serviceUUID,
          cfg.characteristicUUID,
        );
      } catch {
        // Continue disconnecting even when notification cleanup is already complete.
      }
      try {
        await BleClient.disconnect(device.deviceId);
      } catch {
        // Native disconnect is idempotent from the UI perspective.
      }
    }
    sensorPacketQueueRef.current = [];
    if (mountedRef.current && connectionGenerationRef.current === generation) {
      setConnectedDevice(null);
      setSensorData(null);
      setLastPacketReceivedAt(null);
      setConnectionState('idle');
      setError(null);
      setTransportDroppedPacketCount(0);
      setIsConnecting(false);
    }
  }, [cfg.characteristicUUID, cfg.serviceUUID, clearReconnectTimer]);

  return {
    isAvailable,
    isScanning,
    isConnecting,
    devices,
    connectedDevice,
    sensorData,
    sensorPacketVersion,
    transportDroppedPacketCount,
    error,
    connectionState,
    lastPacketReceivedAt,
    drainSensorPackets,
    scan,
    stopScan,
    connect,
    disconnect,
  };
}

export default useBluetooth;
