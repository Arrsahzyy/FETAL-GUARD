import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import AuthScreen from "../../../components/AuthScreen/AuthScreen";
import FHRDisplay from "../../../components/FHRDisplay/FHRDisplay";
import Icon from "../../../components/Icon/Icon";
import StatusBadge from "../../../components/StatusBadge/StatusBadge";
import WaveformChart from "../../../components/WaveformChart/WaveformChart";
import { useAuth } from "../../../context/useAuth";
import { usePatientDevice } from "../../../context/usePatientDevice";
import { usePatientMonitoring } from "../../../context/usePatientMonitoring";
import { t } from "../../../i18n";
import { useI18n } from "../../../i18n/useI18n";
import { getPatientLiveReadings } from "../../../utils/patientLiveReadings";
import PatientAIAnalysisPanel from "./PatientAIAnalysisPanel";
import "./MonitoringScreen.css";

const SIGNAL_VIEW_OPTIONS = ["all", "fhr", "contraction", "events"];
const HISTORY_LIMIT = 180;

const appendHistoryValue = (history, value) => {
  if (value === null) return history;
  const next = [...history, value];
  return next.length > HISTORY_LIMIT ? next.slice(-HISTORY_LIMIT) : next;
};

const getSignalLevelFromPercent = (value) => {
  if (value === null) return "waiting";
  if (value >= 85) return "excellent";
  if (value >= 65) return "good";
  if (value >= 45) return "fair";
  return "poor";
};

const formatBpm = (value) => (
  value === null ? "--" : Math.round(value)
);

