import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../../context/useAuth";
import { usePatientDevice } from "../../../context/usePatientDevice";
import { getWeeklyEducationArticle } from "../../../content/patientEducation";
import Icon from "../../../components/Icon/Icon";
import { t } from "../../../i18n";
import { useI18n } from "../../../i18n/useI18n";
import "./HomeScreen.css";

// ─── SVG Ring constants ────────────────────────────────────────────────────────
const RING_RADIUS = 44;
const RING_STROKE = 9;
const RING_CX = RING_RADIUS + RING_STROKE / 2; // 48.5
const RING_VIEWBOX = RING_CX * 2; // 97
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS; // ≈ 276.46

// ─── Pure helpers ──────────────────────────────────────────────────────────────

const getNumericValue = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const formatPercent = (value) => {
  const numeric = getNumericValue(value);
  if (numeric === null) return "--";
  return `${Math.round(numeric)}%`;
};

const formatLastSync = (value, locale) => {
  if (!value) return t("patient.home.syncEmpty");

  const syncDate = new Date(value);
  if (Number.isNaN(syncDate.getTime())) return t("patient.home.syncEmpty");

  const diffMs = Date.now() - syncDate.getTime();
  if (diffMs < -60 * 1000) {
    return syncDate.toLocaleString(locale === "en" ? "en-US" : "id-ID");
  }
  if (diffMs < 60 * 1000) return t("patient.home.syncNow");

  const diffMinutes = Math.floor(diffMs / (60 * 1000));
  if (diffMinutes < 60) return t("patient.home.minutesAgo", { count: diffMinutes });

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return t("patient.home.hoursAgo", { count: diffHours });

  return syncDate.toLocaleDateString(locale === "en" ? "en-US" : "id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
};

const getGreeting = () => {
  const hour = new Date().getHours();
  if (hour < 11) return t("patient.home.greetingMorning");
  if (hour < 15) return t("patient.home.greetingNoon");
  if (hour < 18) return t("patient.home.greetingAfternoon");
  return t("patient.home.greetingNight");
};

const getFhrStatus = (fhr) => {
  const numeric = getNumericValue(fhr);
  if (numeric === null) return { label: t("patient.home.fhrWaiting"), tone: "neutral" };
  // Threshold FHR rujukan 110–160 bpm — JANGAN ubah tanpa approval klinis
  if (numeric >= 110 && numeric <= 160)
    return { label: t("patient.home.fhrReference"), tone: "success" };
  return { label: t("patient.home.fhrReview"), tone: "warning" };
};

const getBatteryTone = (battery) => {
  const numeric = getNumericValue(battery);
  if (numeric === null) return "neutral";
  if (numeric <= 20) return "warning";
  return "success";
};

const getSignalLabel = (signalQuality) => {
  const numeric = getNumericValue(signalQuality);
  if (numeric === null) return t("patient.home.signalUnavailable");
  if (numeric >= 80) return t("patient.home.signalGood");
  if (numeric >= 55) return t("patient.home.signalFair");
  return t("patient.home.signalCheck");
};

const getSignalTone = (signalQuality) => {
  const numeric = getNumericValue(signalQuality);
  if (numeric === null) return "neutral";
  return numeric >= 55 ? "success" : "warning";
};

const estimateRemainingSession = (battery) => {
  const numeric = getNumericValue(battery);
  if (numeric === null) return t("patient.home.batteryWaiting");
  if (numeric <= 20) return t("patient.home.batteryCharge");
  return t("patient.home.batteryLevelOnly");
};

/** Kembalikan label trimester + konteks singkat berdasarkan minggu kehamilan */
const getTrimesterLabel = (week) => {
  if (!week) return t("patient.home.trimesterUnknown");
  if (week <= 12) return t("patient.home.trimesterFirst");
  if (week <= 27) return t("patient.home.trimesterSecond");
  return t("patient.home.trimesterThird");
};

// ─── Atoms ────────────────────────────────────────────────────────────────────

/**
 * DeviceStatusPill
 * Menampilkan status koneksi sabuk. Saat terhubung, dot berdenyut (breathing).
 */
const DeviceStatusPill = ({ pairedDevice, pairingState, connectionState, isTelemetryFresh }) => {
  const isPaired = Boolean(pairedDevice);
  const isCurrent = isPaired && isTelemetryFresh;
  const label = connectionState === "reconnecting"
    ? t("patient.monitoring.reconnecting")
    : isCurrent
      ? t("patient.home.deviceConnected")
      : isPaired
        ? t("patient.monitoring.dataStale")
    : pairingState === "scanning"
      ? t("patient.home.deviceScanning")
      : pairingState === "pairing"
        ? t("patient.home.devicePairing")
        : t("patient.home.deviceDisconnected");

  const pillClass = [
    "home-status-pill",
    `home-status-pill--${isCurrent ? "success" : "neutral"}`,
    isCurrent ? "home-status-pill--breathing" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={pillClass}>
      <span className="home-status-pill__dot" />
      {label}
    </span>
  );
};

// ─── DevicePanel ──────────────────────────────────────────────────────────────

const DevicePanel = ({
  availableDevices,
  connectToDevice,
  disconnectDevice,
  deviceRegistryError,
  hasRegisteredDevice,
  isBleAvailable,
  isConnecting,
  isDeviceRegistryLoading,
  isScanning,
  isTelemetryFresh,
  connectionState,
  pairedDevice,
  pairingError,
  pairingState,
  registeredDevices,
  scanForDevice,
}) => (
  <section className="home-device" aria-labelledby="home-device-title">
    <div className="home-section-heading">
      <div>
        <p className="home-section-heading__eyebrow">{t("patient.home.deviceEyebrow")}</p>
        <h2 id="home-device-title">{t("patient.home.deviceTitle")}</h2>
      </div>
      <DeviceStatusPill
        pairedDevice={pairedDevice}
        pairingState={pairingState}
        connectionState={connectionState}
        isTelemetryFresh={isTelemetryFresh}
      />
    </div>

    {pairedDevice ? (
      <div className="home-device__connected">
        <div className="home-device__icon" aria-hidden="true">
          <Icon className="material-symbols-outlined" name="sensors" />
        </div>
        <div className="home-device__copy">
          <strong>{pairedDevice.name}</strong>
          <span>
            {t("patient.home.bleActive")}
          </span>
        </div>
        <button
          type="button"
          className="home-button home-button--ghost"
          onClick={disconnectDevice}
        >
          {t("patient.home.disconnectDevice")}
        </button>
      </div>
    ) : (
      <>
        <div className="home-device-registry" role="status">
          <div className="home-device-registry__header">
            <Icon className="material-symbols-outlined" name="inventory_2" />
            <strong>{t("patient.home.registeredDeviceTitle")}</strong>
          </div>
          {isDeviceRegistryLoading ? (
            <p>{t("patient.home.deviceRegistryLoading")}</p>
          ) : deviceRegistryError ? (
            <p>{t("patient.home.deviceRegistryUnavailable")}</p>
          ) : registeredDevices.length > 0 ? (
            <div className="home-device-registry__list">
              {registeredDevices.map((device) => (
                <span key={device.id} className="home-device-registry__chip">
                  {device.display_name || device.device_uid}
                  <small>{t(`patient.home.deviceStatus.${device.status}`)}</small>
                </span>
              ))}
            </div>
          ) : (
            <p>{t("patient.home.noRegisteredDevice")}</p>
          )}
        </div>

        <ol className="home-pairing-steps" aria-label={t("patient.home.pairingSteps")}>
          <li>{t("patient.home.pairStep1")}</li>
          <li>{t("patient.home.pairStep2")}</li>
          <li>{t("patient.home.pairStep3")}</li>
        </ol>

        <button
          type="button"
          className="home-button home-button--primary"
          onClick={() => {
            void scanForDevice();
          }}
          disabled={isScanning || isConnecting || isDeviceRegistryLoading || !hasRegisteredDevice}
        >
          <Icon className="material-symbols-outlined" name="bluetooth_searching" />
          {isScanning ? t("patient.home.scanLoading") : t("patient.home.scanButton")}
        </button>

        {!isBleAvailable && hasRegisteredDevice && (
          <p className="home-device__hint">
            {t("patient.home.bleUnavailableHint")}
          </p>
        )}

        {pairingError && (
          <p className="home-device__error" role="alert">
            {pairingError}
          </p>
        )}

        <div className="home-device-list" aria-live="polite">
          {availableDevices.map((device) => (
            <button
              key={device.deviceId}
              type="button"
              className="home-device-row"
              onClick={() => {
                void connectToDevice(device);
              }}
              disabled={isConnecting || !device.isRegistered}
            >
              <Icon className="material-symbols-outlined" name="sensors" />
              <span>
                <strong>{device.name}</strong>
                <small>
                  {!device.isRegistered
                    ? t("patient.home.deviceNotInRegistry")
                    : device.rssi
                    ? t("patient.home.deviceNear")
                    : t("patient.home.deviceReady")}
                </small>
              </span>
              <Icon className="material-symbols-outlined" name="chevron_right" />
            </button>
          ))}

          {!isScanning && availableDevices.length === 0 && (
            <p className="home-device-list__empty">
              {!hasRegisteredDevice
                ? t("patient.home.noRegisteredDeviceScan")
                : !isBleAvailable
                  ? t("patient.home.bleUnavailableHint")
                  : t("patient.home.deviceEmpty")}
            </p>
          )}
        </div>
      </>
    )}
  </section>
);

// ─── MetricCard ───────────────────────────────────────────────────────────────

const MetricCard = ({
  icon,
  label,
  value,
  helper,
  tone = "neutral",
  children,
}) => (
  <section className={`home-metric home-metric--${tone}`}>
    <div className="home-metric__header">
      <Icon className="material-symbols-outlined" name={icon} />
      <span>{label}</span>
    </div>
    <strong>{value}</strong>
    {helper && <p>{helper}</p>}
    {children}
  </section>
);

// ─── AlertRow ─────────────────────────────────────────────────────────────────

const AlertRow = ({ tone, title, message, action }) => (
  <article className={`home-alert-row home-alert-row--${tone}`}>
    <div className="home-alert-row__icon" aria-hidden="true">
      <Icon
        className="material-symbols-outlined"
        name={tone === "critical"
          ? "call"
          : tone === "warning"
            ? "priority_high"
            : tone === "success"
              ? "check"
              : "info"}
      />
    </div>
    <div>
      <strong>{title}</strong>
      <p>{message}</p>
      {action && <span>{action}</span>}
    </div>
  </article>
);

// ─── PregnancyHero ────────────────────────────────────────────────────────────

/**
 * PregnancyHero
 * Hero section dengan SVG circular progress ring.
 * – Saat pregnancyWeek ada → ring terisi sesuai proporsi minggu/40
 * – Saat pregnancyWeek null  → half-ring + shimmer animation
 */
const PregnancyHero = ({ pregnancyWeek }) => {
  const isNull = pregnancyWeek === null;
  // Null → tampilkan setengah ring agar ada konten visual
  const progress = isNull ? 0.5 : Math.min(pregnancyWeek / 40, 1);
  const offset = RING_CIRCUMFERENCE * (1 - progress);

  return (
    <section
      className="home-pregnancy-hero"
      aria-labelledby="home-pregnancy-title"
    >
      {/* Header: judul kiri, chip kanan */}
      <div className="home-section-heading">
        <div>
          <p className="home-section-heading__eyebrow">{t("patient.home.pregnancy")}</p>
          <h2 id="home-pregnancy-title">{t("home.pregnancyProgress")}</h2>
        </div>
        <span className="home-pregnancy-week-chip">{t("home.weekOf")}</span>
      </div>

      {/* Layout: ring kiri, info kanan */}
      <div className="home-pregnancy-hero__layout">
        {/* SVG Ring */}
        <div className="home-pregnancy-hero__ring" aria-hidden="true">
          <svg
            width={RING_VIEWBOX}
            height={RING_VIEWBOX}
            viewBox={`0 0 ${RING_VIEWBOX} ${RING_VIEWBOX}`}
          >
            <defs>
              <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#FF6B9A" />
                <stop offset="100%" stopColor="#4AA3FF" />
              </linearGradient>
            </defs>

            {/* Track background */}
            <circle
              cx={RING_CX}
              cy={RING_CX}
              r={RING_RADIUS}
              fill="none"
              stroke="#EEF2F7"
              strokeWidth={RING_STROKE}
            />

            {/* Progress arc — shimmer saat null */}
            <circle
              cx={RING_CX}
              cy={RING_CX}
              r={RING_RADIUS}
              fill="none"
              stroke="url(#ringGrad)"
              strokeWidth={RING_STROKE}
              strokeLinecap="round"
              strokeDasharray={RING_CIRCUMFERENCE}
              strokeDashoffset={offset}
              transform={`rotate(-90 ${RING_CX} ${RING_CX})`}
              className={isNull ? "home-pregnancy-ring--shimmer" : undefined}
            />

            {/* Center: angka minggu (22px bold) */}
            <text
              x={RING_CX}
              y={RING_CX - 12}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize="22"
              fontWeight="700"
              fontFamily="Inter, -apple-system, sans-serif"
              fill="var(--color-text-primary)"
            >
              {pregnancyWeek ?? "?"}
            </text>

            {/* Center: label "minggu" (10px) */}
            <text
              x={RING_CX}
              y={RING_CX + 8}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize="12"
              fontFamily="Inter, -apple-system, sans-serif"
              fill="var(--color-text-secondary)"
            >
              {t("patient.home.weekUnit")}
            </text>

            {/* Center: sub "dari 40" (8px) */}
            <text
              x={RING_CX}
              y={RING_CX + 20}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize="11"
              fontFamily="Inter, -apple-system, sans-serif"
              fill="var(--color-text-tertiary)"
            >
              {t("patient.home.ofForty")}
            </text>
          </svg>
        </div>

        {/* Info panel */}
        <div className="home-pregnancy-hero__info">
          <p className="home-pregnancy-hero__label">{t("home.gestationalAge")}</p>
          <strong className="home-pregnancy-hero__week">
            {pregnancyWeek != null
              ? `${pregnancyWeek} ${t("patient.home.weekUnit")}`
              : `-- ${t("patient.home.weekUnit")}`}
          </strong>
          <p className="home-pregnancy-hero__sub">
            {getTrimesterLabel(pregnancyWeek)}
          </p>
        </div>
      </div>
    </section>
  );
};

// ─── DailyTipCard ─────────────────────────────────────────────────────────────

/**
 * DailyTipCard
 * Tip harian dipilih berdasarkan tanggal hari ini (getDate() % 7).
 * Konten statis — tidak memerlukan fetch.
 */
const WeeklyEducationCard = ({ pregnancyWeek, locale, onOpen }) => {
  const article = getWeeklyEducationArticle(pregnancyWeek, locale);
  const numericWeek = Number(pregnancyWeek);
  const hasPregnancyWeek = Number.isFinite(numericWeek)
    && numericWeek >= 1
    && numericWeek <= 42;

  return (
    <section className={`home-tip-card home-tip-card--${article.tone}`} aria-labelledby="home-education-title">
      <div className="home-tip-card__header">
        <span className="home-tip-card__title">{t("patient.education.weeklyTitle")}</span>
        <span className="home-tip-card__badge">
          {hasPregnancyWeek
            ? t("patient.education.weekLabel", { week: Math.round(numericWeek) })
            : t("patient.education.generalLabel")}
        </span>
      </div>

      <div className="home-tip-card__body">
        <div className="home-tip-card__icon" aria-hidden="true">
          <Icon className="material-symbols-outlined" name={article.icon} />
        </div>

        <div className="home-tip-card__text">
          <strong id="home-education-title">{article.title}</strong>
          <p>{article.summary}</p>
        </div>
      </div>
      <div className="home-tip-card__footer">
        <span>
          {t("patient.education.sourceLabel")}: {article.sources[0].organization}
        </span>
        <button type="button" onClick={onOpen}>
          {t("patient.education.readMore")}
          <Icon className="material-symbols-outlined" name="arrow_forward" />
        </button>
      </div>
    </section>
  );
};

// ─── HomeScreen ───────────────────────────────────────────────────────────────

const HomeScreen = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const { locale } = useI18n();

  const {
    activeAlerts,
    alerts,
    availableDevices,
    connectToDevice,
    connectionState,
    disconnectDevice,
    deviceRegistryError,
    hasRegisteredDevice,
    isBleAvailable,
    isConnecting,
    isDeviceRegistryLoading,
    isScanning,
    isTelemetryFresh,
    pairedDevice,
    pairingError,
    pairingState,
    registeredDevices,
    scanForDevice,
    telemetry,
  } = usePatientDevice();

  const patientProfile = user?.patientProfile;
  const currentTelemetry = isTelemetryFresh ? telemetry : {};
  const patientName =
    patientProfile?.name || user?.email?.split("@")[0] || t("patient.home.userFallback");
  const patientInitial = patientName.trim().charAt(0).toUpperCase() || "P";
  const pregnancyWeek = getNumericValue(patientProfile?.gestational_age_weeks);
  const pregnancyText = pregnancyWeek
    ? `${pregnancyWeek} ${t("patient.home.weekUnit")}`
    : t("patient.home.profileIncomplete");
  const fhrStatus = getFhrStatus(currentTelemetry.fhr);
  const primaryAlert = activeAlerts[0] || alerts[0];
  const batteryTone = getBatteryTone(currentTelemetry.battery);
  const batteryPercent = getNumericValue(currentTelemetry.battery);

  const handlePrimaryAction = () => {
    if (pairedDevice) {
      navigate("/patient/monitoring");
      return;
    }
    if (!hasRegisteredDevice) {
      navigate("/patient/settings");
      return;
    }
    void scanForDevice();
  };

  return (
    <div className="home-screen">
      {/* ── Topbar ── */}
      <header className="home-topbar">
        <button
          type="button"
          className="home-profile-button"
          onClick={() => navigate("/patient/profile")}
          aria-label={t("patient.home.openProfile")}
        >
          {patientInitial}
        </button>

        <div className="home-topbar__copy">
          <span>{getGreeting()}</span>
          <strong>{patientName}</strong>
          <small>{pregnancyText}</small>
        </div>

        <button
          type="button"
          className="home-icon-button"
          onClick={() => navigate("/patient/notifications")}
          aria-label={t("patient.home.openNotifications")}
        >
          <Icon className="material-symbols-outlined" name="notifications" />
        </button>
      </header>

      {/* ── Main content ── */}
      <main className="home-content">
        {/* 1 ─ Safety note */}
        <section className="home-safety-note" aria-label={t("patient.home.safetyLabel")}>
          <Icon className="material-symbols-outlined" name="info" />
          <p>
            {t("patient.home.safetyNote")}
          </p>
        </section>

        {/* 2 ─ Pregnancy Hero (BARU) */}
        <PregnancyHero pregnancyWeek={pregnancyWeek} />

        {/* 3 ─ Daily Tips Card (BARU) */}
        <WeeklyEducationCard
          pregnancyWeek={pregnancyWeek}
          locale={locale}
          onOpen={() => navigate("/patient/education")}
        />

        {/* 4 ─ Device Panel */}
        <DevicePanel
          availableDevices={availableDevices}
          connectToDevice={connectToDevice}
          disconnectDevice={disconnectDevice}
          deviceRegistryError={deviceRegistryError}
          hasRegisteredDevice={hasRegisteredDevice}
          isBleAvailable={isBleAvailable}
          isConnecting={isConnecting}
          isDeviceRegistryLoading={isDeviceRegistryLoading}
          isScanning={isScanning}
          isTelemetryFresh={isTelemetryFresh}
          connectionState={connectionState}
          pairedDevice={pairedDevice}
          pairingError={pairingError}
          pairingState={pairingState}
          registeredDevices={registeredDevices}
          scanForDevice={scanForDevice}
        />

        {/* 5 ─ Summary Grid 2×2 */}
        <section className="home-summary-grid" aria-label={t("patient.home.summaryLabel")}>
          <MetricCard
            icon="battery_5_bar"
            label={t("patient.home.battery")}
            value={formatPercent(currentTelemetry.battery)}
            helper={estimateRemainingSession(currentTelemetry.battery)}
            tone={batteryTone}
          >
            <div className="home-battery-bar" aria-hidden="true">
              <span style={{ width: `${batteryPercent ?? 0}%` }} />
            </div>
          </MetricCard>

          <MetricCard
            icon="monitor_heart"
            label={t("patient.home.estimatedFhr")}
            value={currentTelemetry.fhr ? `${Math.round(currentTelemetry.fhr)} bpm` : "--"}
            helper={fhrStatus.label}
            tone={fhrStatus.tone}
          />

          <MetricCard
            icon="signal_cellular_alt"
            label={t("patient.home.signalQuality")}
            value={formatPercent(currentTelemetry.signalQuality)}
            helper={getSignalLabel(currentTelemetry.signalQuality)}
            tone={getSignalTone(currentTelemetry.signalQuality)}
          />

          <MetricCard
            icon="sync"
            label={t("patient.home.sync")}
            value={formatLastSync(telemetry.lastSync, locale)}
            helper={
              isTelemetryFresh
                ? t("patient.home.latestDeviceData")
                : pairedDevice
                  ? t("patient.monitoring.dataStale")
                  : t("patient.home.waitingPairing")
            }
          />
        </section>

        {/* 6 ─ Alert Panel */}
        <section
          className="home-alert-panel"
          aria-labelledby="home-alert-title"
        >
          <div className="home-section-heading">
            <div>
              <p className="home-section-heading__eyebrow">{t("patient.home.alertEyebrow")}</p>
              <h2 id="home-alert-title">{t("patient.home.currentStatus")}</h2>
            </div>
            <button
              type="button"
              onClick={() => navigate("/patient/notifications")}
            >
              {t("patient.home.viewAll")}
            </button>
          </div>

          {primaryAlert ? (
            <AlertRow
              tone={primaryAlert.tone}
              title={primaryAlert.title}
              message={primaryAlert.message}
              action={primaryAlert.action}
            />
          ) : (
            <AlertRow
              tone="neutral"
              title={t("patient.home.noActiveStatus")}
              message={t("patient.home.noActiveStatusDesc")}
            />
          )}

          <details className="home-alert-scale">
            <summary>{t("patient.home.alertLegendTitle")}</summary>
            <div aria-label={t("patient.home.alertScaleLabel")}>
              <AlertRow
                tone="success"
                title={t("patient.home.routineMonitoring")}
                message={t("patient.home.routineMonitoringDesc")}
              />
              <AlertRow
                tone="warning"
                title={t("patient.home.checkPlacement")}
                message={t("patient.home.checkPlacementDesc")}
              />
              <AlertRow
                tone="critical"
                title={t("patient.home.contactClinician")}
                message={t("patient.home.contactClinicianDesc")}
              />
            </div>
          </details>
        </section>

        {/* 7 ─ Primary Action Button */}
        <button
          type="button"
          className="home-primary-action"
          onClick={handlePrimaryAction}
          disabled={isScanning || isConnecting}
        >
          <Icon
            className="material-symbols-outlined"
            name={pairedDevice ? "play_circle" : "bluetooth"}
          />
          {pairedDevice
            ? t("patient.home.startMonitoring")
            : hasRegisteredDevice
              ? t("patient.home.pairDeviceFirst")
              : t("patient.home.registerDeviceFirst")}
        </button>
      </main>
    </div>
  );
};

export default HomeScreen;
