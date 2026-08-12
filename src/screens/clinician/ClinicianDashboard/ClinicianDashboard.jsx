import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { t } from '../../../i18n';
import { useI18n } from '../../../i18n/useI18n';
import api, {
  AUTH_SCOPE_CHANGED_EVENT,
  clearStoredOrganizationId,
  getApiErrorMessage,
  getStoredOrganizationId,
  isAuthorizationDeniedError,
  isRequestCanceled,
  setStoredOrganizationId,
} from '../../../services/api';
import { createRealtimeEventPoller } from '../../../services/realtimeEventPoller';
import { useTheme } from '../../../context/useTheme';
import { useAuth } from '../../../context/useAuth';
import FeedbackModal from '../../../components/FeedbackModal/FeedbackModal';
import BrandLogo from '../../../components/BrandLogo/BrandLogo';
import Icon from '../../../components/Icon';
import {
  RISK_PRIORITY,
  getClinicianCopy,
  getRiskFilters,
  getStatusFilters,
  mapAlertsBySession,
  normalizeClinicianStatistics,
  formatAggregateCount,
  toPatientViewModel,
  toAlertViewModel,
  exportPatientCsv,
} from '../../../utils/clinicianModels';
import {
  formatDateLong,
  formatRelativeTime,
} from '../../../utils/formatters';
import RiskBadge from './components/RiskBadge';
import DataAvailability from './components/DataAvailability';
import AlertsTab from './components/AlertsTab';
import PatientDetailPanel from './components/PatientDetailPanel';
import './ClinicianDashboard.css';

const DASHBOARD_HEARTBEAT_INTERVAL_MS = 45_000;
const STALE_AFTER_MS = 90_000;

