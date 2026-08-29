/**
 * Builds the clinician-facing "patient monitoring + hybrid AI analysis" PDF report.
 *
 * The report is intentionally built only from data already fetched from the
 * backend (session summaries + AI analysis results). No values are invented:
 * every figure either comes straight from the API or is a plain aggregate
 * (average/count) computed over the records that were actually returned.
 */
import { t } from '../i18n';
import { formatDuration } from './formatters';

const formatDateOnly = (value, locale) => {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--';
  return new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
};

const formatTimeOnly = (value) => {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--';
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
};

const roundOrDash = (value, unit = '') => (
  Number.isFinite(value) ? `${Math.round(value)}${unit}` : '--'
);

const percentOrDash = (value) => (
  Number.isFinite(value) ? `${Math.round(value * 100)}%` : '--'
);

const average = (values) => {
  const valid = values.filter((value) => Number.isFinite(value));
  if (valid.length === 0) return null;
  return valid.reduce((sum, value) => sum + value, 0) / valid.length;
};

const pad2 = (value) => String(value).padStart(2, '0');

const NEEDS_REVIEW_STATUSES = new Set(['needs_observation', 'review_with_clinician']);

/**
 * @param {object} params
 * @param {object} params.patient - patient view model (toPatientViewModel output)
 * @param {Array} params.sessions - patient.sessions (latest/active sessions known to the system)
 * @param {Array} params.aiResults - normalized AI analysis results already filtered to the report range
 * @param {'daily'|'weekly'} params.rangeKey
 * @param {string} params.rangeStart - ISO date string
 * @param {string} params.rangeEnd - ISO date string
 * @param {string} params.clinicianLabel - name/email of the clinician generating the report
 * @param {string} params.locale
 * @returns {Promise<{ filename: string, recordCount: number }>}
 */
