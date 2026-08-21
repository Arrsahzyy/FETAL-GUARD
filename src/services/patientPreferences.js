const STORAGE_PREFIX = 'fetal_guard_patient_preferences_v1';
export const PATIENT_PREFERENCES_CHANGED_EVENT = 'fetalguard:patient-preferences-changed';

export const DEFAULT_PATIENT_PREFERENCES = Object.freeze({
  pushNotifications: false,
  importantAlerts: false,
  soundAlerts: false,
  hapticFeedback: false,
  uploadWifiOnly: false,
  shareLocation: false,
});

const BOOLEAN_KEYS = Object.keys(DEFAULT_PATIENT_PREFERENCES);

const getStorage = () => {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
};

const normalizeUserId = (userId) => {
  const value = String(userId || '').trim();
  if (!value) throw new Error('patient_preferences_require_user');
  return encodeURIComponent(value);
};

const getStorageKey = (userId) => `${STORAGE_PREFIX}:${normalizeUserId(userId)}`;

export const sanitizePatientPreferences = (value) => {
  const source = value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  return BOOLEAN_KEYS.reduce((preferences, key) => {
    preferences[key] = source[key] === true;
    return preferences;
  }, {});
};

export const getPatientPreferences = (userId) => {
  const storage = getStorage();
  if (!storage || !userId) return { ...DEFAULT_PATIENT_PREFERENCES };
  try {
    const stored = JSON.parse(storage.getItem(getStorageKey(userId)) || '{}');
    return sanitizePatientPreferences(stored);
  } catch {
    return { ...DEFAULT_PATIENT_PREFERENCES };
  }
};

export const setPatientPreferences = (userId, nextValue) => {
  const preferences = sanitizePatientPreferences(nextValue);
  const storage = getStorage();
  if (storage) storage.setItem(getStorageKey(userId), JSON.stringify(preferences));

  if (typeof globalThis.dispatchEvent === 'function' && typeof CustomEvent !== 'undefined') {
    globalThis.dispatchEvent(new CustomEvent(PATIENT_PREFERENCES_CHANGED_EVENT, {
      detail: { userId: String(userId), preferences },
    }));
  }
  return preferences;
};

export const updatePatientPreference = (userId, key, enabled) => {
  if (!BOOLEAN_KEYS.includes(key)) throw new Error('unsupported_patient_preference');
  return setPatientPreferences(userId, {
    ...getPatientPreferences(userId),
    [key]: enabled === true,
  });
};

export const clearPatientPreferences = (userId) => {
  const storage = getStorage();
  if (storage && userId) storage.removeItem(getStorageKey(userId));
};
