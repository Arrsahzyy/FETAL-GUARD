import React from 'react';
import './StatusBadge.css';

const StatusBadge = ({
    status = 'info', // 'success', 'warning', 'critical', 'info'
    label,
    value,
    showIcon = true,
    size = 'medium' // 'small', 'medium', 'large'
}) => {
    const getIcon = () => {
        switch (status) {
            case 'success':
                return (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                        <polyline points="22 4 12 14.01 9 11.01" />
                    </svg>
                );
            case 'warning':
                return (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                        <line x1="12" y1="9" x2="12" y2="13" />
                        <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                );
            case 'critical':
                return (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="15" y1="9" x2="9" y2="15" />
                        <line x1="9" y1="9" x2="15" y2="15" />
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

    return (
        <div className={`status-badge status-badge--${status} status-badge--${size}`}>
            {showIcon && (
                <span className="status-badge__icon" aria-hidden="true">
                    {getIcon()}
                </span>
            )}
            {label && <span className="status-badge__label">{label}</span>}
            {value !== undefined && <span className="status-badge__value">{value}</span>}
            <span className="sr-only">{`Status: ${status}${label ? `, ${label}` : ''}${value !== undefined ? `: ${value}` : ''}`}</span>
        </div>
    );
};

export default StatusBadge;
