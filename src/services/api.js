import axios from 'axios';
import { Capacitor } from '@capacitor/core';
import { t } from '../i18n';
import { authSessionEpoch } from './authSessionEpoch.js';
import {
  evaluateApiRuntimePolicy,
  normalizePrivateNetworkApiBaseUrl,
} from './apiRuntimeConfig.js';

const configuredApiBaseUrl = String(import.meta.env.VITE_API_BASE_URL || '').trim();
const isNativeRuntime = Capacitor.isNativePlatform();
const isLocalAndroidDebugRuntime = isNativeRuntime
  && import.meta.env.MODE === 'android-local'
  && import.meta.env.VITE_ALLOW_INSECURE_LOCAL_API === 'true';
const LOCAL_ANDROID_API_STORAGE_KEY = 'fetal_guard_local_android_api_base_url';
const storedLocalAndroidApiBaseUrl = isLocalAndroidDebugRuntime && typeof window !== 'undefined'
  ? normalizePrivateNetworkApiBaseUrl(
    window.localStorage.getItem(LOCAL_ANDROID_API_STORAGE_KEY),
  )
  : null;
let API_BASE_URL = storedLocalAndroidApiBaseUrl
  || configuredApiBaseUrl
  || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '');
const {
  hasMissingNativeApiConfig,
  hasUnsafeProductionApiConfig,
} = evaluateApiRuntimePolicy({
  configuredApiBaseUrl: API_BASE_URL,
  isNativeRuntime,
  isProduction: import.meta.env.PROD,
  mode: import.meta.env.MODE,
  allowInsecureLocalApi: import.meta.env.VITE_ALLOW_INSECURE_LOCAL_API === 'true',
});
const AUTH_TOKEN_KEY = 'fetal_guard_access_token';
const AUTH_REFRESH_TOKEN_KEY = 'fetal_guard_refresh_token';
const AUTH_USER_KEY = 'fetal_guard_user';
const AUTH_ORGANIZATION_KEY = 'fetal_guard_organization_id';
const AUTH_SESSION_CLEARED_EVENT = 'fetal_guard_auth_session_cleared';
const AUTH_SCOPE_CHANGED_EVENT = 'fetal_guard_auth_scope_changed';

export const API_ERROR_CODES = Object.freeze({
  ACCOUNT_INACTIVE: 'ACCOUNT_INACTIVE',
  PASSWORD_RESET_REQUIRED: 'PASSWORD_RESET_REQUIRED',
  PERMISSION_DENIED: 'PERMISSION_DENIED',
  SCOPE_REVOKED: 'SCOPE_REVOKED',
});

const LEGACY_ERROR_CODES = Object.freeze({
  'This account is inactive': API_ERROR_CODES.ACCOUNT_INACTIVE,
  'Password reset required before accessing this resource': API_ERROR_CODES.PASSWORD_RESET_REQUIRED,
  'Not enough permissions': API_ERROR_CODES.PERMISSION_DENIED,
  'Only clinician users can access this resource': API_ERROR_CODES.PERMISSION_DENIED,
});

const getAuthStorage = () => (
  typeof window !== 'undefined' ? window.sessionStorage : null
);

if (typeof window !== 'undefined') {
  // Remove legacy persistent copies that may contain tokens or patient profile data.
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem(AUTH_REFRESH_TOKEN_KEY);
  window.localStorage.removeItem(AUTH_USER_KEY);
  window.localStorage.removeItem(AUTH_ORGANIZATION_KEY);
}

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export function setLocalAndroidApiBaseUrl(value) {
  if (!isLocalAndroidDebugRuntime || typeof window === 'undefined') {
    throw new Error('Local Android API override is unavailable in this build');
  }
  const normalizedValue = normalizePrivateNetworkApiBaseUrl(value);
  if (!normalizedValue) {
    throw new TypeError('Local Android API must be a private HTTP origin');
  }
  window.localStorage.setItem(LOCAL_ANDROID_API_STORAGE_KEY, normalizedValue);
  API_BASE_URL = normalizedValue;
  apiClient.defaults.baseURL = normalizedValue;
  return normalizedValue;
}

