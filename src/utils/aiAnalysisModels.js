const QUALITY_STATUSES = new Set(['usable', 'limited', 'unusable']);
const SCREENING_STATUSES = new Set([
  'routine_monitoring',
  'needs_observation',
  'review_with_clinician',
  'insufficient_signal',
]);
const VISIBILITIES = new Set(['shadow', 'clinician', 'patient']);

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

export const getAIStatusTone = (screeningStatus) => {
  if (screeningStatus === 'routine_monitoring') return 'success';
  if (
    screeningStatus === 'needs_observation'
    || screeningStatus === 'review_with_clinician'
  ) return 'warning';
  return 'info';
};

export const normalizeAIAnalysisResult = (value) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const windowStartedAt = validDateOrNull(value.window_started_at);
  const windowEndedAt = validDateOrNull(value.window_ended_at);
  if (
    typeof value.id !== 'string'
    || !value.id
    || typeof value.session_id !== 'string'
    || !value.session_id
    || !windowStartedAt
    || !windowEndedAt
    || new Date(windowEndedAt) <= new Date(windowStartedAt)
    || !QUALITY_STATUSES.has(value.quality_status)
    || !SCREENING_STATUSES.has(value.screening_status)
    || !VISIBILITIES.has(value.visibility)
  ) return null;

  const qualityScore = finiteOrNull(value.quality_score, 0, 1);
  if (qualityScore === null) return null;

  return {
    id: value.id,
    patientId: typeof value.patient_id === 'string' ? value.patient_id : null,
    sessionId: value.session_id,
    deviceId: typeof value.device_id === 'string' ? value.device_id : null,
    windowStartedAt,
    windowEndedAt,
    qualityStatus: value.quality_status,
    qualityScore,
    fhrBpm: finiteOrNull(value.fhr_bpm, 30, 240),
    maternalHrBpm: finiteOrNull(value.maternal_hr_bpm, 30, 220),
    contractionProbability: finiteOrNull(value.contraction_probability, 0, 1),
    screeningStatus: value.screening_status,
    uncertainty: finiteOrNull(value.uncertainty, 0, 1),
    reasons: Array.isArray(value.reasons)
      ? value.reasons.filter((reason) => typeof reason === 'string').slice(0, 16)
      : [],
    visibility: value.visibility,
    isSimulated: value.is_simulated === true,
    modelVersion: typeof value.model_version === 'string' ? value.model_version : '',
    preprocessingVersion: typeof value.preprocessing_version === 'string'
      ? value.preprocessing_version
      : '',
    createdAt: validDateOrNull(value.created_at),
    review: value.review && typeof value.review === 'object'
      ? {
          decision: value.review.decision,
          note: typeof value.review.note === 'string' ? value.review.note : null,
          version: Number.isSafeInteger(value.review.version) ? value.review.version : 0,
        }
      : null,
    tone: getAIStatusTone(value.screening_status),
  };
};

export const normalizeAIAnalysisPage = (page) => {
  const items = Array.isArray(page?.items) ? page.items : [];
  return items
    .map(normalizeAIAnalysisResult)
    .filter(Boolean)
    .sort((left, right) => (
      new Date(right.windowEndedAt).getTime() - new Date(left.windowEndedAt).getTime()
    ));
};

export const getPatientAIReadings = (result) => {
  const canShowMeasurements = Boolean(
    result
    && result.visibility === 'patient'
    && result.qualityStatus === 'usable'
    && result.screeningStatus !== 'insufficient_signal'
    && !result.isSimulated,
  );
  return {
    fhrBpm: canShowMeasurements ? result.fhrBpm : null,
    maternalHrBpm: canShowMeasurements ? result.maternalHrBpm : null,
  };
};
