import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getLocale, t } from "../../../i18n";
import { useI18n } from "../../../i18n/useI18n";
import { useAuth } from "../../../context/useAuth";
import FeedbackModal from "../../../components/FeedbackModal/FeedbackModal";
import Icon from "../../../components/Icon/Icon";
import api, { isRequestCanceled } from "../../../services/api";
import { createRealtimeEventPoller } from "../../../services/realtimeEventPoller";
import "./HistoryScreen.css";

// ─── Helper: Format jam saja (HH:MM) — hindari locale titik-sebagai-pemisah ───
const formatTimeOnly = (timeString) => {
  if (!timeString) return "--";
  const date = new Date(timeString);
  if (isNaN(date.getTime())) return "--";
  const h = date.getHours().toString().padStart(2, "0");
  const m = date.getMinutes().toString().padStart(2, "0");
  return `${h}:${m}`;
};

// ─── Helper: Format tanggal saja ─────────────────────────────────────────────
const formatDateOnly = (timeString, locale = getLocale()) => {
  if (!timeString) return "--";
  const date = new Date(timeString);
  if (isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat(locale === "en" ? "en-US" : "id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
};

// ─── Helper: Hitung durasi aktual dari dua timestamp ─────────────────────────
const formatDurationFromTimes = (startTime, endTime) => {
  if (!startTime) return "--";
  if (!endTime) return t("patient.common.running");
  const start = new Date(startTime);
  const end = new Date(endTime);
  if (isNaN(start.getTime()) || isNaN(end.getTime())) return "--";
  const diffMs = end.getTime() - start.getTime();
  if (diffMs <= 0) return t("patient.history.lessThanMinute");
  const totalMins = Math.round(diffMs / 60000);
  if (totalMins < 60) return t("patient.history.minutes", { count: totalMins });
  const hours = Math.floor(totalMins / 60);
  const mins = totalMins % 60;
  return mins > 0
    ? t("patient.history.hoursMinutes", { hours, minutes: mins })
    : t("patient.history.hours", { hours });
};

// ─── Helper: Grup sessions per hari, terbaru di atas ─────────────────────────
const groupSessionsByDate = (sessions, locale) => {
  const groups = {};
  sessions.forEach((session) => {
    if (!session.start_time) return;
    const dateKey = formatDateOnly(session.start_time, locale);
    if (!groups[dateKey]) groups[dateKey] = [];
    groups[dateKey].push(session);
  });
  return Object.entries(groups).sort((a, b) => {
    const dateA = new Date(groups[a[0]][0]?.start_time || 0);
    const dateB = new Date(groups[b[0]][0]?.start_time || 0);
    return dateB - dateA; // newest first
  });
};

// ─── Helper: Tentukan class modifier berdasarkan status ──────────────────────
const getStatusModifier = (status) => {
  if (status === "completed") return "completed";
  if (status === "active") return "active";
  return "default";
};

const normalizeSessionContract = (session) => {
  const summary = session?.sensor_summary || null;
  return {
    ...session,
    fhr_estimate_bpm: summary?.fhr_estimate_bpm ?? null,
    maternal_hr_bpm: summary?.maternal_hr_bpm ?? null,
    signal_quality_index: summary?.signal_quality_index ?? null,
    contraction_indicator: summary?.contraction_indicator ?? "unknown",
    sample_count: summary?.sample_count ?? 0,
    source: summary?.source ?? null,
    is_simulated: summary?.is_simulated ?? false,
  };
};

// ─────────────────────────────────────────────────────────────────────────────
// HistoryScreen Component
// ─────────────────────────────────────────────────────────────────────────────
const HistoryScreen = () => {
  const navigate = useNavigate();
  const { locale } = useI18n();
  const { user } = useAuth();

  const [modalConfig, setModalConfig] = useState({ isOpen: false });
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const sessionRequestControllerRef = useRef(null);
  const fetchSessions = useCallback(async ({ silent = false } = {}) => {
    sessionRequestControllerRef.current?.abort();
    const controller = new AbortController();
    sessionRequestControllerRef.current = controller;
    if (!silent) setIsLoading(true);
    try {
      const data = await api.sessions.listSessions({ limit: 100, signal: controller.signal });
      if (controller.signal.aborted) return;
      setSessions(data.map(normalizeSessionContract));
      setError(null);
    } catch (requestError) {
      if (!controller.signal.aborted && !isRequestCanceled(requestError)) setError(true);
    } finally {
      if (sessionRequestControllerRef.current === controller) {
        sessionRequestControllerRef.current = null;
        if (!silent) setIsLoading(false);
      }
    }
  }, []);

  // ── Fetch sessions on mount ──────────────────────────────────────────────
  useEffect(() => {
    void fetchSessions();
    return () => sessionRequestControllerRef.current?.abort();
  }, [fetchSessions]);

  useEffect(() => {
    const poller = createRealtimeEventPoller({
      fetchEvents: ({ cursor, signal }) => api.patients.listRealtimeEvents({
        afterCursor: cursor,
        limit: 100,
        signal,
      }),
      onEvents: (events) => (
        events.some((event) => (
          event.event_type.startsWith("session.")
          || event.event_type === "telemetry.updated"
        ))
          ? fetchSessions({ silent: true })
          : undefined
      ),
      onHeartbeat: () => fetchSessions({ silent: true }),
      initialDelayMs: 2_000,
      heartbeatIntervalMs: 60_000,
    });
    poller.start();
    return () => poller.stop();
  }, [fetchSessions]);

  // ── Modal helpers ────────────────────────────────────────────────────────
  const openModal = (config) => setModalConfig({ ...config, isOpen: true });
  const closeModal = () =>
    setModalConfig((prev) => ({ ...prev, isOpen: false }));

  // ── Ekspor PDF nyata dengan jspdf ────────────────────────────────────────
  // ── Helper: nilai field dengan fallback "--" ───────────────────────────
  const safeVal = (raw, unit = "", decimals = 0) => {
    const num = Number(raw);
    if (!Number.isFinite(num)) return "--";
    return decimals > 0
      ? `${num.toFixed(decimals)}${unit ? " " + unit : ""}`
      : `${Math.round(num)}${unit ? " " + unit : ""}`;
  };

  const getRiskLabel = (score) => {
    const n = Number(score);
    if (!Number.isFinite(n)) return "--";
    if (n < 25) return t("history.lowRisk");
    if (n < 60) return t("history.mediumRisk");
    return t("history.highRisk");
  };

  const handleExportPDF = async () => {
    if (sessions.length === 0) {
      openModal({
        title: t("patient.history.emptyExportTitle"),
        message: t("patient.history.emptyExportMessage"),
        type: "info",
        confirmText: t("patient.common.gotIt"),
      });
      return;
    }
    try {
      const { jsPDF } = await import("jspdf");
      const autoTable = (await import("jspdf-autotable")).default;
      const now = new Date();

      const doc = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: "a4",
      });
      const PAGE_W = 210;
      const MARGIN = 14;
      const CONTENT_W = PAGE_W - MARGIN * 2;

      // ================================================================
      // HEADER BAR
      // ================================================================
      doc.setFillColor(255, 107, 154);
      doc.rect(0, 0, PAGE_W, 24, "F");
      // Accent strip biru di bawah pink
      doc.setFillColor(74, 163, 255);
      doc.rect(0, 22, PAGE_W, 3, "F");

      doc.setTextColor(255, 255, 255);
      doc.setFontSize(17);
      doc.setFont("helvetica", "bold");
      doc.text("FETAL-GUARD", MARGIN, 11);
      doc.setFontSize(8.5);
      doc.setFont("helvetica", "normal");
      doc.text(t("patient.history.pdfSubtitle"), MARGIN, 18);

      // ================================================================
      // JUDUL & META
      // ================================================================
      doc.setTextColor(26, 29, 38);
      doc.setFontSize(14);
      doc.setFont("helvetica", "bold");
      doc.text(t("patient.history.pdfTitle"), MARGIN, 36);

      doc.setFont("helvetica", "normal");
      doc.setFontSize(8.5);
      doc.setTextColor(107, 114, 128);
      const printLine = `${t("patient.history.pdfPrinted")}: ${formatDateOnly(now.toISOString(), locale)} ${formatTimeOnly(now.toISOString())}   |   ${t("patient.history.pdfTotalSessions")}: ${sessions.length}`;
      doc.text(printLine, MARGIN, 42);
      const patientName = user?.patientProfile?.name || user?.email || t("patient.common.unavailable");
      doc.text(`${t("patient.history.pdfPatient")}: ${patientName}`, MARGIN, 46);

      // Garis pemisah
      doc.setDrawColor(229, 231, 235);
      doc.setLineWidth(0.4);
      doc.line(MARGIN, 49, PAGE_W - MARGIN, 49);

      // ================================================================
      // TABEL 1 — RINGKASAN SESI
      // ================================================================
      doc.setTextColor(26, 29, 38);
      doc.setFontSize(10);
      doc.setFont("helvetica", "bold");
      doc.text(t("patient.history.pdfSessionSummary"), MARGIN, 56);

      const tbl1Data = sessions.map((s, idx) => [
        idx + 1,
        formatDateOnly(s.start_time, locale),
        `${formatTimeOnly(s.start_time)} - ${s.end_time ? formatTimeOnly(s.end_time) : "-"}`,
        formatDurationFromTimes(s.start_time, s.end_time),
        s.status === "active" ? t("patient.common.running") : t("patient.common.finished"),
        s.source || "--",
      ]);

      autoTable(doc, {
        startY: 59,
        head: [[
          "No.",
          locale === "en" ? "Date" : "Tanggal",
          locale === "en" ? "Session Time" : "Waktu Sesi",
          t("history.duration"),
          "Status",
          t("patient.history.pdfSource"),
        ]],
        body: tbl1Data,
        styles: {
          fontSize: 8.5,
          cellPadding: 2.5,
          font: "helvetica",
          overflow: "linebreak",
        },
        headStyles: {
          fillColor: [255, 107, 154],
          textColor: 255,
          fontStyle: "bold",
          fontSize: 8.5,
        },
        alternateRowStyles: { fillColor: [253, 242, 247] },
        columnStyles: {
          0: { cellWidth: 10, halign: "center" },
          1: { cellWidth: 32 },
          2: { cellWidth: 44 },
          3: { cellWidth: 32 },
          4: { cellWidth: 28 },
        },
        margin: { left: MARGIN, right: MARGIN },
      });

      // ================================================================
      // TABEL 2 — DATA DETAK JANTUNG JANIN (DJJ / FHR)
      // ================================================================
      let curY = (doc.lastAutoTable?.finalY || 100) + 8;

      // Cek apakah ada data FHR pada session manapun
      const hasFhrData = sessions.some(
        (s) => s.fhr_estimate_bpm != null,
      );

      doc.setTextColor(26, 29, 38);
      doc.setFontSize(10);
      doc.setFont("helvetica", "bold");
      doc.text(t("patient.history.pdfFhr"), MARGIN, curY);

      const tbl2Data = sessions.map((s, idx) => [
        idx + 1,
        formatDateOnly(s.start_time, locale),
        safeVal(s.fhr_estimate_bpm, "bpm"),
        // Indikasi berdasarkan avg_fhr
        (() => {
          const fhr = Number(s.fhr_estimate_bpm);
          if (!Number.isFinite(fhr)) return "--";
          if (fhr >= 110 && fhr <= 160) return t("patient.common.inRange");
          if ((fhr >= 100 && fhr < 110) || (fhr > 160 && fhr <= 170))
            return t("patient.common.recheck");
          return t("patient.common.consult");
        })(),
      ]);

      autoTable(doc, {
        startY: curY + 3,
        head: [
          [
            "No.",
            locale === "en" ? "Date" : "Tanggal",
            locale === "en" ? "Available FHR estimate" : "Estimasi FHR tersedia",
            locale === "en" ? "Indication" : "Indikasi",
          ],
        ],
        body: tbl2Data,
        styles: { fontSize: 8.5, cellPadding: 2.5, font: "helvetica" },
        headStyles: {
          fillColor: [74, 163, 255],
          textColor: 255,
          fontStyle: "bold",
          fontSize: 8.5,
        },
        alternateRowStyles: { fillColor: [242, 249, 255] },
        columnStyles: {
          0: { cellWidth: 10, halign: "center" },
          1: { cellWidth: 32 },
          2: { cellWidth: 32, halign: "center" },
          3: { cellWidth: 28, halign: "center" },
          4: { cellWidth: 28, halign: "center" },
          5: { cellWidth: 32 },
        },
        margin: { left: MARGIN, right: MARGIN },
      });

      if (!hasFhrData) {
        const noteY = (doc.lastAutoTable?.finalY || curY + 20) + 2;
        doc.setFontSize(7.5);
        doc.setTextColor(156, 163, 175);
        doc.setFont("helvetica", "italic");
        doc.text(
          locale === "en"
            ? "* FHR data is not available for this session. Connect the belt device to capture data."
            : "* Data FHR belum tersedia untuk sesi ini. Hubungkan perangkat sabuk untuk mendapatkan data.",
          MARGIN,
          noteY,
          { maxWidth: CONTENT_W },
        );
      }

      // ================================================================
      // TABEL 3 — TANDA VITAL IBU
      // ================================================================
      curY = (doc.lastAutoTable?.finalY || 140) + 8;

      // Cek apakah halaman hampir habis
      if (curY > 240) {
        doc.addPage();
        curY = 20;
      }

      doc.setTextColor(26, 29, 38);
      doc.setFontSize(10);
      doc.setFont("helvetica", "bold");
      doc.text(t("patient.history.pdfVitals"), MARGIN, curY);

      const tbl3Data = sessions.map((s, idx) => [
        idx + 1,
        formatDateOnly(s.start_time, locale),
        safeVal(s.maternal_hr_bpm, "bpm"),
        "--",
        // Status HR ibu
        (() => {
          const hr = Number(s.maternal_hr_bpm);
          if (!Number.isFinite(hr)) return "--";
          if (hr >= 60 && hr <= 100) return t("patient.common.inRange");
          return t("patient.common.recheck");
        })(),
        "--",
      ]);

      autoTable(doc, {
        startY: curY + 3,
        head: [
          [
            "No.",
            locale === "en" ? "Date" : "Tanggal",
            locale === "en" ? "Maternal HR (avg)" : "HR Ibu (avg)",
            "SpO2 (avg)",
            "Status HR",
            "Status SpO2",
          ],
        ],
        body: tbl3Data,
        styles: { fontSize: 8.5, cellPadding: 2.5, font: "helvetica" },
        headStyles: {
          fillColor: [34, 184, 169],
          textColor: 255,
          fontStyle: "bold",
          fontSize: 8.5,
        },
        alternateRowStyles: { fillColor: [242, 254, 252] },
        columnStyles: {
          0: { cellWidth: 10, halign: "center" },
          1: { cellWidth: 32 },
          2: { cellWidth: 30, halign: "center" },
          3: { cellWidth: 28, halign: "center" },
          4: { cellWidth: 30 },
          5: { cellWidth: 32 },
        },
        margin: { left: MARGIN, right: MARGIN },
      });

      // ================================================================
      // TABEL 4 — PERISTIWA & PREDIKSI KONTRAKSI
      // ================================================================
      const hasEventData = sessions.some((session) => (
        session.acceleration_count != null
        || session.deceleration_count != null
        || session.contraction_count != null
        || session.movement_count != null
        || session.risk_score != null
      ));
      if (hasEventData) {
        curY = (doc.lastAutoTable?.finalY || 180) + 8;

      if (curY > 240) {
        doc.addPage();
        curY = 20;
      }

      doc.setTextColor(26, 29, 38);
      doc.setFontSize(10);
      doc.setFont("helvetica", "bold");
      doc.text(t("patient.history.pdfEvents"), MARGIN, curY);

      const tbl4Data = sessions.map((s, idx) => [
        idx + 1,
        formatDateOnly(s.start_time, locale),
        safeVal(s.acceleration_count), // Akselerasi DJJ
        safeVal(s.deceleration_count), // Deselerasi DJJ
        safeVal(s.contraction_count), // Indikasi kontraksi rahim (dari FSR)
        safeVal(s.movement_count), // Gerakan janin
        // Risk score + label
        (() => {
          const rs = Number(s.risk_score);
          if (!Number.isFinite(rs)) return "--";
          return `${Math.round(rs)}% (${getRiskLabel(rs)})`;
        })(),
      ]);

      autoTable(doc, {
        startY: curY + 3,
        head: [
          [
            "No.",
            locale === "en" ? "Date" : "Tanggal",
            t("monitoring.accelerations"),
            t("monitoring.decelerations"),
            `${t("patient.monitoring.contraction")}*`,
            t("monitoring.movements"),
            locale === "en" ? "Indication Score" : "Skor Indikasi",
          ],
        ],
        body: tbl4Data,
        styles: { fontSize: 8, cellPadding: 2.5, font: "helvetica" },
        headStyles: {
          fillColor: [255, 176, 32],
          textColor: 26,
          fontStyle: "bold",
          fontSize: 8,
        },
        alternateRowStyles: { fillColor: [255, 251, 235] },
        columnStyles: {
          0: { cellWidth: 10, halign: "center" },
          1: { cellWidth: 30 },
          2: { cellWidth: 22, halign: "center" },
          3: { cellWidth: 22, halign: "center" },
          4: { cellWidth: 22, halign: "center" },
          5: { cellWidth: 20, halign: "center" },
          6: { cellWidth: 36 },
        },
        margin: { left: MARGIN, right: MARGIN },
      });
      }

      // ================================================================
      // FOOTER DISCLAIMER
      // ================================================================
      const finalY = (doc.lastAutoTable?.finalY || 230) + 10;

      if (finalY > 260) {
        doc.addPage();
      }

      const disclaimerY = finalY > 260 ? 20 : finalY;

      doc.setFillColor(249, 250, 251);
      doc.roundedRect(MARGIN, disclaimerY, CONTENT_W, 28, 2, 2, "F");
      doc.setDrawColor(229, 231, 235);
      doc.setLineWidth(0.3);
      doc.roundedRect(MARGIN, disclaimerY, CONTENT_W, 28, 2, 2, "S");

      doc.setFontSize(7.5);
      doc.setTextColor(107, 114, 128);
      doc.setFont("helvetica", "bold");
      doc.text(
        t("patient.history.pdfImportant"),
        MARGIN + 3,
        disclaimerY + 5,
      );
      doc.setFont("helvetica", "normal");
      doc.text(
        t("patient.history.pdfDisclaimer1"),
        MARGIN + 3,
        disclaimerY + 10,
        { maxWidth: CONTENT_W - 6 },
      );
      doc.text(
        t("patient.history.pdfDisclaimer2"),
        MARGIN + 3,
        disclaimerY + 15,
        { maxWidth: CONTENT_W - 6 },
      );
      doc.text(
        t("patient.history.pdfDisclaimer3"),
        MARGIN + 3,
        disclaimerY + 20,
        { maxWidth: CONTENT_W - 6 },
      );
      doc.text(
        `${t("patient.history.pdfPrinted")} FETAL-GUARD v1.0 ${formatDateOnly(now.toISOString(), locale)} ${formatTimeOnly(now.toISOString())}`,
        MARGIN + 3,
        disclaimerY + 25,
        { maxWidth: CONTENT_W - 6 },
      );

      // ── Simpan file ──────────────────────────────────────────────────
      const filenameLabel = locale === "en" ? "History" : "Riwayat";
      const filename = `FETAL-GUARD-${filenameLabel}-${now.getFullYear()}${(now.getMonth() + 1).toString().padStart(2, "0")}${now.getDate().toString().padStart(2, "0")}.pdf`;
      doc.save(filename);

      openModal({
        title: t("patient.history.pdfSuccessTitle"),
        message: t("patient.history.pdfSuccessMessage", {
          filename,
          count: sessions.length,
        }),
        type: "success",
        confirmText: t("common.ok"),
      });
    } catch (err) {
      console.error("[HistoryScreen] PDF export failed:", err);
      openModal({
        title: t("patient.history.pdfFailTitle"),
        message: t("patient.history.pdfFailMessage"),
        type: "error",
        confirmText: t("common.ok"),
      });
    }
  };

  // ── Bagikan ke klinik — belum tersedia ───────────────────────────────────
  const handleShareToClinic = () => {
    openModal({
      title: t("patient.common.featureUnavailable"),
      message: t("patient.history.shareUnavailableMessage"),
      type: "info",
      confirmText: t("patient.common.gotIt"),
    });
  };

  // ── Render satu timeline item ─────────────────────────────────────────────
  const renderTimelineItem = (session, isLast) => {
    const modifier = getStatusModifier(session.status);
    const timeStart = formatTimeOnly(session.start_time);
    const timeEnd = session.end_time ? formatTimeOnly(session.end_time) : "–";
    const duration = formatDurationFromTimes(
      session.start_time,
      session.end_time,
    );
    const avgFhr = session.fhr_estimate_bpm
      ? `${Math.round(session.fhr_estimate_bpm)} bpm`
      : null;
    const isActive = session.status === "active";
    const badgeLabel = isActive
      ? t("patient.common.running")
      : t("patient.common.finished");

    return (
      <div key={session.id} className="history-timeline__item">
        {/* Kolom kiri: dot + garis */}
        <div className="history-timeline__connector">
          <div
            className={`history-timeline__dot history-timeline__dot--${modifier}`}
          />
          {!isLast && <div className="history-timeline__line" />}
        </div>

        {/* Kolom kanan: card */}
        <div
          className={`history-timeline__card history-timeline__card--${modifier}`}
        >
          {/* Waktu mulai – selesai */}
          <div className="history-timeline__time">
            {timeStart} – {timeEnd}
          </div>

          {/* Meta: durasi + avg FHR */}
          <div className="history-timeline__meta">
            <span className="history-timeline__meta-item">
              <Icon className="material-symbols-outlined" name="timer" />
              {duration}
            </span>
            {avgFhr && (
              <>
                <span aria-hidden="true">•</span>
                <span className="history-timeline__meta-item">
                  <Icon className="material-symbols-outlined" name="favorite" />
                  {avgFhr}
                </span>
              </>
            )}
          </div>

          {/* Badge status */}
          <div style={{ marginTop: "6px" }}>
            <span
              className={`history-timeline__badge history-timeline__badge--${modifier}`}
            >
              {isActive ? "●" : "●"} {badgeLabel}
            </span>
          </div>
        </div>
      </div>
    );
  };

  // ── Render grouped timeline ───────────────────────────────────────────────
  const renderTimeline = () => {
    const grouped = groupSessionsByDate(sessions, locale);
    return (
      <div className="history-timeline">
        {grouped.map(([dateLabel, daySessions]) => (
          <div key={dateLabel} className="history-timeline__group">
            <div className="history-timeline__date-label">{dateLabel}</div>
            {daySessions.map((session, idx) =>
              renderTimelineItem(session, idx === daySessions.length - 1),
            )}
          </div>
        ))}
      </div>
    );
  };

  // ────────────────────────────────────────────────────────────────────────
  return (
    <div className="history-screen">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="history-header">
        <button
          type="button"
          className="history-header__back"
          onClick={() => navigate("/patient/home")}
          aria-label={t("patient.history.backAria")}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
        </button>
        <h1>{t("history.title")}</h1>
        {/* Tombol header kanan — placeholder agar layout simetris */}
        <button
          type="button"
          className="history-header__export"
          onClick={handleExportPDF}
          aria-label={t("patient.history.exportAria")}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
        </button>
      </header>

      {/* ── Stats ──────────────────────────────────────────────────── */}
      <aside className="history-review-note" role="note">
        <Icon className="material-symbols-outlined" name="clinical_notes" />
        <div>
          <strong>{t("patient.history.reviewNoteTitle")}</strong>
          <p>{t("patient.history.reviewNoteDesc")}</p>
        </div>
      </aside>

      <section className="history-stats" aria-label={t("patient.history.summaryLabel")}>
        <div className="history-stats__card">
          <span className="history-stats__value">{sessions.length}</span>
          <span className="history-stats__label">{t("history.sessions")}</span>
        </div>
        <div className="history-stats__card history-stats__card--empty">
          <span className="history-stats__value">--</span>
          <span className="history-stats__label">{t("history.duration")}</span>
        </div>
        <div className="history-stats__card history-stats__card--empty">
          <span className="history-stats__value">--</span>
          <span className="history-stats__label">{t("history.avgFhr")}</span>
        </div>
      </section>

      {/* ── Session list / Timeline ─────────────────────────────────── */}
      <section className="history-list" aria-label={t("patient.history.listLabel")}>
        {isLoading ? (
          <div className="history-empty" role="status">
            <p>{t("patient.history.loading")}</p>
          </div>
        ) : error ? (
          <div className="history-empty" role="alert">
            <p className="error-text">{t("patient.history.loadError")}</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="history-empty" role="status">
            <div className="history-empty__icon" aria-hidden="true">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M12 8v4l3 3" />
                <circle cx="12" cy="12" r="10" />
              </svg>
            </div>
            <h2>{t("patient.history.emptyTitle")}</h2>
            <p>{t("patient.history.emptyDesc")}</p>
            <div className="history-empty__actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => navigate("/patient/monitoring")}
              >
                {t("patient.history.startMonitoring")}
              </button>
            </div>
          </div>
        ) : (
          renderTimeline()
        )}
      </section>

      {/* ── Export bar — IN FLOW, tidak tertutup navbar ────────────────── */}
      <div className="history-export" role="group" aria-label={t("patient.history.actionsLabel")}>
        <button
          type="button"
          className="history-export__btn"
          onClick={handleExportPDF}
          aria-label={t("patient.history.downloadAria")}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          {t("patient.history.downloadPdf")}
        </button>
        <button
          type="button"
          className="history-export__btn"
          onClick={handleShareToClinic}
          aria-label={t("patient.history.shareAria")}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="18" cy="5" r="3" />
            <circle cx="6" cy="12" r="3" />
            <circle cx="18" cy="19" r="3" />
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
          </svg>
          {t("patient.history.shareClinic")}
        </button>
      </div>

      {/* ── Feedback Modal ──────────────────────────────────────────── */}
      <FeedbackModal {...modalConfig} onClose={closeModal} />
    </div>
  );
};

export default HistoryScreen;
