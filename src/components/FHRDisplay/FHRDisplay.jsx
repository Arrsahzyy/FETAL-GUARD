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
            {/* This used to carry a hardcoded ECG-shaped squiggle that animated
                continuously and looked like a live trace, while being the same
                fixed path at 140 bpm as at 90, and drawing even when the reading
                was unavailable. The real signal is charted by SignalTrendChart;
                an ornament that reads as data does not belong next to it. */}
        </div>
    );
};

export default FHRDisplay;