export function getStoredToken() {
  return getAuthStorage()?.getItem(AUTH_TOKEN_KEY) || null;
}

export function setStoredToken(token) {
  getAuthStorage()?.setItem(AUTH_TOKEN_KEY, token);
}

export function clearStoredToken() {
  getAuthStorage()?.removeItem(AUTH_TOKEN_KEY);
}

export function getStoredRefreshToken() {
  return getAuthStorage()?.getItem(AUTH_REFRESH_TOKEN_KEY) || null;
}

export function setStoredRefreshToken(token) {
  if (token) {
    getAuthStorage()?.setItem(AUTH_REFRESH_TOKEN_KEY, token);
    return;
  }
  getAuthStorage()?.removeItem(AUTH_REFRESH_TOKEN_KEY);
}

export function clearStoredRefreshToken() {
  getAuthStorage()?.removeItem(AUTH_REFRESH_TOKEN_KEY);
}

export function getStoredUser() {
  const rawUser = getAuthStorage()?.getItem(AUTH_USER_KEY);
  if (!rawUser) return null;

  try {
    return JSON.parse(rawUser);
  } catch {
    getAuthStorage()?.removeItem(AUTH_USER_KEY);
    return null;
  }
}

export function setStoredUser(user) {
  if (!user) {
    clearStoredUser();
    return;
  }
  const sessionIdentity = {
    id: user.id,
    email: user.email,
    role: user.role,
    is_active: user.is_active,
    must_reset_password: user.must_reset_password,
    password_changed_at: user.password_changed_at,
  };
  getAuthStorage()?.setItem(AUTH_USER_KEY, JSON.stringify(sessionIdentity));
}

export function clearStoredUser() {
  getAuthStorage()?.removeItem(AUTH_USER_KEY);
}

function normalizeOrganizationId(organizationId) {
  const normalizedId = String(organizationId || '').trim();
  if (!normalizedId) return null;
  return /^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$/.test(normalizedId)
    ? normalizedId
    : null;
}

export function getStoredOrganizationId() {
  const storedId = getAuthStorage()?.getItem(AUTH_ORGANIZATION_KEY) || null;
  const normalizedId = normalizeOrganizationId(storedId);
  if (storedId && !normalizedId) removeStoredOrganizationId();
  return normalizedId;
}

function removeStoredOrganizationId() {
  getAuthStorage()?.removeItem(AUTH_ORGANIZATION_KEY);
}

function notifyScopeChanged(organizationId) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(AUTH_SCOPE_CHANGED_EVENT, {
      detail: { organizationId },
    }));
  }
}

export function setStoredOrganizationId(organizationId) {
  const normalizedId = normalizeOrganizationId(organizationId);
  if (!String(organizationId || '').trim()) {
    clearStoredOrganizationId();
    return;
  }
  if (!normalizedId) throw new TypeError('Invalid organization identifier');
  if (getStoredOrganizationId() === normalizedId) return;

  getAuthStorage()?.setItem(AUTH_ORGANIZATION_KEY, normalizedId);
  notifyScopeChanged(normalizedId);
}

export function clearStoredOrganizationId() {
  if (!getStoredOrganizationId()) return;
  removeStoredOrganizationId();
  notifyScopeChanged(null);
}

export function clearAuthStorage() {
  authSessionEpoch.advance();
  clearStoredToken();
  clearStoredRefreshToken();
  clearStoredUser();
  removeStoredOrganizationId();
}

export function getAuthSessionGeneration() {
  return authSessionEpoch.current();
}

export function isRequestCanceled(error) {
  return axios.isCancel(error) || error?.code === 'ERR_CANCELED';
}

