import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Icon from '../../../components/Icon/Icon';
import { t } from '../../../i18n';
import { useI18n } from '../../../i18n/useI18n';
import api, { isRequestCanceled } from '../../../services/api';
import { createRealtimeEventPoller } from '../../../services/realtimeEventPoller';
import {
  getPatientAIReadings,
  normalizeAIAnalysisPage,
} from '../../../utils/aiAnalysisModels';
import { formatDateTime } from '../../../utils/formatters';
import {
  getPatientHomeSessionReadings,
  normalizePatientHomeSessions,
} from '../../../utils/patientHomeSummary';

const SESSION_LIMIT = 10;

const formatBpm = (value) => (
  Number.isFinite(value) ? `${Math.round(value)} bpm` : t('patient.common.unavailable')
);

const formatSignalQuality = (value) => (
  Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : t('patient.common.unavailable')
);

const isRelevantRealtimeEvent = (event) => (
  event.event_type === 'ai.analysis.updated'
  || event.event_type === 'telemetry.updated'
  || event.event_type === 'session.started'
  || event.event_type === 'session.completed'
);

export default function PatientHomeAnalysisSummary({ onOpenMonitoring, onOpenHistory }) {
  const { locale } = useI18n();
  const [analysis, setAnalysis] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [analysisLoadError, setAnalysisLoadError] = useState(false);
  const [sessionLoadError, setSessionLoadError] = useState(false);
  const requestControllerRef = useRef(null);

  const fetchSummary = useCallback(async ({ silent = false } = {}) => {
    requestControllerRef.current?.abort();
    const controller = new AbortController();
    requestControllerRef.current = controller;
    if (!silent) setIsLoading(true);

    const [analysisRequest, sessionRequest] = await Promise.allSettled([
      api.patients.listAIResults({ limit: 1, signal: controller.signal }),
      api.sessions.listSessions({ limit: SESSION_LIMIT, signal: controller.signal }),
    ]);

    if (controller.signal.aborted) return;

    if (analysisRequest.status === 'fulfilled') {
      setAnalysis(normalizeAIAnalysisPage(analysisRequest.value)[0] || null);
      setAnalysisLoadError(false);
    } else if (!isRequestCanceled(analysisRequest.reason)) {
      setAnalysisLoadError(true);
    }

    if (sessionRequest.status === 'fulfilled') {
      setSessions(normalizePatientHomeSessions(sessionRequest.value));
      setSessionLoadError(false);
    } else if (!isRequestCanceled(sessionRequest.reason)) {
      setSessionLoadError(true);
    }

    if (requestControllerRef.current === controller) {
      requestControllerRef.current = null;
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialFetchTimer = window.setTimeout(() => {
      void fetchSummary();
    }, 0);
    return () => {
      window.clearTimeout(initialFetchTimer);
      requestControllerRef.current?.abort();
    };
  }, [fetchSummary]);

  useEffect(() => {
    const poller = createRealtimeEventPoller({
      fetchEvents: ({ cursor, signal }) => api.patients.listRealtimeEvents({
        afterCursor: cursor,
        limit: 100,
        signal,
      }),
      onEvents: (events) => (
        events.some(isRelevantRealtimeEvent)
          ? fetchSummary({ silent: true })
          : undefined
      ),
      onHeartbeat: () => fetchSummary({ silent: true }),
      initialDelayMs: 2_000,
      heartbeatIntervalMs: 45_000,
    });
    poller.start();
    return () => poller.stop();
  }, [fetchSummary]);

  const sourceSession = useMemo(() => {
    if (!analysis) return sessions[0] || null;
    return sessions.find((session) => session.id === analysis.sessionId) || null;
  }, [analysis, sessions]);
  const analysisReadings = useMemo(() => getPatientAIReadings(analysis), [analysis]);
  const sessionReadings = useMemo(
    () => getPatientHomeSessionReadings(sourceSession),
    [sourceSession],
  );
  const readings = {
    fhrBpm: sessionReadings.fhrBpm ?? analysisReadings.fhrBpm,
    maternalHrBpm: sessionReadings.maternalHrBpm ?? analysisReadings.maternalHrBpm,
    signalQuality: sessionReadings.signalQuality,
    contractionIndicator: sessionReadings.contractionIndicator,
  };
  const hasStoredData = Boolean(analysis || sourceSession);
  const hasLoadError = analysisLoadError || sessionLoadError;
  const resultTimestamp = analysis?.windowEndedAt
    || sourceSession?.summary?.updatedAt
    || sourceSession?.lastDataAt
    || sourceSession?.startTime
    || null;

  return (
    <section
      className={`home-analysis-overview home-analysis-overview--${analysis?.tone || 'neutral'}`}
      aria-labelledby="home-analysis-title"
    >
      <header className="home-analysis-overview__header">
        <div className="home-analysis-overview__heading-icon" aria-hidden="true">
          <Icon className="material-symbols-outlined" name="neurology" />
        </div>
        <div>
          <p>{t('patient.home.analysis.eyebrow')}</p>
          <h2 id="home-analysis-title">{t('patient.home.analysis.title')}</h2>
          <span>{t('patient.home.analysis.subtitle')}</span>
        </div>
        <button type="button" onClick={onOpenMonitoring}>
          {t('patient.home.analysis.openMonitoring')}
          <Icon className="material-symbols-outlined" name="arrow_forward" />
        </button>
      </header>

      {isLoading && !hasStoredData && (
        <div className="home-analysis-state" role="status" aria-live="polite">
          <Icon className="material-symbols-outlined home-analysis-state__spin" name="progress_activity" />
          <div>
            <strong>{t('patient.home.analysis.loadingTitle')}</strong>
            <p>{t('patient.home.analysis.loadingDesc')}</p>
          </div>
        </div>
      )}

      {hasLoadError && !hasStoredData && !isLoading && (
        <div className="home-analysis-state home-analysis-state--warning" role="alert">
          <Icon className="material-symbols-outlined" name="cloud_off" />
          <div>
            <strong>{t('patient.home.analysis.loadErrorTitle')}</strong>
            <p>{t('patient.home.analysis.loadErrorDesc')}</p>
            <button type="button" onClick={() => { void fetchSummary(); }}>
              {t('patient.monitoring.ai.retry')}
            </button>
          </div>
        </div>
      )}

      {(!isLoading || hasStoredData) && (
        <div className="home-analysis-overview__body" aria-live="polite">
          <article className="home-analysis-result">
            <div className="home-analysis-card-heading">
              <div>
                <span>{t('patient.home.analysis.resultLabel')}</span>
                <h3>
                  {analysis
                    ? t(`patient.monitoring.ai.status.${analysis.screeningStatus}.label`)
                    : analysisLoadError
                      ? t('patient.home.analysis.loadErrorTitle')
                      : t('patient.home.analysis.pendingTitle')}
                </h3>
              </div>
              {analysis && (
                <span className={`home-analysis-quality home-analysis-quality--${analysis.tone}`}>
                  {t(`patient.monitoring.ai.quality.${analysis.qualityStatus}`)}
                </span>
              )}
            </div>

            <p>
              {analysis
                ? t('patient.home.analysis.resultAvailableDesc')
                : analysisLoadError
                  ? t('patient.home.analysis.loadErrorDesc')
                  : t('patient.home.analysis.pendingDesc')}
            </p>

            <div className="home-analysis-result__meta">
              {resultTimestamp && (
                <span>
                  <Icon className="material-symbols-outlined" name="schedule" />
                  {formatDateTime(resultTimestamp, locale)}
                </span>
              )}
              {analysis?.review && (
                <span>
                  <Icon className="material-symbols-outlined" name="verified_user" />
                  {t('patient.monitoring.ai.reviewed')}
                </span>
              )}
            </div>

            {(analysis?.isSimulated || sourceSession?.summary?.isSimulated) && (
              <div className="home-analysis-result__simulation" role="note">
                <Icon className="material-symbols-outlined" name="science" />
                {t('patient.monitoring.ai.simulatedNotice')}
              </div>
            )}
          </article>

          <div className="home-analysis-overview__details">
            <article className="home-analysis-recommendation">
              <div className="home-analysis-detail-title">
                <Icon className="material-symbols-outlined" name="clinical_notes" />
                <span>{t('patient.home.analysis.recommendationLabel')}</span>
              </div>
              <strong>
                {analysis
                  ? t(`patient.monitoring.ai.status.${analysis.screeningStatus}.label`)
                  : analysisLoadError
                    ? t('patient.home.analysis.recommendationUnavailable')
                    : t('patient.home.analysis.recommendationPending')}
              </strong>
              <p>
                {analysis
                  ? t(`patient.monitoring.ai.status.${analysis.screeningStatus}.description`)
                  : analysisLoadError
                    ? t('patient.home.analysis.recommendationUnavailableDesc')
                    : t('patient.home.analysis.recommendationPendingDesc')}
              </p>
            </article>

            <article className="home-analysis-monitoring">
              <div className="home-analysis-detail-title">
                <Icon className="material-symbols-outlined" name="monitor_heart" />
                <span>{t('patient.home.analysis.monitoringLabel')}</span>
              </div>
              <div className="home-analysis-monitoring__meta">
                <strong>
                  {sourceSession
                    ? t(`patient.home.analysis.sessionStatus.${sourceSession.status}`)
                    : analysis
                      ? t('patient.home.analysis.sourceSessionUnavailable')
                    : t('patient.home.analysis.noSession')}
                </strong>
                {sourceSession && (
                  <button type="button" onClick={sourceSession.status === 'active' ? onOpenMonitoring : onOpenHistory}>
                    {sourceSession.status === 'active'
                      ? t('patient.home.analysis.openActiveSession')
                      : t('patient.home.analysis.openHistory')}
                  </button>
                )}
              </div>
              <div className="home-analysis-monitoring__grid">
                <div>
                  <span>{t('patient.monitoring.ai.fhr')}</span>
                  <strong>{formatBpm(readings.fhrBpm)}</strong>
                </div>
                <div>
                  <span>{t('patient.monitoring.ai.maternalHr')}</span>
                  <strong>{formatBpm(readings.maternalHrBpm)}</strong>
                </div>
                <div>
                  <span>{t('patient.monitoring.ai.signalQuality')}</span>
                  <strong>{formatSignalQuality(readings.signalQuality)}</strong>
                </div>
                <div>
                  <span>{t('patient.home.analysis.contractionIndicator')}</span>
                  <strong>{t(`patient.home.analysis.contraction.${readings.contractionIndicator}`)}</strong>
                </div>
              </div>
              {/* An empty reading has several very different causes, and the
                  right response differs for each. Saying which one applies is
                  more useful than four identical blanks. */}
              {readings.derivationStatus && readings.derivationStatus !== 'derived' && (
                <p className="home-analysis-monitoring__status" role="status">
                  <Icon className="material-symbols-outlined" name="info" />
                  {t(`patient.home.analysis.derivation.${readings.derivationStatus}`)}
                </p>
              )}
              <p className="home-analysis-monitoring__note">
                {t('patient.home.analysis.monitoringNote')}
              </p>
            </article>
          </div>

          {hasLoadError && hasStoredData && (
            <p className="home-analysis-refresh-warning" role="status">
              <Icon className="material-symbols-outlined" name="sync_problem" />
              {t('patient.home.analysis.refreshWarning')}
            </p>
          )}
        </div>
      )}

      <p className="home-analysis-overview__disclaimer">
        {t('patient.monitoring.ai.disclaimer')}
      </p>
    </section>
  );
}
