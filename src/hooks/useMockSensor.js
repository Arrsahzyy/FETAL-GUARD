/**
 * useMockSensor Hook — React Hook untuk MockSensorService
 * ========================================================
 *
 * Hook ini menjembatani MockSensorService (class biasa) dengan
 * React state management. Setiap kali data baru masuk dari service,
 * state di-update dan komponen ter-render ulang.
 *
 * CARA PAKAI:
 * ```jsx
 * function MonitoringScreen() {
 *   const {
 *     isConnected,
 *     fhr, motherHR, spo2,
 *     signalQuality, contraction,
 *     stats, sessionDuration,
 *     fhrHistory,
 *     start, stop
 *   } = useMockSensor();
 *
 *   return (
 *     <div>
 *       <p>FHR: {fhr} bpm</p>
 *       <button onClick={start}>Mulai</button>
 *       <button onClick={stop}>Berhenti</button>
 *     </div>
 *   );
 * }
 * ```
 */

import { useState, useEffect, useCallback } from 'react';
import mockSensorService from '../services/MockSensorService';

/**
 * Ukuran buffer FHR history untuk grafik waveform
 * 500 titik = ~125 detik data pada 4 Hz
 */
const FHR_HISTORY_SIZE = 500;

/**
 * Ukuran buffer piezo waveform untuk grafik detail
 * 200 titik = ~1 detik data pada 200 Hz (4 batch x 50 sampel)
 */
const PIEZO_BUFFER_SIZE = 200;

export function useMockSensor() {
  // ============================================
  // STATE
  // ============================================

  const [isConnected, setIsConnected] = useState(false);
  const [fhr, setFhr] = useState(0);
  const [fhrBaseline, setFhrBaseline] = useState(0);
  const [motherHR, setMotherHR] = useState(0);
  const [spo2, setSpo2] = useState(0);
  const [signalQuality, setSignalQuality] = useState({ percent: 0, level: 'poor' });
  const [contraction, setContraction] = useState({ fsrRaw: 0, isContracting: false, intensity: 0 });
  const [stats, setStats] = useState({ accelerations: 0, decelerations: 0, movements: 0, contractions: 0 });
  const [sessionDuration, setSessionDuration] = useState(0);
  const [isAcceleration, setIsAcceleration] = useState(false);
  const [isDeceleration, setIsDeceleration] = useState(false);
  const [syncError, setSyncError] = useState('');
  const [isStartingSession, setIsStartingSession] = useState(false);
  const [isStoppingSession, setIsStoppingSession] = useState(false);

  // Buffer untuk grafik
  const [fhrHistory, setFhrHistory] = useState([]);
  const [contractionHistory, setContractionHistory] = useState([]);
  const [piezoBuffer, setPiezoBuffer] = useState([[], [], [], []]);

  // ============================================
  // DATA HANDLER
  // ============================================

  useEffect(() => {
    // Subscribe ke data stream
    const unsubData = mockSensorService.onData((packet) => {
      // Update semua state dari paket data
      setFhr(packet.fhrData.fhr);
      setFhrBaseline(packet.fhrData.baseline);
      setIsAcceleration(packet.fhrData.isAcceleration);
      setIsDeceleration(packet.fhrData.isDeceleration);
      setMotherHR(packet.maternal.heartRate);
      setSpo2(packet.maternal.spo2);
      setSignalQuality(packet.signalQuality);
      setContraction(packet.contraction);
      setStats(packet.stats);
      setSessionDuration(packet.sessionDurationSec);

      // Append FHR ke history (rolling buffer)
      setFhrHistory(prev => {
        const next = [...prev, packet.fhrData.fhr];
        return next.length > FHR_HISTORY_SIZE ? next.slice(-FHR_HISTORY_SIZE) : next;
      });

      // Append contraction ke history
      setContractionHistory(prev => {
        const next = [...prev, packet.contraction.intensity];
        return next.length > FHR_HISTORY_SIZE ? next.slice(-FHR_HISTORY_SIZE) : next;
      });

      // Append piezo channel 0 ke buffer (untuk grafik waveform detail)
      setPiezoBuffer(prev => {
        const newBuffers = prev.map((ch, i) => {
          const merged = [...ch, ...packet.piezoChannels[i]];
          return merged.length > PIEZO_BUFFER_SIZE ? merged.slice(-PIEZO_BUFFER_SIZE) : merged;
        });
        return newBuffers;
      });
    });

    // Subscribe ke status changes
    const unsubStatus = mockSensorService.onStatus((status) => {
      setIsConnected(status === 'connected');
      if (status === 'connecting') setSyncError('');
    });

    // Cleanup
    return () => {
      unsubData();
      unsubStatus();
    };
  }, []);

  // ============================================
  // ACTIONS
  // ============================================

  const start = useCallback(async () => {
    // Reset buffers
    setSyncError('');
    setIsStartingSession(true);
    setFhrHistory([]);
    setContractionHistory([]);
    setPiezoBuffer([[], [], [], []]);
    try {
      await mockSensorService.start();
    } catch (error) {
      setSyncError(error.message);
      throw error;
    } finally {
      setIsStartingSession(false);
    }
  }, []);

  const stop = useCallback(async () => {
    setIsStoppingSession(true);
    try {
      await mockSensorService.stop();
    } catch (error) {
      setSyncError(error.message);
      throw error;
    } finally {
      setIsStoppingSession(false);
    }
  }, []);

  // ============================================
  // DERIVED VALUES
  // ============================================

  /** Rata-rata FHR selama sesi */
  const fhrAverage = fhrHistory.length > 0
    ? Math.round(fhrHistory.reduce((a, b) => a + b, 0) / fhrHistory.length)
    : 0;

  /** Status FHR berdasarkan nilai klinis */
  const fhrStatus = fhr >= 110 && fhr <= 160 ? 'success'
    : (fhr >= 100 && fhr < 110) || (fhr > 160 && fhr <= 170) ? 'warning'
    : 'critical';

  /** Status HR ibu */
  const motherHRStatus = motherHR >= 60 && motherHR <= 100 ? 'success'
    : motherHR > 100 && motherHR <= 110 ? 'warning'
    : 'critical';

  /** Risk score sederhana (0-100) */
  const riskScore = (() => {
    let score = 0;
    if (fhr < 110 || fhr > 160) score += 30;
    else if (fhr < 120 || fhr > 150) score += 10;
    if (stats.decelerations > 2) score += 25;
    if (motherHR > 100) score += 15;
    if (signalQuality.percent < 50) score += 10;
    if (contraction.isContracting && contraction.intensity > 80) score += 10;
    return Math.min(100, score);
  })();

  const riskLevel = riskScore < 25 ? 'low' : riskScore < 60 ? 'medium' : 'high';

  // ============================================
  // RETURN
  // ============================================

  return {
    // Status koneksi
    isConnected,
    isStartingSession,
    isStoppingSession,
    syncError,

    // Data sensor real-time
    fhr,
    fhrBaseline,
    motherHR,
    spo2,
    signalQuality,
    contraction,
    isAcceleration,
    isDeceleration,

    // Buffers untuk grafik
    fhrHistory,
    contractionHistory,
    piezoBuffer,

    // Statistik
    stats,
    fhrAverage,
    sessionDuration,

    // Derived / computed
    fhrStatus,
    motherHRStatus,
    riskScore,
    riskLevel,

    // Actions
    start,
    stop,
  };
}

export default useMockSensor;