export function getApiErrorCode(error) {
  const responseData = error?.response?.data;
  const detail = responseData?.detail;
  const explicitCode = responseData?.code
    || responseData?.error_code
    || (detail && typeof detail === 'object' && !Array.isArray(detail)
      ? detail.code || detail.error_code
      : null);

  if (typeof explicitCode === 'string' && explicitCode.trim()) {
    return explicitCode.trim().toUpperCase();
  }

  return typeof detail === 'string' ? LEGACY_ERROR_CODES[detail] || null : null;
}

export function isAuthorizationDeniedError(error) {
  return error?.response?.status === 403;
}

function createStaleAuthRequestError() {
  const error = new axios.CanceledError('Authorization context changed while the request was running');
  error.isAuthSessionStale = true;
  return error;
}

function isRequestFromCurrentAuthSession(config = {}) {
  const generationMatches = config.authSessionGeneration === undefined
    || authSessionEpoch.isCurrent(config.authSessionGeneration);
  const organizationMatches = config.authOrganizationId === undefined
    || config.authOrganizationId === getStoredOrganizationId();
  return generationMatches && organizationMatches;
}

function notifySessionCleared() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_SESSION_CLEARED_EVENT));
  }
}

function isAuthLifecycleRequest(requestUrl = '') {
  return (
    requestUrl.includes('/auth/login')
    || requestUrl.includes('/auth/register')
    || requestUrl.includes('/auth/refresh')
    || requestUrl.includes('/auth/logout')
  );
}

async function refreshAccessToken() {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    throw new Error('Missing refresh token');
  }

  const generation = authSessionEpoch.current();
  const existingRefresh = authSessionEpoch.getRefreshPromise(generation, refreshToken);
  if (existingRefresh) return existingRefresh;

  let refreshPromise;
  refreshPromise = apiClient.post(
    '/auth/refresh',
    { refresh_token: refreshToken },
    { skipAuthRefresh: true, skipAuthHeader: true, skipScopeBinding: true },
  )
    .then((response) => {
      if (
        !authSessionEpoch.isCurrent(generation)
        || getStoredRefreshToken() !== refreshToken
      ) {
        throw createStaleAuthRequestError();
      }

      const tokenResponse = response.data;
      setStoredToken(tokenResponse.access_token);
      setStoredRefreshToken(tokenResponse.refresh_token);
      return tokenResponse;
    })
    .finally(() => {
      authSessionEpoch.clearRefreshPromise(refreshPromise);
    });

  if (!authSessionEpoch.setRefreshPromise(generation, refreshToken, refreshPromise)) {
    throw createStaleAuthRequestError();
  }
  return refreshPromise;
}

export function getApiErrorMessage(error) {
  const detail = error?.response?.data?.detail;

  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(', ');
  }

  if (typeof detail === 'string') {
    return detail;
  }

  if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    return detail.message;
  }

  if (error?.code === 'ECONNABORTED') {
    return t('common.apiTimeout');
  }

  if (error?.code === 'API_CONFIGURATION_ERROR') {
    return error.message;
  }

  if (!error?.response) {
    return isLocalAndroidDebugRuntime
      ? t('common.apiUnavailableLocal', { address: API_BASE_URL })
      : t('common.apiUnavailable');
  }

  return t('common.apiError');
}

