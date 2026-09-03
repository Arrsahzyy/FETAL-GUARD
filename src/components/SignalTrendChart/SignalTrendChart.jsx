import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { t } from '../../i18n';
import './SignalTrendChart.css';

/**
 * A readable trend chart for one sensor channel.
 *
 * Written to fix the thing that makes an auto-scaled sparkline misleading in a
 * screening context: when the y-axis is just the visible min and max, a reading
 * wobbling 139-141 bpm fills the plot exactly like one collapsing 160 to 90, so
 * a stable signal and a dangerous one draw the same picture. Here the domain
 * always contains the reference range, so the height of the trace means
 * something and "outside the range" is visible at a glance rather than inferred.
 *
 * The numbers plotted are technical estimates from the device signal. The
 * reference band is a display aid, not a diagnostic threshold.
 */

import { formatElapsed, normalizePoints, resolveDomain } from './signalTrendDomain';

const AXIS_TICK_COUNT = 4;
const PADDING = { top: 12, right: 12, bottom: 26, left: 40 };

const SignalTrendChart = ({
  data = [],
  unit = '',
  label,
  referenceRange = null,
  domain = null,
  height = 200,
  sampleIntervalMs = 1000,
  isLive = false,
  emptyMessage,
  decimals = 0,
}) => {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(0);
  const [cursorIndex, setCursorIndex] = useState(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return undefined;
    const measure = () => setWidth(element.clientWidth);
    measure();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', measure);
      return () => window.removeEventListener('resize', measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const points = useMemo(
    () => normalizePoints(data, sampleIntervalMs),
    [data, sampleIntervalMs],
  );
  const values = useMemo(() => points.map((point) => point.value), [points]);
  const [minimum, maximum] = useMemo(
    () => resolveDomain(values, referenceRange, domain),
    [values, referenceRange, domain],
  );

  const plotWidth = Math.max(0, width - PADDING.left - PADDING.right);
  const plotHeight = Math.max(0, height - PADDING.top - PADDING.bottom);
  const span = maximum - minimum || 1;

  const toX = useCallback(
    (index) => (points.length <= 1
      ? PADDING.left + plotWidth / 2
      : PADDING.left + (index / (points.length - 1)) * plotWidth),
    [points.length, plotWidth],
  );
  const toY = useCallback(
    (value) => PADDING.top + ((maximum - value) / span) * plotHeight,
    [maximum, span, plotHeight],
  );

  const linePath = useMemo(() => {
    if (points.length < 2) return '';
    return points
      .map((point, index) => `${index === 0 ? 'M' : 'L'}${toX(index).toFixed(2)},${toY(point.value).toFixed(2)}`)
      .join(' ');
  }, [points, toX, toY]);

  const ticks = useMemo(() => {
    const step = span / AXIS_TICK_COUNT;
    return Array.from({ length: AXIS_TICK_COUNT + 1 }, (_, index) => minimum + step * index);
  }, [minimum, span]);

  const outOfRangePoints = useMemo(() => {
    if (!referenceRange) return [];
    const [low, high] = referenceRange;
    return points
      .map((point, index) => ({ ...point, index }))
      .filter((point) => point.value < low || point.value > high);
  }, [points, referenceRange]);

  const latest = points.length > 0 ? points[points.length - 1] : null;
  const activeIndex = cursorIndex !== null && cursorIndex < points.length
    ? cursorIndex
    : null;
  const activePoint = activeIndex !== null ? points[activeIndex] : null;

  const formatValue = useCallback(
    (value) => `${value.toFixed(decimals)}${unit ? ` ${unit}` : ''}`,
    [decimals, unit],
  );

  const pointFromClientX = useCallback(
    (clientX) => {
      const element = containerRef.current;
      if (!element || points.length === 0) return null;
      const bounds = element.getBoundingClientRect();
      const ratio = (clientX - bounds.left - PADDING.left) / (plotWidth || 1);
      const index = Math.round(ratio * (points.length - 1));
      return Math.min(points.length - 1, Math.max(0, index));
    },
    [points.length, plotWidth],
  );

  const handlePointer = (event) => {
    const index = pointFromClientX(event.clientX);
    if (index !== null) setCursorIndex(index);
  };

  const handleKeyDown = (event) => {
    if (points.length === 0) return;
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    setCursorIndex((current) => {
      const start = current === null ? points.length - 1 : current;
      const next = event.key === 'ArrowLeft' ? start - 1 : start + 1;
      return Math.min(points.length - 1, Math.max(0, next));
    });
  };

  // Screen readers get the shape of the data as a sentence, since the trace
  // itself carries no text.
  const accessibleSummary = points.length === 0
    ? emptyMessage || t('patient.chart.empty')
    : t('patient.chart.summary', {
      label: label || '',
      count: points.length,
      min: formatValue(Math.min(...values)),
      max: formatValue(Math.max(...values)),
      latest: formatValue(latest.value),
    });

  const hasPlot = width > 0 && points.length > 0;

  return (
    <figure className="signal-trend" ref={containerRef}>
      {label && (
        <figcaption className="signal-trend__caption">
          <span className="signal-trend__label">{label}</span>
          {referenceRange && (
            <span className="signal-trend__reference">
              {t('patient.chart.referenceBand', {
                low: referenceRange[0],
                high: referenceRange[1],
                unit,
              })}
            </span>
          )}
        </figcaption>
      )}

      <div
        className="signal-trend__plot"
        style={{ height: `${height}px` }}
        role="img"
        aria-label={accessibleSummary}
        tabIndex={points.length > 0 ? 0 : -1}
        onKeyDown={handleKeyDown}
        onPointerMove={handlePointer}
        onPointerDown={handlePointer}
        onPointerLeave={() => setCursorIndex(null)}
        onBlur={() => setCursorIndex(null)}
      >
        {!hasPlot ? (
          <p className="signal-trend__empty">{emptyMessage || t('patient.chart.empty')}</p>
        ) : (
          <svg width={width} height={height} className="signal-trend__svg" aria-hidden="true">
            {referenceRange && (
              <rect
                className="signal-trend__band"
                x={PADDING.left}
                y={toY(Math.min(referenceRange[1], maximum))}
                width={plotWidth}
                height={Math.max(
                  0,
                  toY(Math.max(referenceRange[0], minimum)) - toY(Math.min(referenceRange[1], maximum)),
                )}
              />
            )}

            {ticks.map((tick) => (
              <g key={tick}>
                <line
                  className="signal-trend__gridline"
                  x1={PADDING.left}
                  x2={PADDING.left + plotWidth}
                  y1={toY(tick)}
                  y2={toY(tick)}
                />
                <text
                  className="signal-trend__axis-label"
                  x={PADDING.left - 6}
                  y={toY(tick)}
                  textAnchor="end"
                  dominantBaseline="middle"
                >
                  {Math.round(tick)}
                </text>
              </g>
            ))}

            <text
              className="signal-trend__axis-label"
              x={PADDING.left}
              y={height - 8}
              textAnchor="start"
            >
              {formatElapsed(0)}
            </text>
            <text
              className="signal-trend__axis-label"
              x={PADDING.left + plotWidth}
              y={height - 8}
              textAnchor="end"
            >
              {points[0]?.isAbsolute
                ? formatElapsed(latest.elapsedMs - points[0].elapsedMs)
                : formatElapsed(latest.elapsedMs)}
            </text>

            {linePath && <path className="signal-trend__line" d={linePath} />}

            {outOfRangePoints.map((point) => (
              <circle
                key={`out-${point.index}`}
                className="signal-trend__point signal-trend__point--outside"
                cx={toX(point.index)}
                cy={toY(point.value)}
                r={3}
              />
            ))}

            {latest && (
              <circle
                className={`signal-trend__point signal-trend__point--latest${isLive ? ' signal-trend__point--live' : ''}`}
                cx={toX(points.length - 1)}
                cy={toY(latest.value)}
                r={4}
              />
            )}

            {activePoint && (
              <g>
                <line
                  className="signal-trend__cursor"
                  x1={toX(activeIndex)}
                  x2={toX(activeIndex)}
                  y1={PADDING.top}
                  y2={PADDING.top + plotHeight}
                />
                <circle
                  className="signal-trend__point signal-trend__point--active"
                  cx={toX(activeIndex)}
                  cy={toY(activePoint.value)}
                  r={5}
                />
              </g>
            )}
          </svg>
        )}

        {activePoint && (
          <div
            className="signal-trend__tooltip"
            style={{
              left: `${Math.min(Math.max(toX(activeIndex), PADDING.left), width - PADDING.right)}px`,
            }}
          >
            <strong>{formatValue(activePoint.value)}</strong>
            <span>
              {activePoint.isAbsolute
                ? formatElapsed(activePoint.elapsedMs - points[0].elapsedMs)
                : formatElapsed(activePoint.elapsedMs)}
            </span>
          </div>
        )}
      </div>
    </figure>
  );
};

export default SignalTrendChart;
