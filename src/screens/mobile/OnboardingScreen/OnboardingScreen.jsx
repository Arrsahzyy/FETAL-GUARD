import React, { useState } from 'react';
import { t } from '../../../i18n';
import './OnboardingScreen.css';

const OnboardingScreen = ({ onComplete }) => {
    const [currentStep, setCurrentStep] = useState(0);
    const [formData, setFormData] = useState({
        name: '',
        patientId: '',
        lmpDate: '',
        birthDate: '',
        weight: '',
        height: '',
        medicalHistory: {
            diabetes: false,
            hypertension: false,
            heartDisease: false,
            preeclampsia: false,
            other: ''
        },
        emergencyContact: {
            name: '',
            relation: '',
            phone: ''
        },
        clinic: '',
        consent: false,
        consentTimestamp: null
    });

    const [permissions, setPermissions] = useState({
        bluetooth: false,
        notifications: false,
        location: false
    });

    const steps = [
        { id: 'welcome', title: t('onboarding.welcome') },
        { id: 'profile', title: 'Profil Pasien' },
        { id: 'medical', title: 'Riwayat Kesehatan' },
        { id: 'emergency', title: 'Kontak Darurat' },
        { id: 'setup', title: 'Panduan Pemasangan' },
        { id: 'permissions', title: t('onboarding.permissions.title') },
        { id: 'consent', title: t('onboarding.consent.title') }
    ];

    const calculateBMI = () => {
        if (formData.weight && formData.height) {
            const heightM = parseFloat(formData.height) / 100;
            const bmi = parseFloat(formData.weight) / (heightM * heightM);
            return bmi.toFixed(1);
        }
        return '-';
    };

    const calculateGestationalAge = () => {
        if (formData.lmpDate) {
            const lmp = new Date(formData.lmpDate);
            const today = new Date();
            const diff = today - lmp;
            const weeks = Math.floor(diff / (7 * 24 * 60 * 60 * 1000));
            const days = Math.floor((diff % (7 * 24 * 60 * 60 * 1000)) / (24 * 60 * 60 * 1000));
            return { weeks, days };
        }
        return null;
    };

    const handleInputChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleMedicalChange = (field, value) => {
        setFormData(prev => ({
            ...prev,
            medicalHistory: { ...prev.medicalHistory, [field]: value }
        }));
    };

    const handleEmergencyChange = (field, value) => {
        setFormData(prev => ({
            ...prev,
            emergencyContact: { ...prev.emergencyContact, [field]: value }
        }));
    };

    const handlePermission = (permission) => {
        setPermissions(prev => ({ ...prev, [permission]: true }));
    };

    const handleConsent = () => {
        setFormData(prev => ({
            ...prev,
            consent: true,
            consentTimestamp: new Date().toISOString()
        }));
    };

    const nextStep = () => {
        if (currentStep < steps.length - 1) {
            setCurrentStep(prev => prev + 1);
        } else {
            onComplete?.(formData);
        }
    };

    const prevStep = () => {
        if (currentStep > 0) {
            setCurrentStep(prev => prev - 1);
        }
    };

    const renderStep = () => {
        switch (steps[currentStep].id) {
            case 'welcome':
                return (
                    <div className="onboarding-welcome">
                        <div className="onboarding-logo">
                            <div className="onboarding-logo__icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                                </svg>
                            </div>
                            <h1>FETAL-GUARD</h1>
                        </div>
                        <h2>{t('onboarding.welcome')}</h2>
                        <p>{t('onboarding.subtitle')}</p>
                        <div className="onboarding-features">
                            <div className="onboarding-feature">
                                <span className="onboarding-feature__icon">📊</span>
                                <span>Pemantauan real-time</span>
                            </div>
                            <div className="onboarding-feature">
                                <span className="onboarding-feature__icon">🔔</span>
                                <span>Peringatan dini</span>
                            </div>
                            <div className="onboarding-feature">
                                <span className="onboarding-feature__icon">📱</span>
                                <span>Koneksi ke klinik</span>
                            </div>
                        </div>
                    </div>
                );

            case 'profile':
                return (
                    <div className="onboarding-form">
                        <div className="input-group">
                            <label className="input-label">{t('onboarding.form.name')} *</label>
                            <input
                                type="text"
                                className="input"
                                value={formData.name}
                                onChange={(e) => handleInputChange('name', e.target.value)}
                                placeholder="Masukkan nama lengkap"
                            />
                        </div>
                        <div className="input-group">
                            <label className="input-label">{t('onboarding.form.patientId')}</label>
                            <input
                                type="text"
                                className="input"
                                value={formData.patientId}
                                onChange={(e) => handleInputChange('patientId', e.target.value)}
                                placeholder="Opsional"
                            />
                        </div>
                        <div className="input-group">
                            <label className="input-label">{t('onboarding.form.lmpDate')} *</label>
                            <input
                                type="date"
                                className="input"
                                value={formData.lmpDate}
                                onChange={(e) => handleInputChange('lmpDate', e.target.value)}
                            />
                            {calculateGestationalAge() && (
                                <span className="input-helper">
                                    Usia Kehamilan: {calculateGestationalAge().weeks} minggu {calculateGestationalAge().days} hari
                                </span>
                            )}
                        </div>
                        <div className="input-group">
                            <label className="input-label">{t('onboarding.form.birthDate')}</label>
                            <input
                                type="date"
                                className="input"
                                value={formData.birthDate}
                                onChange={(e) => handleInputChange('birthDate', e.target.value)}
                            />
                        </div>
                        <div className="input-row">
                            <div className="input-group">
                                <label className="input-label">{t('onboarding.form.weight')}</label>
                                <input
                                    type="number"
                                    className="input"
                                    value={formData.weight}
                                    onChange={(e) => handleInputChange('weight', e.target.value)}
                                />
                            </div>
                            <div className="input-group">
                                <label className="input-label">{t('onboarding.form.height')}</label>
                                <input
                                    type="number"
                                    className="input"
                                    value={formData.height}
                                    onChange={(e) => handleInputChange('height', e.target.value)}
                                />
                            </div>
                            <div className="input-group">
                                <label className="input-label">{t('onboarding.form.bmi')}</label>
                                <div className="input input--readonly">{calculateBMI()}</div>
                            </div>
                        </div>
                    </div>
                );

            case 'medical':
                return (
                    <div className="onboarding-form">
                        <p className="onboarding-form__desc">Pilih jika Anda memiliki riwayat kondisi berikut:</p>
                        <div className="onboarding-checkboxes">
                            {['diabetes', 'hypertension', 'heartDisease', 'preeclampsia'].map((condition) => (
                                <label key={condition} className="checkbox-item">
                                    <input
                                        type="checkbox"
                                        checked={formData.medicalHistory[condition]}
                                        onChange={(e) => handleMedicalChange(condition, e.target.checked)}
                                    />
                                    <span className="checkbox-custom"></span>
                                    <span className="checkbox-label">{t(`onboarding.form.${condition}`)}</span>
                                </label>
                            ))}
                        </div>
                        <div className="input-group">
                            <label className="input-label">{t('onboarding.form.otherConditions')}</label>
                            <textarea
                                className="input input--textarea"
                                value={formData.medicalHistory.other}
                                onChange={(e) => handleMedicalChange('other', e.target.value)}
                                placeholder="Tuliskan kondisi lainnya..."
                                rows={3}
                            />
                        </div>
                    </div>
                );

            case 'emergency':
                return (
                    <div className="onboarding-form">
                        <h3>{t('onboarding.form.emergencyContact')}</h3>
                        <div className="input-group">
                            <label className="input-label">{t('onboarding.form.contactName')} *</label>
                            <input
                                type="text"
                                className="input"
                                value={formData.emergencyContact.name}
                                onChange={(e) => handleEmergencyChange('name', e.target.value)}
                            />
                        </div>
                        <div className="input-group">
                            <label className="input-label">{t('onboarding.form.contactRelation')}</label>
                            <select
                                className="input"
                                value={formData.emergencyContact.relation}
                                onChange={(e) => handleEmergencyChange('relation', e.target.value)}
                            >
                                <option value="">Pilih...</option>
                                <option value="spouse">Suami</option>
                                <option value="parent">Orang Tua</option>
                                <option value="sibling">Saudara</option>
                                <option value="other">Lainnya</option>
                            </select>
                        </div>
                        <div className="input-group">
                            <label className="input-label">{t('onboarding.form.contactPhone')} *</label>
                            <input
                                type="tel"
                                className="input"
                                value={formData.emergencyContact.phone}
                                onChange={(e) => handleEmergencyChange('phone', e.target.value)}
                                placeholder="+62..."
                            />
                        </div>
                        <div className="input-group">
                            <label className="input-label">{t('onboarding.form.clinicConnection')}</label>
                            <select
                                className="input"
                                value={formData.clinic}
                                onChange={(e) => handleInputChange('clinic', e.target.value)}
                            >
                                <option value="">{t('onboarding.form.selectClinic')}</option>
                                <option value="clinic1">RS Bunda Jakarta</option>
                                <option value="clinic2">Klinik Ibu & Anak Harapan</option>
                                <option value="clinic3">RSUD Tangerang</option>
                            </select>
                        </div>
                    </div>
                );

            case 'setup':
                return (
                    <div className="onboarding-setup">
                        <div className="setup-steps">
                            <div className="setup-step">
                                <div className="setup-step__number">1</div>
                                <div className="setup-step__content">
                                    <h4>{t('onboarding.step1Title')}</h4>
                                    <p>{t('onboarding.step1Desc')}</p>
                                    <div className="setup-step__illustration">
                                        <svg viewBox="0 0 200 120" fill="none">
                                            <ellipse cx="100" cy="60" rx="60" ry="45" stroke="var(--color-primary-pink)" strokeWidth="3" strokeDasharray="8 4" />
                                            <rect x="70" y="40" width="60" height="40" rx="8" fill="var(--color-primary-blue)" opacity="0.2" stroke="var(--color-primary-blue)" strokeWidth="2" />
                                            <circle cx="100" cy="60" r="8" fill="var(--color-primary-pink)" />
                                        </svg>
                                    </div>
                                </div>
                            </div>
                            <div className="setup-step">
                                <div className="setup-step__number">2</div>
                                <div className="setup-step__content">
                                    <h4>{t('onboarding.step2Title')}</h4>
                                    <p>{t('onboarding.step2Desc')}</p>
                                    <div className="setup-step__illustration">
                                        <svg viewBox="0 0 200 120" fill="none">
                                            <rect x="70" y="20" width="60" height="80" rx="12" fill="var(--color-bg-secondary)" stroke="var(--color-primary-blue)" strokeWidth="2" />
                                            <path d="M85 50 Q100 30 115 50" stroke="var(--color-primary-pink)" strokeWidth="2" fill="none" />
                                            <path d="M85 60 Q100 40 115 60" stroke="var(--color-primary-pink)" strokeWidth="2" fill="none" opacity="0.6" />
                                            <path d="M85 70 Q100 50 115 70" stroke="var(--color-primary-pink)" strokeWidth="2" fill="none" opacity="0.3" />
                                        </svg>
                                    </div>
                                </div>
                            </div>
                            <div className="setup-step">
                                <div className="setup-step__number">3</div>
                                <div className="setup-step__content">
                                    <h4>{t('onboarding.step3Title')}</h4>
                                    <p>{t('onboarding.step3Desc')}</p>
                                    <div className="setup-step__illustration">
                                        <svg viewBox="0 0 200 120" fill="none">
                                            <circle cx="100" cy="60" r="40" fill="var(--color-success-bg)" stroke="var(--color-success)" strokeWidth="2" />
                                            <path d="M80 60 L95 75 L120 45" stroke="var(--color-success)" strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                                        </svg>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <button className="setup-video-btn">
                            <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
                                <polygon points="5 3 19 12 5 21 5 3" />
                            </svg>
                            Tonton Video Panduan (30 detik)
                        </button>
                    </div>
                );

            case 'permissions':
                return (
                    <div className="onboarding-permissions">
                        <p className="onboarding-permissions__desc">
                            Izinkan FETAL-GUARD untuk mengakses fitur berikut agar dapat bekerja dengan optimal.
                        </p>
                        <div className="permissions-list">
                            <div className={`permission-item ${permissions.bluetooth ? 'permission-item--granted' : ''}`}>
                                <div className="permission-item__icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M6.5 6.5l11 11L12 23V1l5.5 5.5-11 11" />
                                    </svg>
                                </div>
                                <div className="permission-item__content">
                                    <h4>{t('onboarding.permissions.bluetooth')}</h4>
                                    <p>{t('onboarding.permissions.bluetoothDesc')}</p>
                                </div>
                                <button
                                    className="permission-item__btn"
                                    onClick={() => handlePermission('bluetooth')}
                                    disabled={permissions.bluetooth}
                                >
                                    {permissions.bluetooth ? '✓' : t('onboarding.permissions.allow')}
                                </button>
                            </div>

                            <div className={`permission-item ${permissions.notifications ? 'permission-item--granted' : ''}`}>
                                <div className="permission-item__icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                                        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                                    </svg>
                                </div>
                                <div className="permission-item__content">
                                    <h4>{t('onboarding.permissions.notifications')}</h4>
                                    <p>{t('onboarding.permissions.notificationsDesc')}</p>
                                </div>
                                <button
                                    className="permission-item__btn"
                                    onClick={() => handlePermission('notifications')}
                                    disabled={permissions.notifications}
                                >
                                    {permissions.notifications ? '✓' : t('onboarding.permissions.allow')}
                                </button>
                            </div>

                            <div className={`permission-item ${permissions.location ? 'permission-item--granted' : ''}`}>
                                <div className="permission-item__icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                                        <circle cx="12" cy="10" r="3" />
                                    </svg>
                                </div>
                                <div className="permission-item__content">
                                    <h4>{t('onboarding.permissions.location')}</h4>
                                    <p>{t('onboarding.permissions.locationDesc')}</p>
                                </div>
                                <button
                                    className="permission-item__btn permission-item__btn--optional"
                                    onClick={() => handlePermission('location')}
                                    disabled={permissions.location}
                                >
                                    {permissions.location ? '✓' : t('onboarding.permissions.allow')}
                                </button>
                            </div>
                        </div>
                    </div>
                );

            case 'consent':
                return (
                    <div className="onboarding-consent">
                        <div className="consent-icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                                <path d="M9 12l2 2 4-4" />
                            </svg>
                        </div>
                        <h3>{t('onboarding.consent.title')}</h3>
                        <div className="consent-text">
                            <p>{t('onboarding.consent.text')}</p>
                            <button className="consent-read-more">{t('onboarding.consent.readMore')} →</button>
                        </div>
                        <label className="consent-toggle">
                            <div
                                className={`toggle ${formData.consent ? 'active' : ''}`}
                                onClick={handleConsent}
                            ></div>
                            <span>{t('onboarding.consent.agree')}</span>
                        </label>
                        {formData.consentTimestamp && (
                            <p className="consent-timestamp">
                                {t('onboarding.consent.timestamp')}: {new Date(formData.consentTimestamp).toLocaleString('id-ID')}
                            </p>
                        )}
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="onboarding-screen">
            {/* Progress */}
            <div className="onboarding-progress">
                <div className="onboarding-progress__bar">
                    <div
                        className="onboarding-progress__fill"
                        style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
                    />
                </div>
                <span className="onboarding-progress__text">
                    {currentStep + 1} / {steps.length}
                </span>
            </div>

            {/* Content */}
            <div className="onboarding-content">
                {renderStep()}
            </div>

            {/* Navigation */}
            <div className="onboarding-nav">
                {currentStep > 0 && (
                    <button className="onboarding-nav__btn onboarding-nav__btn--back" onClick={prevStep}>
                        {t('onboarding.back')}
                    </button>
                )}
                <button
                    className="onboarding-nav__btn onboarding-nav__btn--next btn btn-primary"
                    onClick={nextStep}
                    disabled={currentStep === steps.length - 1 && !formData.consent}
                >
                    {currentStep === steps.length - 1 ? t('onboarding.finish') : t('onboarding.next')}
                </button>
            </div>
        </div>
    );
};

export default OnboardingScreen;
