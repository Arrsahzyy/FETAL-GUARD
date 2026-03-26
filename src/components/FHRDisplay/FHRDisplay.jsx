import React, { useEffect, useState, useRef } from 'react';
import './FHRDisplay.css';

const FHRDisplay = ({
    value = 0,
    unit = 'bpm',
    label = 'Detak Jantung Janin',
    showAnimation = true,
    size = 'large' // 'small', 'medium', 'large'
}) => {
    const [displayValue, setDisplayValue] = useState(value);
    const [isAnimating, setIsAnimating] = useState(false);
    const prevValue = useRef(value);

    useEffect(() => {
        if (showAnimation && value !== prevValue.current) {
            setIsAnimating(true);

            // Animate value change
            const diff = value - prevValue.current;
            const steps = 10;
            const stepValue = diff / steps;
            let current = prevValue.current;
            let step = 0;

            const animate = () => {
                if (step < steps) {
                    current += stepValue;
                    setDisplayValue(Math.round(current));
                    step++;
                    requestAnimationFrame(animate);
                } else {
                    setDisplayValue(value);
                    setIsAnimating(false);
                }
            };

            requestAnimationFrame(animate);
            prevValue.current = value;
        } else {
            setDisplayValue(value);
        }
    }, [value, showAnimation]);

    const getStatusClass = () => {
        if (value >= 110 && value <= 160) return 'normal';
        if (value >= 100 && value < 110) return 'warning';
        if (value > 160 && value <= 180) return 'warning';
        return 'critical';
    };

    return (
        <div className={`fhr-display fhr-display--${size} fhr-display--${getStatusClass()}`}>
            <div className="fhr-display__label">{label}</div>
            <div className={`fhr-display__value ${isAnimating ? 'animating' : ''}`}>
                {displayValue}
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
