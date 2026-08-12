import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import BrandLogo from '../BrandLogo/BrandLogo';
import './PasswordResetScreen.css';

const ROLE_HOME_PATHS = {
  admin: '/admin',
  clinician: '/clinician/dashboard',
  patient: '/patient/home',
};

const INITIAL_FORM = {
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
};

const PasswordResetScreen = () => {
  const navigate = useNavigate();
  const { user, changePassword, logout, authError } = useAuth();
  const [form, setForm] = useState(INITIAL_FORM);
  const [submitError, setSubmitError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const roleLabel = useMemo(() => {
    if (user?.role === 'admin') return 'admin';
    if (user?.role === 'clinician') return 'nakes';
    return 'pasien';
  }, [user?.role]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitError('');

    if (form.newPassword !== form.confirmPassword) {
      setSubmitError('Konfirmasi password baru belum sama.');
      return;
    }

    setIsSubmitting(true);
    try {
      const updatedUser = await changePassword({
        currentPassword: form.currentPassword,
        newPassword: form.newPassword,
      });
      setForm(INITIAL_FORM);
      navigate(ROLE_HOME_PATHS[updatedUser.role] || '/', { replace: true });
    } catch (error) {
      setSubmitError(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const errorMessage = submitError || authError;

  return (
    <main className="password-reset-screen">
      <section className="password-reset-panel" aria-label="Ganti password awal">
        <div className="password-reset-panel__header">
          <BrandLogo variant="auth" />
          <span>Akses {roleLabel}</span>
          <h1>Ganti password awal</h1>
          <p>
            Akun ini memakai kredensial sementara. Buat password baru sebelum masuk ke
            dashboard agar akses tidak bergantung pada password yang dibagikan admin.
          </p>
        </div>

        <form className="password-reset-form" onSubmit={handleSubmit}>
          <label className="password-reset-form__field">
            <span>Password sementara</span>
            <input
              name="currentPassword"
              type="password"
              value={form.currentPassword}
              onChange={handleChange}
              autoComplete="current-password"
              minLength={8}
              required
            />
          </label>

          <label className="password-reset-form__field">
            <span>Password baru</span>
            <input
              name="newPassword"
              type="password"
              value={form.newPassword}
              onChange={handleChange}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>

          <label className="password-reset-form__field">
            <span>Konfirmasi password baru</span>
            <input
              name="confirmPassword"
              type="password"
              value={form.confirmPassword}
              onChange={handleChange}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>

          {errorMessage && (
            <div className="password-reset-form__error" role="alert">
              {errorMessage}
            </div>
          )}

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Menyimpan...' : 'Simpan password baru'}
          </button>
          <button type="button" className="password-reset-form__logout" onClick={logout}>
            Keluar
          </button>
        </form>
      </section>
    </main>
  );
};

export default PasswordResetScreen;
