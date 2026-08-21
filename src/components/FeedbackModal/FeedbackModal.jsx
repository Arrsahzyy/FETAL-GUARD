import React, { useEffect, useRef } from 'react';
import { t } from '../../i18n';
import Icon from '../Icon/Icon';
import './FeedbackModal.css';

const FeedbackModal = ({ isOpen, onClose, title, message, type = 'info', confirmText = 'OK', onConfirm }) => {
    const modalRef = useRef(null);
    const primaryButtonRef = useRef(null);
    const previousFocusRef = useRef(null);

    useEffect(() => {
        if (!isOpen) return undefined;

        previousFocusRef.current = document.activeElement;
        primaryButtonRef.current?.focus();

        const handleKeyDown = (event) => {
            if (event.key === 'Escape') {
                onClose?.();
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
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    const titleId = 'feedback-modal-title';
    const messageId = 'feedback-modal-message';

    return (
        <div className="feedback-modal-overlay">
            <div
                ref={modalRef}
                className="feedback-modal-content"
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                aria-describedby={messageId}
            >
                <div className={`feedback-modal-icon feedback-modal-icon--${type}`}>
                    {type === 'info' && (
                        <Icon className="material-symbols-outlined" name="info" />
                    )}
                    {type === 'warning' && (
                        <Icon className="material-symbols-outlined" name="warning" />
                    )}
                    {type === 'success' && (
                        <Icon className="material-symbols-outlined" name="check_circle" />
                    )}
                    {type === 'error' && (
                        <Icon className="material-symbols-outlined" name="error" />
                    )}
                </div>
                <h3 id={titleId} className="feedback-modal-title">{title}</h3>
                <p id={messageId} className="feedback-modal-message">{message}</p>
                <div className="feedback-modal-actions">
                    {onConfirm ? (
                        <>
                            <button type="button" className="feedback-modal-btn feedback-modal-btn--cancel" onClick={onClose}>
                                {t('common.cancel')}
                            </button>
                            <button
                                ref={primaryButtonRef}
                                type="button"
                                className={`feedback-modal-btn feedback-modal-btn--${type}`}
                                onClick={() => { onConfirm(); onClose(); }}
                            >
                                {confirmText}
                            </button>
                        </>
                    ) : (
                        <button
                            ref={primaryButtonRef}
                            type="button"
                            className="feedback-modal-btn feedback-modal-btn--primary"
                            onClick={onClose}
                        >
                            {confirmText}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default FeedbackModal;
