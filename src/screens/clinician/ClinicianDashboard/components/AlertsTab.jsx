import React, { useState } from 'react';
import { t } from '../../../../i18n';
import Icon from '../../../../components/Icon';
import RiskBadge from './RiskBadge';

export default function AlertsTab({
  showAcknowledgedAlerts,
  setShowAcknowledgedAlerts,
  openAlerts,
  acknowledgedAlertRows,
  pendingAlertIds = [],
  setSelectedPatientId,
  setActiveTab,
  handleAcknowledgeAlert,
}) {
  const [acknowledgementNotes, setAcknowledgementNotes] = useState({});

  const handleViewPatient = (patientId) => {
    if (!patientId) return;
    setSelectedPatientId(patientId);
    setActiveTab('patients');
  };

  const handleNoteChange = (alertId, value) => {
    setAcknowledgementNotes((current) => ({ ...current, [alertId]: value }));
  };

  const handleAcknowledge = async (alertId) => {
    const note = acknowledgementNotes[alertId] || '';
    const acknowledged = await handleAcknowledgeAlert(alertId, note);
    if (!acknowledged) return;
    setAcknowledgementNotes((current) => {
      const next = { ...current };
      delete next[alertId];
      return next;
    });
  };

  return (
    <section className="workspace-panel">
      <div className="panel-heading">
        <div>
          <h2>{t('clinician.alertsTitle')}</h2>
          <p>{t('clinician.alertsDesc')}</p>
        </div>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showAcknowledgedAlerts}
            onChange={(event) => setShowAcknowledgedAlerts(event.target.checked)}
          />
          {t('clinician.showHandled')}
        </label>
      </div>

      <div className="alert-board">
        <div className="alert-column">
          <div className="alert-column__header">
            <h3>{t('clinician.pendingAction')}</h3>
            <span>{t('clinician.alertCount', { count: openAlerts.length })}</span>
          </div>
          {openAlerts.map((alert) => (
            <article key={alert.id} className={`alert-row alert-row--${alert.type}`}>
              <div className="alert-row__icon">
                <Icon name={alert.type === 'critical' ? 'alert' : 'bell'} />
              </div>
              <div className="alert-row__content">
                <div className="alert-row__title">
                  <strong>{alert.patientName}</strong>
                  <RiskBadge risk={alert.riskLevel} />
                </div>
                <p>{alert.message}</p>
                <small>{alert.patientCode} - {alert.absoluteTime} - {alert.timestamp}</small>
                <label className="alert-note-field">
                  <span>{t('clinician.acknowledgementNote')}</span>
                  <textarea
                    value={acknowledgementNotes[alert.id] || ''}
                    onChange={(event) => handleNoteChange(alert.id, event.target.value)}
                    maxLength={500}
                    rows="2"
                    placeholder={t('clinician.acknowledgementNotePlaceholder')}
                  />
                </label>
              </div>
              <div className="alert-row__actions">
                <button type="button" disabled={!alert.patientId} onClick={() => handleViewPatient(alert.patientId)}>
                  {t('clinician.viewPatient')}
                </button>
                <button
                  type="button"
                  disabled={pendingAlertIds.includes(alert.id)}
                  onClick={() => handleAcknowledge(alert.id)}
                >
                  {t('clinician.markHandled')}
                </button>
              </div>
            </article>
          ))}
          {openAlerts.length === 0 && (
            <div className="empty-state empty-state--compact">
              <Icon name="check" />
              <strong>{t('clinician.noPendingAlerts')}</strong>
              <span>{t('clinician.noPendingAlertsDesc')}</span>
            </div>
          )}
        </div>

        {showAcknowledgedAlerts && (
          <div className="alert-column alert-column--handled">
            <div className="alert-column__header">
              <h3>{t('clinician.handledTitle')}</h3>
              <span>{t('clinician.alertCount', { count: acknowledgedAlertRows.length })}</span>
            </div>
            {acknowledgedAlertRows.map((alert) => (
              <article key={alert.id} className="alert-row alert-row--handled">
                <div className="alert-row__icon"><Icon name="check" /></div>
                <div className="alert-row__content">
                  <div className="alert-row__title">
                    <strong>{alert.patientName}</strong>
                    <span className="handled-token">{alert.statusLabel || t('clinician.handled')}</span>
                  </div>
                  <p>{alert.message}</p>
                  <small>{alert.absoluteTime}</small>
                  {alert.acknowledgementNote && (
                    <span className="handled-note">{alert.acknowledgementNote}</span>
                  )}
                </div>
              </article>
            ))}
            {acknowledgedAlertRows.length === 0 && (
              <div className="empty-state empty-state--compact">
                <Icon name="info" />
                <strong>{t('clinician.handledEmptyTitle')}</strong>
                <span>{t('clinician.handledEmptyDesc')}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
