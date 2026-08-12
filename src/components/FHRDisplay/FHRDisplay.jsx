import React from 'react';
import './FHRDisplay.css';

const FHRDisplay = ({
    value = null,
    unit = 'bpm',
    label = 'Detak Jantung Janin',
    showAnimation = true,
    size = 'large' // 'small', 'medium', 'large'
}) => {
    const normalizedValue = Number.isFinite(Number(value)) && Number(value) > 0
        ? Math.round(Number(value))
        : null;
    const isAnimating = showAnimation && normalizedValue !== null;

    const getStatusClass = () => {
        if (normalizedValue === null) return 'unavailable';
        if (normalizedValue >= 110 && normalizedValue <= 160) return 'normal';
        return 'warning';
    };

    return (
        <div className={`fhr-display fhr-display--${size} fhr-display--${getStatusClass()}`}>
            <div className="fhr-display__label">{label}</div>
            <div className={`fhr-display__value ${isAnimating ? 'animating' : ''}`}>
                {normalizedValue ?? '--'}
            </div>
            <div className="fhr-display__unit">{unit}</div>
            <div className="fhr-display__pulse">
                <svg viewBox="0 0 100 40" className="fhr-display__pulse-svg">
                    <path
                        d="M0,20 L20,20 L25,5 L30,35 L35,15 L40,25 L45,20 L100,20"
                        fill="none"
                        strokeWidth="2"
                        className="fhr-display__pulse-path"
                    />
                </svg>
            </div>
        </div>
    );
};

export default FHRDisplay;