const MonitoringScreen = ({ patientData }) => {
  const navigate = useNavigate();
  const { isAuthenticated, isAuthLoading, user } = useAuth();

  if (isAuthLoading) {
    return (
      <div className="monitoring-screen monitoring-screen--auth-loading">
        <div className="monitoring-sync-panel">
          <strong>{t("patient.monitoring.authChecking")}</strong>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthScreen />;
  }

  const profilePatientData = user?.patientProfile
    ? {
        ...patientData,
        fullName: user.patientProfile.name,
        pregnancyWeek: user.patientProfile.gestational_age_weeks,
      }
    : patientData;

  return (
    <MonitoringScreenContent
      navigate={navigate}
      patientData={profilePatientData}
    />
  );
};

const MonitoringScreenContent = ({ navigate, patientData }) => {
  // ============================================
  // Sensor data hook — easy swap point for the hardware data provider later.
  // ============================================
  const {
    availableDevices,
    connectToDevice,
    connectionState,
    droppedPacketCount,
    hasRegisteredDevice,
    isBleAvailable,
    isConnecting,
    isScanning,
    isTelemetryFresh,
    pairedDevice,
    pairingError,
    scanForDevice,
    telemetry,
  } = usePatientDevice();
  const {
    activeSession,
    dataPersistenceState,
    isSessionActive,
    pendingUploadCount,
    rejectedUploadCount,
    sessionError,
    sessionState,
    startSession,
    stopSession,
  } = usePatientMonitoring();

  // Session active state — toggled oleh stop/resume button
  const [activeSignalView, setActiveSignalView] = useState("all");
  const [sessionDuration, setSessionDuration] = useState(0);
  const [fhrHistory, setFhrHistory] = useState([]);
  const [contractionHistory, setContractionHistory] = useState([]);
  const isMonitoringActive = Boolean(pairedDevice) && isSessionActive;
  const isLiveTelemetry = isMonitoringActive && isTelemetryFresh;

  // Reactive locale — memastikan re-render saat user ganti bahasa
  // eslint-disable-next-line no-unused-vars
  const { locale } = useI18n();

  // Pregnancy data from patient profile
  const pregnancyWeek =
    patientData?.pregnancyWeek || patientData?.gestationalWeeks || null;

  useEffect(() => {
    if (!isMonitoringActive || !activeSession?.start_time) return undefined;
    const sessionStartedAt = new Date(activeSession.start_time).getTime();
    if (Number.isNaN(sessionStartedAt)) return undefined;

    const timer = window.setInterval(() => {
      setSessionDuration(Math.floor((Date.now() - sessionStartedAt) / 1000));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [activeSession?.start_time, isMonitoringActive]);

  // Never keep presenting the last device reading as current after the
  // authenticated session stops or telemetry becomes stale.
  const liveReadings = getPatientLiveReadings(telemetry, isLiveTelemetry);
  const currentFHR = liveReadings.fhr;
  const motherHeartRate = liveReadings.maternalHeartRate;
  const spo2 = liveReadings.spo2;
  const signalPercent = liveReadings.signalQuality;
  const contractionIntensity = liveReadings.contractionLevel;
  const signalQuality = getSignalLevelFromPercent(signalPercent);
  const contractionIntensityDisplay = contractionIntensity ?? 0;

  useEffect(() => {
    if (!isLiveTelemetry) return undefined;

    const historyUpdate = window.setTimeout(() => {
      setFhrHistory((current) => appendHistoryValue(current, currentFHR));
      setContractionHistory((current) => appendHistoryValue(current, contractionIntensity));
    }, 0);

    return () => window.clearTimeout(historyUpdate);
  }, [contractionIntensity, currentFHR, isLiveTelemetry, telemetry.bootId, telemetry.sequenceNumber]);

  const fhrAverage = useMemo(() => (
    fhrHistory.length > 0
      ? Math.round(fhrHistory.reduce((total, value) => total + value, 0) / fhrHistory.length)
      : null
  ), [fhrHistory]);
  const counters = useMemo(() => ({
    accelerations: null,
    decelerations: null,
    movements: null,
    contractions: null,
  }), []);
  const hasLiveTelemetry = isLiveTelemetry;
  const isAcceleration = false;
  const isDeceleration = false;
  const isStartingSession = sessionState === "starting";
  const isStoppingSession = sessionState === "stopping";
  const syncError = sessionError || pairingError;
  const syncErrorTitle = sessionError
    ? t("patient.monitoring.syncFailed")
    : t("patient.monitoring.deviceConnectionFailed");

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const getSignalQualityLabel = () => {
    switch (signalQuality) {
      case "waiting":
        return t("patient.monitoring.waitingDeviceData");
      case "excellent":
        return t("monitoring.excellent");
      case "good":
        return t("monitoring.good");
      case "fair":
        return t("monitoring.fair");
      case "poor":
        return t("monitoring.poor");
      default:
        return signalQuality;
    }
  };

  const getSignalStatus = () => {
    switch (signalQuality) {
      case "waiting":
        return "info";
      case "excellent":
      case "good":
        return "success";
      case "fair":
        return "warning";
      case "poor":
        return "warning";
      default:
        return "info";
    }
  };

  const getObservationStatus = () => {
    if (!hasLiveTelemetry) {
      return {
        label: t("patient.monitoring.waitingDeviceDataShort"),
        status: "info",
        recommendation: t("patient.monitoring.waitingDeviceDataDesc"),
      };
    }

    if ((currentFHR !== null && (currentFHR < 110 || currentFHR > 160))
        || (motherHeartRate !== null && (motherHeartRate < 60 || motherHeartRate > 100))) {
      return {
        label: t("patient.monitoring.reviewReading"),
        status: "warning",
        recommendation: t("patient.monitoring.recommendedRepeat"),
      };
    }
    return {
      label: t("patient.monitoring.readingAvailable"),
      status: "success",
      recommendation: t("patient.monitoring.recommendedStable"),
    };
  };

  const getMotherHRStatus = () => {
    if (motherHeartRate === null) return "info";
    if (motherHeartRate >= 60 && motherHeartRate <= 100) return "success";
    return "warning";
  };

  const getSpO2Status = () => {
    if (spo2 === null) return "info";
    return "info";
  };

  const getFHRStatus = () => {
    if (currentFHR === null) return "info";
    if (currentFHR >= 110 && currentFHR <= 160) return "success";
    return "warning";
  };

  const getStatusLabel = (status, warningLabel = t("patient.common.recheck")) => {
    if (status === "success") return t("patient.common.inRange");
    if (status === "warning") return warningLabel;
    if (status === "info") return t("patient.monitoring.waitingDeviceDataShort");
    return t("patient.common.consult");
  };

  const getRangePercent = (value, min, max) => {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 0;
    return Math.min(100, Math.max(0, ((numeric - min) / (max - min)) * 100));
  };

  const handleToggleSession = async () => {
    if (isSessionActive) {
      // STOP — tidak navigate, tetap di tab Pantau
      await stopSession();
    } else {
      // RESUME
      setFhrHistory([]);
      setContractionHistory([]);
      setSessionDuration(0);
      await startSession();
    }
  };

  const observationStatus = getObservationStatus();
  const connectionLabel = connectionState === "reconnecting"
    ? t("patient.monitoring.reconnecting")
    : isTelemetryFresh
      ? t("patient.monitoring.dataFresh")
      : t("patient.monitoring.dataStale");
  const persistenceLabels = {
    waiting: t("patient.monitoring.persistenceWaiting"),
    awaiting_raw_channels: t("patient.monitoring.persistenceNoRawChannels"),
    pending: t("patient.monitoring.persistencePending"),
    synced: t("patient.monitoring.persistenceSynced"),
    retrying: t("patient.monitoring.persistenceRetrying"),
    offline: t("patient.monitoring.persistenceOffline"),
    wifi_required: t("patient.monitoring.persistenceWifiRequired"),
    rejected: t("patient.monitoring.persistenceRejected"),
    queue_full: t("patient.monitoring.persistenceQueueFull"),
  };
  const persistenceLabel = persistenceLabels[dataPersistenceState]
    || t("patient.monitoring.persistenceWaiting");
  const showFhrSignal =
    activeSignalView === "all" || activeSignalView === "fhr";
  const showContractionSignal =
    activeSignalView === "all" || activeSignalView === "contraction";
  const showEventSignal =
    activeSignalView === "all" || activeSignalView === "events";

  if (!pairedDevice) {
    const emptyTitle = hasRegisteredDevice
      ? t("patient.monitoring.deviceNotConnectedTitle")
      : t("patient.monitoring.deviceNotRegisteredTitle");
    const emptyDesc = hasRegisteredDevice
      ? t("patient.monitoring.deviceNotConnectedDesc")
      : t("patient.monitoring.deviceNotRegisteredDesc");

    return (
      <div className="monitoring-screen">
        <header className="monitoring-header">
          <div className="monitoring-header__left">
            <button
              className="monitoring-back-btn"
              onClick={() => navigate("/patient/home")}
              type="button"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
            </button>
            <h1>{t("monitoring.title")}</h1>
          </div>
          <div className="monitoring-header__duration">
            <span className="monitoring-header__duration-label">
              {t("monitoring.duration")}
            </span>
            <span className="monitoring-header__duration-value">00:00</span>
          </div>
        </header>

        {syncError && (
          <div className="monitoring-sync-panel monitoring-sync-panel--error">
            <strong>{syncErrorTitle}</strong>
            <p>{syncError}</p>
          </div>
        )}

        <section className="monitoring-device-empty" role="status">
          <div className="monitoring-device-empty__visual" aria-hidden="true">
            <Icon className="material-symbols-outlined" name="sensors_off" />
            <i />
            <i />
          </div>
          <div className="monitoring-device-empty__copy">
            <span>{t("patient.monitoring.deviceConnectionRequired")}</span>
            <h2>{emptyTitle}</h2>
            <p>{emptyDesc}</p>
          </div>
          <div className="monitoring-device-empty__actions">
            {hasRegisteredDevice ? (
              <button
                type="button"
                className="monitoring-device-empty__primary"
                disabled={isScanning || isConnecting}
                onClick={() => {
                  void scanForDevice();
                }}
              >
                <Icon className="material-symbols-outlined" name="bluetooth_searching" />
                {isScanning
                  ? t("patient.home.scanLoading")
                  : t("patient.monitoring.scanFromHome")}
              </button>
            ) : (
              <button
                type="button"
                className="monitoring-device-empty__primary"
                onClick={() => navigate("/patient/settings")}
              >
                <Icon className="material-symbols-outlined" name="settings" />
                {t("patient.monitoring.openDeviceSettings")}
              </button>
            )}
            <button
              type="button"
              className="monitoring-device-empty__secondary"
              onClick={() => navigate("/patient/home")}
            >
              {t("patient.common.backHome")}
            </button>
          </div>

          {hasRegisteredDevice && availableDevices.length > 0 && (
            <div
              className="monitoring-device-results"
              aria-label={t("patient.home.devicePickerFound", { count: availableDevices.length })}
            >
              <strong>
                {t("patient.home.devicePickerFound", { count: availableDevices.length })}
              </strong>
              <div className="monitoring-device-results__list">
                {availableDevices.map((device) => (
                  <article key={device.deviceId} className="monitoring-device-result">
                    <Icon className="material-symbols-outlined" name="sensors" />
                    <div>
                      <strong>{device.name}</strong>
                      <span>
                        {device.rssi !== null && device.rssi !== undefined
                          ? t("patient.home.deviceSignal", { value: device.rssi })
                          : t("patient.home.deviceReady")}
                      </span>
                      <small className={device.isRegistered ? "is-registered" : "is-unregistered"}>
                        {device.isRegistered
                          ? t("patient.home.deviceRegisteredForYou")
                          : t("patient.home.deviceNotInRegistry")}
                      </small>
                    </div>
                    <button
                      type="button"
                      disabled={isConnecting || !device.isRegistered}
                      onClick={() => {
                        void connectToDevice(device);
                      }}
                    >
                      {isConnecting
                        ? t("patient.home.deviceConnecting")
                        : t("patient.home.connectDevice")}
                    </button>
                  </article>
                ))}
              </div>
            </div>
          )}

          {hasRegisteredDevice && !isBleAvailable && (
            <p className="monitoring-device-empty__hint" role="status">
              {t("patient.home.bleUnavailableHint")}
            </p>
          )}
        </section>
      </div>
    );
  }

  return (
    <div className="monitoring-screen">
      {/* Header */}
      <header className="monitoring-header">
        <div className="monitoring-header__left">
          <button
            className="monitoring-back-btn"
            onClick={() => navigate("/patient/home")}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
          </button>
          <h1>{t("monitoring.title")}</h1>
        </div>
        <div className="monitoring-header__duration">
          <span className="monitoring-header__duration-label">
            {t("monitoring.duration")}
          </span>
          <span className="monitoring-header__duration-value">
            {formatDuration(sessionDuration)}
          </span>
        </div>
      </header>

      {(isStartingSession || isStoppingSession || syncError) && (
        <div
          className={`monitoring-sync-panel ${syncError ? "monitoring-sync-panel--error" : ""}`}
        >
          <strong>
            {syncError
              ? syncErrorTitle
              : isStoppingSession
                ? t("patient.monitoring.closingSession")
                : t("patient.monitoring.preparingSession")}
          </strong>
          {syncError && <p>{syncError}</p>}
        </div>
      )}

      <section
        className="monitoring-source-banner"
        aria-label={t("patient.monitoring.dataSourceStatus")}
      >
        <div className="monitoring-source-banner__icon" aria-hidden="true">
          <Icon className="material-symbols-outlined" name="sensors" />
        </div>
        <div>
          <strong>{connectionLabel}</strong>
          <p>{persistenceLabel}</p>
        </div>
      </section>

      <section className={`monitoring-live-panel monitoring-live-panel--${observationStatus.status}`}>
        <div className="monitoring-live-panel__header">
          <div>
            <span className="monitoring-live-panel__eyebrow">
              {t("patient.monitoring.sessionOverview")}
            </span>
            <h2>
              {isTelemetryFresh
                ? t("patient.monitoring.liveNow")
                : t("patient.monitoring.dataStale")}
            </h2>
          </div>
          <StatusBadge
            status={observationStatus.status}
            label={observationStatus.label}
            size="small"
          />
        </div>

        <div className="monitoring-live-panel__body">
          <div className="monitoring-fhr-container">
            <div
              className={`monitoring-fhr-radar${
                isMonitoringActive ? " monitoring-fhr-radar--active" : ""
              }`}
            >
              <div className="monitoring-fhr-radar__ring" />
              <div className="monitoring-fhr-radar__ring" />
              <div className="monitoring-fhr-radar__ring" />
              <FHRDisplay
                value={currentFHR}
                label={t("home.fhr")}
                size="large"
                showAnimation={false}
              />
            </div>
          </div>

          <div className="monitoring-live-metrics" aria-label={t("patient.monitoring.sessionOverview")}>
            <article className="monitoring-live-metric">
              <Icon className="material-symbols-outlined" name="pregnant_woman" />
              <div>
                <small>{t("patient.monitoring.gestation")}</small>
                <strong>
                  {pregnancyWeek
                    ? `${pregnancyWeek} ${t("patient.monitoring.weeks")}`
                    : t("patient.common.unavailable")}
                </strong>
              </div>
            </article>

            <article className={`monitoring-live-metric monitoring-live-metric--${getSignalStatus()}`}>
              <Icon className="material-symbols-outlined" name="signal_cellular_alt" />
              <div>
                <small>{t("patient.monitoring.signal")}</small>
                <strong>{getSignalQualityLabel()}</strong>
              </div>
            </article>

            <article className="monitoring-live-metric">
              <Icon className="material-symbols-outlined" name="sensors" />
              <div>
                <small>{t("patient.monitoring.beltPosition")}</small>
                <strong>
                  {isTelemetryFresh
                    ? t("patient.monitoring.deviceVerified")
                    : t("patient.monitoring.deviceStandby")}
                </strong>
              </div>
            </article>

            <article className="monitoring-live-metric">
              <Icon className="material-symbols-outlined" name="show_chart" />
              <div>
                <small>{t("patient.monitoring.fhrBaseline")}</small>
                <strong>{formatBpm(fhrAverage)} bpm</strong>
              </div>
            </article>
          </div>
        </div>

        {signalQuality === "poor" && (
          <div className="monitoring-warning monitoring-warning--inline">
            <Icon className="material-symbols-outlined" name="warning" />
            <div>
              <strong>{t("patient.monitoring.signalAlertTitle")}</strong>
              <p>{t("monitoring.signalPoorNotice")}</p>
            </div>
            <button
              className="monitoring-warning__btn"
              type="button"
              onClick={() => navigate("/patient/settings")}
            >
              {t("patient.monitoring.signalAlertAction")}
            </button>
          </div>
        )}
      </section>

      <PatientAIAnalysisPanel
        sessionId={activeSession?.id || null}
        isSessionActive={isSessionActive}
      />

      {isMonitoringActive && (
        <>
          <div
            className={`monitoring-risk monitoring-risk--${observationStatus.status}`}
          >
            <div className="monitoring-risk__header">
              <div className="monitoring-risk__title-group">
                <span className="monitoring-risk__tag">
                  {t("patient.monitoring.dataStatusTag")}
                </span>
                <h3>{t("patient.monitoring.readingStatusTitle")}</h3>
                <p>{t("patient.monitoring.readingStatusDescription")}</p>
              </div>
              <StatusBadge
                status={observationStatus.status}
                label={observationStatus.label}
              />
            </div>

            <div className="monitoring-risk__insights">
              <article className="monitoring-risk__insight">
                <Icon className="material-symbols-outlined" name="bluetooth_connected" />
                <div>
                  <strong>{t("patient.monitoring.connectionStatus")}</strong>
                  <p>{connectionLabel}</p>
                </div>
              </article>
              <article className="monitoring-risk__insight">
                <Icon className="material-symbols-outlined" name="cloud_sync" />
                <div>
                  <strong>{t("patient.monitoring.storageStatus")}</strong>
                  <p>{persistenceLabel}</p>
                </div>
              </article>
            </div>

            {(pendingUploadCount > 0 || droppedPacketCount > 0 || rejectedUploadCount > 0) && (
              <details className="monitoring-delivery-details">
                <summary>{t("patient.monitoring.deliveryDetailsTitle")}</summary>
                <div className="monitoring-delivery-details__list" role="status">
                  <span>{t("patient.monitoring.pendingPackets", { count: pendingUploadCount })}</span>
                  <span>{t("patient.monitoring.detectedPacketGaps", { count: droppedPacketCount })}</span>
                  <span>{t("patient.monitoring.rejectedPackets", { count: rejectedUploadCount })}</span>
                </div>
              </details>
            )}

            <div className="monitoring-risk__recommendation">
              <Icon className="material-symbols-outlined" name="clinical_notes" />
              <div>
                <strong>{t("patient.monitoring.recommendedAction")}</strong>
                <p>{observationStatus.recommendation}</p>
              </div>
            </div>
          </div>

          {/* Mother's Vital Signs */}
          <section className="monitoring-vitals">
            <div className="monitoring-section-heading">
              <div>
                <span>{t("patient.monitoring.sessionOverview")}</span>
                <h3>{t("patient.monitoring.maternalVitals")}</h3>
              </div>
              <p>{t("patient.monitoring.maternalVitalsSubtitle")}</p>
            </div>
            <div className="monitoring-vitals__grid">
              {/* Mother's Heart Rate */}
              <article
                className={`monitoring-vital-card monitoring-vital-card--${getMotherHRStatus()}`}
              >
                <div className="monitoring-vital-card__top">
                  <div className="monitoring-vital-card__icon">
                    <Icon className="material-symbols-outlined" name="favorite" />
                  </div>
                  <StatusBadge
                    status={getMotherHRStatus()}
                    size="small"
                    label={getStatusLabel(getMotherHRStatus())}
                    showIcon={false}
                  />
                </div>
                <div className="monitoring-vital-card__content">
                  <span className="monitoring-vital-card__label">
                    {t("patient.monitoring.maternalHr")}
                  </span>
                  <span className="monitoring-vital-card__value">
                    {formatBpm(motherHeartRate)} <small>bpm</small>
                  </span>
                </div>
                <div className="monitoring-vital-card__range" aria-hidden="true">
                  <span style={{ width: `${getRangePercent(motherHeartRate, 45, 125)}%` }} />
                </div>
                <small className="monitoring-vital-card__reference">
                  {t("patient.monitoring.maternalHrReference")}
                </small>
              </article>

              {/* SpO2 dari MAX30102 */}
              <article
                className={`monitoring-vital-card monitoring-vital-card--${getSpO2Status()}`}
              >
                <div className="monitoring-vital-card__top">
                  <div className="monitoring-vital-card__icon">
                    <Icon className="material-symbols-outlined" name="spo2" />
                  </div>
                  <StatusBadge
                    status={getSpO2Status()}
                    size="small"
                    label={spo2 === null
                      ? t("patient.monitoring.waitingDeviceDataShort")
                      : t("patient.monitoring.readingAvailable")}
                    showIcon={false}
                  />
                </div>
                <div className="monitoring-vital-card__content">
                  <span className="monitoring-vital-card__label">SpO2</span>
                  <span className="monitoring-vital-card__value">
                    {spo2 === null ? "--" : Math.round(spo2)} <small>%</small>
                  </span>
                </div>
                <div className="monitoring-vital-card__range" aria-hidden="true">
                  <span style={{ width: `${getRangePercent(spo2, 88, 100)}%` }} />
                </div>
                <small className="monitoring-vital-card__reference">
                  {t("patient.monitoring.spo2Reference")}
                </small>
              </article>

              {/* Fetal Heart Rate Status Card */}
              <article
                className={`monitoring-vital-card monitoring-vital-card--${getFHRStatus()}`}
              >
                <div className="monitoring-vital-card__top">
                  <div className="monitoring-vital-card__icon monitoring-vital-card__icon--fetal">
                    <Icon className="material-symbols-outlined" name="cardiology" />
                  </div>
                  <StatusBadge
                    status={getFHRStatus()}
                    size="small"
                    label={getStatusLabel(getFHRStatus(), t("patient.common.monitorAgain"))}
                    showIcon={false}
                  />
                </div>
                <div className="monitoring-vital-card__content">
                  <span className="monitoring-vital-card__label">
                    {t("patient.monitoring.fetalHr")}
                  </span>
                  <span className="monitoring-vital-card__value">
                    {formatBpm(currentFHR)} <small>bpm</small>
                  </span>
                </div>
                <div className="monitoring-vital-card__range" aria-hidden="true">
                  <span style={{ width: `${getRangePercent(currentFHR, 90, 180)}%` }} />
                </div>
                <small className="monitoring-vital-card__reference">
                  {t("patient.monitoring.fhrReference")}
                </small>
              </article>
            </div>
          </section>

          {/* Signal waveforms are optional details; patients do not need to interpret them. */}
          <details className="monitoring-technical-details">
            <summary>
              <Icon className="material-symbols-outlined" name="monitoring" />
              <span>
                <strong>{t("patient.monitoring.technicalDetailsTitle")}</strong>
                <small>{t("patient.monitoring.technicalDetailsDesc")}</small>
              </span>
              <Icon
                className="material-symbols-outlined monitoring-technical-details__chevron"
                name="expand_more"
              />
            </summary>
          <section className="monitoring-waveform-group">
            <div className="monitoring-section-heading monitoring-section-heading--signals">
              <div>
                <span>{t("patient.monitoring.signalPipeline")}</span>
                <h3>{t("patient.monitoring.waveformSection")}</h3>
              </div>
              <p>{t("patient.monitoring.waveformHint")}</p>
            </div>

            <div
              className="monitoring-signal-tabs"
              role="tablist"
              aria-label={t("patient.monitoring.signalTabsLabel")}
            >
              {SIGNAL_VIEW_OPTIONS.map((view) => (
                <button
                  key={view}
                  type="button"
                  role="tab"
                  aria-selected={activeSignalView === view}
                  className={`monitoring-signal-tab${
                    activeSignalView === view
                      ? " monitoring-signal-tab--active"
                      : ""
                  }`}
                  onClick={() => setActiveSignalView(view)}
                >
                  <Icon
                    className="material-symbols-outlined"
                    name={view === "all"
                      ? "stacked_line_chart"
                      : view === "fhr"
                        ? "cardiology"
                        : view === "contraction"
                          ? "compress"
                          : "analytics"}
                  />
                  {t(
                    `patient.monitoring.signalView${
                      view.charAt(0).toUpperCase() + view.slice(1)
                    }`,
                  )}
                </button>
              ))}
            </div>

            <div className="monitoring-waveform-stack">
              {showFhrSignal && (
                <div className="monitoring-waveform monitoring-waveform--fhr">
                  <div className="monitoring-waveform__header">
                    <h3 className="monitoring-waveform__label">
                      {t("patient.monitoring.fhrWaveform")}
                    </h3>
                    <span className="monitoring-waveform__live-chip">
                      {t("patient.common.running")}
                    </span>
                  </div>
                  <WaveformChart
                    data={fhrHistory}
                    isLive={isLiveTelemetry}
                    height={180}
                    showGrid={true}
                    showMarkers={true}
                    signalQuality={signalQuality}
                    markers={[
                      ...(isAcceleration
                        ? [
                            {
                              position: fhrHistory.length - 5,
                              type: "acceleration",
                              label: "A",
                            },
                          ]
                        : []),
                      ...(isDeceleration
                        ? [
                            {
                              position: fhrHistory.length - 5,
                              type: "deceleration",
                              label: "D",
                            },
                          ]
                        : []),
                    ]}
                  />
                  <div className="monitoring-waveform__legend">
                    <span>
                      <i className="monitoring-waveform__legend-dot monitoring-waveform__legend-dot--fhr" />
                      {t("patient.monitoring.fhrLegendReference")}
                    </span>
                    <span>
                      <i className="monitoring-waveform__legend-dot monitoring-waveform__legend-dot--signal" />
                      {t("patient.monitoring.signalQualityLegend", {
                        quality: getSignalQualityLabel(),
                      })}
                    </span>
                  </div>
                </div>
              )}

              {showContractionSignal && (
                <div className="monitoring-waveform monitoring-waveform--tokogram">
                  <div className="monitoring-waveform__header">
                    <h3 className="monitoring-waveform__label">
                      {t("patient.monitoring.contractionWaveform")}
                    </h3>
                    {contractionIntensity !== null && (
                      <span className="monitoring-waveform__contraction-badge">
                        {t("patient.monitoring.fsrReading")}{" "}
                        {contractionIntensityDisplay}%
                      </span>
                    )}
                  </div>
                  <WaveformChart
                    data={contractionHistory}
                    isLive={isLiveTelemetry}
                    height={120}
                    showGrid={true}
                    showMarkers={false}
                    signalQuality={signalQuality}
                  />
                  <div className="monitoring-waveform__axis-label">
                    <span>0%</span>
                    <span>{t("patient.monitoring.fsrAxis")}</span>
                    <span>100%</span>
                  </div>
                  <div className="monitoring-waveform__legend">
                    <span>
                      <i className="monitoring-waveform__legend-dot monitoring-waveform__legend-dot--contraction" />
                      {t("patient.monitoring.contractionLegend")}
                    </span>
                  </div>
                </div>
              )}

              {showEventSignal && (
                <section
                  className="monitoring-counters monitoring-counters--in-waveform"
                  aria-label={t("patient.monitoring.eventSummary")}
                >
                  <div className="monitoring-counter">
                    <Icon className="material-symbols-outlined" name="trending_up" />
                    <span className="monitoring-counter__value monitoring-counter__value--success">
                      {counters.accelerations ?? "--"}
                    </span>
                    <span className="monitoring-counter__label">
                      {t("monitoring.accelerations")}
                    </span>
                  </div>
                  <div className="monitoring-counter">
                    <Icon className="material-symbols-outlined" name="trending_down" />
                    <span className="monitoring-counter__value monitoring-counter__value--critical">
                      {counters.decelerations ?? "--"}
                    </span>
                    <span className="monitoring-counter__label">
                      {t("monitoring.decelerations")}
                    </span>
                  </div>
                  <div className="monitoring-counter">
                    <Icon className="material-symbols-outlined" name="child_care" />
                    <span className="monitoring-counter__value monitoring-counter__value--info">
                      {counters.movements ?? "--"}
                    </span>
                    <span className="monitoring-counter__label">
                      {t("monitoring.movements")}
                    </span>
                  </div>
                  <div className="monitoring-counter">
                    <Icon className="material-symbols-outlined" name="compress" />
                    <span className="monitoring-counter__value monitoring-counter__value--warning">
                      {counters.contractions ?? "--"}
                    </span>
                    <span className="monitoring-counter__label">
                      {t("patient.monitoring.contraction")}
                    </span>
                  </div>
                  <p className="monitoring-counters__note">
                    {t("patient.monitoring.eventLegend")}
                  </p>
                </section>
              )}
            </div>
          </section>
          </details>

          {/* Tombol Hentikan Pemantauan */}
          <button
            className="monitoring-stop-btn"
            onClick={() => { void handleToggleSession(); }}
            disabled={isStoppingSession}
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
            {isStoppingSession
              ? t("patient.monitoring.stopping")
              : t("monitoring.stopMonitoring")}
          </button>
        </>
      )}

      {/* Panel Sesi Dihentikan */}
      {!isMonitoringActive && (
        <div className="monitoring-stopped-panel">
          <div className="monitoring-stopped-panel__icon">
            <Icon className="material-symbols-outlined" name="check_circle" />
          </div>
          <h2>
            {sessionState === "completed"
              ? t("monitoring.sessionStopped")
              : t("patient.monitoring.sessionReady")}
          </h2>
          <p>
            {sessionState === "completed"
              ? t("monitoring.sessionStoppedDesc")
              : t("patient.monitoring.sessionReadyDesc")}
          </p>
          <div className="monitoring-stopped-panel__actions">
            <button
              className="monitoring-stopped-panel__resume"
              onClick={() => { void handleToggleSession(); }}
              disabled={isStartingSession || !isTelemetryFresh}
            >
              <svg
                viewBox="0 0 24 24"
                fill="currentColor"
                width="20"
                height="20"
              >
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              {isStartingSession
                ? t("patient.monitoring.preparingSession")
                : t("patient.monitoring.startSession")}
            </button>
            <button
              className="monitoring-stopped-panel__home"
              onClick={() => navigate("/patient/home")}
            >
              {t("patient.common.backHome")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default MonitoringScreen;
