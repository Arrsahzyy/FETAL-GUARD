import { useCallback, useEffect, useRef } from 'react';
import { useI18n } from '../../i18n/useI18n';
import { t } from '../../i18n';
import { useAuth } from '../../context/useAuth';
import { usePatientDevice } from '../../context/usePatientDevice';
import api from '../../services/api';
import { createRealtimeEventPoller } from '../../services/realtimeEventPoller';
import {
  getPatientPreferences,
  PATIENT_PREFERENCES_CHANGED_EVENT,
} from '../../services/patientPreferences';
import {
  playPatientNotificationSound,
  showPatientNotification,
  triggerPatientHaptic,
} from '../../services/nativePatientFeatures';

const seenStorageKey = (userId) => `fetal_guard_seen_patient_alerts_v1:${encodeURIComponent(userId)}`;

const readSeenIds = (userId) => {
  try {
    const value = JSON.parse(localStorage.getItem(seenStorageKey(userId)) || '[]');
    return new Set(Array.isArray(value) ? value.map(String).slice(-250) : []);
  } catch {
    return new Set();
  }
};

const persistSeenIds = (userId, seenIds) => {
  try {
    localStorage.setItem(seenStorageKey(userId), JSON.stringify([...seenIds].slice(-250)));
  } catch {
    // Notification delivery must not break patient navigation when storage is unavailable.
  }
};

const isImportant = (riskLevel) => riskLevel === 'medium' || riskLevel === 'high';

const PatientNotificationBridge = () => {
  useI18n();
  const { user } = useAuth();
  const { activeAlerts } = usePatientDevice();
  const userId = user?.id;
  const seenIdsRef = useRef(new Set());
  const initializedRef = useRef(false);
  const preferencesRef = useRef(getPatientPreferences(userId));

  useEffect(() => {
    seenIdsRef.current = userId ? readSeenIds(userId) : new Set();
    preferencesRef.current = getPatientPreferences(userId);
    initializedRef.current = false;
  }, [userId]);

  useEffect(() => {
    const handlePreferencesChanged = (event) => {
      if (String(event.detail?.userId) === String(userId)) {
        preferencesRef.current = event.detail.preferences;
      }
    };
    window.addEventListener(PATIENT_PREFERENCES_CHANGED_EVENT, handlePreferencesChanged);
    return () => window.removeEventListener(PATIENT_PREFERENCES_CHANGED_EVENT, handlePreferencesChanged);
  }, [userId]);

  const processAlerts = useCallback(async (alerts, { initialize = false } = {}) => {
    if (!userId || !Array.isArray(alerts)) return;
    const normalized = alerts.map((alert) => ({
      id: String(alert.id),
      title: alert.title || t('patient.notifications.monitoringAlert'),
      message: alert.message || t('patient.notifications.openAppForDetails'),
      riskLevel: alert.risk_level || (alert.tone === 'critical' ? 'high' : alert.tone === 'warning' ? 'medium' : 'low'),
    }));

    if (initialize) {
      normalized.forEach((alert) => seenIdsRef.current.add(alert.id));
      persistSeenIds(userId, seenIdsRef.current);
      return;
    }

    for (const alert of normalized) {
      if (seenIdsRef.current.has(alert.id)) continue;
      seenIdsRef.current.add(alert.id);
      const preferences = preferencesRef.current;
      const permittedBySeverity = !isImportant(alert.riskLevel) || preferences.importantAlerts;
      if (preferences.pushNotifications && permittedBySeverity) {
        await showPatientNotification({
          id: alert.id,
          title: alert.title,
          body: alert.message,
          sound: preferences.soundAlerts,
        }).catch(() => false);
        if (preferences.soundAlerts) await playPatientNotificationSound().catch(() => false);
        if (preferences.hapticFeedback) await triggerPatientHaptic().catch(() => false);
      }
    }
    persistSeenIds(userId, seenIdsRef.current);
  }, [userId]);

  useEffect(() => {
    if (!userId) return undefined;
    if (!initializedRef.current) {
      void processAlerts(activeAlerts, { initialize: true });
      initializedRef.current = true;
      return undefined;
    }
    void processAlerts(activeAlerts);
    return undefined;
  }, [activeAlerts, processAlerts, userId]);

  useEffect(() => {
    if (!userId) return undefined;
    let firstFetch = true;
    const fetchAlerts = async ({ signal } = {}) => {
      const alerts = await api.patients.listAlerts({ limit: 100, signal });
      await processAlerts(alerts, { initialize: firstFetch });
      firstFetch = false;
    };
    const poller = createRealtimeEventPoller({
      fetchEvents: ({ cursor, signal }) => api.patients.listRealtimeEvents({
        afterCursor: cursor,
        limit: 100,
        signal,
      }),
      onEvents: (events) => (
        events.some((event) => event.event_type.startsWith('alert.'))
          ? fetchAlerts()
          : undefined
      ),
      onHeartbeat: () => fetchAlerts(),
      initialDelayMs: 2_000,
      heartbeatIntervalMs: 60_000,
    });
    void fetchAlerts().catch(() => undefined);
    poller.start();
    return () => poller.stop();
  }, [processAlerts, userId]);

  return null;
};

export default PatientNotificationBridge;
