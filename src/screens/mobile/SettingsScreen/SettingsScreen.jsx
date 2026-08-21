import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { t } from "../../../i18n";
import { useI18n } from "../../../i18n/useI18n";
import { useAuth } from "../../../context/useAuth";
import { useTheme } from "../../../context/useTheme";
import { usePatientDevice } from "../../../context/usePatientDevice";
import FeedbackModal from "../../../components/FeedbackModal/FeedbackModal";
import Icon from "../../../components/Icon/Icon";
import {
  getPatientNetworkStatus,
  playPatientNotificationSound,
  requestLocationPermission,
  requestNotificationPermission,
  triggerPatientHaptic,
} from "../../../services/nativePatientFeatures";
import {
  getPatientPreferences,
  setPatientPreferences,
} from "../../../services/patientPreferences";
import api, { getApiErrorMessage } from "../../../services/api";
import { clearTelemetryRecordsForUser } from "../../../services/patientTelemetryQueue";
import "./SettingsScreen.css";

const ToggleButton = ({ active, label, disabled = false, onClick }) => (
  <button
    type="button"
    className={`toggle ${active ? "active" : ""}`}
    aria-pressed={active}
    aria-label={label}
    disabled={disabled}
    onClick={onClick}
  />
);

const formatBattery = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${Math.round(parsed)}%` : t("patient.common.unavailable");
};

const formatLastSync = (value, locale) => {
  if (!value) return t("patient.home.syncEmpty");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t("patient.home.syncEmpty");
  return date.toLocaleString(locale === "en" ? "en-US" : "id-ID", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const SettingsScreen = () => {
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const { isDarkMode, toggleTheme } = useTheme();
  const {
    deviceRegistryError,
    hasRegisteredDevice,
    isDeviceRegistryLoading,
    pairedDevice,
    refreshRegisteredDevices,
    registeredDevices,
    telemetry,
    disconnectDevice,
  } = usePatientDevice();
  const { locale: currentLocale, changeLocale } = useI18n();

  const [settings, setSettings] = useState(() => ({
    ...getPatientPreferences(user?.id),
    language: currentLocale,
  }));
  const [faqOpen, setFaqOpen] = useState(false);
  const [modalConfig, setModalConfig] = useState({ isOpen: false });
  const [isDeletingData, setIsDeletingData] = useState(false);

  useEffect(() => {
    setSettings((current) => ({
      ...current,
      ...getPatientPreferences(user?.id),
      language: currentLocale,
    }));
  }, [currentLocale, user?.id]);

  const patientProfile = user?.patientProfile;
  const patientName =
    patientProfile?.name || user?.email?.split("@")[0] || t("patient.settings.profileFallback");
  const patientInitial = patientName.trim().charAt(0).toUpperCase() || "P";
  const patientId = patientProfile?.id
    ? t("patient.settings.profileId", { id: String(patientProfile.id).slice(0, 8) })
    : t("patient.settings.profileIncomplete");
  const pregnancyWeek = patientProfile?.gestational_age_weeks
    ? `${patientProfile.gestational_age_weeks} ${t("home.weeks")}`
    : t("patient.common.unavailable");
  const primaryRegisteredDevice = registeredDevices.find((device) => device.status === "active")
    || registeredDevices[0]
    || null;
  const visibleDeviceName =
    pairedDevice?.name ||
    primaryRegisteredDevice?.display_name ||
    t("patient.settings.deviceDisconnected");
  const visibleDeviceStatus = pairedDevice
    ? t("patient.settings.connected")
    : primaryRegisteredDevice
      ? t(`patient.home.deviceStatus.${primaryRegisteredDevice.status}`)
      : t("patient.settings.offline");
  const visibleDeviceCopy = pairedDevice
    ? t("patient.settings.deviceReady")
    : primaryRegisteredDevice
      ? t("patient.settings.registeredDevicePairHint")
      : t("patient.settings.deviceRegisterHint");
  const openModal = (config) => setModalConfig({ ...config, isOpen: true });
  const closeModal = () =>
    setModalConfig((prev) => ({ ...prev, isOpen: false }));

  const handleLanguageChange = (lang) => {
    setSettings((prev) => ({ ...prev, language: lang }));
    changeLocale(lang); // Reactive: memicu re-render seluruh app
  };

  const commitPreferences = (nextPreferences) => {
    if (!user?.id) return;
    const persisted = setPatientPreferences(user.id, nextPreferences);
    setSettings((current) => ({ ...current, ...persisted }));
  };

  const showCapabilityError = (messageKey) => {
    openModal({
      title: t("patient.settings.permissionTitle"),
      message: t(messageKey),
      type: "warning",
      confirmText: t("patient.common.gotIt"),
    });
  };

  const handlePreferenceToggle = async (key) => {
    const enabled = !settings[key];
    try {
      if (enabled && (key === "pushNotifications" || key === "importantAlerts")) {
        const granted = await requestNotificationPermission();
        if (!granted) {
          showCapabilityError("patient.settings.notificationPermissionDenied");
          return;
        }
      }
      if (enabled && key === "uploadWifiOnly") {
        const network = await getPatientNetworkStatus();
        if (!network.canIdentifyWifi) {
          showCapabilityError("patient.settings.wifiDetectionUnavailable");
          return;
        }
      }
      if (enabled && key === "shareLocation") {
        const granted = await requestLocationPermission();
        if (!granted) {
          showCapabilityError("patient.settings.locationPermissionDenied");
          return;
        }
      }

      const nextPreferences = {
        ...settings,
        [key]: enabled,
        ...(key === "importantAlerts" && enabled ? { pushNotifications: true } : {}),
        ...(key === "pushNotifications" && !enabled ? { importantAlerts: false } : {}),
      };
      commitPreferences(nextPreferences);
      if (enabled && key === "soundAlerts") await playPatientNotificationSound();
      if (enabled && key === "hapticFeedback") await triggerPatientHaptic();
    } catch {
      showCapabilityError("patient.settings.permissionRequestFailed");
    }
  };

  const handleDeleteMonitoringData = async () => {
    setIsDeletingData(true);
    try {
      await api.patients.deleteMonitoringData();
      await clearTelemetryRecordsForUser(user.id);
      openModal({
        title: t("patient.settings.deleteSuccessTitle"),
        message: t("patient.settings.deleteSuccessMessage"),
        type: "success",
        confirmText: t("patient.common.gotIt"),
      });
    } catch (error) {
      openModal({
        title: t("patient.settings.deleteFailedTitle"),
        message: error?.response?.status === 409
          ? t("patient.settings.deleteActiveSessionMessage")
          : getApiErrorMessage(error),
        type: "error",
        confirmText: t("patient.common.gotIt"),
      });
    } finally {
      setIsDeletingData(false);
    }
  };

  const handleDeviceAction = async () => {
    if (pairedDevice) {
      await disconnectDevice();
      return;
    }

    navigate("/patient/home");
  };

  return (
    <div className="settings-screen">
      <header className="settings-header">
        <button
          type="button"
          className="settings-header__back"
          onClick={() => navigate("/patient/home")}
          aria-label={t("patient.common.backHome")}
        >
          <Icon className="material-symbols-outlined" name="arrow_back" />
        </button>
        <h1>{t("settings.title")}</h1>
      </header>

      <div className="settings-content">
        <section className="settings-section">
          <h2 className="settings-section__title">{t("settings.profile")}</h2>
          <div className="settings-profile">
            <div className="settings-profile__avatar">{patientInitial}</div>
            <div className="settings-profile__info">
              <h3>{patientName}</h3>
              <p>{patientId}</p>
            </div>
            <button
              type="button"
              className="settings-profile__edit"
              onClick={() => navigate("/patient/profile")}
            >
              {t("settings.editProfile")}
            </button>
          </div>
          <div className="settings-item settings-item--info">
            <span className="settings-item__label">{t("patient.settings.pregnancyAge")}</span>
            <span className="settings-item__value">{pregnancyWeek}</span>
          </div>
          <div className="settings-item settings-item--info">
            <span className="settings-item__label">{t("patient.settings.connectedClinic")}</span>
            <span className="settings-item__value">{t("patient.settings.notConnected")}</span>
          </div>
          <div className="settings-item settings-item--info">
            <span className="settings-item__label">{t("patient.settings.clinician")}</span>
            <span className="settings-item__value">{t("patient.settings.notAssigned")}</span>
          </div>
        </section>

        <section className="settings-section">
          <h2 className="settings-section__title">
            {t("settings.device.title")}
          </h2>
          <div className="settings-device">
            <div className="settings-device__icon">
              <Icon className="material-symbols-outlined" name="sensors" />
            </div>
            <div className="settings-device__info">
              <h4>{visibleDeviceName}</h4>
              <p>{visibleDeviceCopy}</p>
            </div>
            <div className="settings-device__status">
              <span
                className={`settings-device__status-label ${
                  pairedDevice
                    ? "settings-device__status-label--online"
                    : hasRegisteredDevice
                      ? "settings-device__status-label--registered"
                      : ""
                }`}
              >
                {visibleDeviceStatus}
              </span>
            </div>
          </div>
          <div className="settings-device-registry">
            <Icon className="material-symbols-outlined" name="inventory_2" />
            <div>
              <strong>{t("patient.settings.deviceRegistry")}</strong>
              <p>
                {isDeviceRegistryLoading
                  ? t("patient.home.deviceRegistryLoading")
                  : deviceRegistryError
                    ? t("patient.home.deviceRegistryUnavailable")
                    : hasRegisteredDevice
                      ? t("patient.settings.registeredDeviceCount", {
                          count: registeredDevices.length,
                        })
                      : t("patient.home.noRegisteredDevice")}
              </p>
            </div>
          </div>
          <div className="settings-item settings-item--info">
            <span className="settings-item__label">{t("patient.settings.deviceBattery")}</span>
            <span className="settings-item__value">
              {formatBattery(telemetry.battery)}
            </span>
          </div>
          <div className="settings-item settings-item--info">
            <span className="settings-item__label">
              {t("settings.device.lastSync")}
            </span>
            <span className="settings-item__value">
              {formatLastSync(telemetry.lastSync, currentLocale)}
            </span>
          </div>
          <button
            type="button"
            className="settings-btn settings-btn--outline"
            onClick={() => {
              void handleDeviceAction();
            }}
          >
            {pairedDevice ? t("settings.device.unpair") : t("patient.settings.openPairing")}
          </button>
          <button
            type="button"
            className="settings-btn settings-btn--link"
            disabled={isDeviceRegistryLoading}
            onClick={() => {
              void refreshRegisteredDevices();
            }}
          >
            {t("patient.settings.refreshDeviceRegistry")}
          </button>
        </section>

        <section className="settings-section">
          <h2 className="settings-section__title">{t("patient.settings.deviceConnection")}</h2>
          <p className="settings-section__desc">
            {t("patient.settings.connectionDesc")}
          </p>

          <button
            type="button"
            className="settings-connection-card"
            onClick={() => navigate("/patient/home")}
          >
            <div className="settings-connection-card__icon settings-connection-card__icon--ble">
              <Icon className="material-symbols-outlined" name="bluetooth" />
            </div>
            <div className="settings-connection-card__content">
              <h4>{t("patient.settings.bleTitle")}</h4>
              <p>{t("patient.settings.bleDesc")}</p>
            </div>
          </button>

          <button
            type="button"
            className="settings-connection-card"
            onClick={() => openModal({
              title: t("patient.settings.internetTitle"),
              message: t("patient.settings.internetStatusMessage"),
              type: "info",
              confirmText: t("patient.common.gotIt"),
            })}
          >
            <div className="settings-connection-card__icon settings-connection-card__icon--mqtt">
              <Icon className="material-symbols-outlined" name="cloud" />
            </div>
            <div className="settings-connection-card__content">
              <h4>{t("patient.settings.internetTitle")}</h4>
              <p>{t("patient.settings.internetDesc")}</p>
            </div>
          </button>
        </section>

        <section className="settings-section">
          <h2 className="settings-section__title">
            {t("settings.notifications.title")}
          </h2>
          <p className="settings-section__desc">{t("patient.settings.notificationFeatureDesc")}</p>
          <div className="settings-item">
            <span className="settings-item__label">
              {t("settings.notifications.push")}
            </span>
            <ToggleButton
              active={settings.pushNotifications}
              label={t("settings.notifications.push")}
              onClick={() => { void handlePreferenceToggle("pushNotifications"); }}
            />
          </div>
          <div className="settings-item">
            <span className="settings-item__label">{t("patient.settings.importantAlerts")}</span>
            <ToggleButton
              active={settings.importantAlerts}
              label={t("patient.settings.importantAlerts")}
              onClick={() => { void handlePreferenceToggle("importantAlerts"); }}
            />
          </div>
          <div className="settings-item">
            <span className="settings-item__label">
              {t("settings.notifications.sound")}
            </span>
            <ToggleButton
              active={settings.soundAlerts}
              label={t("settings.notifications.sound")}
              onClick={() => { void handlePreferenceToggle("soundAlerts"); }}
            />
          </div>
          <div className="settings-item">
            <span className="settings-item__label">{t("patient.settings.haptic")}</span>
            <ToggleButton
              active={settings.hapticFeedback}
              label={t("patient.settings.haptic")}
              onClick={() => { void handlePreferenceToggle("hapticFeedback"); }}
            />
          </div>
        </section>

        <section className="settings-section">
          <h2 className="settings-section__title">
            {t("settings.privacy.title")}
          </h2>
          <p className="settings-section__desc">{t("patient.settings.privacyFeatureDesc")}</p>
          <div className="settings-item">
            <div className="settings-item__content">
              <span className="settings-item__label">
                {t("settings.privacy.wifiOnly")}
              </span>
              <span className="settings-item__desc">
                {t("patient.settings.wifiDesc")}
              </span>
            </div>
            <ToggleButton
              active={settings.uploadWifiOnly}
              label={t("settings.privacy.wifiOnly")}
              onClick={() => { void handlePreferenceToggle("uploadWifiOnly"); }}
            />
          </div>
          <div className="settings-item">
            <div className="settings-item__content">
              <span className="settings-item__label">
                {t("settings.privacy.locationShare")}
              </span>
              <span className="settings-item__desc">
                {t("patient.settings.locationDesc")}
              </span>
            </div>
            <ToggleButton
              active={settings.shareLocation}
              label={t("settings.privacy.locationShare")}
              onClick={() => { void handlePreferenceToggle("shareLocation"); }}
            />
          </div>
          <button
            type="button"
            className="settings-btn settings-btn--link"
            onClick={() => openModal({
              title: t("settings.privacy.dataRetention"),
              message: t("patient.settings.retentionMessage"),
              type: "info",
              confirmText: t("patient.common.gotIt"),
            })}
          >
            {t("settings.privacy.dataRetention")}
          </button>
          <button
            type="button"
            className="settings-btn settings-btn--link settings-btn--danger"
            disabled={isDeletingData}
            onClick={() => openModal({
              title: t("patient.settings.deleteConfirmTitle"),
              message: t("patient.settings.deleteConfirmMessage"),
              type: "warning",
              confirmText: t("patient.settings.deleteConfirmAction"),
              onConfirm: () => { void handleDeleteMonitoringData(); },
            })}
          >
            {isDeletingData ? t("patient.settings.deletingData") : t("settings.privacy.deleteData")}
          </button>
        </section>

        <section className="settings-section">
          <h2 className="settings-section__title">{t("settings.language")}</h2>
          <div className="settings-language">
            <button
              type="button"
              className={`settings-language__btn ${settings.language === "id" ? "active" : ""}`}
              onClick={() => handleLanguageChange("id")}
            >
              {t("settings.indonesian")}
            </button>
            <button
              type="button"
              className={`settings-language__btn ${settings.language === "en" ? "active" : ""}`}
              onClick={() => handleLanguageChange("en")}
            >
              {t("settings.english")}
            </button>
          </div>
        </section>

        <section className="settings-section">
          <h2 className="settings-section__title">{t("patient.settings.appearance")}</h2>
          <div className="settings-item">
            <div className="settings-item__content">
              <span className="settings-item__label">{t("patient.settings.darkMode")}</span>
            </div>
            <ToggleButton
              active={isDarkMode}
              onClick={toggleTheme}
              label={t("patient.settings.darkMode")}
            />
          </div>
        </section>

        <section className="settings-section">
          <h2 className="settings-section__title">{t("settings.about")}</h2>
          <button
            type="button"
            className="settings-btn settings-btn--link"
            onClick={() => navigate("/patient/education")}
          >
            {t("patient.settings.userGuide")}
          </button>
          <button
            type="button"
            className="settings-btn settings-btn--link"
            onClick={() => setFaqOpen((prev) => !prev)}
          >
            FAQ
            <Icon
              className="material-symbols-outlined"
              name="chevron_right"
              style={{
                transform: faqOpen ? "rotate(90deg)" : "none",
                transition: "transform 0.2s",
                marginLeft: "auto",
              }}
            />
          </button>
          {faqOpen && (
            <div className="settings-faq-panel">
              <div className="settings-faq-item">
                <h4>{t("patient.settings.faqWhatTitle")}</h4>
                <p>{t("patient.settings.faqWhatDesc")}</p>
              </div>
              <div className="settings-faq-item">
                <h4>{t("patient.settings.faqReplaceTitle")}</h4>
                <p>{t("patient.settings.faqReplaceDesc")}</p>
              </div>
            </div>
          )}
          <button
            type="button"
            className="settings-btn settings-btn--link"
            onClick={() => window.dispatchEvent(new CustomEvent("fetalguard:open-emergency"))}
          >
            {t("patient.settings.support")}
          </button>
          <button
            type="button"
            className="settings-btn settings-btn--link"
            onClick={() => openModal({
              title: t("settings.privacyPolicy"),
              message: t("patient.settings.privacyPolicyMessage"),
              type: "info",
              confirmText: t("patient.common.gotIt"),
            })}
          >
            {t("settings.privacyPolicy")}
          </button>
        </section>

        <div className="settings-version">
          <p>FETAL-GUARD v1.0.0</p>
          <p>
            {t("patient.settings.versionNote")}
          </p>
        </div>

        <button
          type="button"
          className="settings-logout"
          onClick={() =>
            openModal({
              title: t("patient.settings.logoutTitle"),
              message: t("patient.settings.logoutMessage"),
              type: "info",
              confirmText: t("settings.logout"),
              onConfirm: () => {
                logout();
                navigate("/login");
              },
            })
          }
        >
          <Icon className="material-symbols-outlined" name="logout" />
          {t("settings.logout")}
        </button>
      </div>

      <FeedbackModal {...modalConfig} onClose={closeModal} />
    </div>
  );
};

export default SettingsScreen;
