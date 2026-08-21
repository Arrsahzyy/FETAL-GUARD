const SESSION_STATUSES = new Set(['active', 'completed', 'error']);
const CONTRACTION_INDICATORS = new Set(['unknown', 'none', 'mild', 'regular', 'strong']);

const finiteOrNull = (value, minimum, maximum) => {
  if (value === null || value === undefined || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric >= minimum && numeric <= maximum
    ? numeric
    : null;
};

const validDateOrNull = (value) => {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
};

export const normalizePatientHomeSession = (value) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const startTime = validDateOrNull(value.start_time);
  if (
    typeof value.id !== 'string'
    || !value.id
    || !startTime
    || !SESSION_STATUSES.has(value.status)
  ) return null;

  const summary = value.sensor_summary && typeof value.sensor_summary === 'object'
    ? value.sensor_summary
    : null;

  return {
    id: value.id,
    status: value.status,
    startTime,
    endTime: validDateOrNull(value.end_time),
    lastDataAt: validDateOrNull(value.last_data_at),
    summary: summary
      ? {
          fhrBpm: finiteOrNull(summary.fhr_estimate_bpm, 30, 240),
          maternalHrBpm: finiteOrNull(summary.maternal_hr_bpm, 30, 220),
          signalQuality: finiteOrNull(summary.signal_quality_index, 0, 1),
          contractionIndicator: CONTRACTION_INDICATORS.has(summary.contraction_indicator)
            ? summary.contraction_indicator
            : 'unknown',
          sampleCount: Number.isSafeInteger(summary.sample_count) && summary.sample_count >= 0
            ? summary.sample_count
            : 0,
          source: typeof summary.source === 'string' ? summary.source : null,
          isSimulated: summary.is_simulated === true,
          updatedAt: validDateOrNull(summary.updated_at),
        }
      : null,
  };
};

export const normalizePatientHomeSessions = (sessions) => (
  (Array.isArray(sessions) ? sessions : [])
    .map(normalizePatientHomeSession)
    .filter(Boolean)
    .sort((left, right) => new Date(right.startTime) - new Date(left.startTime))
);

export const getPatientHomeSessionReadings = (session) => {
  const canShowMeasurements = Boolean(session?.summary && !session.summary.isSimulated);
  return {
    fhrBpm: canShowMeasurements ? session.summary.fhrBpm : null,
    maternalHrBpm: canShowMeasurements ? session.summary.maternalHrBpm : null,
    signalQuality: canShowMeasurements ? session.summary.signalQuality : null,
    contractionIndicator: canShowMeasurements
      ? session.summary.contractionIndicator
      : 'unknown',
  };
};
