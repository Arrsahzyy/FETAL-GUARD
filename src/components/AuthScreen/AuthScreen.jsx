import React, { useEffect, useMemo, useState } from 'react';
import { Capacitor } from '@capacitor/core';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import { t } from '../../i18n';
import { API_BASE_URL, setLocalAndroidApiBaseUrl } from '../../services/api';
import BrandLogo from '../BrandLogo/BrandLogo';
import './AuthScreen.css';

const INITIAL_FORM = {
  email: '',
  password: '',
  name: '',
  age: '',
  gestationalAgeWeeks: '',
  medicalHistory: '',
};

const PORTAL_CONFIG = {
  patient: {
    className: 'auth-screen--patient',
    backPath: '/portal-ibu-hamil',
    backLabel: 'Kembali ke Portal Ibu Hamil',
    expectedRole: 'patient',
    allowRegister: true,
    label: 'Portal Ibu Hamil',
    loginTitle: 'Masuk Portal Ibu Hamil',
    registerTitle: 'Daftar Akun Pasien',
    loginDescription: 'Masuk ke ruang pemantauan pribadi untuk melihat ringkasan kondisi, sesi monitoring, riwayat, dan edukasi tindak lanjut.',
    registerDescription: 'Buat akun pasien untuk menyimpan profil dasar dan sesi pemantauan FETAL-GUARD.',
    submitLogin: 'Masuk sebagai pasien',
    roleMismatch: 'Akun ini bukan akun pasien. Gunakan Portal Nakes bila Anda masuk sebagai tenaga kesehatan.',
  },
  clinician: {
    className: 'auth-screen--clinician',
    backPath: '/portal-nakes',
    backLabel: 'Kembali ke Portal Nakes',
    expectedRole: 'clinician',
    allowRegister: false,
    label: 'Portal Nakes',
    loginTitle: 'Masuk Portal Nakes',
    registerTitle: '',
    loginDescription: 'Akses khusus tenaga kesehatan untuk meninjau daftar pasien, sesi monitoring, status risiko skrining awal, dan catatan tindak lanjut.',
    registerDescription: '',
    submitLogin: 'Masuk sebagai nakes',
    roleMismatch: 'Akun ini bukan akun nakes. Akses dashboard nakes hanya tersedia untuk akun yang diprovisikan oleh sistem.',
  },
  admin: {
    className: 'auth-screen--admin',
    backPath: '/',
    backLabel: 'Kembali ke Beranda',
    expectedRole: 'admin',
    allowRegister: false,
    label: 'Portal Admin',
    loginTitle: 'Masuk Portal Admin',
    registerTitle: '',
    loginDescription: 'Akses terbatas untuk mengelola provisioning akun nakes dan menjaga pemisahan akses sistem.',
    registerDescription: '',
    submitLogin: 'Masuk sebagai admin',
    roleMismatch: 'Akun ini bukan akun admin. Akses provisioning nakes hanya tersedia untuk administrator.',
  },
  general: {
    className: 'auth-screen--general',
    backPath: '/',
    backLabel: 'Kembali ke Beranda',
    expectedRole: null,
    allowRegister: true,
    label: 'Akses FETAL-GUARD',
    loginTitle: 'Masuk ke Fetal-Guard',
    registerTitle: 'Daftar Akun Pasien',
    loginDescription: 'Pilih jalur portal yang sesuai sebelum masuk agar data pasien dan akses nakes tetap terpisah.',
    registerDescription: 'Buat akun pasien untuk menyimpan profil dasar dan sesi pemantauan FETAL-GUARD.',
    submitLogin: 'Masuk',
    roleMismatch: '',
  },
};

