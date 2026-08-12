import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { t } from '../i18n';
import { useI18n } from '../i18n/useI18n';
import useBluetooth from '../hooks/useBluetooth';
import api, { getApiErrorMessage, isRequestCanceled } from '../services/api';
import PatientDeviceContext from './patientDeviceContext';

const TELEMETRY_STALE_AFTER_MS = 10000;
const TELEMETRY_MAX_FUTURE_SKEW_MS = 5000;
const DEVICE_REGISTRY_REFRESH_MS = 30000;
const MAX_VERIFIED_PACKET_QUEUE = 512;
const MAX_REORDER_WINDOW = 4096;
const MAX_RETIRED_BOOT_IDS = 64;

const EMPTY_TELEMETRY = Object.freeze({
  fhr: null,
  battery: null,
  charging: false,
  signalQuality: null,
  lastSync: null,
  receivedAt: null,
  maternalHeartRate: null,
  spo2: null,
  contractionLevel: null,
  deviceUid: null,
  bootId: null,
  sequenceNumber: null,
  schemaVersion: null,
  sampleRateHz: null,
  rawChannels: null,
});

const normalizeDeviceIdentity = (value) => String(value || '').trim().toUpperCase();

const createSequenceTracker = () => ({
  bootId: null,
  highestSequence: null,
  seenSequences: new Set(),
  seenOrder: [],
  missingSequences: new Set(),
});

const findRegistryMatch = (device, registeredDevices) => {
  const deviceId = normalizeDeviceIdentity(device?.deviceId);
  const deviceName = normalizeDeviceIdentity(device?.name);
  return registeredDevices.find((registeredDevice) => (
    registeredDevice.status === 'active' && (
      normalizeDeviceIdentity(registeredDevice.device_uid) === deviceId
      || normalizeDeviceIdentity(registeredDevice.device_uid) === deviceName
    )
  ));
};

const buildDeviceAlerts = ({
  pairedDevice,
  registeredDevices,
  telemetry,
  isTelemetryFresh,
  connectionState,
}) => {
  if (!pairedDevice) {
    const hasRegisteredDevice = registeredDevices.some((device) => device.status === 'active');
    return [{
      id: hasRegisteredDevice ? 'device-registered-not-connected' : 'device-not-registered',
      tone: 'warning',
      title: hasRegisteredDevice
        ? t('patient.deviceAlerts.registeredNotConnectedTitle')
        : t('patient.deviceAlerts.notRegisteredTitle'),
      message: hasRegisteredDevice
        ? t('patient.deviceAlerts.registeredNotConnectedMessage')
        : t('patient.deviceAlerts.notRegisteredMessage'),
      action: hasRegisteredDevice
        ? t('patient.deviceAlerts.scanAction')
        : t('patient.deviceAlerts.contactAdminAction'),
    }];
  }

  if (!isTelemetryFresh) {
    const reconnecting = connectionState === 'reconnecting';
    return [{
      id: reconnecting ? 'device-reconnecting' : 'device-data-stale',
      tone: 'warning',
      title: reconnecting
        ? t('patient.deviceAlerts.reconnectingTitle')
        : t('patient.deviceAlerts.staleTitle'),
      message: reconnecting
        ? t('patient.deviceAlerts.reconnectingMessage')
        : t('patient.deviceAlerts.staleMessage'),
      action: t('patient.deviceAlerts.checkConnectionAction'),
    }];
  }

  const alerts = [];
  if (telemetry.battery !== null && telemetry.battery <= 20) {
    alerts.push({
      id: 'battery-low',
      tone: 'warning',
      title: t('patient.deviceAlerts.batteryLowTitle'),
      message: t('patient.deviceAlerts.batteryLowMessage'),
      action: t('patient.deviceAlerts.chargeAction'),
    });
  }
  if (telemetry.signalQuality !== null && telemetry.signalQuality < 55) {
    alerts.push({
      id: 'signal-low',
      tone: 'warning',
      title: t('patient.deviceAlerts.signalLowTitle'),
      message: t('patient.deviceAlerts.signalLowMessage'),
      action: t('patient.deviceAlerts.checkPlacementAction'),
    });
  }
  if (telemetry.fhr !== null && (telemetry.fhr < 110 || telemetry.fhr > 160)) {
    alerts.push({
      id: 'fhr-review',
      tone: 'warning',
      title: t('patient.deviceAlerts.fhrReviewTitle'),
      message: t('patient.deviceAlerts.fhrReviewMessage'),
      action: t('patient.deviceAlerts.contactClinicianAction'),
    });
  }
  return alerts.length ? alerts : [{
    id: 'routine-monitoring',
    tone: 'success',
    title: t('patient.deviceAlerts.routineTitle'),
    message: t('patient.deviceAlerts.routineMessage'),
    action: t('patient.deviceAlerts.continueAction'),
  }];
};

