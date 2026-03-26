import React, { useState } from 'react';
import { t } from '../../../i18n';
import './LoginScreen.css';

const LoginScreen = ({ onLogin, onRegister }) => {
    const [isLogin, setIsLogin] = useState(true);
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        name: '',
        phone: '',
        confirmPassword: ''
    });
    const [errors, setErrors] = useState({});
    const [isLoading, setIsLoading] = useState(false);

    const validateForm = () => {
        const newErrors = {};
        
        if (!formData.email) {
            newErrors.email = 'Email wajib diisi';
        } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
            newErrors.email = 'Format email tidak valid';
        }
        
        if (!formData.password) {
            newErrors.password = 'Password wajib diisi';
        } else if (formData.password.length < 6) {
            newErrors.password = 'Password minimal 6 karakter';
        }
        
        if (!isLogin) {
            if (!formData.name) {
                newErrors.name = 'Nama wajib diisi';
            }
            if (!formData.phone) {
                newErrors.phone = 'Nomor telepon wajib diisi';
            }
            if (formData.password !== formData.confirmPassword) {
                newErrors.confirmPassword = 'Password tidak cocok';
            }
        }
        
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!validateForm()) return;
        
        setIsLoading(true);
        
        // Simulate API call
        setTimeout(() => {
            setIsLoading(false);
            if (isLogin) {
                onLogin?.({
                    email: formData.email,
                    name: formData.name || 'Pengguna'
                });
            } else {
                onRegister?.({
                    email: formData.email,
                    name: formData.name,
                    phone: formData.phone
                });
            }
        }, 1500);
    };

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        // Clear error on change
        if (errors[name]) {
            setErrors(prev => ({ ...prev, [name]: '' }));
        }
    };

    return (
        <div className="login-screen">
            <div className="login-background">
                <div className="login-background__gradient" />
                <div className="login-background__pattern" />
            </div>

            <div className="login-container">
                {/* Logo & Branding */}
                <div className="login-header">
                    <div className="login-logo">
                        <svg viewBox="0 0 48 48" fill="none">
                            <defs>
                                <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                    <stop offset="0%" stopColor="#FF6B9A" />
                                    <stop offset="100%" stopColor="#4AA3FF" />
                                </linearGradient>
                            </defs>
                            <circle cx="24" cy="24" r="22" stroke="url(#logoGradient)" strokeWidth="3" fill="none" />
                            <path d="M24 12C24 12 16 18 16 26C16 30.4183 19.5817 34 24 34C28.4183 34 32 30.4183 32 26C32 18 24 12 24 12Z" 
                                fill="url(#logoGradient)" />
                            <circle cx="24" cy="24" r="4" fill="white" />
                        </svg>
                    </div>
                    <h1 className="login-title">FETAL-GUARD</h1>
                    <p className="login-subtitle">Sistem Monitoring Kesehatan Ibu & Janin</p>
                </div>

                {/* Form Container */}
                <div className="login-card">
                    {/* Tab Switcher */}
                    <div className="login-tabs">
                        <button 
                            className={`login-tab ${isLogin ? 'active' : ''}`}
                            onClick={() => setIsLogin(true)}
                        >
                            Masuk
                        </button>
                        <button 
                            className={`login-tab ${!isLogin ? 'active' : ''}`}
                            onClick={() => setIsLogin(false)}
                        >
                            Daftar
                        </button>
                    </div>

                    <form className="login-form" onSubmit={handleSubmit}>
                        {!isLogin && (
                            <div className="login-field">
                                <label className="login-label">Nama Lengkap</label>
                                <div className="login-input-wrapper">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                                        <circle cx="12" cy="7" r="4" />
                                    </svg>
                                    <input
                                        type="text"
                                        name="name"
                                        className={`login-input ${errors.name ? 'error' : ''}`}
                                        placeholder="Masukkan nama lengkap"
                                        value={formData.name}
                                        onChange={handleInputChange}
                                    />
                                </div>
                                {errors.name && <span className="login-error">{errors.name}</span>}
                            </div>
                        )}

                        <div className="login-field">
                            <label className="login-label">Email</label>
                            <div className="login-input-wrapper">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                                    <polyline points="22,6 12,13 2,6" />
                                </svg>
                                <input
                                    type="email"
                                    name="email"
                                    className={`login-input ${errors.email ? 'error' : ''}`}
                                    placeholder="contoh@email.com"
                                    value={formData.email}
                                    onChange={handleInputChange}
                                />
                            </div>
                            {errors.email && <span className="login-error">{errors.email}</span>}
                        </div>

                        {!isLogin && (
                            <div className="login-field">
                                <label className="login-label">Nomor Telepon</label>
                                <div className="login-input-wrapper">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                                    </svg>
                                    <input
                                        type="tel"
                                        name="phone"
                                        className={`login-input ${errors.phone ? 'error' : ''}`}
                                        placeholder="08xxxxxxxxxx"
                                        value={formData.phone}
                                        onChange={handleInputChange}
                                    />
                                </div>
                                {errors.phone && <span className="login-error">{errors.phone}</span>}
                            </div>
                        )}

                        <div className="login-field">
                            <label className="login-label">Password</label>
                            <div className="login-input-wrapper">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                                </svg>
                                <input
                                    type="password"
                                    name="password"
                                    className={`login-input ${errors.password ? 'error' : ''}`}
                                    placeholder="Minimal 6 karakter"
                                    value={formData.password}
                                    onChange={handleInputChange}
                                />
                            </div>
                            {errors.password && <span className="login-error">{errors.password}</span>}
                        </div>

                        {!isLogin && (
                            <div className="login-field">
                                <label className="login-label">Konfirmasi Password</label>
                                <div className="login-input-wrapper">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                                    </svg>
                                    <input
                                        type="password"
                                        name="confirmPassword"
                                        className={`login-input ${errors.confirmPassword ? 'error' : ''}`}
                                        placeholder="Ulangi password"
                                        value={formData.confirmPassword}
                                        onChange={handleInputChange}
                                    />
                                </div>
                                {errors.confirmPassword && <span className="login-error">{errors.confirmPassword}</span>}
                            </div>
                        )}

                        {isLogin && (
                            <button type="button" className="login-forgot">
                                Lupa Password?
                            </button>
                        )}

                        <button 
                            type="submit" 
                            className="login-submit"
                            disabled={isLoading}
                        >
                            {isLoading ? (
                                <span className="login-loading">
                                    <svg className="login-spinner" viewBox="0 0 24 24">
                                        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" fill="none" strokeDasharray="60" strokeLinecap="round" />
                                    </svg>
                                    Memproses...
                                </span>
                            ) : (
                                isLogin ? 'Masuk' : 'Daftar'
                            )}
                        </button>
                    </form>

                    {/* Social Login */}
                    <div className="login-divider">
                        <span>atau</span>
                    </div>

                    <div className="login-social">
                        <button className="login-social-btn login-social-btn--google">
                            <svg viewBox="0 0 24 24" width="20" height="20">
                                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                            </svg>
                            Google
                        </button>
                    </div>
                </div>

                {/* Footer */}
                <p className="login-footer">
                    Dengan masuk, Anda menyetujui <a href="#">Syarat & Ketentuan</a> dan <a href="#">Kebijakan Privasi</a>
                </p>
            </div>
        </div>
    );
};

export default LoginScreen;