apiClient.interceptors.request.use((config) => {
  if (hasMissingNativeApiConfig || hasUnsafeProductionApiConfig) {
    const configurationError = new Error(
      hasMissingNativeApiConfig
        ? t('common.apiMobileConfigMissing')
        : t('common.apiHttpsRequired'),
    );
    configurationError.code = 'API_CONFIGURATION_ERROR';
    return Promise.reject(configurationError);
  }
  if (config.authorizationContextBound) {
    if (!isRequestFromCurrentAuthSession(config)) {
      return Promise.reject(createStaleAuthRequestError());
    }
  } else {
    config.authorizationContextBound = true;
    config.authSessionGeneration = authSessionEpoch.current();
    const isScopeBoundRequest = !config.skipScopeBinding
      && !isAuthLifecycleRequest(config.url || '');
    const organizationId = isScopeBoundRequest ? getStoredOrganizationId() : null;
    config.authOrganizationId = isScopeBoundRequest ? organizationId : undefined;
    if (organizationId) {
      config.headers['X-Organization-ID'] = organizationId;
    } else if (typeof config.headers.delete === 'function') {
      config.headers.delete('X-Organization-ID');
    } else {
      delete config.headers['X-Organization-ID'];
    }

    const token = getStoredToken();
    if (token && !config.skipAuthHeader) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => {
    if (!isRequestFromCurrentAuthSession(response?.config)) {
      return Promise.reject(createStaleAuthRequestError());
    }
    return response;
  },
  async (error) => {
    const statusCode = error?.response?.status;
    const originalRequest = error?.config || {};
    const requestUrl = originalRequest.url || '';
    const isAuthEntryRequest = isAuthLifecycleRequest(requestUrl);
    const errorCode = getApiErrorCode(error);
    const isSessionBlockingError = statusCode === 403 && [
      API_ERROR_CODES.ACCOUNT_INACTIVE,
      API_ERROR_CODES.PASSWORD_RESET_REQUIRED,
    ].includes(errorCode);

    if (isRequestCanceled(error)) return Promise.reject(error);
    if (!isRequestFromCurrentAuthSession(originalRequest)) {
      return Promise.reject(createStaleAuthRequestError());
    }

    if (isSessionBlockingError) {
      clearAuthStorage();
      notifySessionCleared();
      return Promise.reject(error);
    }

    if (statusCode === 403 && errorCode === API_ERROR_CODES.SCOPE_REVOKED) {
      clearStoredOrganizationId();
      return Promise.reject(error);
    }

    if (
      statusCode === 401
      && !isAuthEntryRequest
      && !originalRequest.skipAuthRefresh
      && !originalRequest._retry
      && getStoredRefreshToken()
    ) {
      originalRequest._retry = true;
      try {
        const tokenResponse = await refreshAccessToken();
        if (!isRequestFromCurrentAuthSession(originalRequest)) {
          throw createStaleAuthRequestError();
        }
        originalRequest.headers = {
          ...originalRequest.headers,
          Authorization: `Bearer ${tokenResponse.access_token}`,
        };
        return apiClient(originalRequest);
      } catch (refreshError) {
        if (
          isRequestCanceled(refreshError)
          || !isRequestFromCurrentAuthSession(originalRequest)
        ) {
          return Promise.reject(refreshError);
        }
        clearAuthStorage();
        notifySessionCleared();
        return Promise.reject(refreshError);
      }
    }

    if (statusCode === 401 && !isAuthEntryRequest) {
      clearAuthStorage();
      notifySessionCleared();
    }

    return Promise.reject(error);
  },
);

const auth = {
  async register({ email, password, role = 'patient' }) {
    const response = await apiClient.post('/auth/register', { email, password, role });
    return response.data;
  },

  async registerPatient({ email, password, profile }) {
    const response = await apiClient.post('/auth/register/patient', {
      email,
      password,
      role: 'patient',
      profile,
    });
    return response.data;
  },

  async login({ email, password }) {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await apiClient.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  async refresh({ refreshToken }) {
    const response = await apiClient.post(
      '/auth/refresh',
      { refresh_token: refreshToken },
      { skipAuthRefresh: true, skipAuthHeader: true, skipScopeBinding: true },
    );
    return response.data;
  },

  async logout({ refreshToken } = {}) {
    const response = await apiClient.post(
      '/auth/logout',
      { refresh_token: refreshToken || null },
      { skipAuthRefresh: true, skipAuthHeader: true },
    );
    return response.data;
  },

  async me() {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },

  async changePassword({ currentPassword, newPassword }) {
    const response = await apiClient.post('/auth/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  },
};

const patients = {
  async createProfile(data) {
    const response = await apiClient.post('/patients', data);
    return response.data;
  },

  async me() {
    const response = await apiClient.get('/patients/me');
    return response.data;
  },

  async updateProfile(data) {
    const response = await apiClient.patch('/patients/me', data);
    return response.data;
  },

  async listAlerts({ limit = 50, offset = 0, signal } = {}) {
    const response = await apiClient.get('/patients/me/alerts', {
      signal,
      params: { limit, offset },
    });
    return response.data;
  },

  async deleteMonitoringData() {
    const response = await apiClient.delete('/patients/me/monitoring-data');
    return response.data;
  },

  async listRealtimeEvents({ afterCursor = null, limit = 50, signal } = {}) {
    const response = await apiClient.get('/realtime/patient/events', {
      signal,
      params: {
        after_cursor: Number.isSafeInteger(afterCursor) ? afterCursor : undefined,
        limit,
      },
    });
    return response.data;
  },

  async listAIResults({ sessionId, limit = 25, offset = 0, signal } = {}) {
    const response = await apiClient.get('/ai/results', {
      signal,
      params: {
        session_id: sessionId || undefined,
        limit,
        offset,
      },
    });
    return response.data;
  },
};

const devices = {
  async listMine() {
    const response = await apiClient.get('/devices/me');
    return response.data;
  },
};

const sessions = {
  async listSessions({ limit = 50, offset = 0, signal } = {}) {
    const response = await apiClient.get('/sessions', {
      signal,
      params: { limit, offset },
    });
    return response.data;
  },

  async createSession(data = {}) {
    const response = await apiClient.post('/sessions', data);
    return response.data;
  },

  async sendDataChunk(sessionId, payload, metadata = {}) {
    const response = await apiClient.post(`/sessions/${sessionId}/data`, { payload, ...metadata });
    return response.data;
  },

  async endSession(sessionId) {
    const response = await apiClient.patch(`/sessions/${sessionId}`, { status: 'completed' });
    return response.data;
  },
};

const organizations = {
  async listMine({ signal } = {}) {
    const response = await apiClient.get('/organizations/me', {
      signal,
      skipScopeBinding: true,
    });
    return response.data;
  },
};

const clinician = {
  async listRealtimeEvents({ afterCursor = null, patientId, limit = 50, signal } = {}) {
    const response = await apiClient.get('/realtime/clinician/events', {
      signal,
      params: {
        after_cursor: Number.isSafeInteger(afterCursor) ? afterCursor : undefined,
        patient_id: patientId || undefined,
        limit,
      },
    });
    return response.data;
  },

  async getStatistics({ signal } = {}) {
    const response = await apiClient.get('/clinician/statistics', { signal });
    return response.data;
  },

  async listPatients({ q, risk, status, sort = 'recent', limit = 100, offset = 0, signal } = {}) {
    const response = await apiClient.get('/clinician/patients', {
      signal,
      params: {
        q: q || undefined,
        risk: risk && risk !== 'all' ? risk : undefined,
        status: status && status !== 'all' ? status : undefined,
        sort,
        limit,
        offset,
      },
    });
    return response.data;
  },

  async getPatient(patientId, { signal } = {}) {
    const response = await apiClient.get(`/clinician/patients/${patientId}`, { signal });
    return response.data;
  },

  async listAlerts({
    risk,
    acknowledged = 'all',
    patientId,
    sort = 'priority',
    limit = 100,
    offset = 0,
    signal,
  } = {}) {
    const response = await apiClient.get('/clinician/alerts', {
      signal,
      params: {
        risk: risk || undefined,
        acknowledged: acknowledged !== 'all' ? acknowledged : undefined,
        patient_id: patientId || undefined,
        sort,
        limit,
        offset,
      },
    });
    return response.data;
  },

  async acknowledgeAlert(alertId, { note, expectedVersion } = {}) {
    const response = await apiClient.post(`/clinician/alerts/${alertId}/acknowledge`, {
      note: note || undefined,
      expected_version: expectedVersion || undefined,
    });
    return response.data;
  },

  async updateAlertStatus(alertId, { status, note, expectedVersion } = {}) {
    const response = await apiClient.patch(`/clinician/alerts/${alertId}/status`, {
      status,
      note: note || undefined,
      expected_version: expectedVersion || undefined,
    });
    return response.data;
  },

  async listPatientAIResults(
    patientId,
    { sessionId, limit = 25, offset = 0, signal } = {},
  ) {
    const response = await apiClient.get(`/ai/clinician/patients/${patientId}/results`, {
      signal,
      params: {
        session_id: sessionId || undefined,
        limit,
        offset,
      },
    });
    return response.data;
  },

  async reviewAIResult(resultId, { decision, note, expectedVersion = 0 }) {
    const response = await apiClient.patch(`/ai/clinician/results/${resultId}/review`, {
      decision,
      note: note?.trim() || undefined,
      expected_version: expectedVersion,
    });
    return response.data;
  },
};

const admin = {
  async listClinicians({ q, limit = 25, offset = 0, signal } = {}) {
    const response = await apiClient.get('/admin/clinicians', {
      signal,
      params: { q: q || undefined, limit, offset },
    });
    return response.data;
  },

  async listPatients({ q, limit = 25, offset = 0, signal } = {}) {
    const response = await apiClient.get('/admin/patients', {
      signal,
      params: { q: q || undefined, limit, offset },
    });
    return response.data;
  },

  async provisionClinician(data) {
    const response = await apiClient.post('/admin/clinicians', data);
    return response.data;
  },

  async bulkProvisionClinicians(data) {
    const response = await apiClient.post('/admin/clinicians/bulk', data);
    return response.data;
  },

  async listAuditLogs({ limit = 20, signal } = {}) {
    const response = await apiClient.get('/admin/audit-logs', {
      signal,
      params: { limit },
    });
    return response.data;
  },

  async assignPatientToClinician(data) {
    const response = await apiClient.post('/admin/patient-assignments', data);
    return response.data;
  },

  async unassignPatientAssignment(assignmentId) {
    const response = await apiClient.delete(`/admin/patient-assignments/${assignmentId}`);
    return response.data;
  },

  async revokeClinicianMembership(membershipId) {
    const response = await apiClient.delete(`/admin/clinician-memberships/${membershipId}`);
    return response.data;
  },

  async deactivateClinician(clinicianId) {
    const response = await apiClient.post(`/admin/clinicians/${clinicianId}/deactivate`);
    return response.data;
  },

  async activateClinician(clinicianId) {
    const response = await apiClient.post(`/admin/clinicians/${clinicianId}/activate`);
    return response.data;
  },

  async resetClinicianPassword(clinicianId, data = {}) {
    const response = await apiClient.post(`/admin/clinicians/${clinicianId}/reset-password`, data);
    return response.data;
  },

  async listDevices({ q, patientId, status, limit = 25, offset = 0 } = {}) {
    const response = await apiClient.get('/devices', {
      params: {
        q: q || undefined,
        patient_id: patientId || undefined,
        status: status && status !== 'all' ? status : undefined,
        limit,
        offset,
      },
    });
    return response.data;
  },

  async registerDevice(data) {
    const response = await apiClient.post('/devices', data);
    return response.data;
  },

  async updateDevice(deviceId, data) {
    const response = await apiClient.patch(`/devices/${deviceId}`, data);
    return response.data;
  },
};

const api = {
  client: apiClient,
  auth,
  patients,
  devices,
  sessions,
  organizations,
  clinician,
  admin,
};

export {
  API_BASE_URL,
  AUTH_REFRESH_TOKEN_KEY,
  AUTH_TOKEN_KEY,
  AUTH_USER_KEY,
  AUTH_ORGANIZATION_KEY,
  AUTH_SESSION_CLEARED_EVENT,
  AUTH_SCOPE_CHANGED_EVENT,
  auth,
  patients,
  devices,
  sessions,
  organizations,
  clinician,
  admin,
};
export default api;