export function PatientDeviceProvider({ children }) {
  const {
    connect: connectBluetooth,
    connectedDevice,
    connectionState,
    devices: bluetoothDevices,
    disconnect: disconnectBluetooth,
    drainSensorPackets,
    error: bluetoothError,
    isAvailable: isBleAvailable,
    isConnecting: isBluetoothConnecting,
    isScanning,
    scan: scanBluetooth,
    sensorPacketVersion,
    transportDroppedPacketCount,
  } = useBluetooth();
  const { locale } = useI18n();
  const [registeredDevices, setRegisteredDevices] = useState([]);
  const [pairedDevice, setPairedDevice] = useState(null);
  const [telemetry, setTelemetry] = useState(EMPTY_TELEMETRY);
  const [pairingState, setPairingState] = useState('idle');
  const [isDeviceRegistryLoading, setIsDeviceRegistryLoading] = useState(true);
  const [deviceRegistryError, setDeviceRegistryError] = useState('');
  const [pairingError, setPairingError] = useState('');
  const [handledAlertIds, setHandledAlertIds] = useState([]);
  const [freshnessClock, setFreshnessClock] = useState(() => Date.now());
  const [sequenceDroppedPacketCount, setSequenceDroppedPacketCount] = useState(0);
  const [verifiedQueueDroppedPacketCount, setVerifiedQueueDroppedPacketCount] = useState(0);
  const [verifiedPacketVersion, setVerifiedPacketVersion] = useState(0);
  const selectedRegistryDeviceRef = useRef(null);
  const verifiedPacketQueueRef = useRef([]);
  const sequenceTrackerRef = useRef(createSequenceTracker());
  const sequenceRegistryDeviceRef = useRef(null);
  const retiredBootIdsRef = useRef([]);
  const pairingAttemptRef = useRef(0);
  const registryRequestGenerationRef = useRef(0);
  const registryAbortControllerRef = useRef(null);

  const refreshRegisteredDevices = useCallback(async () => {
    const generation = registryRequestGenerationRef.current + 1;
    registryRequestGenerationRef.current = generation;
    registryAbortControllerRef.current?.abort();
    const controller = new AbortController();
    registryAbortControllerRef.current = controller;
    setDeviceRegistryError('');
    setIsDeviceRegistryLoading(true);
    try {
      const response = await api.client.get('/devices/me', { signal: controller.signal });
      if (registryRequestGenerationRef.current !== generation) return;
      setRegisteredDevices(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      if (isRequestCanceled(error) || registryRequestGenerationRef.current !== generation) return;
      setDeviceRegistryError(getApiErrorMessage(error));
    } finally {
      if (registryRequestGenerationRef.current === generation) {
        setIsDeviceRegistryLoading(false);
        if (registryAbortControllerRef.current === controller) {
          registryAbortControllerRef.current = null;
        }
      }
    }
  }, []);

  const drainTelemetryPackets = useCallback(() => {
    if (verifiedPacketQueueRef.current.length === 0) return [];
    return verifiedPacketQueueRef.current.splice(0, verifiedPacketQueueRef.current.length);
  }, []);

  useEffect(() => {
    void refreshRegisteredDevices();
    return () => {
      registryRequestGenerationRef.current += 1;
      registryAbortControllerRef.current?.abort();
    };
  }, [refreshRegisteredDevices]);

  useEffect(() => {
    if (!pairedDevice) return undefined;
    const timer = window.setInterval(() => {
      void refreshRegisteredDevices();
    }, DEVICE_REGISTRY_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [pairedDevice, refreshRegisteredDevices]);

  useEffect(() => {
    const timer = window.setInterval(() => setFreshnessClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!connectedDevice) return;
    const registryDevice = selectedRegistryDeviceRef.current;
    if (sequenceRegistryDeviceRef.current !== registryDevice?.id) {
      sequenceTrackerRef.current = createSequenceTracker();
      retiredBootIdsRef.current = [];
      setSequenceDroppedPacketCount(0);
      setVerifiedQueueDroppedPacketCount(0);
    }
    sequenceRegistryDeviceRef.current = registryDevice?.id || null;
    verifiedPacketQueueRef.current = [];
    setPairedDevice({
      id: registryDevice?.id || connectedDevice.deviceId,
      deviceId: connectedDevice.deviceId,
      deviceUid: normalizeDeviceIdentity(registryDevice?.device_uid) || null,
      name: registryDevice?.display_name || connectedDevice.name || 'FETAL-GUARD',
      rssi: connectedDevice.rssi ?? null,
      source: 'ble',
      registryDeviceId: registryDevice?.id || null,
      registryUidMatched: false,
    });
    setPairingState('paired');
  }, [connectedDevice]);

  useEffect(() => {
    if (connectedDevice || ['reconnecting', 'connecting'].includes(connectionState)) return;
    setPairedDevice(null);
    setTelemetry(EMPTY_TELEMETRY);
    selectedRegistryDeviceRef.current = null;
    verifiedPacketQueueRef.current = [];
    sequenceTrackerRef.current = createSequenceTracker();
    sequenceRegistryDeviceRef.current = null;
    retiredBootIdsRef.current = [];
  }, [connectedDevice, connectionState]);

  useEffect(() => {
    const packets = drainSensorPackets();
    if (packets.length === 0) return;

    const registryDevice = selectedRegistryDeviceRef.current;
    const expectedDeviceUid = normalizeDeviceIdentity(registryDevice?.device_uid);
    if (!expectedDeviceUid) {
      verifiedPacketQueueRef.current = [];
      setPairingError(t('patient.deviceAlerts.identityMismatch'));
      void disconnectBluetooth();
      return;
    }

    const acceptedPackets = [];
    let latestForwardPacket = null;
    let hasPacketOrderError = false;
    for (const packet of packets) {
      if (packet.deviceUid !== expectedDeviceUid) {
        verifiedPacketQueueRef.current = [];
        setPairingError(t('patient.deviceAlerts.identityMismatch'));
        void disconnectBluetooth();
        return;
      }

      let tracker = sequenceTrackerRef.current;
      if (tracker.bootId !== packet.bootId) {
        if (retiredBootIdsRef.current.includes(packet.bootId)) {
          hasPacketOrderError = true;
          continue;
        }

        if (tracker.bootId) {
          retiredBootIdsRef.current.push(tracker.bootId);
          if (retiredBootIdsRef.current.length > MAX_RETIRED_BOOT_IDS) {
            retiredBootIdsRef.current.shift();
          }
        }
        tracker = createSequenceTracker();
        tracker.bootId = packet.bootId;
        sequenceTrackerRef.current = tracker;
      }

      if (tracker.seenSequences.has(packet.sequenceNumber)) {
        hasPacketOrderError = true;
        continue;
      }

      if (tracker.highestSequence === null || packet.sequenceNumber > tracker.highestSequence) {
        const reorderFloor = packet.sequenceNumber - MAX_REORDER_WINDOW;
        for (const missingSequence of tracker.missingSequences) {
          if (missingSequence < reorderFloor) tracker.missingSequences.delete(missingSequence);
        }
        if (
          tracker.highestSequence !== null
          && packet.sequenceNumber > tracker.highestSequence + 1
        ) {
          const gap = packet.sequenceNumber - tracker.highestSequence - 1;
          setSequenceDroppedPacketCount((count) => count + gap);
          const trackedGapStart = Math.max(
            tracker.highestSequence + 1,
            packet.sequenceNumber - MAX_REORDER_WINDOW,
          );
          for (let missing = trackedGapStart; missing < packet.sequenceNumber; missing += 1) {
            tracker.missingSequences.add(missing);
          }
        }
        tracker.highestSequence = packet.sequenceNumber;
        latestForwardPacket = packet;
      } else if (tracker.missingSequences.has(packet.sequenceNumber)) {
        tracker.missingSequences.delete(packet.sequenceNumber);
        setSequenceDroppedPacketCount((count) => Math.max(0, count - 1));
      } else {
        hasPacketOrderError = true;
        continue;
      }

      tracker.seenSequences.add(packet.sequenceNumber);
      tracker.seenOrder.push(packet.sequenceNumber);
      if (tracker.seenOrder.length > MAX_REORDER_WINDOW) {
        const expiredSequence = tracker.seenOrder.shift();
        tracker.seenSequences.delete(expiredSequence);
      }
      acceptedPackets.push(packet);
    }

    if (acceptedPackets.length === 0) {
      if (hasPacketOrderError) setPairingError(t('patient.deviceAlerts.packetOrderError'));
      return;
    }

    verifiedPacketQueueRef.current.push(...acceptedPackets);
    if (verifiedPacketQueueRef.current.length > MAX_VERIFIED_PACKET_QUEUE) {
      const overflow = verifiedPacketQueueRef.current.length - MAX_VERIFIED_PACKET_QUEUE;
      verifiedPacketQueueRef.current.splice(0, overflow);
      setVerifiedQueueDroppedPacketCount((count) => count + overflow);
    }
    setVerifiedPacketVersion((version) => version + 1);

    if (latestForwardPacket) {
      const packet = latestForwardPacket;
      setTelemetry({
        fhr: packet.fhr,
        battery: packet.battery,
        charging: packet.charging,
        signalQuality: packet.signalQuality,
        lastSync: packet.capturedAt,
        receivedAt: new Date(packet.receivedAtMs).toISOString(),
        maternalHeartRate: packet.motherHR,
        spo2: packet.spo2,
        contractionLevel: packet.contractionLevel,
        deviceUid: packet.deviceUid,
        bootId: packet.bootId,
        sequenceNumber: packet.sequenceNumber,
        schemaVersion: packet.schemaVersion,
        sampleRateHz: packet.sampleRateHz,
        rawChannels: packet.rawChannels,
      });
    }
    // This proves only that the packet's declared UID matches the server
    // registry. It is not cryptographic device authentication.
    setPairedDevice((current) => current ? { ...current, registryUidMatched: true } : current);
    setPairingError(hasPacketOrderError ? t('patient.deviceAlerts.packetOrderError') : '');
  }, [disconnectBluetooth, drainSensorPackets, sensorPacketVersion]);

  useEffect(() => {
    if (!pairedDevice?.registryDeviceId || isDeviceRegistryLoading || deviceRegistryError) return;
    const currentRegistryDevice = registeredDevices.find(
      (device) => device.id === pairedDevice.registryDeviceId,
    );
    const identityStillMatches = currentRegistryDevice?.status === 'active'
      && normalizeDeviceIdentity(currentRegistryDevice.device_uid)
        === normalizeDeviceIdentity(pairedDevice.deviceUid);
    if (identityStillMatches) {
      selectedRegistryDeviceRef.current = currentRegistryDevice;
      return;
    }

    verifiedPacketQueueRef.current = [];
    setPairingError(t('patient.deviceAlerts.unregisteredDevice'));
    void disconnectBluetooth();
  }, [
    deviceRegistryError,
    disconnectBluetooth,
    isDeviceRegistryLoading,
    pairedDevice,
    registeredDevices,
  ]);

  useEffect(() => {
    if (pairingState === 'scanning' && !isScanning) setPairingState('idle');
  }, [isScanning, pairingState]);

  const bluetoothErrorMessage = useMemo(() => {
    void locale;
    if (!bluetoothError) return '';
    const messageKeys = {
      ble_unavailable: 'patient.deviceAlerts.bleUnavailable',
      scan_failed: 'patient.deviceAlerts.scanFailed',
      connect_failed: 'patient.deviceAlerts.pairingFailed',
      reconnect_failed: 'patient.deviceAlerts.reconnectFailed',
      unexpected_disconnect: 'patient.deviceAlerts.unexpectedDisconnect',
      unsupported_schema: 'patient.deviceAlerts.protocolError',
      transport_queue_overflow: 'patient.deviceAlerts.protocolError',
    };
    return t(messageKeys[bluetoothError] || 'patient.deviceAlerts.protocolError');
  }, [bluetoothError, locale]);

  const availableDevices = useMemo(() => bluetoothDevices.map((device) => {
    const registryMatch = findRegistryMatch(device, registeredDevices);
    return {
      ...device,
      id: device.deviceId,
      source: 'ble',
      registeredDeviceId: registryMatch?.id || null,
      registeredDeviceUid: registryMatch?.device_uid || null,
      isRegistered: Boolean(registryMatch),
    };
  }), [bluetoothDevices, registeredDevices]);

  const scanForDevice = useCallback(async () => {
    setPairingError('');
    setHandledAlertIds([]);
    setPairingState('scanning');
    try {
      await scanBluetooth();
    } catch {
      setPairingState('idle');
    }
  }, [scanBluetooth]);

  const connectToDevice = useCallback(async (device) => {
    if (!device || !device.isRegistered || !device.registeredDeviceId) {
      setPairingError(t('patient.deviceAlerts.unregisteredDevice'));
      return;
    }
    const registryDevice = registeredDevices.find((item) => item.id === device.registeredDeviceId);
    if (!registryDevice || registryDevice.status !== 'active') {
      setPairingError(t('patient.deviceAlerts.inactiveDevice'));
      return;
    }

    setPairingError('');
    setPairingState('pairing');
    const pairingAttempt = pairingAttemptRef.current + 1;
    pairingAttemptRef.current = pairingAttempt;
    selectedRegistryDeviceRef.current = registryDevice;
    try {
      await connectBluetooth(device.deviceId);
    } catch {
      if (pairingAttemptRef.current !== pairingAttempt) return;
      selectedRegistryDeviceRef.current = null;
      setPairingState('idle');
    }
  }, [connectBluetooth, registeredDevices]);

  const disconnectDevice = useCallback(async () => {
    pairingAttemptRef.current += 1;
    await disconnectBluetooth();
    setPairedDevice(null);
    setTelemetry(EMPTY_TELEMETRY);
    setHandledAlertIds([]);
    setSequenceDroppedPacketCount(0);
    setVerifiedQueueDroppedPacketCount(0);
    setPairingState('idle');
    selectedRegistryDeviceRef.current = null;
    verifiedPacketQueueRef.current = [];
    sequenceTrackerRef.current = createSequenceTracker();
    sequenceRegistryDeviceRef.current = null;
    retiredBootIdsRef.current = [];
  }, [disconnectBluetooth]);

  const receivedAtMs = Date.parse(telemetry.receivedAt || '');
  const capturedAtMs = Date.parse(telemetry.lastSync || '');
  const receivedAgeMs = freshnessClock - receivedAtMs;
  const capturedAgeMs = freshnessClock - capturedAtMs;
  const isTelemetryFresh = Boolean(
    pairedDevice?.registryUidMatched
    && connectionState === 'connected'
    && Number.isFinite(receivedAtMs)
    && Number.isFinite(capturedAtMs)
    && receivedAgeMs >= -TELEMETRY_MAX_FUTURE_SKEW_MS
    && capturedAgeMs >= -TELEMETRY_MAX_FUTURE_SKEW_MS
    && receivedAgeMs <= TELEMETRY_STALE_AFTER_MS
    && capturedAgeMs <= TELEMETRY_STALE_AFTER_MS
  );
  const droppedPacketCount = sequenceDroppedPacketCount
    + verifiedQueueDroppedPacketCount
    + transportDroppedPacketCount;

  const alerts = useMemo(() => (
    (void locale, buildDeviceAlerts({
      pairedDevice,
      registeredDevices,
      telemetry,
      isTelemetryFresh,
      connectionState,
    }))
  ), [connectionState, isTelemetryFresh, locale, pairedDevice, registeredDevices, telemetry]);

  useEffect(() => {
    const activeIds = new Set(alerts.map((alert) => alert.id));
    setHandledAlertIds((current) => current.filter((id) => activeIds.has(id)));
  }, [alerts]);

  const markAlertHandled = useCallback((alertId) => {
    setHandledAlertIds((current) => current.includes(alertId) ? current : [...current, alertId]);
  }, []);
  const activeAlerts = useMemo(
    () => alerts.filter((alert) => !handledAlertIds.includes(alert.id)),
    [alerts, handledAlertIds],
  );
  const notificationCount = activeAlerts.filter((alert) => alert.tone !== 'success').length;

  const value = useMemo(() => ({
    isBleAvailable,
    isScanning,
    isConnecting: isBluetoothConnecting || pairingState === 'pairing',
    connectionState,
    isTelemetryFresh,
    isDeviceRegistryLoading,
    deviceRegistryError,
    pairingState,
    pairingError: pairingError || bluetoothErrorMessage,
    availableDevices,
    registeredDevices,
    hasRegisteredDevice: registeredDevices.some((device) => device.status === 'active'),
    pairedDevice,
    telemetry,
    telemetryPacketVersion: verifiedPacketVersion,
    drainTelemetryPackets,
    droppedPacketCount,
    alerts,
    activeAlerts,
    notificationCount,
    scanForDevice,
    connectToDevice,
    disconnectDevice,
    markAlertHandled,
    refreshRegisteredDevices,
  }), [
    activeAlerts,
    alerts,
    availableDevices,
    connectionState,
    isBleAvailable,
    isBluetoothConnecting,
    isScanning,
    bluetoothErrorMessage,
    connectToDevice,
    deviceRegistryError,
    disconnectDevice,
    drainTelemetryPackets,
    droppedPacketCount,
    isDeviceRegistryLoading,
    isTelemetryFresh,
    markAlertHandled,
    notificationCount,
    pairedDevice,
    pairingError,
    pairingState,
    refreshRegisteredDevices,
    registeredDevices,
    scanForDevice,
    telemetry,
    verifiedPacketVersion,
  ]);

  return <PatientDeviceContext.Provider value={value}>{children}</PatientDeviceContext.Provider>;
}
