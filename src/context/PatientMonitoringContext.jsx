import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { t } from '../i18n';
import api, { getApiErrorMessage } from '../services/api';
import {
  addPatientNetworkStatusListener,
  canUploadWithPatientPolicy,
} from '../services/nativePatientFeatures';
import {
  getPatientPreferences,
  PATIENT_PREFERENCES_CHANGED_EVENT,
} from '../services/patientPreferences';
import {
  createTelemetryQueueScope,
  deleteTelemetryRecord,
  getNextPendingTelemetryRecord,
  getTelemetryQueueStats,
  hasTelemetryRecord,
  putTelemetryRecord,
  requeueFailedTelemetryRecords,
  updateTelemetryRecord,
} from '../services/patientTelemetryQueue';
import PatientMonitoringContext from './patientMonitoringContext';
import { useAuth } from './useAuth';
import { usePatientDevice } from './usePatientDevice';

const MAX_PENDING_PACKETS = 500;
const MAX_RETAINED_PACKETS = 1000;
const MAX_STAGED_PACKETS = 512;
const RETRY_LIMIT = 5;
const RETRY_MAX_DELAY_MS = 30000;
const RETRY_MAX_SERVER_DELAY_MS = 24 * 60 * 60 * 1000;
const SENSOR_CHANNEL_LIMITS = Object.freeze({
  p: 4095,
  fsr: 4095,
  hr_ir: 262143,
  hr_red: 262143,
});
const MAX_SENSOR_VALUES_PER_CHANNEL = 5000;

