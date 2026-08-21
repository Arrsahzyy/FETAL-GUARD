import React, { useCallback, useEffect, useRef, useState } from 'react';
import Icon from '../../../../components/Icon';
import { t } from '../../../../i18n';
import { useI18n } from '../../../../i18n/useI18n';
import api, { isRequestCanceled } from '../../../../services/api';
import { createRealtimeEventPoller } from '../../../../services/realtimeEventPoller';
import { formatDateTime } from '../../../../utils/formatters';
import { normalizeAIAnalysisPage } from '../../../../utils/aiAnalysisModels';

const REVIEW_DECISIONS = ['confirmed', 'needs_followup', 'dismissed'];

const metric = (value, unit = '') => (
  Number.isFinite(value) ? `${Math.round(value)}${unit}` : '--'
);

export default function ClinicianAIAnalysisPanel({ patientId }) {
  const { locale } = useI18n();
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasLoadError, setHasLoadError] = useState(false);
  const [pendingReviewId, setPendingReviewId] = useState(null);
  const [reviewErrorId, setReviewErrorId] = useState(null);
  const requestControllerRef = useRef(null);

  const fetchResults = useCallback(async ({ silent = false } = {}) => {
    requestControllerRef.current?.abort();
    if (!patientId) {
      setResults([]);
      setIsLoading(false);
      return;
    }
    const controller = new AbortController();
    requestControllerRef.current = controller;
    if (!silent) setIsLoading(true);
    try {
      const page = await api.clinician.listPatientAIResults(patientId, {
        limit: 25,
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setResults(normalizeAIAnalysisPage(page));
      setHasLoadError(false);
    } catch (error) {
      if (!controller.signal.aborted && !isRequestCanceled(error)) setHasLoadError(true);
    } finally {
      if (requestControllerRef.current === controller) {
        requestControllerRef.current = null;
        if (!silent) setIsLoading(false);
      }
    }
  }, [patientId]);

  useEffect(() => {
    void fetchResults();
    return () => requestControllerRef.current?.abort();
  }, [fetchResults]);

  useEffect(() => {
    if (!patientId) return undefined;
    const poller = createRealtimeEventPoller({
      fetchEvents: ({ cursor, signal }) => api.clinician.listRealtimeEvents({
        afterCursor: cursor,
        patientId,
        limit: 100,
        signal,
      }),
      onEvents: (events) => (
        events.some((event) => event.event_type === 'ai.analysis.updated')
          ? fetchResults({ silent: true })
          : undefined
      ),
      onHeartbeat: () => fetchResults({ silent: true }),
      initialDelayMs: 2_000,
      heartbeatIntervalMs: 45_000,
    });
    poller.start();
    return () => poller.stop();
  }, [fetchResults, patientId]);

  const reviewResult = async (result, decision) => {
    if (pendingReviewId || !REVIEW_DECISIONS.includes(decision)) return;
    setPendingReviewId(result.id);
    setReviewErrorId(null);
    try {
      await api.clinician.reviewAIResult(result.id, {
        decision,
        expectedVersion: result.review?.version || 0,
      });
      await fetchResults({ silent: true });
    } catch (error) {
      if (!isRequestCanceled(error)) setReviewErrorId(result.id);
    } finally {
      setPendingReviewId(null);
    }
  };

  return (
    <div className="detail-section clinician-ai-section">
      <div className="detail-section__header">
        <h3>{t('clinician.aiTimelineTitle')}</h3>
        {!isLoading && <span>{t('clinician.aiResultCount', { count: results.length })}</span>}
      </div>
      <p className="clinician-ai-section__intro">{t('clinician.aiTimelineDesc')}</p>

      {isLoading && results.length === 0 && (
        <span className="detail-empty">{t('clinician.aiLoading')}</span>
      )}
      {hasLoadError && results.length === 0 && !isLoading && (
        <div className="clinician-ai-empty">
          <span>{t('clinician.aiLoadError')}</span>
          <button type="button" onClick={() => { void fetchResults(); }}>
            {t('clinician.retry')}
          </button>
        </div>
      )}
      {!isLoading && !hasLoadError && results.length === 0 && (
        <span className="detail-empty">{t('clinician.aiEmpty')}</span>
      )}

      {results.length > 0 && (
        <ol className="clinician-ai-list">
          {results.map((result) => (
            <li key={result.id} className={`clinician-ai-result clinician-ai-result--${result.tone}`}>
              <div className="clinician-ai-result__heading">
                <div>
                  <strong>{t(`patient.monitoring.ai.status.${result.screeningStatus}.label`)}</strong>
                  <span>{formatDateTime(result.windowEndedAt, locale)}</span>
                </div>
                <span className="clinician-ai-result__quality">
                  {t(`patient.monitoring.ai.quality.${result.qualityStatus}`)}
                </span>
              </div>

              <dl className="clinician-ai-result__metrics">
                <div>
                  <dt>{t('clinician.fetalHr')}</dt>
                  <dd>{metric(result.fhrBpm, ' bpm')}</dd>
                </div>
                <div>
                  <dt>{t('clinician.maternalHr')}</dt>
                  <dd>{metric(result.maternalHrBpm, ' bpm')}</dd>
                </div>
                <div>
                  <dt>{t('clinician.aiUncertainty')}</dt>
                  <dd>{Number.isFinite(result.uncertainty) ? `${Math.round(result.uncertainty * 100)}%` : '--'}</dd>
                </div>
              </dl>

              {result.review && (
                <div className={`clinician-ai-result__reviewed clinician-ai-result__reviewed--${result.review.decision}`}>
                  <Icon name={result.review.decision === 'dismissed' ? 'cancel' : 'check_circle'} />
                  <span>{t(`clinician.aiReview.${result.review.decision}`)}</span>
                </div>
              )}
              <div className="clinician-ai-result__actions" aria-label={t('clinician.aiReviewActions')}>
                {REVIEW_DECISIONS.map((decision) => {
                  const isCurrentDecision = result.review?.decision === decision;
                  return (
                    <button
                      key={decision}
                      type="button"
                      aria-pressed={isCurrentDecision}
                      disabled={Boolean(pendingReviewId) || isCurrentDecision}
                      onClick={() => { void reviewResult(result, decision); }}
                    >
                      {pendingReviewId === result.id
                        ? t('clinician.aiReviewSaving')
                        : t(`clinician.aiReview.${decision}`)}
                    </button>
                  );
                })}
              </div>
              {reviewErrorId === result.id && (
                <span className="clinician-ai-result__error" role="alert">
                  {t('clinician.aiReviewError')}
                </span>
              )}
              <small className="clinician-ai-result__visibility">
                {result.visibility === 'patient'
                  ? t('clinician.aiVisibleToPatient')
                  : t('clinician.aiAwaitingPatientPublication')}
              </small>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
