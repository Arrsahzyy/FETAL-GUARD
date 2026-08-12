import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FeedbackModal from '../../../components/FeedbackModal/FeedbackModal';
import Icon from '../../../components/Icon/Icon';
import { useAuth } from '../../../context/useAuth';
import { t } from '../../../i18n';
import { useI18n } from '../../../i18n/useI18n';
import './ProfileScreen.css';

const parseWeekValue = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
};

const optionalText = (value) => value?.trim() || null;
const optionalNumber = (value) => {
    if (value === '' || value === null || value === undefined) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
};

const createFormError = (message, field, tab) => {
    const error = new Error(message);
    error.field = field;
    error.tab = tab;
    return error;
};

const ProfileScreen = ({ onSave, patientData, initialData }) => {
    const navigate = useNavigate();
    const { user, updatePatientProfile } = useAuth();
    useI18n();
    const backendProfile = user?.patientProfile;
    const today = new Date().toISOString().slice(0, 10);
    // Support both prop names for flexibility
    const data = patientData || initialData || {};
    
    const [activeTab, setActiveTab] = useState('biodata');
    const [formData, setFormData] = useState({
        // Biodata
        fullName: data?.fullName || backendProfile?.name || '',
        nik: data?.nik || backendProfile?.national_id || '',
        birthDate: data?.birthDate || backendProfile?.birth_date || '',
        bloodType: data?.bloodType || backendProfile?.blood_type || '',
        address: data?.address || backendProfile?.address || '',
        phone: data?.phone || backendProfile?.phone_number || '',
        emergencyContact: data?.emergencyContact || backendProfile?.emergency_contact_name || '',
        emergencyPhone: data?.emergencyPhone || backendProfile?.emergency_contact_phone || '',
        
        // Medical Records
        pregnancyWeek: data?.pregnancyWeek || backendProfile?.gestational_age_weeks || '',
        expectedDueDate: data?.expectedDueDate || backendProfile?.estimated_due_date || '',
        lastMenstrualDate: data?.lastMenstrualDate || backendProfile?.last_menstrual_period || '',
        gravida: data?.gravida ?? backendProfile?.gravida ?? '1',
        para: data?.para ?? backendProfile?.para ?? '0',
        abortus: data?.abortus ?? backendProfile?.abortus ?? '0',
        height: data?.height ?? backendProfile?.height_cm ?? '',
        weightBeforePregnancy: data?.weightBeforePregnancy ?? backendProfile?.pre_pregnancy_weight_kg ?? '',
        currentWeight: data?.currentWeight ?? backendProfile?.current_weight_kg ?? '',
        
        // Medical History
        hasHypertension: data?.hasHypertension ?? backendProfile?.has_hypertension ?? false,
        hasDiabetes: data?.hasDiabetes ?? backendProfile?.has_diabetes ?? false,
        hasHeartDisease: data?.hasHeartDisease ?? backendProfile?.has_heart_condition ?? false,
        hasAsthma: data?.hasAsthma ?? backendProfile?.has_asthma ?? false,
        hasAllergies: data?.hasAllergies ?? backendProfile?.has_allergies ?? false,
        allergiesDetail: data?.allergiesDetail || backendProfile?.allergy_details || '',
        otherConditions: data?.otherConditions || backendProfile?.medical_history || '',
        currentMedications: data?.currentMedications || backendProfile?.current_medications || '',
        
        // Pregnancy History
        previousComplications: data?.previousComplications || backendProfile?.previous_pregnancy_complications || '',
        previousDeliveryType: data?.previousDeliveryType || backendProfile?.previous_delivery_type || '',
    });

    const [isSaving, setIsSaving] = useState(false);
    const [formError, setFormError] = useState(null);
    const [modalConfig, setModalConfig] = useState({ isOpen: false });

    const openModal = (config) => setModalConfig({ ...config, isOpen: true });
    const closeModal = () => setModalConfig(prev => ({ ...prev, isOpen: false }));

    const handleInputChange = (e) => {
        const { name, value, type, checked } = e.target;
        if (formError?.field === name) setFormError(null);
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    const saveProfile = async () => {
        setIsSaving(true);
        setFormError(null);

        try {
            const pregnancyWeek = parseWeekValue(formData.pregnancyWeek || calculatePregnancyWeek());
            const name = formData.fullName.trim();

            if (!name) {
                throw createFormError(t('patient.profile.nameRequired'), 'fullName', 'biodata');
            }

            if (!pregnancyWeek || pregnancyWeek < 1 || pregnancyWeek > 42) {
                throw createFormError(t('patient.profile.weekInvalid'), 'pregnancyWeek', 'pregnancy');
            }
            if (formData.nik && !/^\d{16}$/.test(formData.nik.trim())) {
                throw createFormError(t('patient.profile.nikInvalid'), 'nik', 'biodata');
            }
            const gravida = optionalNumber(formData.gravida);
            const para = optionalNumber(formData.para);
            const abortus = optionalNumber(formData.abortus);
            if (gravida !== null && (para || 0) + (abortus || 0) > gravida) {
                throw createFormError(t('patient.profile.obstetricInvalid'), 'gravida', 'pregnancy');
            }

            const updatedProfile = await updatePatientProfile({
                name,
                gestational_age_weeks: pregnancyWeek,
                medical_history: optionalText(formData.otherConditions),
                national_id: optionalText(formData.nik),
                birth_date: optionalText(formData.birthDate),
                blood_type: optionalText(formData.bloodType),
                address: optionalText(formData.address),
                phone_number: optionalText(formData.phone),
                emergency_contact_name: optionalText(formData.emergencyContact),
                emergency_contact_phone: optionalText(formData.emergencyPhone),
                last_menstrual_period: optionalText(formData.lastMenstrualDate),
                estimated_due_date: optionalText(formData.expectedDueDate || calculateDueDate()),
                gravida,
                para,
                abortus,
                height_cm: optionalNumber(formData.height),
                pre_pregnancy_weight_kg: optionalNumber(formData.weightBeforePregnancy),
                current_weight_kg: optionalNumber(formData.currentWeight),
                previous_delivery_type: optionalText(formData.previousDeliveryType),
                previous_pregnancy_complications: optionalText(formData.previousComplications),
                has_hypertension: formData.hasHypertension,
                has_diabetes: formData.hasDiabetes,
                has_heart_condition: formData.hasHeartDisease,
                has_asthma: formData.hasAsthma,
                has_allergies: formData.hasAllergies,
                allergy_details: formData.hasAllergies ? optionalText(formData.allergiesDetail) : null,
                current_medications: optionalText(formData.currentMedications),
            });

            onSave?.(updatedProfile);
            openModal({
                title: t('patient.profile.successTitle'),
                message: t('patient.profile.successMessage'),
                type: 'success',
                confirmText: t('onboarding.finish')
            });
        } catch (error) {
            if (error.field) {
                setFormError({ message: error.message, field: error.field });
                setActiveTab(error.tab);
                window.requestAnimationFrame(() => {
                    document.querySelector(`[name="${error.field}"]`)?.focus();
                });
                return;
            }
            openModal({
                title: t('patient.profile.errorTitle'),
                message: error.message || t('patient.profile.errorMessage'),
                type: 'error',
                confirmText: t('common.close')
            });
        } finally {
            setIsSaving(false);
        }
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        void saveProfile();
    };

    const calculatePregnancyWeek = () => {
        if (!formData.lastMenstrualDate) return '';
        const lmp = new Date(formData.lastMenstrualDate);
        const today = new Date();
        const diffTime = today - lmp;
        if (Number.isNaN(lmp.getTime()) || diffTime < 0) return '';
        const diffWeeks = Math.floor(diffTime / (1000 * 60 * 60 * 24 * 7));
        return diffWeeks;
    };

    const calculateDueDate = () => {
        if (!formData.lastMenstrualDate) return '';
        const lmp = new Date(formData.lastMenstrualDate);
        if (Number.isNaN(lmp.getTime())) return '';
        const dueDate = new Date(lmp);
        dueDate.setDate(dueDate.getDate() + 280); // 40 weeks
        return dueDate.toISOString().split('T')[0];
    };

    return (
        <div className="profile-screen">
            {/* Header */}
            <header className="profile-header">
                <button
                    type="button"
                    className="profile-header__back"
                    onClick={() => navigate('/patient/home')}
                    aria-label={t('common.back')}
                >
                    <Icon className="material-symbols-outlined" name="arrow_back" />
                </button>
                <h1>{t('patient.profile.title')}</h1>
                <span className="profile-header__spacer" aria-hidden="true" />
            </header>

            {/* Tabs */}
            <div className="profile-tabs" role="tablist" aria-label={t('patient.profile.title')}>
                <button
                    id="profile-tab-biodata"
                    type="button"
                    role="tab"
                    className={`profile-tab ${activeTab === 'biodata' ? 'active' : ''}`}
                    onClick={() => setActiveTab('biodata')}
                    aria-selected={activeTab === 'biodata'}
                    aria-controls="profile-panel-biodata"
                >
                    <Icon className="material-symbols-outlined" name="person" />
                    {t('patient.profile.biodata')}
                </button>
                <button
                    id="profile-tab-pregnancy"
                    type="button"
                    role="tab"
                    className={`profile-tab ${activeTab === 'pregnancy' ? 'active' : ''}`}
                    onClick={() => setActiveTab('pregnancy')}
                    aria-selected={activeTab === 'pregnancy'}
                    aria-controls="profile-panel-pregnancy"
                >
                    <Icon className="material-symbols-outlined" name="pregnant_woman" />
                    {t('patient.profile.pregnancy')}
                </button>
                <button
                    id="profile-tab-medical"
                    type="button"
                    role="tab"
                    className={`profile-tab ${activeTab === 'medical' ? 'active' : ''}`}
                    onClick={() => setActiveTab('medical')}
                    aria-selected={activeTab === 'medical'}
                    aria-controls="profile-panel-medical"
                >
                    <Icon className="material-symbols-outlined" name="medical_information" />
                    {t('patient.profile.medicalHistory')}
                </button>
            </div>

            <form className="profile-form" onSubmit={handleSubmit}>
                <div className="profile-scope-note" role="note">
                    {t('patient.profile.scopeNote')}
                </div>

                {formError && (
                    <div className="profile-form-error" id="profile-form-error" role="alert">
                        <Icon className="material-symbols-outlined" name="error" />
                        <p>
                            <strong>{t('patient.profile.formErrorTitle')}</strong>
                            {formError.message}
                        </p>
                    </div>
                )}

                {/* Biodata Tab */}
                {activeTab === 'biodata' && (
                    <div
                        className="profile-sections"
                        id="profile-panel-biodata"
                        role="tabpanel"
                        aria-labelledby="profile-tab-biodata"
                    >
                        <section className="profile-section" aria-labelledby="profile-personal-data-title">
                        <h2 className="profile-section__title" id="profile-personal-data-title">
                            {t('patient.profile.personalData')}
                        </h2>
                        
                        <div className="profile-field">
                            <label htmlFor="fullName">{t('patient.profile.fullName')}</label>
                            <input
                                id="fullName"
                                type="text"
                                name="fullName"
                                value={formData.fullName}
                                onChange={handleInputChange}
                                placeholder={t('patient.profile.fullNamePlaceholder')}
                                maxLength="255"
                                required
                                aria-invalid={formError?.field === 'fullName'}
                                aria-describedby={formError?.field === 'fullName' ? 'profile-form-error' : undefined}
                            />
                        </div>

                        <div className="profile-field">
                            <label htmlFor="nik">{t('patient.profile.nik')}</label>
                            <input
                                id="nik"
                                type="text"
                                name="nik"
                                value={formData.nik}
                                onChange={handleInputChange}
                                placeholder={t('patient.profile.nikPlaceholder')}
                                maxLength="16"
                                inputMode="numeric"
                                pattern="[0-9]{16}"
                                aria-invalid={formError?.field === 'nik'}
                                aria-describedby={formError?.field === 'nik' ? 'profile-form-error nik-hint' : 'nik-hint'}
                            />
                            <span className="profile-field__hint" id="nik-hint">{t('patient.profile.nikHint')}</span>
                        </div>

                        <div className="profile-row">
                            <div className="profile-field">
                                <label htmlFor="birthDate">{t('onboarding.form.birthDate')}</label>
                                <input
                                    id="birthDate"
                                    type="date"
                                    name="birthDate"
                                    value={formData.birthDate}
                                    onChange={handleInputChange}
                                    max={today}
                                />
                            </div>
                            <div className="profile-field">
                                <label htmlFor="bloodType">{t('patient.profile.bloodType')}</label>
                                <select
                                    id="bloodType"
                                    name="bloodType"
                                    value={formData.bloodType}
                                    onChange={handleInputChange}
                                >
                                    <option value="">{t('patient.profile.select')}</option>
                                    <option value="A+">A+</option>
                                    <option value="A-">A-</option>
                                    <option value="B+">B+</option>
                                    <option value="B-">B-</option>
                                    <option value="AB+">AB+</option>
                                    <option value="AB-">AB-</option>
                                    <option value="O+">O+</option>
                                    <option value="O-">O-</option>
                                </select>
                            </div>
                        </div>

                        <div className="profile-field">
                            <label htmlFor="address">{t('patient.profile.address')}</label>
                            <textarea
                                id="address"
                                name="address"
                                value={formData.address}
                                onChange={handleInputChange}
                                placeholder={t('patient.profile.addressPlaceholder')}
                                rows="3"
                                maxLength="1000"
                            />
                        </div>

                        <div className="profile-field">
                            <label htmlFor="phone">{t('patient.profile.phone')}</label>
                            <input
                                id="phone"
                                type="tel"
                                name="phone"
                                value={formData.phone}
                                onChange={handleInputChange}
                                placeholder={t('patient.profile.phonePlaceholder')}
                                maxLength="24"
                            />
                        </div>

                        </section>

                        <section className="profile-section" aria-labelledby="profile-emergency-contact-title">
                        <h2 className="profile-section__title" id="profile-emergency-contact-title">
                            {t('patient.profile.emergencyContact')}
                        </h2>

                        <div className="profile-field">
                            <label htmlFor="emergencyContact">{t('patient.profile.emergencyContactName')}</label>
                            <input
                                id="emergencyContact"
                                type="text"
                                name="emergencyContact"
                                value={formData.emergencyContact}
                                onChange={handleInputChange}
                                placeholder={t('patient.profile.emergencyContactPlaceholder')}
                                maxLength="255"
                            />
                        </div>

                        <div className="profile-field">
                            <label htmlFor="emergencyPhone">{t('patient.profile.emergencyPhone')}</label>
                            <input
                                id="emergencyPhone"
                                type="tel"
                                name="emergencyPhone"
                                value={formData.emergencyPhone}
                                onChange={handleInputChange}
                                placeholder={t('patient.profile.emergencyPhonePlaceholder')}
                                maxLength="24"
                            />
                        </div>
                        </section>
                    </div>
                )}

                {/* Pregnancy Tab */}
                {activeTab === 'pregnancy' && (
                    <div
                        className="profile-sections"
                        id="profile-panel-pregnancy"
                        role="tabpanel"
                        aria-labelledby="profile-tab-pregnancy"
                    >
                        <section className="profile-section" aria-labelledby="profile-pregnancy-data-title">
                        <h2 className="profile-section__title" id="profile-pregnancy-data-title">
                            {t('patient.profile.pregnancyData')}
                        </h2>

                        <div className="profile-field">
                            <label htmlFor="lastMenstrualDate">{t('patient.profile.lmp')}</label>
                            <input
                                id="lastMenstrualDate"
                                type="date"
                                name="lastMenstrualDate"
                                value={formData.lastMenstrualDate}
                                onChange={handleInputChange}
                                max={today}
                            />
                        </div>

                        <div className="profile-row">
                            <div className="profile-field">
                                <label htmlFor="pregnancyWeek">{t('patient.profile.pregnancyWeek')}</label>
                                <input
                                    id="pregnancyWeek"
                                    type="number"
                                    name="pregnancyWeek"
                                    value={formData.pregnancyWeek || calculatePregnancyWeek()}
                                    onChange={handleInputChange}
                                    placeholder={t('patient.profile.pregnancyWeekHint')}
                                    min="1"
                                    max="42"
                                    aria-invalid={formError?.field === 'pregnancyWeek'}
                                    aria-describedby={formError?.field === 'pregnancyWeek' ? 'profile-form-error pregnancy-week-hint' : 'pregnancy-week-hint'}
                                />
                                <span className="profile-field__hint" id="pregnancy-week-hint">
                                    {t('patient.profile.pregnancyWeekHint')}
                                </span>
                            </div>
                            <div className="profile-field">
                                <label htmlFor="expectedDueDate">{t('patient.profile.dueDate')}</label>
                                <input
                                    id="expectedDueDate"
                                    type="date"
                                    name="expectedDueDate"
                                    value={formData.expectedDueDate || calculateDueDate()}
                                    onChange={handleInputChange}
                                />
                            </div>
                        </div>

                        </section>

                        <section className="profile-section" aria-labelledby="profile-obstetric-status-title">
                        <h2 className="profile-section__title" id="profile-obstetric-status-title">
                            {t('patient.profile.obstetricStatus')}
                        </h2>
                        <div className="profile-row profile-row--three">
                            <div className="profile-field">
                                <label htmlFor="gravida">{t('patient.profile.gravida')}</label>
                                <input
                                    id="gravida"
                                    type="number"
                                    name="gravida"
                                    value={formData.gravida}
                                    onChange={handleInputChange}
                                    placeholder={t('patient.profile.gravidaHint')}
                                    min="1"
                                    max="20"
                                    aria-invalid={formError?.field === 'gravida'}
                                    aria-describedby={formError?.field === 'gravida' ? 'profile-form-error gravida-hint' : 'gravida-hint'}
                                />
                                <span className="profile-field__hint" id="gravida-hint">{t('patient.profile.gravidaHint')}</span>
                            </div>
                            <div className="profile-field">
                                <label htmlFor="para">{t('patient.profile.para')}</label>
                                <input
                                    id="para"
                                    type="number"
                                    name="para"
                                    value={formData.para}
                                    onChange={handleInputChange}
                                    placeholder="0"
                                    min="0"
                                    max="20"
                                    aria-describedby="para-hint"
                                />
                                <span className="profile-field__hint" id="para-hint">{t('patient.profile.paraHint')}</span>
                            </div>
                            <div className="profile-field">
                                <label htmlFor="abortus">{t('patient.profile.abortus')}</label>
                                <input
                                    id="abortus"
                                    type="number"
                                    name="abortus"
                                    value={formData.abortus}
                                    onChange={handleInputChange}
                                    placeholder="0"
                                    min="0"
                                    max="20"
                                    aria-describedby="abortus-hint"
                                />
                                <span className="profile-field__hint" id="abortus-hint">{t('patient.profile.abortusHint')}</span>
                            </div>
                        </div>

                        </section>

                        <section className="profile-section" aria-labelledby="profile-physical-data-title">
                        <h2 className="profile-section__title" id="profile-physical-data-title">
                            {t('patient.profile.physicalData')}
                        </h2>
                        <div className="profile-row profile-row--three">
                            <div className="profile-field">
                                <label htmlFor="height">{t('patient.profile.height')}</label>
                                <input
                                    id="height"
                                    type="number"
                                    name="height"
                                    value={formData.height}
                                    onChange={handleInputChange}
                                    placeholder="160"
                                    min="100"
                                    max="220"
                                    step="0.1"
                                />
                            </div>
                            <div className="profile-field">
                                <label htmlFor="weightBeforePregnancy">{t('patient.profile.weightBefore')}</label>
                                <input
                                    id="weightBeforePregnancy"
                                    type="number"
                                    name="weightBeforePregnancy"
                                    value={formData.weightBeforePregnancy}
                                    onChange={handleInputChange}
                                    placeholder="55"
                                    min="20"
                                    max="300"
                                    step="0.1"
                                />
                            </div>
                            <div className="profile-field">
                                <label htmlFor="currentWeight">{t('patient.profile.weightCurrent')}</label>
                                <input
                                    id="currentWeight"
                                    type="number"
                                    name="currentWeight"
                                    value={formData.currentWeight}
                                    onChange={handleInputChange}
                                    placeholder="60"
                                    min="20"
                                    max="350"
                                    step="0.1"
                                />
                            </div>
                        </div>

                        </section>

                        {formData.para > 0 && (
                            <section className="profile-section" aria-labelledby="profile-previous-pregnancy-title">
                                <h2 className="profile-section__title" id="profile-previous-pregnancy-title">
                                    {t('patient.profile.previousPregnancy')}
                                </h2>
                                <div className="profile-field">
                                    <label htmlFor="previousDeliveryType">{t('patient.profile.previousDelivery')}</label>
                                    <select
                                        id="previousDeliveryType"
                                        name="previousDeliveryType"
                                        value={formData.previousDeliveryType}
                                        onChange={handleInputChange}
                                    >
                                        <option value="">{t('patient.profile.select')}</option>
                                        <option value="normal">{t('patient.profile.deliveryNormal')}</option>
                                        <option value="cesarean">{t('patient.profile.deliveryCesarean')}</option>
                                        <option value="vacuum">{t('patient.profile.deliveryVacuum')}</option>
                                        <option value="forceps">{t('patient.profile.deliveryForceps')}</option>
                                    </select>
                                </div>
                                <div className="profile-field">
                                    <label htmlFor="previousComplications">{t('patient.profile.previousComplications')}</label>
                                    <textarea
                                        id="previousComplications"
                                        name="previousComplications"
                                        value={formData.previousComplications}
                                        onChange={handleInputChange}
                                        placeholder={t('patient.profile.previousComplicationsPlaceholder')}
                                        rows="3"
                                        maxLength="2000"
                                    />
                                </div>
                            </section>
                        )}
                    </div>
                )}

                {/* Health History Tab */}
                {activeTab === 'medical' && (
                    <div
                        className="profile-sections"
                        id="profile-panel-medical"
                        role="tabpanel"
                        aria-labelledby="profile-tab-medical"
                    >
                        <section className="profile-section" aria-labelledby="profile-medical-history-title">
                        <h2 className="profile-section__title" id="profile-medical-history-title">
                            {t('patient.profile.medicalHistory')}
                        </h2>
                        
                        <div className="profile-checklist">
                            <label className="profile-checkbox">
                                <input
                                    type="checkbox"
                                    name="hasHypertension"
                                    checked={formData.hasHypertension}
                                    onChange={handleInputChange}
                                />
                                <span className="profile-checkbox__mark"></span>
                                <span className="profile-checkbox__label">{t('patient.profile.hypertension')}</span>
                            </label>

                            <label className="profile-checkbox">
                                <input
                                    type="checkbox"
                                    name="hasDiabetes"
                                    checked={formData.hasDiabetes}
                                    onChange={handleInputChange}
                                />
                                <span className="profile-checkbox__mark"></span>
                                <span className="profile-checkbox__label">{t('patient.profile.diabetes')}</span>
                            </label>

                            <label className="profile-checkbox">
                                <input
                                    type="checkbox"
                                    name="hasHeartDisease"
                                    checked={formData.hasHeartDisease}
                                    onChange={handleInputChange}
                                />
                                <span className="profile-checkbox__mark"></span>
                                <span className="profile-checkbox__label">{t('patient.profile.heartDisease')}</span>
                            </label>

                            <label className="profile-checkbox">
                                <input
                                    type="checkbox"
                                    name="hasAsthma"
                                    checked={formData.hasAsthma}
                                    onChange={handleInputChange}
                                />
                                <span className="profile-checkbox__mark"></span>
                                <span className="profile-checkbox__label">{t('patient.profile.asthma')}</span>
                            </label>

                            <label className="profile-checkbox">
                                <input
                                    type="checkbox"
                                    name="hasAllergies"
                                    checked={formData.hasAllergies}
                                    onChange={handleInputChange}
                                />
                                <span className="profile-checkbox__mark"></span>
                                <span className="profile-checkbox__label">{t('patient.profile.allergy')}</span>
                            </label>
                        </div>

                        {formData.hasAllergies && (
                            <div className="profile-field">
                                <label htmlFor="allergiesDetail">{t('patient.profile.allergyDetail')}</label>
                                <textarea
                                    id="allergiesDetail"
                                    name="allergiesDetail"
                                    value={formData.allergiesDetail}
                                    onChange={handleInputChange}
                                    placeholder={t('patient.profile.allergyPlaceholder')}
                                    rows="2"
                                    maxLength="1000"
                                />
                            </div>
                        )}

                        <div className="profile-field">
                            <label htmlFor="otherConditions">{t('patient.profile.otherConditions')}</label>
                            <textarea
                                id="otherConditions"
                                name="otherConditions"
                                value={formData.otherConditions}
                                onChange={handleInputChange}
                                placeholder={t('patient.profile.otherConditionsPlaceholder')}
                                rows="3"
                                maxLength="2000"
                            />
                        </div>

                        </section>

                        <section className="profile-section" aria-labelledby="profile-medications-title">
                        <h2 className="profile-section__title" id="profile-medications-title">
                            {t('patient.profile.medications')}
                        </h2>
                        <div className="profile-field">
                            <label htmlFor="currentMedications">{t('patient.profile.currentMedications')}</label>
                            <textarea
                                id="currentMedications"
                                name="currentMedications"
                                value={formData.currentMedications}
                                onChange={handleInputChange}
                                placeholder={t('patient.profile.currentMedicationsPlaceholder')}
                                rows="3"
                                maxLength="2000"
                            />
                        </div>

                        <div className="profile-info-card">
                            <Icon className="material-symbols-outlined" name="info" />
                            <p>{t('patient.profile.infoCard')}</p>
                        </div>
                        </section>
                    </div>
                )}

                {/* Save the profile fields shown across all tabs. */}
                <div className="profile-actions">
                    <button 
                        type="submit" 
                        className="profile-save-btn"
                        disabled={isSaving}
                    >
                        {isSaving ? (
                            <>
                                <Icon className="material-symbols-outlined" name="autorenew" />
                                {t('patient.profile.saving')}
                            </>
                        ) : (
                            <>
                                <Icon className="material-symbols-outlined" name="save" />
                                {t('patient.profile.saveChanges')}
                            </>
                        )}
                    </button>
                </div>
            </form>
            <FeedbackModal {...modalConfig} onClose={closeModal} />
        </div>
    );
};

export default ProfileScreen;
