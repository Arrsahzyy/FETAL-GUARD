import React, { useRef, useEffect, useState, useCallback } from 'react';
import './WaveformChart.css';

const WaveformChart = ({
    data = [],
    height = 200,
    showGrid = true,
    showMarkers = true,
    markers = [],
    isLive = false,
    playbackPosition = 0,
    onPositionChange,
    signalQuality = 'good'
}) => {
    const canvasRef = useRef(null);
    const containerRef = useRef(null);
    const animationRef = useRef(null);
    const [dimensions, setDimensions] = useState({ width: 0, height });
    const [isPinching, setIsPinching] = useState(false);
    const [scale, setScale] = useState(1);
    const [offset, setOffset] = useState(0);

    // Generate mock waveform data for demo
    const generateWaveformData = useCallback((length = 500) => {
        const points = [];
        for (let i = 0; i < length; i++) {
            // Simulate fetal heart rate waveform
            const baseValue = 135;
            const variability = Math.sin(i * 0.1) * 10;
            const noise = (Math.random() - 0.5) * 5;
            const heartbeat = Math.sin(i * 0.5) * 15 * Math.exp(-((i % 20) / 5));
            points.push(baseValue + variability + noise + heartbeat);
        }
        return points;
    }, []);

    const waveformData = data.length > 0 ? data : generateWaveformData();

    // Handle resize
    useEffect(() => {
        const handleResize = () => {
            if (containerRef.current) {
                setDimensions({
                    width: containerRef.current.offsetWidth,
                    height
                });
            }
        };

        handleResize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [height]);

    // Draw waveform
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || dimensions.width === 0) return;

        const ctx = canvas.getContext('2d');
        const { width, height } = dimensions;

        // Set canvas size
        canvas.width = width * window.devicePixelRatio;
        canvas.height = height * window.devicePixelRatio;
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

        const draw = () => {
            // Clear canvas
            ctx.clearRect(0, 0, width, height);

            // Draw grid
            if (showGrid) {
                ctx.strokeStyle = 'rgba(74, 163, 255, 0.1)';
                ctx.lineWidth = 1;

                // Horizontal lines
                for (let y = 0; y <= height; y += 20) {
                    ctx.beginPath();
                    ctx.moveTo(0, y);
                    ctx.lineTo(width, y);
                    ctx.stroke();
                }

                // Vertical lines
                for (let x = 0; x <= width; x += 20) {
                    ctx.beginPath();
                    ctx.moveTo(x, 0);
                    ctx.lineTo(x, height);
                    ctx.stroke();
                }
            }

            // Calculate visible data range
            const visibleStart = Math.floor(offset);
            const visibleEnd = Math.min(visibleStart + Math.floor(width / scale), waveformData.length);
            const visibleData = waveformData.slice(visibleStart, visibleEnd);

            if (visibleData.length < 2) return;

            // Find min/max for scaling
            const minValue = Math.min(...visibleData);
            const maxValue = Math.max(...visibleData);
            const range = maxValue - minValue || 1;
            const padding = 20;

            // Draw waveform
            ctx.beginPath();
            ctx.strokeStyle = signalQuality === 'poor' ? '#FFB020' : '#FF6B9A';
            ctx.lineWidth = 2;
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';

            visibleData.forEach((value, index) => {
                const x = (index * scale);
                const y = padding + ((maxValue - value) / range) * (height - 2 * padding);

                if (index === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            });

            ctx.stroke();

            // Draw glow effect
            ctx.shadowColor = '#FF6B9A';
            ctx.shadowBlur = 10;
            ctx.stroke();
            ctx.shadowBlur = 0;

            // Draw markers
            if (showMarkers && markers.length > 0) {
                markers.forEach(marker => {
                    if (marker.position >= visibleStart && marker.position < visibleEnd) {
                        const x = (marker.position - visibleStart) * scale;

                        ctx.beginPath();
                        ctx.strokeStyle = marker.type === 'acceleration' ? '#28C76F' : '#FF3B30';
                        ctx.lineWidth = 2;
                        ctx.setLineDash([5, 5]);
                        ctx.moveTo(x, 0);
                        ctx.lineTo(x, height);
                        ctx.stroke();
                        ctx.setLineDash([]);

                        // Draw marker label
                        ctx.fillStyle = marker.type === 'acceleration' ? '#28C76F' : '#FF3B30';
                        ctx.font = '12px Inter';
                        ctx.fillText(marker.label || marker.type[0].toUpperCase(), x + 5, 15);
                    }
                });
            }

            // Draw playback position line for non-live mode
            if (!isLive && playbackPosition > 0) {
                const posX = (playbackPosition - visibleStart) * scale;
                if (posX >= 0 && posX <= width) {
                    ctx.beginPath();
                    ctx.strokeStyle = '#4AA3FF';
                    ctx.lineWidth = 2;
                    ctx.moveTo(posX, 0);
                    ctx.lineTo(posX, height);
                    ctx.stroke();
                }
            }

            // Live mode animation
            if (isLive) {
                animationRef.current = requestAnimationFrame(draw);
            }
        };

        draw();

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
        };
    }, [waveformData, dimensions, showGrid, showMarkers, markers, isLive, playbackPosition, scale, offset, signalQuality]);

    // Handle pinch zoom
    const handleWheel = (e) => {
        e.preventDefault();
        const newScale = Math.max(0.5, Math.min(5, scale + e.deltaY * -0.01));
        setScale(newScale);
    };

    const handleTouchStart = (e) => {
        if (e.touches.length === 2) {
            setIsPinching(true);
        }
    };

    const handleTouchMove = (e) => {
        if (isPinching && e.touches.length === 2) {
            // Calculate pinch distance
            const touch1 = e.touches[0];
            const touch2 = e.touches[1];
            const distance = Math.hypot(
                touch2.clientX - touch1.clientX,
                touch2.clientY - touch1.clientY
            );
            // Adjust scale based on distance
            setScale(Math.max(0.5, Math.min(5, distance / 100)));
        }
    };

    const handleTouchEnd = () => {
        setIsPinching(false);
    };

    return (
        <div
            ref={containerRef}
            className={`waveform-chart waveform-chart--${signalQuality}`}
            onWheel={handleWheel}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
        >
            <canvas
                ref={canvasRef}
                className="waveform-chart__canvas"
                style={{ width: '100%', height: `${height}px` }}
            />
            {isLive && (
                <div className="waveform-chart__live-indicator">
                    <span className="waveform-chart__live-dot"></span>
                    LIVE
                </div>
            )}
            <div className="waveform-chart__scale-info">
                {Math.round(scale * 100)}%
            </div>
        </div>
    );
};

export default WaveformChart;
