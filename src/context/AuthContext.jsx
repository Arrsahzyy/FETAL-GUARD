import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { t } from '../i18n';
import api, {
  AUTH_SESSION_CLEARED_EVENT,
  clearAuthStorage,
  getApiErrorMessage,
  getStoredRefreshToken,
  getStoredToken,
  getStoredUser,
  isRequestCanceled,
  setStoredRefreshToken,
  setStoredToken,
  setStoredUser,
} from '../services/api';
import AuthContext from './authContext';

async function withPatientProfile(user) {
  if (user?.role !== 'patient') return user;

  try {
    const profile = await api.patients.me();
    return { ...user, patientProfile: profile };
  } catch (error) {
    if (error?.response?.status === 404) {
      return { ...user, patientProfile: null, patientProfileMissing: true };
    }
    throw error;
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getStoredToken());
  const [user, setUser] = useState(() => getStoredUser());
  const [isAuthLoading, setIsAuthLoading] = useState(Boolean(getStoredToken()));
  const [authError, setAuthError] = useState('');

  const commitSession = useCallback((nextToken, nextRefreshToken, nextUser) => {
    setStoredToken(nextToken);
    setStoredRefreshToken(nextRefreshToken);
    setStoredUser(nextUser);
    setToken(nextToken);
    setUser(nextUser);
    setAuthError('');
  }, []);

  const logout = useCallback(() => {
    const refreshToken = getStoredRefreshToken();
    clearAuthStorage();
    setToken(null);
    setUser(null);
    setAuthError('');
    if (refreshToken) {
      api.auth.logout({ refreshToken }).catch(() => undefined);
    }
  }, []);

  useEffect(() => {
    const handleSessionCleared = () => {
      setToken(null);
      setUser(null);
      setAuthError(t('common.sessionExpired'));
    };

    window.addEventListener(AUTH_SESSION_CLEARED_EVENT, handleSessionCleared);
    return () => window.removeEventListener(AUTH_SESSION_CLEARED_EVENT, handleSessionCleared);
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function verifyStoredSession() {
      const storedToken = getStoredToken();
      if (!storedToken) {
        if (isMounted) setIsAuthLoading(false);
        return;
      }

      try {
        const currentUser = await api.auth.me();
        const userWithProfile = await withPatientProfile(currentUser);
        if (isMounted) {
          setStoredUser(userWithProfile);
          setUser(userWithProfile);
          setToken(getStoredToken());
        }
      } catch (error) {
        if (isMounted && !isRequestCanceled(error)) logout();
      } finally {
        if (isMounted) setIsAuthLoading(false);
      }
    }

    verifyStoredSession();

    return () => {
      isMounted = false;
    };
  }, [logout]);

  const login = useCallback(async ({ email, password }) => {
    setAuthError('');
    clearAuthStorage();
    setToken(null);
    setUser(null);
    const normalizedEmail = email.trim().toLowerCase();
    try {
      const tokenResponse = await api.auth.login({ email: normalizedEmail, password });
      setStoredToken(tokenResponse.access_token);
      setStoredRefreshToken(tokenResponse.refresh_token);
      const currentUser = await api.auth.me();
      const userWithProfile = await withPatientProfile(currentUser);
      commitSession(tokenResponse.access_token, tokenResponse.refresh_token, userWithProfile);
      return userWithProfile;
    } catch (error) {
      if (isRequestCanceled(error)) throw error;
      clearAuthStorage();
      setToken(null);
      setUser(null);
      const message = getApiErrorMessage(error);
      setAuthError(message);
      throw new Error(message);
    }
  }, [commitSession]);

  const registerPatient = useCallback(async ({
    email,
    password,
    name,
    age,
    gestationalAgeWeeks,
    medicalHistory,
  }) => {
    setAuthError('');
    clearAuthStorage();
    setToken(null);
    setUser(null);
    const normalizedEmail = email.trim().toLowerCase();
    try {
      const profileData = {
        name,
        age: Number(age),
        gestational_age_weeks: Number(gestationalAgeWeeks),
        medical_history: medicalHistory?.trim() || null,
      };
      try {
        await api.auth.registerPatient({
          email: normalizedEmail,
          password,
          profile: profileData,
        });
      } catch (registrationError) {
        // A legacy partial registration may already have an account but no profile.
        // Continue only when the supplied credentials can authenticate that account.
        if (registrationError?.response?.status !== 400) throw registrationError;
      }
      const tokenResponse = await api.auth.login({ email: normalizedEmail, password });
      setStoredToken(tokenResponse.access_token);
      setStoredRefreshToken(tokenResponse.refresh_token);
      let profile;
      try {
        profile = await api.patients.me();
      } catch (profileError) {
        if (profileError?.response?.status !== 404) throw profileError;
        profile = await api.patients.createProfile(profileData);
      }
      const currentUser = await api.auth.me();
      commitSession(tokenResponse.access_token, tokenResponse.refresh_token, { ...currentUser, patientProfile: profile });
      return { user: currentUser, profile };
    } catch (error) {
      if (isRequestCanceled(error)) throw error;
      clearAuthStorage();
      setToken(null);
      setUser(null);
      const message = getApiErrorMessage(error);
      setAuthError(message);
      throw new Error(message);
    }
  }, [commitSession]);

  const updatePatientProfile = useCallback(async (profileData) => {
    setAuthError('');
    try {
      const profile = await api.patients.updateProfile(profileData);
      setUser((currentUser) => {
        if (!currentUser) return currentUser;
        const nextUser = { ...currentUser, patientProfile: profile };
        setStoredUser(nextUser);
        return nextUser;
      });
      return profile;
    } catch (error) {
      if (isRequestCanceled(error)) throw error;
      const message = getApiErrorMessage(error);
      setAuthError(message);
      throw new Error(message);
    }
  }, []);

  const changePassword = useCallback(async ({ currentPassword, newPassword }) => {
    setAuthError('');
    try {
      const updatedUser = await api.auth.changePassword({ currentPassword, newPassword });
      clearAuthStorage();
      setToken(null);
      setUser(null);
      return updatedUser;
    } catch (error) {
      if (isRequestCanceled(error)) throw error;
      const message = getApiErrorMessage(error);
      setAuthError(message);
      throw new Error(message);
    }
  }, []);

  const value = useMemo(() => ({
    token,
    user,
    authError,
    isAuthLoading,
    isAuthenticated: Boolean(token && user),
    login,
    registerPatient,
    updatePatientProfile,
    changePassword,
    logout,
  }), [authError, changePassword, isAuthLoading, login, logout, registerPatient, token, updatePatientProfile, user]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
