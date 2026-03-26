import React from 'react';
import './AlertCard.css';

const AlertCard = ({
    type = 'info', // 'info', 'warning', 'critical'
    title,
    message,
    timestamp,
    recommendation,
    acknowledged = false,
    onAcknowledge,
    onAction,
    actionLabel
}) => {
    const getIcon = () => {
        switch (type) {
            case 'critical':
                return (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                        <line x1="12" y1="9" x2="12" y2="13" />
                        <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                );
            case 'warning':
                return (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="8" x2="12" y2="12" />
                        <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                );
            default:
                return (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="16" x2="12" y2="12" />
                        <line x1="12" y1="8" x2="12.01" y2="8" />
                    </svg>
                );
        }
    };

    const formatTime = (ts) => {
        if (!ts) return '';
        const date = new Date(ts);
        return date.toLocaleTimeString('id-ID', {
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    return (
        <div className={`alert-card alert-card--${type} ${acknowledged ? 'alert-card--acknowledged' : ''}`}>
            <div className={`alert-card__icon alert-card__icon--${type}`}>
                {getIcon()}
            </div>

            <div className="alert-card__content">
                <div className="alert-card__header">
                    <h4 className="alert-card__title">{title}</h4>
                    {timestamp && (
                        <span className="alert-card__time">{formatTime(timestamp)}</span>
                    )}
                </div>

                <p className="alert-card__message">{message}</p>

                {recommendation && (
                    <p className="alert-card__recommendation">
                        <strong>Rekomendasi:</strong> {recommendation}
                    </p>
                )}

                <div className="alert-card__actions">
                    {!acknowledged && onAcknowledge && (
                        <button
                            className="alert-card__btn alert-card__btn--secondary"
                            onClick={onAcknowledge}
                        >
                            Saya sudah kontak klinik
                        </button>
                    )}

                    {onAction && actionLabel && (
                        <button
                            className={`alert-card__btn alert-card__btn--${type}`}
                            onClick={onAction}
                        >
                            {actionLabel}
                        </button>
                    )}
                </div>

                {acknowledged && (
                    <div className="alert-card__acknowledged-badge">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                            <polyline points="20 6 9 17 4 12" />
                        </svg>
                        Sudah ditangani
                    </div>
                )}
            </div>
        </div>
    );
};

export default AlertCard;