const AuthScreen = ({ portal = 'general' }) => {
  const { login, registerPatient, logout, authError, isAuthLoading } = useAuth();
  const config = PORTAL_CONFIG[portal] || PORTAL_CONFIG.general;
  const isNativePatientApp = Capacitor.isNativePlatform() && portal === 'patient';
  const isLocalAndroidBuild = isNativePatientApp && import.meta.env.MODE === 'android-local';
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState(INITIAL_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [localApiAddress, setLocalApiAddress] = useState(API_BASE_URL);
  const [localApiStatus, setLocalApiStatus] = useState('');

  useEffect(() => {
    setMode('login');
    setForm(INITIAL_FORM);
    setSubmitError('');
  }, [portal]);

  const heading = useMemo(() => (
    mode === 'login' ? config.loginTitle : config.registerTitle
  ), [config.loginTitle, config.registerTitle, mode]);

  const description = useMemo(() => (
    mode === 'login' ? config.loginDescription : config.registerDescription
  ), [config.loginDescription, config.registerDescription, mode]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const switchMode = (nextMode) => {
    if (nextMode === 'register' && !config.allowRegister) return;
    setMode(nextMode);
    setSubmitError('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setSubmitError('');

    try {
      if (mode === 'login') {
        const authenticatedUser = await login({ email: form.email, password: form.password });

        if (config.expectedRole && authenticatedUser?.role !== config.expectedRole) {
          logout();
          setSubmitError(config.roleMismatch);
        }
      } else {
        await registerPatient(form);
      }
    } catch (error) {
      setSubmitError(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLocalApiSubmit = (event) => {
    event.preventDefault();
    setLocalApiStatus('');
    try {
      const savedAddress = setLocalAndroidApiBaseUrl(localApiAddress);
      setLocalApiAddress(savedAddress);
      setSubmitError('');
      setLocalApiStatus(t('common.localApiSaved'));
    } catch {
      setLocalApiStatus(t('common.localApiInvalid'));
    }
  };

  const errorMessage = submitError || authError;

  return (
    <div className={`auth-screen ${config.className}${isNativePatientApp ? ' auth-screen--native' : ''}`}>
      <section className="auth-panel" aria-label={`Autentikasi ${config.label}`}>
        <div className="auth-panel__header">
          {!isNativePatientApp && (
            <Link to={config.backPath} className="auth-panel__back-link">
              &larr; {config.backLabel}
            </Link>
          )}
          <BrandLogo variant="auth" />
          <span className="auth-panel__portal-label">{config.label}</span>
          <h1>{heading}</h1>
          <p>{description}</p>
        </div>

        {!isNativePatientApp && (
          <nav className="auth-panel__portal-switch" aria-label="Pilih jalur portal">
            <Link
              to="/login/ibu-hamil"
              className={portal === 'patient' ? 'auth-panel__portal-option auth-panel__portal-option--active' : 'auth-panel__portal-option'}
            >
              Ibu Hamil
            </Link>
            <Link
              to="/login/nakes"
              className={portal === 'clinician' ? 'auth-panel__portal-option auth-panel__portal-option--active' : 'auth-panel__portal-option'}
            >
              Nakes
            </Link>
            <Link
              to="/login/admin"
              className={portal === 'admin' ? 'auth-panel__portal-option auth-panel__portal-option--active' : 'auth-panel__portal-option'}
            >
              Admin
            </Link>
          </nav>
        )}

        {isLocalAndroidBuild && (
          <div className="auth-panel__local-test-note">
            <p>{t('common.localApiHint')}</p>
            <details className="auth-panel__local-api-settings" open>
              <summary>{t('common.localApiSettings')}</summary>
              <form onSubmit={handleLocalApiSubmit}>
                <label htmlFor="local-api-address">{t('common.localApiAddress')}</label>
                <div className="auth-panel__local-api-row">
                  <input
                    id="local-api-address"
                    type="url"
                    inputMode="url"
                    value={localApiAddress}
                    onChange={(event) => setLocalApiAddress(event.target.value)}
                    placeholder="http://192.168.137.1:3020"
                    required
                  />
                  <button type="submit">{t('common.save')}</button>
                </div>
                {localApiStatus && <small role="status">{localApiStatus}</small>}
              </form>
            </details>
          </div>
        )}

        <div
          className={config.allowRegister ? 'auth-panel__tabs' : 'auth-panel__tabs auth-panel__tabs--single'}
          role="tablist"
          aria-label="Mode autentikasi"
        >
          <button
            type="button"
            id="auth-tab-login"
            role="tab"
            aria-selected={mode === 'login'}
            aria-controls="auth-panel-form"
            className={mode === 'login' ? 'auth-panel__tab auth-panel__tab--active' : 'auth-panel__tab'}
            onClick={() => switchMode('login')}
          >
            Masuk
          </button>
          {config.allowRegister && (
            <button
              type="button"
              id="auth-tab-register"
              role="tab"
              aria-selected={mode === 'register'}
              aria-controls="auth-panel-form"
              className={mode === 'register' ? 'auth-panel__tab auth-panel__tab--active' : 'auth-panel__tab'}
              onClick={() => switchMode('register')}
            >
              Daftar Pasien
            </button>
          )}
        </div>

        {!config.allowRegister && (
          <p className="auth-panel__role-note">
            Registrasi akun staf tidak dibuka dari halaman publik. Gunakan akun yang sudah diberikan oleh admin/sistem.
          </p>
        )}

        <form
          id="auth-panel-form"
          className="auth-form"
          role="tabpanel"
          aria-labelledby={mode === 'login' ? 'auth-tab-login' : 'auth-tab-register'}
          onSubmit={handleSubmit}
        >
          <label className="auth-form__field">
            <span>Email</span>
            <input
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              autoComplete="email"
              required
            />
          </label>

          <label className="auth-form__field">
            <span>Password</span>
            <input
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={8}
              required
            />
          </label>

          {mode === 'register' && (
            <>
              <label className="auth-form__field">
                <span>Nama</span>
                <input
                  name="name"
                  type="text"
                  value={form.name}
                  onChange={handleChange}
                  autoComplete="name"
                  required
                />
              </label>

              <div className="auth-form__grid">
                <label className="auth-form__field">
                  <span>Usia</span>
                  <input
                    name="age"
                    type="number"
                    min="10"
                    max="60"
                    value={form.age}
                    onChange={handleChange}
                    required
                  />
                </label>

                <label className="auth-form__field">
                  <span>Usia Kehamilan (Minggu)</span>
                  <select
                    name="gestationalAgeWeeks"
                    value={form.gestationalAgeWeeks}
                    onChange={handleChange}
                    required
                  >
                    <option value="" disabled>Pilih usia kehamilan...</option>
                    {Array.from({ length: 42 }, (_, i) => i + 1).map((week) => {
                      const monthEstimate = Math.ceil(week / 4.345);
                      return (
                        <option key={week} value={week}>
                          {week} minggu (sekitar bulan ke-{monthEstimate})
                        </option>
                      );
                    })}
                  </select>
                </label>
              </div>

              <label className="auth-form__field">
                <span>Riwayat kesehatan singkat <small>(opsional)</small></span>
                <textarea
                  name="medicalHistory"
                  value={form.medicalHistory}
                  onChange={handleChange}
                  rows="3"
                  aria-describedby="medical-history-hint"
                />
                <small id="medical-history-hint" className="auth-form__hint">
                  Contoh: hipertensi, diabetes, alergi obat, obat rutin, atau catatan kehamilan yang relevan.
                  Data ini membantu tenaga kesehatan memahami konteks pemantauan awal.
                </small>
              </label>
            </>
          )}

          {errorMessage && (
            <div className="auth-form__error" role="alert">
              {errorMessage}
            </div>
          )}

          <button className="auth-form__submit" type="submit" disabled={isSubmitting || isAuthLoading}>
            {isSubmitting || isAuthLoading ? 'Memproses...' : mode === 'login' ? config.submitLogin : 'Daftar & Buat Profil'}
          </button>
        </form>
      </section>
    </div>
  );
};

export default AuthScreen;
