/**
 * Pure geometry helpers for SignalTrendChart, kept out of the component so the
 * decisions that determine whether the chart informs or misleads can be tested
 * without a DOM or a JSX transform.
 */

const isFiniteNumber = (value) => Number.isFinite(value);

/** Accepts bare numbers (index-spaced) or `{ value, timestamp }` points. */
export const normalizePoints = (data, sampleIntervalMs = 1000) => {
  if (!Array.isArray(data)) return [];
  return data
    .map((entry, index) => {
      if (isFiniteNumber(entry)) {
        return { value: entry, elapsedMs: index * sampleIntervalMs, isAbsolute: false };
      }
      const value = Number(entry?.value);
      if (!isFiniteNumber(value)) return null;
      const timestamp = entry?.timestamp ? Date.parse(entry.timestamp) : NaN;
      return {
        value,
        elapsedMs: Number.isFinite(timestamp) ? timestamp : index * sampleIntervalMs,
        isAbsolute: Number.isFinite(timestamp),
      };
    })
    .filter(Boolean);
};

/**
 * Pick a y-domain that always shows the reference band, padded around whatever
 * the data actually did.
 *
 * This is the whole reason the chart is trustworthy. With a plain auto-scale the
 * axis is just the visible min and max, so a reading wobbling 139-141 bpm fills
 * the plot exactly like one collapsing 160 to 90: a stable signal and a
 * dangerous one draw the same picture. Keeping the reference band in frame gives
 * the trace's height a fixed meaning and makes "outside the range" visible
 * rather than something the reader has to infer.
 */
export const resolveDomain = (values, referenceRange, explicitDomain) => {
  if (explicitDomain) return explicitDomain;

  const candidates = Array.isArray(values) ? values.filter(isFiniteNumber) : [];
  if (referenceRange) candidates.push(referenceRange[0], referenceRange[1]);
  if (candidates.length === 0) return [0, 1];

  const lowest = Math.min(...candidates);
  const highest = Math.max(...candidates);
  const margin = Math.max((highest - lowest) * 0.15, 5);
  return [Math.floor(lowest - margin), Math.ceil(highest + margin)];
};

export const formatElapsed = (elapsedMs) => {
  const totalSeconds = Math.max(0, Math.round(elapsedMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
};
