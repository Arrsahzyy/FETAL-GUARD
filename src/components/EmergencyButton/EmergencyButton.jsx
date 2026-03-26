import React, { useState } from 'react';
import './EmergencyButton.css';

const EmergencyButton = ({
    onEmergency,
    onCallClinic,
    clinicPhone,
    emergencyPhone = '112',
    disabled = false
}) => {
    const [showConfirm, setShowConfirm] = useState(false);
    const [confirmStep, setConfirmStep] = useState(0);

    const handlePress = () => {
        setShowConfirm(true);
        setConfirmStep(1);
    };

    const handleConfirm = () => {
        if (confirmStep === 1) {
            setConfirmStep(2);
        } else if (confirmStep === 2) {
            if (onEmergency) {
                onEmergency();
            }
            // Auto-call emergency after confirmation
            if (emergencyPhone) {
                window.location.href = `tel:${emergencyPhone}`;
            }
            setShowConfirm(false);
            setConfirmStep(0);
        }
    };

    const handleCallClinic = () => {
        if (onCallClinic) {
            onCallClinic();
        }
        if (clinicPhone) {
            window.location.href = `tel:${clinicPhone}`;
        }
        setShowConfirm(false);
        setConfirmStep(0);
    };

    const handleCancel = () => {
        setShowConfirm(false);
        setConfirmStep(0);
    };

    return (
        <>
            <button
                className="emergency-button"
                onClick={handlePress}
                disabled={disabled}
                aria-label="Tombol Darurat"
            >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="emergency-button__icon">
                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
                <span className="emergency-button__label">DARURAT</span>
            </button>

            {showConfirm && (
                <div className="emergency-overlay" role="dialog" aria-modal="true">
                    <div className="emergency-modal">
                        <div className="emergency-modal__icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                                <line x1="12" y1="9" x2="12" y2="13" />
                                <line x1="12" y1="17" x2="12.01" y2="17" />
                            </svg>
                        </div>

                        {confirmStep === 1 && (
                            <>
                                <h2 className="emergency-modal__title">Konfirmasi Eskalasi</h2>
                                <p className="emergency-modal__message">
                                    Apakah Anda yakin ingin menghubungi layanan darurat?
                                </p>
                                <div className="emergency-modal__actions">
                                    <button
                                        className="emergency-modal__btn emergency-modal__btn--secondary"
                                        onClick={handleCancel}
                                    >
                                        Batal
                                    </button>
                                    <button
                                        className="emergency-modal__btn emergency-modal__btn--clinic"
                                        onClick={handleCallClinic}
                                    >
                                        Hubungi Klinik
                                    </button>
                                    <button
                                        className="emergency-modal__btn emergency-modal__btn--primary"
                                        onClick={handleConfirm}
                                    >
                                        Lanjutkan
                                    </button>
                                </div>
                            </>
                        )}

                        {confirmStep === 2 && (
                            <>
                                <h2 className="emergency-modal__title">Konfirmasi Akhir</h2>
                                <p className="emergency-modal__message emergency-modal__message--warning">
                                    Tekan tombol untuk menghubungi layanan darurat ({emergencyPhone})
                                </p>
                                <div className="emergency-modal__actions">
                                    <button
                                        className="emergency-modal__btn emergency-modal__btn--secondary"
                                        onClick={handleCancel}
                                    >
                                        Batal
                                    </button>
                                    <button
                                        className="emergency-modal__btn emergency-modal__btn--emergency"
                                        onClick={handleConfirm}
                                    >
                                        📞 PANGGIL DARURAT
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
