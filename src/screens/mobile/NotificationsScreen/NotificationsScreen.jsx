import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getLocale, t } from '../../../i18n';
import { useI18n } from '../../../i18n/useI18n';
import { usePatientDevice } from '../../../context/usePatientDevice';
import api, { isRequestCanceled } from '../../../services/api';
import { createRealtimeEventPoller } from '../../../services/realtimeEventPoller';
import Icon from '../../../components/Icon/Icon';
import './NotificationsScreen.css';

const mapToneToRiskLevel = (tone) => {
    if (tone === 'critical') return 'high';
    if (tone === 'warning') return 'medium';
    return 'low';
};

const getRiskLabel = (riskLevel) => {
    if (riskLevel === 'high') return t('patient.notifications.riskHigh');
    if (riskLevel === 'medium') return t('patient.notifications.riskMedium');
    return t('patient.notifications.riskLow');
};

const formatTime = (timeString, locale = getLocale()) => {
    if (!timeString) return '--';
    const date = new Date(timeString);
    if (Number.isNaN(date.getTime())) return '--';
    return date.toLocaleString(locale === 'en' ? 'en-US' : 'id-ID', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
};

const getNotificationTimeLabel = (notification, locale) => {
    if (notification.isLiveStatus) return t('patient.notifications.currentStatus');
    return formatTime(notification.created_at, locale);
};

const NotificationsScreen = () => {
    const navigate = useNavigate();
    const { locale } = useI18n();
    const {
        activeAlerts,
        markAlertHandled,
        pairedDevice,
        telemetry,
    } = usePatientDevice();
    const [serverNotifications, setServerNotifications] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const alertRequestControllerRef = useRef(null);

    const fetchAlerts = useCallback(async ({ silent = false } = {}) => {
        alertRequestControllerRef.current?.abort();
        const controller = new AbortController();
        alertRequestControllerRef.current = controller;
        if (!silent) setIsLoading(true);
        try {
            const data = await api.patients.listAlerts({ signal: controller.signal });
            if (controller.signal.aborted) return;
            setServerNotifications(data);
            setError(null);
        } catch (requestError) {
            if (!controller.signal.aborted && !isRequestCanceled(requestError)) setError(true);
        } finally {
            if (alertRequestControllerRef.current === controller) {
                alertRequestControllerRef.current = null;
                if (!silent) setIsLoading(false);
            }
        }
    }, []);

    useEffect(() => {
        void fetchAlerts();
        return () => alertRequestControllerRef.current?.abort();
    }, [fetchAlerts]);

    useEffect(() => {
        const poller = createRealtimeEventPoller({
            fetchEvents: ({ cursor, signal }) => api.patients.listRealtimeEvents({
                afterCursor: cursor,
                limit: 100,
                signal,
            }),
            onEvents: (events) => (
                events.some((event) => event.event_type.startsWith('alert.'))
                    ? fetchAlerts({ silent: true })
                    : undefined
            ),
            onHeartbeat: () => fetchAlerts({ silent: true }),
            initialDelayMs: 2_000,
            heartbeatIntervalMs: 60_000,
        });
        poller.start();
        return () => poller.stop();
    }, [fetchAlerts]);

    const deviceNotifications = useMemo(() => {
        const deviceFallback = locale === 'en'
            ? t('patient.notifications.deviceNotPaired')
            : t('patient.notifications.deviceNotPaired');

        return activeAlerts.map((alert) => ({
            id: `device-${alert.id}`,
            alertId: alert.id,
            title: alert.title,
            message: alert.message,
            action: alert.action,
            observed_at: telemetry.lastSync || null,
            risk_level: mapToneToRiskLevel(alert.tone),
            source: pairedDevice ? pairedDevice.name : deviceFallback,
            isDeviceAlert: true,
            isLiveStatus: true,
        }));
    }, [activeAlerts, pairedDevice, telemetry.lastSync, locale]);

    const notifications = useMemo(() => {
        const titleFallback = locale === 'en'
            ? t('patient.notifications.monitoringAlert')
            : t('patient.notifications.monitoringAlert');
        const sourceFallback = locale === 'en'
            ? t('patient.notifications.savedSession')
            : t('patient.notifications.savedSession');

        return [
            ...deviceNotifications,
            ...serverNotifications.map((notification) => ({
                ...notification,
                title: notification.title || titleFallback,
                source: notification.source || sourceFallback,
                isDeviceAlert: false,
                isLiveStatus: false,
            })),
        ];
    }, [deviceNotifications, serverNotifications, locale]);

    const showEmptyState = !isLoading && notifications.length === 0;
    const showServerNotice = error && deviceNotifications.length > 0;
    const errorMessage = t('patient.notifications.storedUnavailable');
    const openHelpOptions = () => {
        window.dispatchEvent(new CustomEvent('fetalguard:open-emergency'));
    };

    return (
        <div className="notifications-screen">
            <header className="notifications-header">
                <button
                    type="button"
                  className="notifications-header__back"
                  onClick={() => navigate('/patient/home')}
                  aria-label={t('patient.common.backHome')}
                >
                    <Icon className="material-symbols-outlined" name="arrow_back" />
                </button>
                <h1>{t('notifications.title')}</h1>
            </header>

            {showServerNotice && (
                <section className="notifications-inline-note" role="status">
                    <Icon className="material-symbols-outlined" name="info" />
                    <p>{errorMessage} {t('patient.notifications.serverNotice')}</p>
                </section>
            )}

            {isLoading && deviceNotifications.length === 0 ? (
                <div className="notifications-empty" role="status">
                    <p>{t('patient.notifications.loading')}</p>
                </div>
            ) : error && notifications.length === 0 ? (
                <section className="notifications-empty" role="alert">
                    <div className="notifications-empty__icon" aria-hidden="true">
                        <Icon className="material-symbols-outlined" name="notifications_off" />
                    </div>
                    <h2>{t('patient.notifications.emptyErrorTitle')}</h2>
                    <p>{errorMessage} {t('patient.notifications.pairToSeeAlerts')}</p>
                    <div className="notifications-empty__actions">
                        <button type="button" className="btn btn-primary" onClick={() => navigate('/patient/home')}>
                            {t('patient.notifications.pairDevice')}
                        </button>
                    </div>
                </section>
            ) : showEmptyState ? (
                <section className="notifications-empty" role="status">
                    <div className="notifications-empty__icon" aria-hidden="true">
                        <Icon className="material-symbols-outlined" name="notifications" />
                    </div>
                    <h2>{t('patient.notifications.emptyTitle')}</h2>
                    <p>{t('patient.notifications.emptyDesc')}</p>
                    <div className="notifications-empty__actions">
                        <button type="button" className="btn btn-primary" onClick={() => navigate('/patient/home')}>
                            {t('patient.notifications.pairDevice')}
                        </button>
                        <button type="button" className="btn btn-secondary" onClick={() => navigate('/patient/settings')}>
                            {t('patient.notifications.checkSettings')}
                        </button>
                    </div>
                </section>
            ) : (
                <section className="notifications-list" aria-label={t('patient.notifications.listLabel')}>
                    {notifications.map((notification) => (
                        <article
                            key={notification.id}
                            className={`notifications-card notifications-card--${notification.risk_level || 'medium'}`}
                        >
                            <div className="notifications-card__header">
                                <span>{getNotificationTimeLabel(notification, locale)}</span>
                                <strong>{getRiskLabel(notification.risk_level)}</strong>
                            </div>
                            <h2>{notification.title}</h2>
                            <p>{notification.message}</p>
                            <div className="notifications-card__footer">
                                <span>{notification.source}</span>
                                {notification.observed_at && (
                                    <span>
                                        {t('patient.notifications.updatedAt', {
                                            time: formatTime(notification.observed_at, locale),
                                        })}
                                    </span>
                                )}
                                {notification.action && <span>{notification.action}</span>}
                            </div>
                            {notification.risk_level !== 'low' && (
                                <div className="notifications-card__actions">
                                    {notification.risk_level === 'high' && (
                                        <button
                                            type="button"
                                            className="notifications-card__action notifications-card__action--help"
                                            onClick={openHelpOptions}
                                        >
                                            {t('patient.notifications.openHelp')}
                                        </button>
                                    )}
                                    {notification.isDeviceAlert && (
                                        <button
                                            type="button"
                                            className="notifications-card__action"
                                            onClick={() => markAlertHandled(notification.alertId)}
                                        >
                                            {t('patient.notifications.markHandled')}
                                        </button>
                                    )}
                                </div>
                            )}
                        </article>
                    ))}
                </section>
            )}

            <div className="notifications-info">
                <p>
                    <Icon className="material-symbols-outlined" name="info" />
                    {t('patient.notifications.safetyNote')}
                </p>
            </div>
        </div>
    );
};

export default NotificationsScreen;
