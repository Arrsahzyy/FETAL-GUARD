import React, { useMemo } from 'react';
import { t } from '../../../../i18n';
import { useI18n } from '../../../../i18n/useI18n';
import Icon from '../../../../components/Icon';
import RiskBadge from './RiskBadge';
import DataAvailability from './DataAvailability';
import { formatDateTime, formatDuration } from '../../../../utils/formatters';

export default function PatientDetailPanel({
  selectedPatient,
  setSelectedPatientId,
  openAlerts,
  setActiveTab,
  handleCallPatient,
  handleOpenPatient,
  openModal,
}) {
  const { locale } = useI18n();
  const selectedPatientAlerts = useMemo(() => {
    if (!selectedPatient) return [];
    return openAlerts.filter((alert) => alert.patientId === selectedPatient.id);
  }, [openAlerts, selectedPatient]);

  return (
    <aside className="dashboard-detail" aria-label={t('clinician.detailTitle')}>
      <div className="detail-panel">
        <div className="detail-panel__header">
          <h2>{t('clinician.detailTitle')}</h2>
          {selectedPatient && (
            <button
              type="button"
              className="icon-button"
              aria-label={t('clinician.closeDetail')}
              onClick={() => setSelectedPatientId(null)}
            >
              <Icon name="close" />
            </button>
          )}
        </div>

        {selectedPatient ? (
          <>
            <div className="detail-identity">
              <span className="detail-identity__avatar">{selectedPatient.initials}</span>
              <div>
                <strong>{selectedPatient.name}</strong>
                <span>{selectedPatient.patientCode}</span>
              </div>
            </div>

            <div className="detail-metrics">
              <div>
                <span>{t('clinician.gestation')}</span>
                <strong>{selectedPatient.gestationalAgeLabel}</strong>
              </div>
              <div>
                <span>{t('clinician.age')}</span>
                <strong>{selectedPatient.ageLabel}</strong>
              </div>
              <div>
                <span>{t('clinician.sessions')}</span>
                <strong>{selectedPatient.sessions.length}</strong>
              </div>
            </div>

            <div className="detail-section">
              <h3>{t('clinician.screeningStatus')}</h3>
              <RiskBadge risk={selectedPatient.currentRisk} />
              <p>{selectedPatient.riskMeta.description}</p>
            </div>

            <div className="detail-section data-availability">
              <h3>{t('clinician.dataAvailability')}</h3>
              <DataAvailability
                label={t('clinician.sessionMonitoring')}
                value={selectedPatient.lastSession}
                status={selectedPatient.sessions.length ? 'ok' : 'missing'}
              />
              <DataAvailability label={t('clinician.sensorEstimate')} value={selectedPatient.fhrLabel} />
              <DataAvailability label={t('clinician.maternalHr')} value={selectedPatient.maternalHrLabel} />
              <DataAvailability label={t('clinician.signalQuality')} value={selectedPatient.signalLabel} />
              <DataAvailability label={t('clinician.contractionIndicator')} value={selectedPatient.contractionLabel} />
              <DataAvailability
                label={t('clinician.activeAlerts')}
                value={t('clinician.alertCount', { count: selectedPatient.activeAlerts })}
                status={selectedPatient.activeAlerts > 0 ? 'warn' : 'ok'}
              />
            </div>

            <div className="detail-section">
              <h3>{t('clinician.sessionTimeline')}</h3>
              <div className="session-timeline">
                {selectedPatient.sessions.map((session, index) => (
                  <div key={session.id} className={`timeline-item ${session.status === 'active' ? 'timeline-item--active' : ''}`}>
                    <span className="timeline-marker">{session.status === 'active' ? <Icon name="activity" /> : index + 1}</span>
                    <div>
                      <strong>
                        {session.status === 'active'
                          ? t('clinician.activeSession')
                          : t('clinician.sessionNumber', { number: selectedPatient.sessions.length - index })}
                      </strong>
                      <span>
                        {formatDateTime(session.start_time, locale)} - {t('clinician.duration')}{' '}
                        {formatDuration(session.start_time, session.end_time, session.status, locale)}
                      </span>
                    </div>
                  </div>
                ))}
                {selectedPatient.sessions.length === 0 && (
                  <span className="detail-empty">{t('clinician.noMonitoringSession')}</span>
                )}
              </div>
            </div>

            <div className="detail-section">
              <h3>{t('clinician.quickActions')}</h3>
              <div className="quick-actions">
                <button type="button" onClick={() => handleCallPatient(selectedPatient.name)}>
                  <Icon name="phone" />
                  {t('clinician.contact')}
                </button>
                <button type="button" onClick={() => handleOpenPatient(selectedPatient)}>
                  <Icon name="eye" />
                  {t('clinician.viewSession')}
                </button>
                <button
                  type="button"
                  onClick={() => openModal({
                    title: t('clinician.clinicianNotesTitle'),
                    message: t('clinician.clinicianNotesMessage'),
                    type: 'info',
                    confirmText: t('clinician.understand'),
                  })}
                >
                  <Icon name="file" />
                  {t('clinician.notes')}
                </button>
              </div>
            </div>

            <div className="detail-section">
              <div className="detail-section__header">
                <h3>{t('clinician.alertQueueSection')}</h3>
                <button type="button" onClick={() => setActiveTab('alerts')}>{t('clinician.viewAll')}</button>
              </div>
              <div className="compact-alert-list">
                {selectedPatientAlerts.slice(0, 4).map((alert) => (
                  <div key={alert.id} className={`compact-alert compact-alert--${alert.type}`}>
                    <Icon name={alert.type === 'critical' ? 'alert' : 'bell'} />
                    <span>
                      <strong>{alert.patientName}</strong>
                      <small>{alert.riskMeta.shortLabel} - {alert.timestamp}</small>
                    </span>
                  </div>
                ))}
                {selectedPatientAlerts.length === 0 && (
                  <span className="detail-empty">{t('clinician.noPendingAlertShort')}</span>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="empty-state empty-state--compact">
            <Icon name="users" />
            <strong>{t('clinician.choosePatient')}</strong>
            <span>{t('clinician.choosePatientDesc')}</span>
          </div>
        )}
      </div>
    </aside>
  );
}
