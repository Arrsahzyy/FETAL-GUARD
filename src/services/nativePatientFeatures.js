import { Capacitor, registerPlugin } from '@capacitor/core';

const PatientNotifications = registerPlugin('PatientNotifications');

const isNative = () => Capacitor.isNativePlatform();

export const requestNotificationPermission = async () => {
  if (isNative()) {
    const current = await PatientNotifications.checkPermissions();
    const result = current.notifications === 'granted'
      ? current
      : await PatientNotifications.requestPermissions();
    return result.notifications === 'granted';
  }

  if (typeof Notification === 'undefined') return false;
  if (Notification.permission === 'granted') return true;
  if (Notification.permission === 'denied') return false;
  return (await Notification.requestPermission()) === 'granted';
};

const toNotificationId = (value) => {
  const input = String(value || Date.now());
  let hash = 0;
  for (let index = 0; index < input.length; index += 1) {
    hash = Math.imul(31, hash) + input.charCodeAt(index) | 0;
  }
  return Math.max(1, Math.abs(hash));
};

export const showPatientNotification = async ({ id, title, body, sound = false }) => {
  if (!title || !body) return false;
  if (isNative()) {
    await PatientNotifications.show({
      id: toNotificationId(id),
      title,
      body,
      sound,
    });
    return true;
  }

  if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
    const notification = new Notification(title, { body, silent: !sound, tag: String(id || '') });
    notification.onclick = () => globalThis.focus?.();
    return true;
  }
  return false;
};

export const triggerPatientHaptic = async () => {
  return globalThis.navigator?.vibrate?.([120, 60, 120]) === true;
};

export const playPatientNotificationSound = async () => {
  const AudioContextClass = globalThis.AudioContext || globalThis.webkitAudioContext;
  if (!AudioContextClass) return false;
  const context = new AudioContextClass();
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = 'sine';
  oscillator.frequency.setValueAtTime(660, context.currentTime);
  gain.gain.setValueAtTime(0.0001, context.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.08, context.currentTime + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.28);
  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + 0.3);
  oscillator.addEventListener('ended', () => void context.close(), { once: true });
  return true;
};

export const getPatientNetworkStatus = async () => {
  const connection = globalThis.navigator?.connection
    || globalThis.navigator?.mozConnection
    || globalThis.navigator?.webkitConnection;
  return {
    connected: globalThis.navigator?.onLine !== false,
    type: connection?.type || 'unknown',
    canIdentifyWifi: Boolean(connection?.type),
  };
};

export const addPatientNetworkStatusListener = async (listener) => {
  const handleOnline = () => listener({ connected: true, connectionType: 'unknown' });
  const handleOffline = () => listener({ connected: false, connectionType: 'none' });
  const connection = globalThis.navigator?.connection
    || globalThis.navigator?.mozConnection
    || globalThis.navigator?.webkitConnection;
  const handleConnectionChange = () => listener({
    connected: globalThis.navigator?.onLine !== false,
    connectionType: connection?.type || 'unknown',
  });
  globalThis.addEventListener?.('online', handleOnline);
  globalThis.addEventListener?.('offline', handleOffline);
  connection?.addEventListener?.('change', handleConnectionChange);
  return () => {
    globalThis.removeEventListener?.('online', handleOnline);
    globalThis.removeEventListener?.('offline', handleOffline);
    connection?.removeEventListener?.('change', handleConnectionChange);
  };
};

export const canUploadWithPatientPolicy = async (wifiOnly) => {
  const status = await getPatientNetworkStatus();
  if (!status.connected) return { allowed: false, reason: 'offline', status };
  if (!wifiOnly) return { allowed: true, reason: null, status };
  if (!status.canIdentifyWifi) return { allowed: false, reason: 'network-unknown', status };
  return {
    allowed: status.type === 'wifi',
    reason: status.type === 'wifi' ? null : 'wifi-required',
    status,
  };
};

export const requestLocationPermission = async () => {
  return Boolean(globalThis.navigator?.geolocation);
};

export const getPatientLocationShareUrl = async () => {
  const permitted = await requestLocationPermission();
  if (!permitted) throw new Error('location_permission_denied');
  const position = await new Promise((resolve, reject) => {
    globalThis.navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 0,
    });
  });
  const { latitude, longitude } = position.coords;
  return `https://maps.google.com/?q=${latitude.toFixed(6)},${longitude.toFixed(6)}`;
};

export const sharePatientLocation = async ({ title, text }) => {
  const url = await getPatientLocationShareUrl();
  if (globalThis.navigator?.share) {
    await globalThis.navigator.share({ title, text, url });
    return { shared: true, url };
  }
  if (globalThis.navigator?.clipboard?.writeText) {
    await globalThis.navigator.clipboard.writeText(`${text}\n${url}`);
    return { shared: false, copied: true, url };
  }
  return { shared: false, copied: false, url };
};