const createClientSessionId = () => {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `patient-${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

const fallbackIdentityHash = (value) => {
  const seeds = [2166136261, 2246822507, 3266489909, 668265263];
  return seeds.map((seed) => {
    let hash = seed;
    for (let index = 0; index < value.length; index += 1) {
      hash = Math.imul(hash ^ value.charCodeAt(index), 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, '0');
  }).join('');
};

const buildIngestionId = async (deviceUid, bootId, sequenceNumber) => {
  const identity = `${String(deviceUid)}\0${String(bootId)}\0${sequenceNumber}`;
  if (globalThis.crypto?.subtle && typeof TextEncoder !== 'undefined') {
    try {
      const digest = await globalThis.crypto.subtle.digest(
        'SHA-256',
        new TextEncoder().encode(identity),
      );
      const hexDigest = Array.from(new Uint8Array(digest), (byte) => (
        byte.toString(16).padStart(2, '0')
      )).join('');
      return `ble-${hexDigest}`;
    } catch {
      // The deterministic fallback preserves retry identity in restricted WebViews.
    }
  }
  return `ble-${fallbackIdentityHash(identity)}`;
};

const normalizeRawChannels = (rawChannels) => {
  if (!rawChannels || typeof rawChannels !== 'object' || Array.isArray(rawChannels)) {
    return { payload: null, reason: 'missing' };
  }

  const payload = {};
  for (const [channel, maximum] of Object.entries(SENSOR_CHANNEL_LIMITS)) {
    const values = rawChannels[channel];
    if (values === undefined || values === null) continue;
    if (
      !Array.isArray(values)
      || values.length === 0
      || values.length > MAX_SENSOR_VALUES_PER_CHANNEL
      || values.some((value) => !Number.isSafeInteger(value) || value < 0 || value > maximum)
    ) {
      return { payload: null, reason: 'invalid' };
    }
    payload[channel] = values;
  }

  return Object.keys(payload).length
    ? { payload, reason: null }
    : { payload: null, reason: 'missing' };
};

const isCanceledRequest = (error) => (
  error?.code === 'ERR_CANCELED'
  || error?.name === 'AbortError'
  || error?.name === 'CanceledError'
);

const shouldRetryRequest = (error) => {
  const status = error?.response?.status;
  return !status || status === 408 || status === 425 || status === 429 || status >= 500;
};

const getRetryAfterMs = (error) => {
  const value = error?.response?.headers?.['retry-after'];
  if (value === undefined || value === null || value === '') return 0;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return seconds * 1000;
  const retryAt = Date.parse(value);
  return Number.isFinite(retryAt) ? Math.max(0, retryAt - Date.now()) : 0;
};

const getRetryDelayMs = (attempts, error) => {
  const exponential = Math.min(1000 * (2 ** Math.max(0, attempts - 1)), RETRY_MAX_DELAY_MS);
  const jittered = exponential + Math.floor(Math.random() * Math.max(1, exponential * 0.25));
  return Math.min(
    Math.max(jittered, getRetryAfterMs(error)),
    RETRY_MAX_SERVER_DELAY_MS,
  );
};

const countStagedPacketsForScope = (tasks, scopeKey) => tasks.reduce(
  (count, task) => count + (task.scopeKey === scopeKey ? task.packets.length : 0),
  0,
);

export function PatientMonitoringProvider({ children }) {
  const { user } = useAuth();
  const {
    pairedDevice,
    isTelemetryFresh,
    connectionState,
    telemetryPacketVersion,
    drainTelemetryPackets,
  } = usePatientDevice();
  const [activeSession, setActiveSession] = useState(null);
  const [activeSessionUserId, setActiveSessionUserId] = useState(null);
  const [sessionState, setSessionState] = useState('loading');
  const [sessionError, setSessionError] = useState('');
  const [pendingUploadCount, setPendingUploadCount] = useState(0);
  const [rejectedUploadCount, setRejectedUploadCount] = useState(0);
  const [dataPersistenceState, setDataPersistenceState] = useState('waiting');
  const [isUploadQueueDurable, setIsUploadQueueDurable] = useState(true);

  const activeSessionRef = useRef(null);
  const queueScopeRef = useRef(null);
  const flushPromiseRef = useRef(null);
  const flushQueueRef = useRef(null);
  const enqueueWorkerPromiseRef = useRef(null);
  const enqueueStorageBlockedRef = useRef(false);
  const stagedPacketTasksRef = useRef([]);
  const stagedPacketCountRef = useRef(0);
  const enqueueOrderRef = useRef(Date.now() * 1000);
  const hardRejectedPacketCountRef = useRef(0);
  const retryTimerRef = useRef(null);
  const retryDueAtRef = useRef(null);
  const uploadAbortControllerRef = useRef(null);
  const startSessionPromiseRef = useRef(null);
  const stopSessionPromiseRef = useRef(null);
  const clientSessionIdRef = useRef(null);
  const mountedRef = useRef(true);
  const acceptPacketsRef = useRef(false);
  const terminalIngestionPausedRef = useRef(false);
  const liveTelemetryRef = useRef(false);
  const identityGenerationRef = useRef(0);

  useEffect(() => {
    activeSessionRef.current = activeSession;
  }, [activeSession]);

  useEffect(() => {
    liveTelemetryRef.current = isTelemetryFresh && connectionState === 'connected';
  }, [connectionState, isTelemetryFresh]);

  const queueScope = useMemo(() => {
    const deviceId = activeSession?.device_id || pairedDevice?.registryDeviceId;
    if (
      !user?.id
      || activeSessionUserId !== user.id
      || !activeSession?.id
      || !deviceId
    ) return null;
    try {
      return createTelemetryQueueScope({
        userId: user.id,
        sessionId: activeSession.id,
        deviceId,
      });
    } catch {
      return null;
    }
  }, [activeSession, activeSessionUserId, pairedDevice?.registryDeviceId, user?.id]);

  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current !== null) {
      window.clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    retryDueAtRef.current = null;
  }, []);

  const recordRejectedPacket = useCallback((count = 1) => {
    const safeCount = Math.max(0, Number(count) || 0);
    hardRejectedPacketCountRef.current += safeCount;
    if (mountedRef.current) {
      setRejectedUploadCount((current) => current + safeCount);
    }
  }, []);

  const scheduleRetryAt = useCallback((retryAt) => {
    if (!mountedRef.current) return;
    const normalizedRetryAt = Math.max(Date.now(), Number(retryAt) || Date.now());
    if (
      retryTimerRef.current !== null
      && retryDueAtRef.current !== null
      && retryDueAtRef.current <= normalizedRetryAt
    ) {
      return;
    }

    clearRetryTimer();
    retryDueAtRef.current = normalizedRetryAt;
    retryTimerRef.current = window.setTimeout(() => {
      retryTimerRef.current = null;
      retryDueAtRef.current = null;
      void flushQueueRef.current?.();
    }, Math.max(0, normalizedRetryAt - Date.now()));
  }, [clearRetryTimer]);

  const refreshQueueCounts = useCallback(async (scopeKey = queueScopeRef.current) => {
    if (!scopeKey) {
      if (mountedRef.current) {
        setPendingUploadCount(0);
        setRejectedUploadCount(0);
      }
      return { pending: 0, failed: 0, records: [], durable: true };
    }

    const result = await getTelemetryQueueStats(scopeKey);
    const { pending, failed } = result;
    if (mountedRef.current && queueScopeRef.current === scopeKey) {
      setPendingUploadCount(pending);
      setRejectedUploadCount(hardRejectedPacketCountRef.current + failed);
      setIsUploadQueueDurable(result.durable);
    }
    return { ...result, pending, failed };
  }, []);

  const flushQueue = useCallback(() => {
    if (flushPromiseRef.current) return flushPromiseRef.current;

    const scopeKey = queueScopeRef.current;
    const session = activeSessionRef.current;
    if (!scopeKey || !session || session.status !== 'active') return Promise.resolve();

    const operation = (async () => {
      const uploadPolicy = await canUploadWithPatientPolicy(
        getPatientPreferences(user?.id).uploadWifiOnly,
      );
      if (!uploadPolicy.allowed) {
        if (mountedRef.current) {
          setDataPersistenceState(
            uploadPolicy.reason === 'offline' ? 'offline' : 'wifi_required',
          );
        }
        return;
      }

      try {
        while (
          mountedRef.current
          && queueScopeRef.current === scopeKey
          && activeSessionRef.current?.id === session.id
        ) {
          const queue = await refreshQueueCounts(scopeKey);
          if (queue.pending === 0) {
            clearRetryTimer();
            if (mountedRef.current) {
              setDataPersistenceState(queue.failed > 0 ? 'rejected' : 'synced');
            }
            return;
          }

          const nextPending = await getNextPendingTelemetryRecord(scopeKey);
          const item = nextPending.record;
          if (!item) throw new Error('telemetry_queue_index_inconsistent');
          const nextAttemptAt = Number(item.nextAttemptAt || 0);
          if (nextAttemptAt > Date.now()) {
            if (mountedRef.current) setDataPersistenceState('retrying');
            scheduleRetryAt(nextAttemptAt);
            return;
          }

          const controller = new AbortController();
          uploadAbortControllerRef.current = controller;
          try {
            await api.client.post(
              `/sessions/${session.id}/data`,
              { payload: item.payload, ...item.metadata },
              { signal: controller.signal },
            );
            await deleteTelemetryRecord(item.id);
            if (mountedRef.current) {
              setDataPersistenceState('synced');
              setActiveSession((current) => (
                current?.id === session.id && !current.device_id
                  ? { ...current, device_id: item.deviceId }
                  : current
              ));
            }
          } catch (error) {
            if (isCanceledRequest(error)) return;

            if (!shouldRetryRequest(error)) {
              await updateTelemetryRecord(item.id, {
                status: 'failed',
                attempts: Number(item.attempts || 0) + 1,
                nextAttemptAt: 0,
                lastError: getApiErrorMessage(error),
                lastHttpStatus: error?.response?.status || null,
              });
              if (mountedRef.current) {
                acceptPacketsRef.current = false;
                terminalIngestionPausedRef.current = true;
                setDataPersistenceState('rejected');
                setSessionError(getApiErrorMessage(error));
                setSessionState('degraded');
              }
              await refreshQueueCounts(scopeKey);
              return;
            }

            const attempts = Number(item.attempts || 0) + 1;
            if (attempts >= RETRY_LIMIT) {
              await updateTelemetryRecord(item.id, {
                status: 'failed',
                attempts,
                nextAttemptAt: 0,
                lastError: getApiErrorMessage(error),
              });
              if (mountedRef.current) {
                setDataPersistenceState('rejected');
                setSessionError(getApiErrorMessage(error));
                setSessionState('degraded');
              }
              continue;
            }

            const retryAt = Date.now() + getRetryDelayMs(attempts, error);
            await updateTelemetryRecord(item.id, {
              attempts,
              nextAttemptAt: retryAt,
              lastError: getApiErrorMessage(error),
            });
            if (mountedRef.current) setDataPersistenceState('retrying');
            scheduleRetryAt(retryAt);
            return;
          } finally {
            if (uploadAbortControllerRef.current === controller) {
              uploadAbortControllerRef.current = null;
            }
          }
        }
      } catch (error) {
        if (mountedRef.current && !isCanceledRequest(error)) {
          setDataPersistenceState('queue_full');
          setSessionError(getApiErrorMessage(error));
          setSessionState('degraded');
        }
      }
    })();

    flushPromiseRef.current = operation;
    const clearOperation = () => {
      if (flushPromiseRef.current === operation) flushPromiseRef.current = null;
    };
    void operation.then(clearOperation, clearOperation);
    return operation;
  }, [clearRetryTimer, refreshQueueCounts, scheduleRetryAt, user?.id]);

  useEffect(() => {
    flushQueueRef.current = flushQueue;
  }, [flushQueue]);

  useEffect(() => {
    const handlePreferenceChange = (event) => {
      if (String(event.detail?.userId) === String(user?.id)) void flushQueue();
    };
    window.addEventListener(PATIENT_PREFERENCES_CHANGED_EVENT, handlePreferenceChange);
    return () => window.removeEventListener(
      PATIENT_PREFERENCES_CHANGED_EVENT,
      handlePreferenceChange,
    );
  }, [flushQueue, user?.id]);

  useEffect(() => {
    const previousScope = queueScopeRef.current;
    queueScopeRef.current = queueScope;
    if (previousScope !== queueScope) {
      hardRejectedPacketCountRef.current = 0;
      setRejectedUploadCount(0);
      uploadAbortControllerRef.current?.abort();
      clearRetryTimer();
    }

    if (!queueScope) {
      setPendingUploadCount(0);
      setRejectedUploadCount(0);
      return;
    }

    void refreshQueueCounts(queueScope)
      .then(async () => {
        await flushQueue();
        if (queueScopeRef.current === queueScope) await flushQueue();
      })
      .catch((error) => {
        if (!mountedRef.current || queueScopeRef.current !== queueScope) return;
        setDataPersistenceState('queue_full');
        setSessionError(getApiErrorMessage(error));
        setSessionState('degraded');
      });
  }, [clearRetryTimer, flushQueue, queueScope, refreshQueueCounts]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      identityGenerationRef.current += 1;
      acceptPacketsRef.current = false;
      terminalIngestionPausedRef.current = false;
      queueScopeRef.current = null;
      stagedPacketTasksRef.current = [];
      stagedPacketCountRef.current = 0;
      uploadAbortControllerRef.current?.abort();
      clearRetryTimer();
    };
  }, [clearRetryTimer]);

  useEffect(() => {
    const controller = new AbortController();
    let isCurrentIdentity = true;
    identityGenerationRef.current += 1;
    acceptPacketsRef.current = false;
    terminalIngestionPausedRef.current = false;
    enqueueStorageBlockedRef.current = false;
    stagedPacketTasksRef.current = [];
    stagedPacketCountRef.current = 0;
    activeSessionRef.current = null;
    uploadAbortControllerRef.current?.abort();
    clearRetryTimer();
    hardRejectedPacketCountRef.current = 0;
    setActiveSession(null);
    setActiveSessionUserId(null);
    setSessionError('');
    setPendingUploadCount(0);
    setRejectedUploadCount(0);
    setDataPersistenceState('waiting');

    if (!user?.id || user.role !== 'patient') {
      setSessionState('idle');
      return () => {
        isCurrentIdentity = false;
        controller.abort();
      };
    }

    setSessionState('loading');
    const restoreSession = async () => {
      try {
        const response = await api.client.get('/sessions/active', { signal: controller.signal });
        if (!mountedRef.current || !isCurrentIdentity) return;
        const existing = response.data?.status === 'active' ? response.data : null;
        activeSessionRef.current = existing;
        setActiveSession(existing);
        setActiveSessionUserId(existing ? user.id : null);
        setSessionState(existing ? 'interrupted' : 'idle');
      } catch (error) {
        if (!mountedRef.current || !isCurrentIdentity || isCanceledRequest(error)) return;
        if (error?.response?.status === 404) {
          setSessionState('idle');
          return;
        }
        setSessionError(getApiErrorMessage(error));
        setSessionState('error');
      }
    };
    void restoreSession();

    return () => {
      isCurrentIdentity = false;
      controller.abort();
    };
  }, [clearRetryTimer, user?.id, user?.role]);

  useEffect(() => {
    let removeListener = () => undefined;
    let disposed = false;
    void addPatientNetworkStatusListener((status) => {
      if (status.connected) void flushQueue();
      else setDataPersistenceState('offline');
    }).then((remove) => {
      if (disposed) remove();
      else removeListener = remove;
    });
    return () => {
      disposed = true;
      removeListener();
    };
  }, [flushQueue]);

  useEffect(() => {
    if (!activeSession || !acceptPacketsRef.current) return;
    if (!isTelemetryFresh || connectionState !== 'connected') {
      if (sessionState === 'active') setSessionState('stale');
      return;
    }
    if (sessionState === 'stale') setSessionState('active');
  }, [activeSession, connectionState, isTelemetryFresh, sessionState]);

  const enqueuePackets = useCallback(async ({
    packets,
    scopeKey,
    session,
    device,
    owner,
    identityGeneration,
  }) => {
    if (identityGeneration !== identityGenerationRef.current) return;
    const initialQueue = await getTelemetryQueueStats(scopeKey);
    if (identityGeneration !== identityGenerationRef.current) return;
    if (mountedRef.current && queueScopeRef.current === scopeKey) {
      setIsUploadQueueDurable(initialQueue.durable);
    }

    const knownRecordIds = new Set();
    let storedCount = initialQueue.total;
    let pendingCount = initialQueue.pending;
    for (const packet of packets) {
      if (identityGeneration !== identityGenerationRef.current) return;
      const ingestionId = await buildIngestionId(
        packet.deviceUid,
        packet.bootId,
        packet.sequenceNumber,
      );
      const recordId = `${scopeKey}|${ingestionId}`;
      if (knownRecordIds.has(recordId)) continue;
      const existingRecord = await hasTelemetryRecord(recordId);
      if (identityGeneration !== identityGenerationRef.current) return;
      if (existingRecord.exists) {
        knownRecordIds.add(recordId);
        continue;
      }

      const normalizedChannels = normalizeRawChannels(packet.rawChannels);
      if (normalizedChannels.reason === 'missing') {
        if (mountedRef.current && queueScopeRef.current === scopeKey) {
          setDataPersistenceState('awaiting_raw_channels');
        }
        continue;
      }
      if (normalizedChannels.reason === 'invalid') {
        if (mountedRef.current && queueScopeRef.current === scopeKey) {
          recordRejectedPacket();
          setDataPersistenceState('rejected');
          setSessionError(t('patient.monitoring.persistenceRejected'));
          setSessionState('degraded');
        }
        continue;
      }
      const hasV1SampleRate = packet.schemaVersion === 1
        && Number.isFinite(packet.sampleRateHz)
        && packet.sampleRateHz > 0;
      const hasV2SampleRates = packet.schemaVersion === 2
        && packet.sampleRatesHz
        && Object.keys(normalizedChannels.payload).every((channel) => (
          Number.isFinite(packet.sampleRatesHz[channel])
          && packet.sampleRatesHz[channel] > 0
        ));
      const hasValidPiezoLayout = packet.schemaVersion !== 2
        || normalizedChannels.payload.p === undefined
        || (
          packet.channelLayout?.p === 4
          && normalizedChannels.payload.p.length % packet.channelLayout.p === 0
        );
      if ((!hasV1SampleRate && !hasV2SampleRates) || !hasValidPiezoLayout) {
        if (mountedRef.current && queueScopeRef.current === scopeKey) {
          recordRejectedPacket();
          setDataPersistenceState('rejected');
          setSessionError(t('patient.monitoring.errorMissingSampleRate'));
          setSessionState('degraded');
        }
        continue;
      }
      if (pendingCount >= MAX_PENDING_PACKETS || storedCount >= MAX_RETAINED_PACKETS) {
        if (mountedRef.current && queueScopeRef.current === scopeKey) {
          recordRejectedPacket();
          setDataPersistenceState('queue_full');
          setSessionError(t('patient.monitoring.errorQueueFull'));
          setSessionState('degraded');
        }
        continue;
      }

      const capturedAtMs = Date.parse(packet.capturedAt);
      if (!Number.isFinite(capturedAtMs)) {
        if (mountedRef.current && queueScopeRef.current === scopeKey) {
          recordRejectedPacket();
          setDataPersistenceState('rejected');
          setSessionError(t('patient.monitoring.persistenceRejected'));
          setSessionState('degraded');
        }
        continue;
      }

      enqueueOrderRef.current = Math.max(enqueueOrderRef.current + 1, Date.now() * 1000);

      const result = await putTelemetryRecord({
        id: recordId,
        scopeKey,
        userId: owner.userId,
        patientId: session.patient_id || owner.patientId || null,
        sessionId: session.id,
        deviceId: device.registryDeviceId,
        deviceUid: packet.deviceUid,
        bootId: packet.bootId,
        sequenceNumber: packet.sequenceNumber,
        payload: {
          ...normalizedChannels.payload,
          t: capturedAtMs,
        },
        metadata: {
          schema_version: packet.schemaVersion,
          ingestion_id: ingestionId,
          boot_id: packet.bootId,
          sequence_number: packet.sequenceNumber,
          captured_at: packet.capturedAt,
          sample_rate_hz: packet.sampleRateHz,
          sample_rates_hz: packet.sampleRatesHz,
          channel_layout: packet.channelLayout,
          device_uid: packet.deviceUid,
          source: 'ble',
          is_simulated: false,
        },
        status: 'pending',
        attempts: 0,
        nextAttemptAt: 0,
        createdAt: Number(packet.receivedAtMs || Date.now()),
        enqueueOrder: enqueueOrderRef.current,
        lastError: null,
      });
      if (identityGeneration !== identityGenerationRef.current) {
        // A logout or account switch may happen while IndexedDB is writing.
        // Remove the just-written stale packet so it cannot survive under a
        // later user's in-memory monitoring lifecycle.
        await deleteTelemetryRecord(recordId);
        return;
      }
      if (mountedRef.current && queueScopeRef.current === scopeKey) {
        setIsUploadQueueDurable(result.durable);
      }
      knownRecordIds.add(recordId);
      storedCount += 1;
      pendingCount += 1;
      if (mountedRef.current && queueScopeRef.current === scopeKey) {
        setDataPersistenceState('pending');
      }
    }

    await refreshQueueCounts(scopeKey);
    void flushQueue();
  }, [flushQueue, recordRejectedPacket, refreshQueueCounts]);

  const processStagedPackets = useCallback(() => {
    if (enqueueWorkerPromiseRef.current) return enqueueWorkerPromiseRef.current;
    if (enqueueStorageBlockedRef.current) return Promise.resolve();

    const operation = (async () => {
      while (stagedPacketTasksRef.current.length > 0) {
        const task = stagedPacketTasksRef.current[0];
        if (task.identityGeneration !== identityGenerationRef.current) {
          stagedPacketTasksRef.current.shift();
          stagedPacketCountRef.current = Math.max(
            0,
            stagedPacketCountRef.current - task.packets.length,
          );
          continue;
        }
        try {
          await enqueuePackets(task);
          stagedPacketTasksRef.current.shift();
          stagedPacketCountRef.current = Math.max(
            0,
            stagedPacketCountRef.current - task.packets.length,
          );
        } catch (error) {
          enqueueStorageBlockedRef.current = true;
          if (mountedRef.current && queueScopeRef.current === task.scopeKey) {
            setDataPersistenceState('queue_full');
            setSessionError(getApiErrorMessage(error));
            setSessionState('degraded');
          }
          return;
        }
      }
    })();

    enqueueWorkerPromiseRef.current = operation;
    const clearOperation = () => {
      if (enqueueWorkerPromiseRef.current === operation) {
        enqueueWorkerPromiseRef.current = null;
      }
    };
    void operation.then(clearOperation, clearOperation);
    return operation;
  }, [enqueuePackets]);

  useEffect(() => {
    const packets = drainTelemetryPackets();
    if (packets.length === 0) return;

    const session = activeSessionRef.current;
    const scopeKey = queueScopeRef.current;
    if (!session || !scopeKey) return;
    if (!acceptPacketsRef.current) {
      if (terminalIngestionPausedRef.current) recordRejectedPacket(packets.length);
      return;
    }
    if (
      !pairedDevice?.registryUidMatched
      || !pairedDevice.registryDeviceId
      || (session.device_id && session.device_id !== pairedDevice.registryDeviceId)
    ) {
      setSessionError(t('patient.monitoring.errorSessionDeviceConflict'));
      acceptPacketsRef.current = false;
      terminalIngestionPausedRef.current = true;
      recordRejectedPacket(packets.length);
      setSessionState('degraded');
      return;
    }

    const availableCapacity = Math.max(0, MAX_STAGED_PACKETS - stagedPacketCountRef.current);
    const acceptedPackets = packets.slice(0, availableCapacity);
    const rejectedPacketCount = packets.length - acceptedPackets.length;
    if (rejectedPacketCount > 0) {
      recordRejectedPacket(rejectedPacketCount);
      setDataPersistenceState('queue_full');
      setSessionError(t('patient.monitoring.errorQueueFull'));
      setSessionState('degraded');
    }
    if (acceptedPackets.length === 0) return;

    stagedPacketTasksRef.current.push({
      packets: acceptedPackets,
      scopeKey,
      session,
      device: pairedDevice,
      owner: {
        userId: user.id,
        patientId: user.patientProfile?.id || session.patient_id || null,
      },
      identityGeneration: identityGenerationRef.current,
    });
    stagedPacketCountRef.current += acceptedPackets.length;
    void processStagedPackets();
  }, [
    drainTelemetryPackets,
    pairedDevice,
    processStagedPackets,
    recordRejectedPacket,
    telemetryPacketVersion,
    user,
  ]);

  const startSession = useCallback(() => {
    if (startSessionPromiseRef.current) return startSessionPromiseRef.current;
    if (stopSessionPromiseRef.current) return Promise.resolve(null);

    const operation = (async () => {
      setSessionError('');
      if (
        !user?.id
        || !pairedDevice?.registryUidMatched
        || !pairedDevice.deviceUid
        || !isTelemetryFresh
      ) {
        setSessionError(t('patient.monitoring.errorDeviceNotVerified'));
        return null;
      }

      if (activeSessionRef.current?.status === 'active') {
        if (
          activeSessionRef.current.device_id
          && activeSessionRef.current.device_id !== pairedDevice.registryDeviceId
        ) {
          setSessionError(t('patient.monitoring.errorSessionDeviceConflict'));
          return null;
        }
        const existing = activeSessionRef.current;
        const existingScope = createTelemetryQueueScope({
          userId: user.id,
          sessionId: existing.id,
          deviceId: existing.device_id || pairedDevice.registryDeviceId,
        });
        queueScopeRef.current = existingScope;
        acceptPacketsRef.current = false;
        terminalIngestionPausedRef.current = false;
        await requeueFailedTelemetryRecords(existingScope);
        await flushQueue();
        await flushQueue();
        const remaining = await refreshQueueCounts(existingScope);
        if (remaining.pending > 0 || remaining.failed > 0) {
          setSessionError(t('patient.monitoring.errorUnsavedPackets'));
          setSessionState('degraded');
          return existing;
        }
        acceptPacketsRef.current = true;
        terminalIngestionPausedRef.current = false;
        setSessionState('active');
        return activeSessionRef.current;
      }

      setSessionState('starting');
      clientSessionIdRef.current ||= createClientSessionId();
      try {
        const session = await api.sessions.createSession({
          device_uid: pairedDevice.deviceUid,
          client_session_id: clientSessionIdRef.current,
        });
        activeSessionRef.current = session;
        acceptPacketsRef.current = true;
        terminalIngestionPausedRef.current = false;
        setActiveSession(session);
        setActiveSessionUserId(user?.id || null);
        if (user?.id && session.id && pairedDevice.registryDeviceId) {
          queueScopeRef.current = createTelemetryQueueScope({
            userId: user.id,
            sessionId: session.id,
            deviceId: session.device_id || pairedDevice.registryDeviceId,
          });
        }
        clientSessionIdRef.current = null;
        setSessionState('active');
        setDataPersistenceState('waiting');
        hardRejectedPacketCountRef.current = 0;
        setRejectedUploadCount(0);
        return session;
      } catch (error) {
        if (error?.response?.status === 409) {
          try {
            const response = await api.client.get('/sessions/active');
            const existing = response.data?.status === 'active' ? response.data : null;
            if (
              existing
              && (!existing.device_id || existing.device_id === pairedDevice.registryDeviceId)
            ) {
              activeSessionRef.current = existing;
              acceptPacketsRef.current = true;
              terminalIngestionPausedRef.current = false;
              setActiveSession(existing);
              setActiveSessionUserId(user?.id || null);
              if (user?.id && pairedDevice.registryDeviceId) {
                queueScopeRef.current = createTelemetryQueueScope({
                  userId: user.id,
                  sessionId: existing.id,
                  deviceId: existing.device_id || pairedDevice.registryDeviceId,
                });
              }
              clientSessionIdRef.current = null;
              setSessionState('active');
              return existing;
            }
          } catch {
            // Keep the original conflict as the actionable error.
          }
        }
        acceptPacketsRef.current = false;
        terminalIngestionPausedRef.current = false;
        setSessionError(getApiErrorMessage(error));
        setSessionState('error');
        return null;
      }
    })();

    startSessionPromiseRef.current = operation;
    const clearOperation = () => {
      if (startSessionPromiseRef.current === operation) startSessionPromiseRef.current = null;
    };
    void operation.then(clearOperation, clearOperation);
    return operation;
  }, [flushQueue, isTelemetryFresh, pairedDevice, refreshQueueCounts, user?.id]);

  const stopSession = useCallback(() => {
    if (stopSessionPromiseRef.current) return stopSessionPromiseRef.current;

    const operation = (async () => {
      if (startSessionPromiseRef.current) await startSessionPromiseRef.current;
      const session = activeSessionRef.current;
      if (!session) {
        acceptPacketsRef.current = false;
        terminalIngestionPausedRef.current = false;
        setSessionState('idle');
        return true;
      }

      setSessionError('');
      setSessionState('stopping');
      acceptPacketsRef.current = false;
      terminalIngestionPausedRef.current = false;
      if (enqueueWorkerPromiseRef.current) await enqueueWorkerPromiseRef.current;
      const scopeKey = queueScopeRef.current;
      if (countStagedPacketsForScope(stagedPacketTasksRef.current, scopeKey) > 0) {
        setSessionState('degraded');
        setSessionError(t('patient.monitoring.errorUnsavedPackets'));
        return false;
      }
      await flushQueue();

      const queue = scopeKey ? await refreshQueueCounts(scopeKey) : { pending: 0, failed: 0 };
      if (queue.pending > 0 || queue.failed > 0) {
        setSessionState('degraded');
        setSessionError(t('patient.monitoring.errorUnsavedPackets'));
        return false;
      }

      try {
        const ended = await api.sessions.endSession(session.id);
        activeSessionRef.current = ended;
        clientSessionIdRef.current = null;
        setActiveSession(ended);
        setSessionState('completed');
        return true;
      } catch (error) {
        setSessionError(getApiErrorMessage(error));
        setSessionState('error');
        return false;
      }
    })();

    stopSessionPromiseRef.current = operation;
    const clearOperation = () => {
      if (stopSessionPromiseRef.current === operation) stopSessionPromiseRef.current = null;
    };
    void operation.then(clearOperation, clearOperation);
    return operation;
  }, [flushQueue, refreshQueueCounts]);

  const retryPendingUploads = useCallback(async () => {
    const scopeKey = queueScopeRef.current;
    if (!scopeKey) return;
    setSessionError('');
    enqueueStorageBlockedRef.current = false;
    terminalIngestionPausedRef.current = false;
    await processStagedPackets();
    if (countStagedPacketsForScope(stagedPacketTasksRef.current, scopeKey) > 0) {
      setDataPersistenceState('queue_full');
      setSessionState('degraded');
      return;
    }
    await requeueFailedTelemetryRecords(scopeKey);
    await refreshQueueCounts(scopeKey);
    setDataPersistenceState('pending');
    await flushQueue();
    await flushQueue();
    const remaining = await refreshQueueCounts(scopeKey);
    if (remaining.pending === 0 && remaining.failed === 0) {
      acceptPacketsRef.current = true;
      terminalIngestionPausedRef.current = false;
      setSessionState(liveTelemetryRef.current ? 'active' : 'stale');
    } else {
      acceptPacketsRef.current = false;
      terminalIngestionPausedRef.current = true;
      setSessionState('degraded');
    }
  }, [flushQueue, processStagedPackets, refreshQueueCounts]);

  const value = useMemo(() => ({
    activeSession,
    sessionState,
    sessionError,
    pendingUploadCount,
    rejectedUploadCount,
    dataPersistenceState,
    isUploadQueueDurable,
    isSessionActive: ['active', 'stale', 'degraded'].includes(sessionState),
    startSession,
    stopSession,
    retryPendingUploads,
  }), [
    activeSession,
    dataPersistenceState,
    isUploadQueueDurable,
    pendingUploadCount,
    rejectedUploadCount,
    retryPendingUploads,
    sessionError,
    sessionState,
    startSession,
    stopSession,
  ]);

  return <PatientMonitoringContext.Provider value={value}>{children}</PatientMonitoringContext.Provider>;
}
