import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Icon from '../../../components/Icon/Icon';
import StatusBadge from '../../../components/StatusBadge/StatusBadge';
import { t } from '../../../i18n';
import { useI18n } from '../../../i18n/useI18n';
import api, { isRequestCanceled } from '../../../services/api';
import { createRealtimeEventPoller } from '../../../services/realtimeEventPoller';
import { formatDateTime } from '../../../utils/formatters';
import {
  getPatientAIReadings,
  normalizeAIAnalysisPage,
} from '../../../utils/aiAnalysisModels';

const RESULT_LIMIT = 25;

const formatBpm = (value) => (
  Number.isFinite(value) ? `${Math.round(value)} bpm` : t('patient.common.unavailable')
);

export default function PatientAIAnalysisPanel({ sessionId, isSessionActive }) {
  const { locale } = useI18n();
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasLoadError, setHasLoadError] = useState(false);
  const [patientResultsEnabled, setPatientResultsEnabled] = useState(null);
  const requestControllerRef = useRef(null);

  const fetchResults = useCallback(async ({ silent = false } = {}) => {
    requestControllerRef.current?.abort();
    if (!sessionId) {
      setResults([]);
      setPatientResultsEnabled(null);
      setHasLoadError(false);
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    requestControllerRef.current = controller;
    if (!silent) setIsLoading(true);
    try {
      const [availability, page] = await Promise.all([
        api.patients.getAIAvailability({ signal: controller.signal }),
        api.patients.listAIResults({
          sessionId,
          limit: RESULT_LIMIT,
          signal: controller.signal,
        }),
      ]);
      if (controller.signal.aborted) return;
      setPatientResultsEnabled(availability.patient_results_enabled === true);
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
  }, [sessionId]);

  useEffect(() => {
    void fetchResults();
    return () => requestControllerRef.current?.abort();
  }, [fetchResults]);

  useEffect(() => {
    if (!sessionId || patientResultsEnabled !== true) return undefined;
    const poller = createRealtimeEventPoller({
      fetchEvents: ({ cursor, signal }) => api.patients.listRealtimeEvents({
        afterCursor: cursor,
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
  }, [fetchResults, patientResultsEnabled, sessionId]);

  const latest = results[0] || null;
  const readings = useMemo(() => getPatientAIReadings(latest), [latest]);

  return (
    <section className="patient-ai-panel" aria-labelledby="patient-ai-title">
      <div className="patient-ai-panel__header">
        <div>
          <span className="patient-ai-panel__eyebrow">
            {t('patient.monitoring.ai.eyebrow')}
          </span>
          <h2 id="patient-ai-title">{t('patient.monitoring.ai.title')}</h2>
          <p>{t('patient.monitoring.ai.subtitle')}</p>
        </div>
        <Icon className="material-symbols-outlined" name="neurology" />
      </div>

      {!sessionId && (
        <div className="patient-ai-state" role="status">
          <Icon className="material-symbols-outlined" name="hourglass_empty" />
          <div>
            <strong>{t('patient.monitoring.ai.sessionRequiredTitle')}</strong>
            <p>{t('patient.monitoring.ai.sessionRequiredDesc')}</p>
          </div>
        </div>
      )}

      {sessionId && isLoading && results.length === 0 && (
        <div className="patient-ai-state" role="status">
          <Icon className="material-symbols-outlined patient-ai-state__spin" name="progress_activity" />
          <div>
            <strong>{t('patient.monitoring.ai.loadingTitle')}</strong>
            <p>{t('patient.monitoring.ai.loadingDesc')}</p>
          </div>
        </div>
      )}

      {sessionId && hasLoadError && results.length === 0 && !isLoading && (
        <div className="patient-ai-state patient-ai-state--warning" role="status">
          <Icon className="material-symbols-outlined" name="cloud_off" />
          <div>
            <strong>{t('patient.monitoring.ai.loadErrorTitle')}</strong>
            <p>{t('patient.monitoring.ai.loadErrorDesc')}</p>
            <button type="button" onClick={() => { void fetchResults(); }}>
              {t('patient.monitoring.ai.retry')}
            </button>
          </div>
        </div>
      )}

      {sessionId && patientResultsEnabled === false && !latest && !isLoading && !hasLoadError && (
        <div className="patient-ai-state" role="status">
          <Icon className="material-symbols-outlined" name="model_training" />
          <div>
            <strong>{t('patient.monitoring.ai.unavailableTitle')}</strong>
            <p>{t('patient.monitoring.ai.unavailableDesc')}</p>
          </div>
        </div>
      )}

      {sessionId && patientResultsEnabled !== false && !latest && !isLoading && !hasLoadError && (
        <div className="patient-ai-state" role="status">
          <Icon className="material-symbols-outlined" name="pending_actions" />
          <div>
            <strong>{t('patient.monitoring.ai.pendingTitle')}</strong>
            <p>
              {isSessionActive
                ? t('patient.monitoring.ai.pendingActiveDesc')
                : t('patient.monitoring.ai.pendingCompletedDesc')}
            </p>
          </div>
        </div>
      )}

      {latest && (
        <>
          {latest.isSimulated && (
            <div className="patient-ai-panel__simulation" role="note">
              <Icon className="material-symbols-outlined" name="science" />
              <span>{t('patient.monitoring.ai.simulatedNotice')}</span>
            </div>
          )}

          <article className={`patient-ai-latest patient-ai-latest--${latest.tone}`}>
            <div className="patient-ai-latest__heading">
              <div>
                <span>{t('patient.monitoring.ai.latestLabel')}</span>
                <h3>{t(`patient.monitoring.ai.status.${latest.screeningStatus}.label`)}</h3>
              </div>
              <StatusBadge
                status={latest.tone}
                label={t(`patient.monitoring.ai.quality.${latest.qualityStatus}`)}
                size="small"
              />
            </div>
            <p className="patient-ai-latest__description">
              {t(`patient.monitoring.ai.status.${latest.screeningStatus}.description`)}
            </p>

            <div className="patient-ai-latest__metrics">
              <div>
                <Icon className="material-symbols-outlined" name="cardiology" />
                <span>{t('patient.monitoring.ai.fhr')}</span>
                <strong>{formatBpm(readings.fhrBpm)}</strong>
              </div>
              <div>
                <Icon className="material-symbols-outlined" name="favorite" />
                <span>{t('patient.monitoring.ai.maternalHr')}</span>
                <strong>{formatBpm(readings.maternalHrBpm)}</strong>
              </div>
              <div>
                <Icon className="material-symbols-outlined" name="signal_cellular_alt" />
                <span>{t('patient.monitoring.ai.signalQuality')}</span>
                <strong>{t(`patient.monitoring.ai.quality.${latest.qualityStatus}`)}</strong>
              </div>
            </div>

            <div className="patient-ai-latest__meta">
              <span>
                <Icon className="material-symbols-outlined" name="schedule" />
                {formatDateTime(latest.windowEndedAt, locale)}
              </span>
              {latest.review && (
                <span>
                  <Icon className="material-symbols-outlined" name="verified_user" />
                  {t('patient.monitoring.ai.reviewed')}
                </span>
              )}
            </div>
          </article>

          {results.length > 1 && (
            <details className="patient-ai-timeline">
              <summary>
                <span>{t('patient.monitoring.ai.timelineTitle')}</span>
                <small>{t('patient.monitoring.ai.timelineCount', { count: results.length })}</small>
              </summary>
              <ol>
                {results.map((result) => (
                  <li key={result.id} className={`patient-ai-timeline__item patient-ai-timeline__item--${result.tone}`}>
                    <span className="patient-ai-timeline__marker" aria-hidden="true" />
                    <div>
                      <strong>{t(`patient.monitoring.ai.status.${result.screeningStatus}.label`)}</strong>
                      <small>{formatDateTime(result.windowEndedAt, locale)}</small>
                    </div>
                    <span>{t(`patient.monitoring.ai.quality.${result.qualityStatus}`)}</span>
                  </li>
                ))}
              </ol>
            </details>
          )}
        </>
      )}

      <p className="patient-ai-panel__disclaimer">
        {t('patient.monitoring.ai.disclaimer')}
      </p>
    </section>
  );
}