export async function exportClinicianPatientReport({
  patient,
  sessions = [],
  aiResults = [],
  rangeKey,
  rangeStart,
  rangeEnd,
  clinicianLabel,
  locale = 'id',
}) {
  const { jsPDF } = await import('jspdf');
  const autoTable = (await import('jspdf-autotable')).default;
  const now = new Date();

  const PAGE_W = 297;
  const PAGE_H = 210;
  const MARGIN = 14;
  const CONTENT_W = PAGE_W - MARGIN * 2;
  const BREAK_Y = 172;

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });

  const ensureSpace = (currentY, needed = 30) => {
    if (currentY + needed <= BREAK_Y) return currentY;
    doc.addPage();
    return 20;
  };

  // ================================================================
  // HEADER BAR
  // ================================================================
  doc.setFillColor(15, 139, 141);
  doc.rect(0, 0, PAGE_W, 22, 'F');
  doc.setFillColor(23, 105, 224);
  doc.rect(0, 20.5, PAGE_W, 2.4, 'F');

  doc.setTextColor(255, 255, 255);
  doc.setFontSize(16);
  doc.setFont('helvetica', 'bold');
  doc.text('FETAL-GUARD', MARGIN, 10);
  doc.setFontSize(8.5);
  doc.setFont('helvetica', 'normal');
  doc.text(t('clinician.exportReport.pdfSubtitle'), MARGIN, 16.5);

  // ================================================================
  // TITLE + META
  // ================================================================
  const titleText = rangeKey === 'daily'
    ? t('clinician.exportReport.pdfTitleDaily')
    : t('clinician.exportReport.pdfTitleWeekly');

  doc.setTextColor(21, 32, 51);
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.text(titleText, MARGIN, 32);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(93, 107, 124);
  const periodText = `${t('clinician.exportReport.pdfPeriod')}: `
    + `${formatDateOnly(rangeStart, locale)} ${formatTimeOnly(rangeStart)} - `
    + `${formatDateOnly(rangeEnd, locale)} ${formatTimeOnly(rangeEnd)}`;
  doc.text(periodText, MARGIN, 38);
  doc.text(
    `${t('clinician.exportReport.pdfGeneratedAt')}: ${formatDateOnly(now.toISOString(), locale)} ${formatTimeOnly(now.toISOString())}   |   `
    + `${t('clinician.exportReport.pdfGeneratedBy')}: ${clinicianLabel}`,
    MARGIN,
    43,
  );

  doc.setDrawColor(221, 229, 238);
  doc.setLineWidth(0.4);
  doc.line(MARGIN, 46, PAGE_W - MARGIN, 46);

  // ================================================================
  // PATIENT INFO
  // ================================================================
  doc.setTextColor(21, 32, 51);
  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  doc.text(t('clinician.exportReport.pdfPatientSection'), MARGIN, 53);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.7);
  doc.setTextColor(60, 72, 88);
  const col2X = MARGIN + CONTENT_W / 2;
  doc.text(`${t('clinician.exportReport.pdfPatientName')}: ${patient.name}`, MARGIN, 59);
  doc.text(`${t('clinician.exportReport.pdfPatientCode')}: ${patient.patientCode}`, col2X, 59);
  doc.text(`${t('clinician.exportReport.pdfPatientAge')}: ${patient.ageLabel}`, MARGIN, 64);
  doc.text(`${t('clinician.exportReport.pdfPatientGestation')}: ${patient.gestationalAgeLabel}`, col2X, 64);
  doc.text(`${t('clinician.exportReport.pdfPatientRisk')}: ${patient.riskMeta.label}`, MARGIN, 69);

  // ================================================================
  // SUMMARY STATS
  // ================================================================
  let curY = 76;
  const totalRecords = aiResults.length;
  const avgFhr = average(aiResults.map((result) => result.fhrBpm));
  const avgMaternalHr = average(aiResults.map((result) => result.maternalHrBpm));
  const needsReviewCount = aiResults.filter(
    (result) => NEEDS_REVIEW_STATUSES.has(result.screeningStatus),
  ).length;
  const simulatedCount = aiResults.filter((result) => result.isSimulated).length;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(21, 32, 51);
  doc.text(t('clinician.exportReport.pdfSummarySection'), MARGIN, curY);

  autoTable(doc, {
    startY: curY + 3,
    head: [[
      t('clinician.exportReport.pdfSummaryTotalRecords'),
      t('clinician.exportReport.pdfSummaryAvgFhr'),
      t('clinician.exportReport.pdfSummaryAvgMaternalHr'),
      t('clinician.exportReport.pdfSummaryNeedsReview'),
      t('clinician.exportReport.pdfSummarySimulated'),
    ]],
    body: [[
      String(totalRecords),
      roundOrDash(avgFhr, ' bpm'),
      roundOrDash(avgMaternalHr, ' bpm'),
      String(needsReviewCount),
      String(simulatedCount),
    ]],
    styles: {
      fontSize: 9, cellPadding: 3, font: 'helvetica', halign: 'center',
    },
    headStyles: {
      fillColor: [15, 139, 141], textColor: 255, fontStyle: 'bold', fontSize: 8.5,
    },
    margin: { left: MARGIN, right: MARGIN },
  });
  curY = (doc.lastAutoTable?.finalY || curY + 20) + 9;

  // ================================================================
  // TABLE 1 - SESSION HISTORY
  // ================================================================
  curY = ensureSpace(curY, 30);
  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(21, 32, 51);
  doc.text(t('clinician.exportReport.pdfSessionSection'), MARGIN, curY);

  if (sessions.length > 0) {
    const sessionBody = sessions.map((session, index) => [
      index + 1,
      formatDateOnly(session.start_time, locale),
      `${formatTimeOnly(session.start_time)} - ${session.end_time ? formatTimeOnly(session.end_time) : '-'}`,
      formatDuration(session.start_time, session.end_time, session.status, locale),
      session.status === 'active'
        ? t('clinician.exportReport.pdfSessionActive')
        : t('clinician.exportReport.pdfSessionCompleted'),
    ]);

    autoTable(doc, {
      startY: curY + 3,
      head: [[
        t('clinician.exportReport.pdfColNo'),
        t('clinician.exportReport.pdfColDate'),
        t('clinician.exportReport.pdfColSessionWindow'),
        t('clinician.exportReport.pdfColDuration'),
        t('clinician.exportReport.pdfColSessionStatus'),
      ]],
      body: sessionBody,
      styles: { fontSize: 8.5, cellPadding: 2.5, font: 'helvetica' },
      headStyles: {
        fillColor: [15, 139, 141], textColor: 255, fontStyle: 'bold', fontSize: 8.5,
      },
      alternateRowStyles: { fillColor: [237, 247, 246] },
      columnStyles: {
        0: { cellWidth: 12, halign: 'center' },
        1: { cellWidth: 34 },
        2: { cellWidth: 52 },
        3: { cellWidth: 34 },
      },
      margin: { left: MARGIN, right: MARGIN },
    });
    curY = (doc.lastAutoTable?.finalY || curY + 20) + 4;

    doc.setFontSize(7.5);
    doc.setFont('helvetica', 'italic');
    doc.setTextColor(130, 140, 153);
    doc.text(t('clinician.exportReport.pdfSessionNote'), MARGIN, curY, { maxWidth: CONTENT_W });
    curY += 9;
  } else {
    doc.setFontSize(8.5);
    doc.setFont('helvetica', 'italic');
    doc.setTextColor(130, 140, 153);
    doc.text(t('clinician.exportReport.pdfSessionEmpty'), MARGIN, curY + 6);
    curY += 14;
  }

  // ================================================================
  // TABLE 2 - HYBRID AI ANALYSIS HISTORY (main table)
  // ================================================================
  curY = ensureSpace(curY, 34);
  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(21, 32, 51);
  doc.text(t('clinician.exportReport.pdfAiSection'), MARGIN, curY);

  if (aiResults.length > 0) {
    const aiBody = aiResults.map((result, index) => [
      index + 1,
      formatDateOnly(result.windowEndedAt, locale),
      `${formatTimeOnly(result.windowStartedAt)} - ${formatTimeOnly(result.windowEndedAt)}`,
      t(`patient.monitoring.ai.quality.${result.qualityStatus}`),
      roundOrDash(result.fhrBpm),
      roundOrDash(result.maternalHrBpm),
      percentOrDash(result.contractionProbability),
      t(`patient.monitoring.ai.status.${result.screeningStatus}.label`),
      percentOrDash(result.uncertainty),
      result.isSimulated ? t('clinician.exportReport.pdfYes') : t('clinician.exportReport.pdfNo'),
    ]);

    autoTable(doc, {
      startY: curY + 3,
      head: [[
        t('clinician.exportReport.pdfColNo'),
        t('clinician.exportReport.pdfColDate'),
        t('clinician.exportReport.pdfColWindow'),
        t('clinician.exportReport.pdfColQuality'),
        t('clinician.exportReport.pdfColFhr'),
        t('clinician.exportReport.pdfColMaternalHr'),
        t('clinician.exportReport.pdfColContraction'),
        t('clinician.exportReport.pdfColStatus'),
        t('clinician.exportReport.pdfColUncertainty'),
        t('clinician.exportReport.pdfColSimulated'),
      ]],
      body: aiBody,
      styles: {
        fontSize: 8, cellPadding: 2.2, font: 'helvetica', overflow: 'linebreak',
      },
      headStyles: {
        fillColor: [23, 105, 224], textColor: 255, fontStyle: 'bold', fontSize: 7.8,
      },
      alternateRowStyles: { fillColor: [235, 242, 251] },
      columnStyles: {
        0: { cellWidth: 9, halign: 'center' },
        1: { cellWidth: 20 },
        2: { cellWidth: 28 },
        3: { cellWidth: 22 },
        4: { cellWidth: 16, halign: 'center' },
        5: { cellWidth: 20, halign: 'center' },
        6: { cellWidth: 18, halign: 'center' },
        7: { cellWidth: 52 },
        8: { cellWidth: 20, halign: 'center' },
        9: { cellWidth: 16, halign: 'center' },
      },
      margin: { left: MARGIN, right: MARGIN },
      didDrawPage: () => {
        // Keep header bar off subsequent pages; nothing to draw here, but the
        // hook keeps autoTable's page-break bookkeeping consistent.
      },
    });
    curY = (doc.lastAutoTable?.finalY || curY + 20) + 9;
  } else {
    doc.setFontSize(8.5);
    doc.setFont('helvetica', 'italic');
    doc.setTextColor(130, 140, 153);
    doc.text(t('clinician.exportReport.pdfAiEmpty'), MARGIN, curY + 6);
    curY += 16;
  }

  // ================================================================
  // TABLE 3 - AI REASONING NOTES (only rows with reasons)
  // ================================================================
  const reasonRows = aiResults
    .map((result, index) => ({ index, result }))
    .filter(({ result }) => result.reasons.length > 0);

  if (reasonRows.length > 0) {
    curY = ensureSpace(curY, 30);
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(21, 32, 51);
    doc.text(t('clinician.exportReport.pdfReasonSection'), MARGIN, curY);

    autoTable(doc, {
      startY: curY + 3,
      head: [[
        t('clinician.exportReport.pdfColNo'),
        t('clinician.exportReport.pdfColWindow'),
        t('clinician.exportReport.pdfColReason'),
      ]],
      body: reasonRows.map(({ index, result }) => [
        index + 1,
        `${formatDateOnly(result.windowEndedAt, locale)} ${formatTimeOnly(result.windowEndedAt)}`,
        result.reasons.join('; '),
      ]),
      styles: {
        fontSize: 8, cellPadding: 2.3, font: 'helvetica', overflow: 'linebreak',
      },
      headStyles: {
        fillColor: [245, 159, 0], textColor: 255, fontStyle: 'bold', fontSize: 8.2,
      },
      alternateRowStyles: { fillColor: [253, 244, 227] },
      columnStyles: {
        0: { cellWidth: 10, halign: 'center' },
        1: { cellWidth: 40 },
        2: { cellWidth: CONTENT_W - 50 },
      },
      margin: { left: MARGIN, right: MARGIN },
    });
    curY = (doc.lastAutoTable?.finalY || curY + 20) + 9;
  }

  // ================================================================
  // TABLE 4 - CLINICIAN REVIEW HISTORY (only reviewed rows)
  // ================================================================
  const reviewedRows = aiResults
    .map((result, index) => ({ index, result }))
    .filter(({ result }) => result.review);

  curY = ensureSpace(curY, 30);
  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(21, 32, 51);
  doc.text(t('clinician.exportReport.pdfReviewSection'), MARGIN, curY);

  if (reviewedRows.length > 0) {
    autoTable(doc, {
      startY: curY + 3,
      head: [[
        t('clinician.exportReport.pdfColNo'),
        t('clinician.exportReport.pdfColWindow'),
        t('clinician.exportReport.pdfColReviewDecision'),
        t('clinician.exportReport.pdfColReviewNote'),
      ]],
      body: reviewedRows.map(({ index, result }) => [
        index + 1,
        `${formatDateOnly(result.windowEndedAt, locale)} ${formatTimeOnly(result.windowEndedAt)}`,
        t(`clinician.aiReview.${result.review.decision}`),
        result.review.note || '-',
      ]),
      styles: {
        fontSize: 8, cellPadding: 2.3, font: 'helvetica', overflow: 'linebreak',
      },
      headStyles: {
        fillColor: [15, 139, 141], textColor: 255, fontStyle: 'bold', fontSize: 8.2,
      },
      alternateRowStyles: { fillColor: [237, 247, 246] },
      columnStyles: {
        0: { cellWidth: 10, halign: 'center' },
        1: { cellWidth: 40 },
        2: { cellWidth: 45 },
        3: { cellWidth: CONTENT_W - 95 },
      },
      margin: { left: MARGIN, right: MARGIN },
    });
    curY = (doc.lastAutoTable?.finalY || curY + 20) + 9;
  } else {
    doc.setFontSize(8.5);
    doc.setFont('helvetica', 'italic');
    doc.setTextColor(130, 140, 153);
    doc.text(t('clinician.exportReport.pdfReviewEmpty'), MARGIN, curY + 6);
    curY += 16;
  }

  // ================================================================
  // FOOTER DISCLAIMER
  // ================================================================
  curY = ensureSpace(curY, 34);
  doc.setFillColor(249, 250, 251);
  doc.roundedRect(MARGIN, curY, CONTENT_W, 30, 2, 2, 'F');
  doc.setDrawColor(229, 231, 235);
  doc.setLineWidth(0.3);
  doc.roundedRect(MARGIN, curY, CONTENT_W, 30, 2, 2, 'S');

  doc.setFontSize(7.6);
  doc.setTextColor(107, 114, 128);
  doc.setFont('helvetica', 'bold');
  doc.text(t('clinician.exportReport.pdfImportant'), MARGIN + 3, curY + 5.5);
  doc.setFont('helvetica', 'normal');
  [
    'pdfDisclaimer1',
    'pdfDisclaimer2',
    'pdfDisclaimer3',
    'pdfDisclaimer4',
  ].forEach((key, index) => {
    doc.text(
      t(`clinician.exportReport.${key}`),
      MARGIN + 3,
      curY + 10.5 + index * 4.6,
      { maxWidth: CONTENT_W - 6 },
    );
  });

  // ================================================================
  // PAGE NUMBERS
  // ================================================================
  const totalPages = doc.internal.getNumberOfPages();
  for (let page = 1; page <= totalPages; page += 1) {
    doc.setPage(page);
    doc.setFontSize(7.4);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(150, 158, 168);
    doc.text(
      t('clinician.exportReport.pdfPageLabel', { current: page, total: totalPages }),
      PAGE_W - MARGIN,
      PAGE_H - 8,
      { align: 'right' },
    );
  }

  const rangeSlug = rangeKey === 'daily' ? 'Harian' : 'Mingguan';
  const filename = `FETAL-GUARD-Laporan-${patient.patientCode}-${rangeSlug}-`
    + `${now.getFullYear()}${pad2(now.getMonth() + 1)}${pad2(now.getDate())}.pdf`;
  doc.save(filename);

  return { filename, recordCount: aiResults.length };
}