const ClinicianDashboard = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const [selectedPatientRecord, setSelectedPatientRecord] = useState(null);
  const [activeTab, setActiveTab] = useState('patients');
  const [acknowledgedAlerts, setAcknowledgedAlerts] = useState([]);
  const [pendingAlertIds, setPendingAlertIds] = useState([]);
  const [patients, setPatients] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [clinicianStatistics, setClinicianStatistics] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [dashboardError, setDashboardError] = useState('');
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const [now, setNow] = useState(() => Date.now());
  const [showAcknowledgedAlerts, setShowAcknowledgedAlerts] = useState(true);
  const [modalConfig, setModalConfig] = useState({ isOpen: false });
  const [organizationMemberships, setOrganizationMemberships] = useState([]);
  const [selectedOrganizationId, setSelectedOrganizationIdState] = useState(
    () => getStoredOrganizationId(),
  );
  const [isOrganizationContextReady, setIsOrganizationContextReady] = useState(false);

  const requestSequenceRef = useRef(0);
  const requestControllerRef = useRef(null);
  const patientDetailControllerRef = useRef(null);
  const currentUserIdRef = useRef(null);
  const pendingAlertIdsRef = useRef(new Set());
  const { locale } = useI18n();
  const { isDarkMode, toggleTheme } = useTheme();
  const { logout, user } = useAuth();

  const clinicianCopy = useMemo(() => getClinicianCopy(locale), [locale]);
  const riskFilters = useMemo(() => getRiskFilters(locale), [locale]);
  const statusFilters = useMemo(() => getStatusFilters(locale), [locale]);

  const openModal = (config) => setModalConfig({ ...config, isOpen: true });
  const closeModal = () => setModalConfig((current) => ({ ...current, isOpen: false }));

  const clearSensitiveDashboardState = useCallback(() => {
    setPatients([]);
    setAlerts([]);
    setClinicianStatistics(null);
    setAcknowledgedAlerts([]);
    pendingAlertIdsRef.current.clear();
    setPendingAlertIds([]);
    setSelectedPatientId(null);
    setSelectedPatientRecord(null);
    patientDetailControllerRef.current?.abort();
    patientDetailControllerRef.current = null;
    setLastUpdatedAt(null);
    setDashboardError('');
    setIsRefreshing(false);
    setActiveTab('patients');
    setModalConfig({ isOpen: false });
  }, []);

  useEffect(() => {
    const searchTimer = window.setTimeout(() => {
      setDebouncedSearchQuery(searchQuery.trim());
    }, 300);

    return () => window.clearTimeout(searchTimer);
  }, [searchQuery]);

  useEffect(() => {
    currentUserIdRef.current = user?.id || null;
    requestSequenceRef.current += 1;
    requestControllerRef.current?.abort();
    clearSensitiveDashboardState();
  }, [clearSensitiveDashboardState, user?.id]);

  useEffect(() => {
    let canceled = false;
    setOrganizationMemberships([]);
    setIsOrganizationContextReady(false);
    if (!user?.id) return () => { canceled = true; };

    api.organizations.listMine()
      .then((data) => {
        if (canceled) return;
        const memberships = Array.isArray(data?.items) ? data.items : [];
        setOrganizationMemberships(memberships);
        const storedOrganizationId = getStoredOrganizationId();
        const storedIsValid = memberships.some(
          (membership) => membership.organization.id === storedOrganizationId,
        );
        const nextOrganizationId = storedIsValid
          ? storedOrganizationId
          : memberships.length === 1
            ? memberships[0].organization.id
            : null;

        if (nextOrganizationId) {
          setSelectedOrganizationIdState(nextOrganizationId);
          setStoredOrganizationId(nextOrganizationId);
          setIsOrganizationContextReady(true);
        } else {
          setSelectedOrganizationIdState(null);
          clearStoredOrganizationId();
          setIsOrganizationContextReady(false);
        }
      })
      .catch((error) => {
        if (canceled || isRequestCanceled(error)) return;
        setOrganizationMemberships([]);
        setIsOrganizationContextReady(false);
        if (isAuthorizationDeniedError(error)) clearSensitiveDashboardState();
        setDashboardError(getApiErrorMessage(error));
      });

    return () => { canceled = true; };
  }, [clearSensitiveDashboardState, user?.id]);

  const loadDashboardData = useCallback(async ({ refreshOnly = false, silent = false } = {}) => {
    const requestUserId = user?.id || null;
    if (!requestUserId || !isOrganizationContextReady) {
      clearSensitiveDashboardState();
      setIsLoading(false);
      return;
    }

    const requestSequence = requestSequenceRef.current + 1;
    requestSequenceRef.current = requestSequence;
    requestControllerRef.current?.abort();
    const controller = new AbortController();
    requestControllerRef.current = controller;

    if (refreshOnly && !silent) {
      setIsRefreshing(true);
    } else if (!silent) {
      setIsLoading(true);
    }

    if (!silent) setDashboardError('');

    try {
      const [patientData, alertData, statisticsResult] = await Promise.all([
        api.clinician.listPatients({
          q: debouncedSearchQuery,
          risk: riskFilter,
          status: statusFilter,
          sort: riskFilter === 'all' ? 'recent' : 'risk',
          signal: controller.signal,
        }),
        api.clinician.listAlerts({ signal: controller.signal }),
        api.clinician.getStatistics({ signal: controller.signal })
          .then((value) => ({ status: 'fulfilled', value }))
          .catch((reason) => ({ status: 'rejected', reason })),
      ]);

      if (
        controller.signal.aborted
        || requestSequence !== requestSequenceRef.current
        || requestUserId !== currentUserIdRef.current
      ) {
        return;
      }

      if (
        statisticsResult.status === 'rejected'
        && isAuthorizationDeniedError(statisticsResult.reason)
      ) {
        clearSensitiveDashboardState();
        setDashboardError(getApiErrorMessage(statisticsResult.reason));
        return;
      }

      const patientItems = Array.isArray(patientData) ? patientData : patientData?.items || [];
      const alertItems = Array.isArray(alertData) ? alertData : alertData?.items || [];
      const normalizedStatistics = statisticsResult.status === 'fulfilled'
        ? normalizeClinicianStatistics(statisticsResult.value)
        : null;
      setPatients(patientItems);
      setAlerts(alertItems);
      setClinicianStatistics(normalizedStatistics);
      setAcknowledgedAlerts(
        alertItems
          .filter((alert) => alert.is_acknowledged)
          .map((alert) => alert.id),
      );
      setLastUpdatedAt(new Date().toISOString());
      setDashboardError(
        normalizedStatistics ? '' : t('clinician.statisticsUnavailable'),
      );
    } catch (error) {
      if (
        isRequestCanceled(error)
        || requestSequence !== requestSequenceRef.current
        || requestUserId !== currentUserIdRef.current
      ) {
        return;
      }
      if (isAuthorizationDeniedError(error)) clearSensitiveDashboardState();
      setDashboardError(getApiErrorMessage(error));
    } finally {
      if (requestSequence === requestSequenceRef.current) {
        setIsLoading(false);
        setIsRefreshing(false);
        if (requestControllerRef.current === controller) requestControllerRef.current = null;
      }
    }
  }, [
    clearSensitiveDashboardState,
    debouncedSearchQuery,
    isOrganizationContextReady,
    riskFilter,
    statusFilter,
    user?.id,
  ]);

  useEffect(() => {
    loadDashboardData();
    return () => requestControllerRef.current?.abort();
  }, [loadDashboardData]);

  useEffect(() => {
    const handleScopeChanged = () => {
      const nextOrganizationId = getStoredOrganizationId();
      setSelectedOrganizationIdState(nextOrganizationId);
      setIsOrganizationContextReady(Boolean(nextOrganizationId));
      requestSequenceRef.current += 1;
      requestControllerRef.current?.abort();
      clearSensitiveDashboardState();
      void loadDashboardData();
    };
    window.addEventListener(AUTH_SCOPE_CHANGED_EVENT, handleScopeChanged);
    return () => window.removeEventListener(AUTH_SCOPE_CHANGED_EVENT, handleScopeChanged);
  }, [clearSensitiveDashboardState, loadDashboardData]);

  const handleOrganizationChange = (event) => {
    const nextOrganizationId = event.target.value || null;
    setSelectedOrganizationIdState(nextOrganizationId);
    setIsOrganizationContextReady(Boolean(nextOrganizationId));
    if (nextOrganizationId) setStoredOrganizationId(nextOrganizationId);
    else clearStoredOrganizationId();
  };

  useEffect(() => {
    if (!user?.id || !isOrganizationContextReady || !selectedOrganizationId) return undefined;

    const poller = createRealtimeEventPoller({
      fetchEvents: ({ cursor, signal }) => api.clinician.listRealtimeEvents({
        afterCursor: cursor,
        limit: 100,
        signal,
      }),
      onEvents: () => loadDashboardData({ refreshOnly: true, silent: true }),
      onHeartbeat: () => loadDashboardData({ refreshOnly: true, silent: true }),
      initialDelayMs: 2_000,
      heartbeatIntervalMs: DASHBOARD_HEARTBEAT_INTERVAL_MS,
    });
    poller.start();
    return () => poller.stop();
  }, [
    isOrganizationContextReady,
    loadDashboardData,
    selectedOrganizationId,
    user?.id,
  ]);

  useEffect(() => {
    const clockTimer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(clockTimer);
  }, []);

  const alertsBySession = useMemo(() => mapAlertsBySession(alerts), [alerts]);
  const patientRows = useMemo(
    () => patients.map((patient) => toPatientViewModel(patient, alertsBySession, locale)),
    [patients, alertsBySession, locale],
  );
  const alertRows = useMemo(
    () => alerts.map((alert) => toAlertViewModel(alert, patients, locale)),
    [alerts, patients, locale],
  );

  const filteredPatients = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();

    return patientRows.filter((patient) => {
      const matchesSearch = !normalizedQuery ||
        patient.name.toLowerCase().includes(normalizedQuery) ||
        patient.patientCode.toLowerCase().includes(normalizedQuery);
      const matchesRisk = riskFilter === 'all' ||
        (riskFilter === 'alerts' && patient.activeAlerts > 0) ||
        patient.currentRisk === riskFilter;
      const matchesStatus = statusFilter === 'all' ||
        (statusFilter === 'active' && patient.isActiveMonitoring) ||
        (statusFilter === 'inactive' && !patient.isActiveMonitoring);

      return matchesSearch && matchesRisk && matchesStatus;
    });
  }, [patientRows, riskFilter, searchQuery, statusFilter]);

  useEffect(() => {
    if (
      selectedPatientId
      && !filteredPatients.some((patient) => patient.id === selectedPatientId)
    ) {
      setSelectedPatientId(null);
    }
  }, [filteredPatients, selectedPatientId]);

  useEffect(() => {
    patientDetailControllerRef.current?.abort();
    setSelectedPatientRecord(null);
    if (!selectedPatientId || !user?.id) return undefined;

    const controller = new AbortController();
    const requestedPatientId = selectedPatientId;
    const requestedUserId = user.id;
    patientDetailControllerRef.current = controller;

    api.clinician.getPatient(requestedPatientId, { signal: controller.signal })
      .then((patient) => {
        if (
          controller.signal.aborted
          || requestedPatientId !== selectedPatientId
          || requestedUserId !== currentUserIdRef.current
        ) return;
        setSelectedPatientRecord(patient);
      })
      .catch((error) => {
        if (isRequestCanceled(error)) return;
        setSelectedPatientId(null);
        setSelectedPatientRecord(null);
        if (isAuthorizationDeniedError(error)) clearSensitiveDashboardState();
        setDashboardError(getApiErrorMessage(error));
      })
      .finally(() => {
        if (patientDetailControllerRef.current === controller) {
          patientDetailControllerRef.current = null;
        }
      });

    return () => controller.abort();
  }, [clearSensitiveDashboardState, selectedPatientId, user?.id]);

  const selectedPatient = useMemo(() => (
    selectedPatientRecord?.id === selectedPatientId
      ? toPatientViewModel(selectedPatientRecord, alertsBySession, locale)
      : null
  ), [alertsBySession, locale, selectedPatientId, selectedPatientRecord]);

  const openAlerts = useMemo(
    () => alertRows.filter((alert) => !acknowledgedAlerts.includes(alert.id)),
    [acknowledgedAlerts, alertRows],
  );
  const prioritizedOpenAlerts = useMemo(
    () => [...openAlerts].sort((a, b) => (
      (RISK_PRIORITY[b.riskLevel] ?? RISK_PRIORITY.unknown)
      - (RISK_PRIORITY[a.riskLevel] ?? RISK_PRIORITY.unknown)
    )),
    [openAlerts],
  );
  const acknowledgedAlertRows = useMemo(
    () => alertRows.filter((alert) => acknowledgedAlerts.includes(alert.id)),
    [acknowledgedAlerts, alertRows],
  );

  const stats = clinicianStatistics || {
    total: null,
    monitoring: null,
    highRisk: null,
    alerts: null,
  };

  const pageTitle = {
    patients: t('clinician.dashboard'),
    alerts: t('clinician.alertQueue'),
    reports: t('clinician.reports'),
    settings: t('clinician.settings'),
  }[activeTab];

  const clinicianName = user?.email || t('clinician.clinicianFallback');
  const lastUpdatedLabel = lastUpdatedAt ? formatRelativeTime(lastUpdatedAt, locale) : t('clinician.neverUpdated');
  const lastUpdatedTime = lastUpdatedAt ? new Date(lastUpdatedAt).getTime() : 0;
  const isDataStale = lastUpdatedAt ? now - lastUpdatedTime > STALE_AFTER_MS : !isLoading;
  const priorityAlert = prioritizedOpenAlerts[0] || null;

  const handleAcknowledgeAlert = async (alertId, note = '') => {
    if (pendingAlertIdsRef.current.has(alertId)) return false;
    const requestUserId = user?.id || null;
    pendingAlertIdsRef.current.add(alertId);
    setPendingAlertIds((current) => current.includes(alertId) ? current : [...current, alertId]);
    requestSequenceRef.current += 1;
    requestControllerRef.current?.abort();
    setIsLoading(false);
    setIsRefreshing(false);
    try {
      const currentAlert = alerts.find((alert) => alert.id === alertId);
      const updatedAlert = await api.clinician.acknowledgeAlert(alertId, {
        note,
        expectedVersion: currentAlert?.version,
      });
      if (!requestUserId || requestUserId !== currentUserIdRef.current) return false;
      setAcknowledgedAlerts((current) => [...new Set([...current, alertId])]);
      setAlerts((current) => current.map((alert) => (
        alert.id === alertId ? updatedAlert : alert
      )));
      void loadDashboardData({ refreshOnly: true, silent: true });
      return true;
    } catch (err) {
      if (isRequestCanceled(err)) return false;
      if (isAuthorizationDeniedError(err)) clearSensitiveDashboardState();
      setDashboardError(getApiErrorMessage(err));
      return false;
    } finally {
      pendingAlertIdsRef.current.delete(alertId);
      setPendingAlertIds((current) => current.filter((id) => id !== alertId));
    }
  };

  const handleOpenPatient = (patient) => {
    setSelectedPatientId(patient.id);
    setActiveTab('patients');
  };

  const handleCallPatient = (patientName) => {
    openModal({
      title: t('clinician.contactPatientTitle'),
      message: t('clinician.contactPatientMessage', { name: patientName }),
      type: 'info',
      confirmText: t('clinician.understand'),
    });
  };

  const navItems = [
    { key: 'patients', label: t('clinician.dashboard'), icon: 'grid' },
    { key: 'alerts', label: t('clinician.alertQueue'), icon: 'bell', badge: stats.alerts },
    { key: 'reports', label: t('clinician.reports'), icon: 'file' },
    { key: 'settings', label: t('clinician.settings'), icon: 'settings' },
  ];

  return (
    <div className="clinician-dashboard">
      <aside className="dashboard-sidebar">
        <div className="dashboard-sidebar__brand">
          <BrandLogo variant="sidebar" />
          <span className="brand-subtitle">{t('clinician.brandSubtitle')}</span>
        </div>

        <nav className="dashboard-nav" aria-label={t('clinician.navLabel')}>
          {navItems.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`dashboard-nav__item ${activeTab === item.key ? 'is-active' : ''}`}
              onClick={() => setActiveTab(item.key)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.badge > 0 && <strong className="dashboard-nav__badge">{item.badge}</strong>}
            </button>
          ))}
        </nav>

        <div className="system-card">
          <span className="system-card__label">{t('clinician.statusDashboard')}</span>
          <strong>{t('clinician.earlyScreening')}</strong>
          <small>{t('clinician.notDiagnostic')}</small>
        </div>

        <button type="button" className="dashboard-nav__item dashboard-nav__item--logout" onClick={logout}>
          <Icon name="log-out" />
          <span>{t('clinician.logout')}</span>
        </button>
      </aside>

      <main className="dashboard-main">
        <header className="dashboard-header">
          <div className="dashboard-header__title">
            <h1>{pageTitle}</h1>
            <p>{formatDateLong(new Date(), locale)} - {t('clinician.headerSubtitle')}</p>
          </div>
          <div className="dashboard-header__actions">
            {organizationMemberships.length > 0 && (
              <label className="facility-context">
                <span>{t('clinician.facilityLabel')}</span>
                <select
                  value={selectedOrganizationId || ''}
                  onChange={handleOrganizationChange}
                  aria-label={t('clinician.facilityLabel')}
                >
                  {organizationMemberships.length > 1 && (
                    <option value="">{t('clinician.chooseFacility')}</option>
                  )}
                  {organizationMemberships.map((membership) => (
                    <option key={membership.id} value={membership.organization.id}>
                      {membership.organization.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <div className={`data-freshness ${isDataStale ? 'is-stale' : 'is-fresh'}`}>
              <span className="data-freshness__dot" aria-hidden="true" />
              <div>
                <strong>{isDataStale ? t('clinician.dataStale') : t('clinician.dataLive')}</strong>
                <small>{t('clinician.lastUpdated', { time: lastUpdatedLabel })}</small>
              </div>
            </div>
            <button
              type="button"
              className="header-action"
              onClick={() => loadDashboardData({ refreshOnly: true })}
              disabled={isRefreshing}
            >
              <Icon name="refresh" />
              {isRefreshing ? t('clinician.refreshing') : t('clinician.refresh')}
            </button>
            <button
              type="button"
              className="header-action header-action--icon"
              onClick={toggleTheme}
              aria-label={isDarkMode ? t('clinician.lightTheme') : t('clinician.darkTheme')}
            >
              <Icon name={isDarkMode ? 'sun' : 'moon'} />
            </button>
            <div className="clinician-profile">
              <div className="clinician-profile__avatar">
                <Icon name="user" />
              </div>
              <div>
                <strong>{clinicianName}</strong>
                <span>{t('clinician.clinicianRole')}</span>
              </div>
            </div>
          </div>
        </header>

        {dashboardError && (
          <div className="dashboard-feedback dashboard-feedback--error" role="alert">
            <span>{dashboardError}</span>
            <button type="button" onClick={() => loadDashboardData()}>
              {t('clinician.retry')}
            </button>
          </div>
        )}

        {isLoading && (
          <div className="dashboard-feedback">
            <span>{t('clinician.loadingDashboard')}</span>
          </div>
        )}

        {activeTab === 'patients' && (
          <>
            <section className="summary-grid" aria-label={t('clinician.summaryLabel')}>
              <article className="summary-card summary-card--teal">
                <div className="summary-card__icon"><Icon name="users" /></div>
                <div>
                  <span>{t('clinician.totalPatients')}</span>
                  <strong aria-label={stats.total === null ? t('clinician.notAvailable') : undefined}>
                    {formatAggregateCount(stats.total)}
                  </strong>
                  <small>{t('clinician.totalPatientsDesc')}</small>
                </div>
              </article>
              <article className="summary-card summary-card--blue">
                <div className="summary-card__icon"><Icon name="activity" /></div>
                <div>
                  <span>{t('clinician.activeMonitoring')}</span>
                  <strong aria-label={stats.monitoring === null ? t('clinician.notAvailable') : undefined}>
                    {formatAggregateCount(stats.monitoring)}
                  </strong>
                  <small>{t('clinician.activeMonitoringDesc')}</small>
                </div>
              </article>
              <article className="summary-card summary-card--amber">
                <div className="summary-card__icon"><Icon name="alert" /></div>
                <div>
                  <span>{t('clinician.highRisk')}</span>
                  <strong aria-label={stats.highRisk === null ? t('clinician.notAvailable') : undefined}>
                    {formatAggregateCount(stats.highRisk)}
                  </strong>
                  <small>{t('clinician.highRiskDesc')}</small>
                </div>
              </article>
              <article className="summary-card summary-card--red">
                <div className="summary-card__icon"><Icon name="bell" /></div>
                <div>
                  <span>{t('clinician.pendingAlerts')}</span>
                  <strong aria-label={stats.alerts === null ? t('clinician.notAvailable') : undefined}>
                    {formatAggregateCount(stats.alerts)}
                  </strong>
                  <small>{t('clinician.pendingAlertsDesc')}</small>
                </div>
              </article>
            </section>

            <section className="ops-strip" aria-label={t('clinician.operationsTitle')}>
              <article className={`ops-card ${priorityAlert ? 'ops-card--focus' : ''}`}>
                <div className="ops-card__icon"><Icon name={priorityAlert ? 'alert' : 'check'} /></div>
                <div>
                  <span>{t('clinician.topPriority')}</span>
                  <strong>{priorityAlert ? priorityAlert.patientName : t('clinician.noPendingAlert')}</strong>
                  <small>{priorityAlert ? priorityAlert.riskMeta.label : t('clinician.priorityQueueHint')}</small>
                </div>
                {priorityAlert?.patientId && (
                  <button type="button" onClick={() => {
                    setSelectedPatientId(priorityAlert.patientId);
                    setActiveTab('alerts');
                  }}>
                    {t('clinician.viewPatient')}
                  </button>
                )}
              </article>
              <article className="ops-card">
                <div className="ops-card__icon"><Icon name="activity" /></div>
                <div>
                  <span>{t('clinician.activeSessions')}</span>
                  <strong aria-label={stats.monitoring === null ? t('clinician.notAvailable') : undefined}>
                    {formatAggregateCount(stats.monitoring)}
                  </strong>
                  <small>{t('clinician.activeMonitoringDesc')}</small>
                </div>
              </article>
              <article className="ops-card">
                <div className="ops-card__icon"><Icon name="chart" /></div>
                <div>
                  <span>{t('clinician.dataCoverage')}</span>
                  <strong aria-label={t('clinician.notAvailable')}>—</strong>
                  <small>{t('clinician.sensorSummaryUnavailable')}</small>
                </div>
              </article>
            </section>

            <section className="workspace-panel">
              <div className="panel-heading">
                <div>
                  <h2>{t('clinician.patientMonitoringTitle')}</h2>
                  <p>{t('clinician.patientMonitoringDesc')}</p>
                </div>
                <button type="button" className="secondary-action" onClick={() => exportPatientCsv(filteredPatients, locale)}>
                  <Icon name="download" />
                  {t('clinician.exportCsv')}
                </button>
              </div>

              <div className="dashboard-toolbar">
                <label className="search-field">
                  <Icon name="search" />
                  <input
                    type="search"
                    placeholder={t('clinician.search')}
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                  />
                </label>
                <div className="segmented-control" role="group" aria-label={t('clinician.riskFilterLabel')}>
                  {riskFilters.map((filter) => (
                    <button
                      key={filter.key}
                      type="button"
                      className={riskFilter === filter.key ? 'is-selected' : ''}
                      onClick={() => setRiskFilter(filter.key)}
                    >
                      {filter.label}
                    </button>
                  ))}
                </div>
                <select
                  className="status-select"
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                  aria-label={t('clinician.statusFilterLabel')}
                >
                  {statusFilters.map((filter) => (
                    <option key={filter.key} value={filter.key}>{filter.label}</option>
                  ))}
                </select>
              </div>

              <div className="patient-table-wrapper">
                <table className="patient-table">
                  <thead>
                    <tr>
                      <th>{t('clinician.thPatient')}</th>
                      <th>{t('clinician.thGestation')}</th>
                      <th>{t('clinician.thSession')}</th>
                      <th>{t('clinician.thSignalFhr')}</th>
                      <th>{t('clinician.thEarlyRisk')}</th>
                      <th>{t('clinician.thAlert')}</th>
                      <th>{t('clinician.thAction')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPatients.map((patient) => (
                      <tr
                        key={patient.id}
                        className={`${selectedPatient?.id === patient.id ? 'is-selected' : ''} ${patient.activeAlerts > 0 ? 'has-alerts' : ''}`}
                        onClick={() => setSelectedPatientId(patient.id)}
                      >
                        <td>
                          <div className="patient-cell">
                            <span className="row-selector" aria-hidden="true">
                              {selectedPatient?.id === patient.id && <Icon name="check" />}
                            </span>
                            <span className="patient-avatar">{patient.initials}</span>
                            <span>
                              <strong>{patient.name}</strong>
                              <small>{patient.patientCode} - {patient.ageLabel}</small>
                            </span>
                          </div>
                        </td>
                        <td>
                          <strong>{patient.gestationalAgeLabel}</strong>
                          <small className="table-muted">{t('clinician.gestationCaption')}</small>
                        </td>
                        <td>
                          <span className={`session-pill ${patient.isActiveMonitoring ? 'session-pill--active' : ''}`}>
                            {patient.monitoringStatus}
                          </span>
                          <small className="table-muted">{patient.lastSessionTime}</small>
                        </td>
                        <td>
                          <div className="signal-stack">
                            <span>{patient.signalLabel}</span>
                            <small>{clinicianCopy.estimatedFhr}: {patient.fhrLabel}</small>
                          </div>
                        </td>
                        <td>
                          <RiskBadge risk={patient.currentRisk} />
                        </td>
                        <td>
                          {patient.activeAlerts > 0 ? (
                            <span className="alert-counter">{patient.activeAlerts}</span>
                          ) : (
                            <span className="empty-token">-</span>
                          )}
                        </td>
                        <td>
                          <div className="row-actions">
                            <button
                              type="button"
                              className="icon-button"
                              aria-label={t('clinician.viewPatientAria', { name: patient.name })}
                              onClick={(event) => {
                                event.stopPropagation();
                                handleOpenPatient(patient);
                              }}
                            >
                              <Icon name="eye" />
                            </button>
                            <button
                              type="button"
                              className="icon-button"
                              aria-label={t('clinician.contactPatientAria', { name: patient.name })}
                              onClick={(event) => {
                                event.stopPropagation();
                                handleCallPatient(patient.name);
                              }}
                            >
                              <Icon name="phone" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filteredPatients.length === 0 && (
                      <tr>
                        <td colSpan="7">
                          <div className="empty-state">
                            <Icon name="search" />
                            <strong>{t('clinician.noMatchingPatients')}</strong>
                            <span>{t('clinician.adjustFilter')}</span>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}

        {activeTab === 'alerts' && (
          <AlertsTab
            showAcknowledgedAlerts={showAcknowledgedAlerts}
            setShowAcknowledgedAlerts={setShowAcknowledgedAlerts}
            openAlerts={prioritizedOpenAlerts}
            acknowledgedAlertRows={acknowledgedAlertRows}
            pendingAlertIds={pendingAlertIds}
            setSelectedPatientId={setSelectedPatientId}
            setActiveTab={setActiveTab}
            handleAcknowledgeAlert={handleAcknowledgeAlert}
          />
        )}

        {activeTab === 'reports' && (
          <section className="workspace-panel">
            <div className="panel-heading">
              <div>
                <h2>{t('clinician.reportsTitle')}</h2>
                <p>{t('clinician.reportsDesc')}</p>
              </div>
              <button type="button" className="secondary-action" onClick={() => exportPatientCsv(patientRows, locale)}>
                <Icon name="download" />
                {t('clinician.exportPatients')}
              </button>
            </div>

            <div className="report-grid">
              <article className="report-card">
                <span>{t('clinician.signalReadiness')}</span>
                <strong aria-label={t('clinician.notAvailable')}>—</strong>
                <p>{t('clinician.signalReadinessDesc')}</p>
              </article>
              <article className="report-card">
                <span>{t('clinician.activeAlertsReport')}</span>
                <strong aria-label={stats.alerts === null ? t('clinician.notAvailable') : undefined}>
                  {formatAggregateCount(stats.alerts)}
                </strong>
                <p>{t('clinician.activeAlertsReportDesc')}</p>
              </article>
              <article className="report-card">
                <span>{t('clinician.activeSessionsReport')}</span>
                <strong aria-label={stats.monitoring === null ? t('clinician.notAvailable') : undefined}>
                  {formatAggregateCount(stats.monitoring)}
                </strong>
                <p>{t('clinician.activeSessionsReportDesc')}</p>
              </article>
            </div>

            <div className="readiness-table">
              <div className="readiness-table__row readiness-table__row--head">
                <span>{t('clinician.dataArea')}</span>
                <span>{t('clinician.dataStatus')}</span>
                <span>{t('clinician.dataNotes')}</span>
              </div>
              <div className="readiness-table__row">
                <span>{t('clinician.patientProfile')}</span>
                <strong className="status-text status-text--ok">{t('clinician.available')}</strong>
                <span>{t('clinician.patientProfileNote')}</span>
              </div>
              <div className="readiness-table__row">
                <span>{t('clinician.sessionMonitoring')}</span>
                <strong className="status-text status-text--ok">{t('clinician.partiallyAvailable')}</strong>
                <span>{t('clinician.sessionMonitoringNote')}</span>
              </div>
              <div className="readiness-table__row">
                <span>{t('clinician.sensorEstimate')}</span>
                <strong className="status-text status-text--warn">{t('clinician.notAvailable')}</strong>
                <span>{t('clinician.sensorEstimateNote')}</span>
              </div>
            </div>
          </section>
        )}

        {activeTab === 'settings' && (
          <section className="workspace-panel">
            <div className="panel-heading">
              <div>
                <h2>{t('clinician.settingsTitle')}</h2>
                <p>{t('clinician.settingsDesc')}</p>
              </div>
            </div>

            <div className="settings-grid">
              <article className="settings-panel">
                <h3>{t('clinician.displayPreference')}</h3>
                <p className="settings-panel__intro">
                  {t('clinician.displayPreferenceDesc')}
                </p>
                <label className="setting-line">
                  <span>{t('clinician.showHandledAlerts')}</span>
                  <input
                    type="checkbox"
                    checked={showAcknowledgedAlerts}
                    onChange={(event) => setShowAcknowledgedAlerts(event.target.checked)}
                  />
                </label>
                <button type="button" className="secondary-action" onClick={toggleTheme}>
                  <Icon name={isDarkMode ? 'sun' : 'moon'} />
                  {isDarkMode ? t('clinician.lightTheme') : t('clinician.darkTheme')}
                </button>
              </article>

              <article className="settings-panel">
                <h3>{t('clinician.monitoringReference')}</h3>
                <p className="settings-panel__intro">
                  {t('clinician.monitoringReferenceDesc')}
                </p>
                <DataAvailability label={t('clinician.fhrReference')} value="110-160 bpm" status="ok" />
                <DataAvailability label={t('clinician.maternalHrReference')} value="60-100 bpm" status="ok" />
                <p className="settings-note">
                  {t('clinician.settingsNote')}
                </p>
              </article>

              <article className="settings-panel settings-panel--wide">
                <h3>{t('clinician.alertWorkflow')}</h3>
                <div className="workflow-list">
                  <div className="workflow-item workflow-item--low">
                    <strong>{t('clinician.routineMonitoring')}</strong>
                    <span>{t('clinician.routineMonitoringDesc')}</span>
                  </div>
                  <div className="workflow-item workflow-item--medium">
                    <strong>{t('clinician.observationNeeded')}</strong>
                    <span>{t('clinician.observationNeededDesc')}</span>
                  </div>
                  <div className="workflow-item workflow-item--high">
                    <strong>{t('clinician.reviewSoon')}</strong>
                    <span>{t('clinician.reviewSoonDesc')}</span>
                  </div>
                </div>
              </article>

              <article className="settings-panel settings-panel--wide">
                <h3>{t('clinician.currentDataLimits')}</h3>
                <ul className="limitation-list">
                  <li>{t('clinician.limitationSignal')}</li>
                  <li>{t('clinician.limitationAlert')}</li>
                  <li>{t('clinician.limitationNotes')}</li>
                </ul>
              </article>
            </div>
          </section>
        )}

        <p className="medical-disclaimer">
          {t('clinician.medicalDisclaimer')}
        </p>
      </main>

      <PatientDetailPanel
        selectedPatient={selectedPatient}
        setSelectedPatientId={setSelectedPatientId}
        openAlerts={prioritizedOpenAlerts}
        setActiveTab={setActiveTab}
        handleCallPatient={handleCallPatient}
        handleOpenPatient={handleOpenPatient}
        openModal={openModal}
      />

      <FeedbackModal {...modalConfig} onClose={closeModal} />
    </div>
  );
};

export default ClinicianDashboard;
