import React, { useRef, useState } from 'react';
import { t } from '../../../../i18n';
import { useI18n } from '../../../../i18n/useI18n';
import { useAuth } from '../../../../context/useAuth';
import Icon from '../../../../components/Icon';
import api, { isRequestCanceled } from '../../../../services/api';
import { normalizeAIAnalysisPage } from '../../../../utils/aiAnalysisModels';
import { exportClinicianPatientReport } from '../../../../utils/clinicianReportPdf';

const RANGE_OPTIONS = [
  { key: 'daily', hours: 24, labelKey: 'clinician.exportReport.rangeDaily' },
  { key: 'weekly', hours: 24 * 7, labelKey: 'clinician.exportReport.rangeWeekly' },
];

const PAGE_LIMIT = 100;
const MAX_PAGES = 6; // safety cap: up to 600 analysis records per report

/**
 * Fetches every AI analysis result page for the patient until either the
 * oldest fetched record falls before `rangeStart`, all records have been
 * retrieved, or the safety page cap is reached.
 */
async function fetchAnalysisResultsSince(patientId, rangeStart, signal) {
  const rangeStartMs = new Date(rangeStart).getTime();
  const collected = [];
  let offset = 0;

  for (let page = 0; page < MAX_PAGES; page += 1) {
    const response = await api.clinician.listPatientAIResults(patientId, {
      limit: PAGE_LIMIT,
      offset,
      signal,
    });
    const items = Array.isArray(response?.items) ? response.items : [];
    collected.push(...items);

    const total = Number.isSafeInteger(response?.total) ? response.total : collected.length;
    offset += items.length;

    const oldestItem = items[items.length - 1];
    const oldestTime = oldestItem ? new Date(oldestItem.created_at).getTime() : null;
    const reachedRangeStart = Number.isFinite(oldestTime) && oldestTime < rangeStartMs;

    if (items.length === 0 || offset >= total || reachedRangeStart) break;
  }

  return normalizeAIAnalysisPage({ items: collected });
}

export default function PatientReportExport({ patient, openModal }) {
  const { locale } = useI18n();
  const { user } = useAuth();
  const [range, setRange] = useState('daily');
  const [isExporting, setIsExporting] = useState(false);
  const controllerRef = useRef(null);

  if (!patient) return null;

  const clinicianLabel = user?.email || t('clinician.clinicianFallback');

  const handleExport = async () => {
    if (isExporting) return;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setIsExporting(true);

    const option = RANGE_OPTIONS.find((item) => item.key === range) || RANGE_OPTIONS[0];
    const rangeEnd = new Date();
    const rangeStart = new Date(rangeEnd.getTime() - option.hours * 60 * 60 * 1000);

    try {
      const allResults = await fetchAnalysisResultsSince(
        patient.id,
        rangeStart.toISOString(),
        controller.signal,
      );
      if (controller.signal.aborted) return;

      const rangeStartMs = rangeStart.getTime();
      const rangeEndMs = rangeEnd.getTime();
      const resultsInRange = allResults.filter((result) => {
        const windowEndMs = new Date(result.windowEndedAt).getTime();
        return windowEndMs >= rangeStartMs && windowEndMs <= rangeEndMs;
      });

      const { filename, recordCount } = await exportClinicianPatientReport({
        patient,
        sessions: patient.sessions || [],
        aiResults: resultsInRange,
        rangeKey: option.key,
        rangeStart: rangeStart.toISOString(),
        rangeEnd: rangeEnd.toISOString(),
        clinicianLabel,
        locale,
      });

      const rangeLabel = t(option.labelKey);
      openModal({
        title: t('clinician.exportReport.successTitle'),
        message: recordCount > 0
          ? t('clinician.exportReport.successMessage', { filename, count: recordCount, range: rangeLabel })
          : t('clinician.exportReport.successEmptyMessage', { filename, range: rangeLabel }),
        type: 'success',
        confirmText: t('common.ok'),
      });
    } catch (error) {
      if (isRequestCanceled(error)) return;
      openModal({
        title: t('clinician.exportReport.failTitle'),
        message: t('clinician.exportReport.failMessage'),
        type: 'error',
        confirmText: t('clinician.understand'),
      });
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setIsExporting(false);
      }
    }
  };

  return (
    <div className="detail-section patient-report-export">
      <h3>{t('clinician.exportReport.title')}</h3>
      <p className="patient-report-export__desc">{t('clinician.exportReport.desc')}</p>

      <div className="patient-report-export__controls">
        <div
          className="segmented-control patient-report-export__range"
          role="group"
          aria-label={t('clinician.exportReport.rangeLabel')}
        >
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option.key}
              type="button"
              className={range === option.key ? 'is-selected' : ''}
              onClick={() => setRange(option.key)}
            >
              {t(option.labelKey)}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="patient-report-export__button"
          onClick={handleExport}
          disabled={isExporting}
        >
          <Icon name="download" />
          {isExporting ? t('clinician.exportReport.preparing') : t('clinician.exportReport.downloadButton')}
        </button>
      </div>
    </div>
  );
}
