import React, { useEffect, useRef, useState } from 'react';
import { t } from '../../i18n';
import { getPatientPreferences } from '../../services/patientPreferences';
import { sharePatientLocation } from '../../services/nativePatientFeatures';
import './EmergencyButton.css';

const toDialPhone = (value) => String(value || '').replace(/[^\d+]/g, '');

const EmergencyButton = ({
    onEmergency,
    onCallClinic,
    onCallTrustedContact,
    clinicPhone,
    trustedContactPhone,
    patientUserId,
    emergencyPhone = '112',
    disabled = false,
    compact = false,
}) => {
    const [showConfirm, setShowConfirm] = useState(false);
    const [confirmStep, setConfirmStep] = useState(0);
    const [locationShareState, setLocationShareState] = useState('idle');
    const modalRef = useRef(null);
    const cancelButtonRef = useRef(null);
    const previousFocusRef = useRef(null);

    useEffect(() => {
        const openHelpOptions = () => {
            setShowConfirm(true);
            setConfirmStep(1);
        };

        window.addEventListener('fetalguard:open-emergency', openHelpOptions);
        return () => window.removeEventListener('fetalguard:open-emergency', openHelpOptions);
    }, []);

    useEffect(() => {
        if (!showConfirm) return undefined;

        previousFocusRef.current = document.activeElement;

        const handleKeyDown = (event) => {
            if (event.key === 'Escape') {
                setShowConfirm(false);
                setConfirmStep(0);
                return;
            }

            if (event.key !== 'Tab' || !modalRef.current) return;

            const focusableElements = modalRef.current.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            if (focusableElements.length === 0) return;

            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];

            if (event.shiftKey && document.activeElement === firstElement) {
                event.preventDefault();
                lastElement.focus();
            } else if (!event.shiftKey && document.activeElement === lastElement) {
                event.preventDefault();
                firstElement.focus();
            }
        };

        document.addEventListener('keydown', handleKeyDown);

        return () => {
            document.removeEventListener('keydown', handleKeyDown);
            previousFocusRef.current?.focus?.();
        };
    }, [showConfirm]);

    useEffect(() => {
        if (showConfirm) {
            cancelButtonRef.current?.focus();
        }
    }, [showConfirm, confirmStep]);

    const resetConfirm = () => {
        setShowConfirm(false);
        setConfirmStep(0);
        setLocationShareState('idle');
    };

    const handlePress = () => {
        setShowConfirm(true);
        setConfirmStep(1);
    };

    const handleConfirm = () => {
        if (confirmStep === 1) {
            setConfirmStep(2);
            return;
        }

        if (onEmergency) {
            onEmergency('emergency');
        }
        const phone = toDialPhone(emergencyPhone);
        if (phone) {
            window.location.href = `tel:${phone}`;
        }
        resetConfirm();
    };

    const handleCallClinic = () => {
        if (onCallClinic) {
            onCallClinic();
        }
        if (onEmergency) {
            onEmergency('clinic');
        }
        const phone = toDialPhone(clinicPhone);
        if (phone) {
            window.location.href = `tel:${phone}`;
        }
        resetConfirm();
    };

    const handleCallTrustedContact = () => {
        if (onCallTrustedContact) {
            onCallTrustedContact();
        }
        if (onEmergency) {
            onEmergency('trusted-contact');
        }
        const phone = toDialPhone(trustedContactPhone);
        if (phone) {
            window.location.href = `tel:${phone}`;
        }
        resetConfirm();
    };

    const canShareLocation = patientUserId
        && getPatientPreferences(patientUserId).shareLocation;

    const handleShareLocation = async () => {
        setLocationShareState('loading');
        try {
            const result = await sharePatientLocation({
                title: t('patient.emergency.locationShareTitle'),
                text: t('patient.emergency.locationShareText'),
            });
            setLocationShareState(result.shared ? 'shared' : result.copied ? 'copied' : 'ready');
        } catch (error) {
            if (error?.name === 'AbortError') {
                setLocationShareState('idle');
                return;
            }
            setLocationShareState('error');
        }
    };

    const titleId = `emergency-title-${confirmStep}`;
    const messageId = `emergency-message-${confirmStep}`;

    return (
        <>
            <button
                type="button"
                className={`emergency-button${compact ? ' emergency-button--compact' : ''}`}
                onClick={handlePress}
                disabled={disabled}
                aria-label={t('patient.emergency.buttonLabel')}
            >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="emergency-button__icon">
                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
                <span className="emergency-button__label">{t('patient.emergency.buttonText')}</span>
            </button>

            {showConfirm && (
                <div
                    className="emergency-overlay"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby={titleId}
                    aria-describedby={messageId}
                >
                    <div ref={modalRef} className="emergency-modal">
                        <div className="emergency-modal__icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                                <line x1="12" y1="9" x2="12" y2="13" />
                                <line x1="12" y1="17" x2="12.01" y2="17" />
                            </svg>
                        </div>

                        {confirmStep === 1 && (
                            <>
                                <h2 id={titleId} className="emergency-modal__title">
                                    {t('patient.emergency.confirmTitle')}
                                </h2>
                                <p id={messageId} className="emergency-modal__message">
                                    {t('patient.emergency.confirmMessage')}
                                </p>
                                <div className="emergency-modal__actions">
                                    <button
                                        ref={cancelButtonRef}
                                        type="button"
                                        className="emergency-modal__btn emergency-modal__btn--secondary"
                                        onClick={resetConfirm}
                                    >
                                        {t('patient.emergency.cancel')}
                                    </button>
                                    {clinicPhone && (
                                        <button
                                            type="button"
                                            className="emergency-modal__btn emergency-modal__btn--clinic"
                                            onClick={handleCallClinic}
                                        >
                                            {t('patient.emergency.callClinic')}
                                        </button>
                                    )}
                                    {trustedContactPhone && (
                                        <button
                                            type="button"
                                            className="emergency-modal__btn emergency-modal__btn--clinic"
                                            onClick={handleCallTrustedContact}
                                        >
                                            {t('patient.emergency.callTrustedContact')}
                                        </button>
                                    )}
                                    {canShareLocation && (
                                        <button
                                            type="button"
                                            className="emergency-modal__btn emergency-modal__btn--clinic"
                                            onClick={() => { void handleShareLocation(); }}
                                            disabled={locationShareState === 'loading'}
                                        >
                                            {locationShareState === 'loading'
                                                ? t('patient.emergency.locationSharing')
                                                : t('patient.emergency.shareLocation')}
                                        </button>
                                    )}
                                    <button
                                        type="button"
                                        className="emergency-modal__btn emergency-modal__btn--primary"
                                        onClick={handleConfirm}
                                    >
                                        {t('patient.emergency.continue')}
                                    </button>
                                </div>
                                {canShareLocation && locationShareState !== 'idle' && locationShareState !== 'loading' && (
                                    <p className={`emergency-modal__share-status emergency-modal__share-status--${locationShareState}`} role="status">
                                        {t(`patient.emergency.locationShareStatus.${locationShareState}`)}
                                    </p>
                                )}
                            </>
                        )}

                        {confirmStep === 2 && (
                            <>
                                <h2 id={titleId} className="emergency-modal__title">
                                    {t('patient.emergency.finalTitle')}
                                </h2>
                                <p id={messageId} className="emergency-modal__message emergency-modal__message--warning">
                                    {t('patient.emergency.finalMessage', { phone: emergencyPhone })}
                                </p>
                                <div className="emergency-modal__actions">
                                    <button
                                        ref={cancelButtonRef}
                                        type="button"
                                        className="emergency-modal__btn emergency-modal__btn--secondary"
                                        onClick={resetConfirm}
                                    >
                                        {t('patient.emergency.cancel')}
                                    </button>
                                    <button
                                        type="button"
                                        className="emergency-modal__btn emergency-modal__btn--emergency"
                                        onClick={handleConfirm}
                                    >
                                        {t('patient.emergency.callEmergency')}
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}
        </>
    );
};

export default EmergencyButton;
