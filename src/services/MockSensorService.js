import api, { getApiErrorMessage } from './api';

/**
 * MockSensorService — Simulator Sensor FETAL-GUARD
 * =================================================
 *
 * Service ini mensimulasikan koneksi BLE dan menghasilkan data sensor
 * yang realistis secara real-time. Digunakan saat hardware (ESP32 + sabuk)
 * tidak tersedia, agar aplikasi tetap bisa didemokan 100%.
 *
 * Data yang dihasilkan:
 * - FHR (Fetal Heart Rate): 110-160 bpm dengan variabilitas fisiologis
 * - Piezo raw waveform: 4 channel sinyal vibrasi mekanik jantung janin
 * - FSR (Force Sensitive Resistor): tekanan kontraksi rahim
 * - SpO2/HR ibu: denyut jantung dan saturasi oksigen via MAX30102
 * - Signal quality index
 *
 * Pola FHR mengikuti standar CTG (Cardiotocography):
 * - Baseline variability (5-25 bpm, normal)
 * - Accelerations (lonjakan ≥15 bpm selama ≥15 detik)
 * - Occasional decelerations
 * - Sinusoidal pattern (rare, untuk variasi simulasi)
 */

// ============================================
// KONSTANTA FISIOLOGIS
// ============================================

/** Range normal detak jantung janin (bpm) */
const FHR_BASELINE_MIN = 120;
const FHR_BASELINE_MAX = 150;

/** Range normal detak jantung ibu (bpm) */
const MHR_BASELINE_MIN = 68;
const MHR_BASELINE_MAX = 88;

/** Frekuensi emisi data (Hz) — seberapa sering data dikirim */
const EMIT_RATE_HZ = 4; // 4 kali per detik (cukup untuk grafik real-time)

/** Jumlah packet per chunk backend: 20 packet @4Hz = 5 detik */
const CHUNK_PACKET_TARGET = 20;

/** Frekuensi sampling internal untuk waveform piezo (Hz) */
const PIEZO_SAMPLE_RATE = 50; // 50 sampel per batch (simulasi 200 Hz / 4 batch per detik)

// ============================================
// GENERATOR SINYAL FISIOLOGIS
// ============================================

/**
 * Menghasilkan nilai FHR yang realistis secara fisiologis.
 * Menggabungkan:
 * 1. Baseline drift (perubahan lambat)
 * 2. Short-term variability (beat-to-beat, 5-25 bpm)
 * 3. Periodic accelerations (lonjakan berkala)
 * 4. Rare decelerations (penurunan sesekali)
 */
class FHRGenerator {
  constructor() {
    this.baseline = FHR_BASELINE_MIN + Math.random() * (FHR_BASELINE_MAX - FHR_BASELINE_MIN);
    this.currentFHR = this.baseline;
    this.tick = 0;
    this.accelerationActive = false;
    this.accelerationTimer = 0;
    this.decelerationActive = false;
    this.decelerationTimer = 0;
    this.nextEventTick = this._randomEventInterval();
  }

  /** Generate FHR berikutnya */
  next() {
    this.tick++;

    // 1. Baseline drift — perubahan sangat lambat (~0.01 bpm per tick)
    this.baseline += (Math.random() - 0.5) * 0.02;
    this.baseline = Math.max(FHR_BASELINE_MIN, Math.min(FHR_BASELINE_MAX, this.baseline));

    // 2. Short-term variability — noise beat-to-beat (±3-8 bpm)
    const stv = (Math.random() - 0.5) * 6 + Math.sin(this.tick * 0.3) * 3;

    // 3. Long-term variability — osilasi lambat (±5-10 bpm, periode ~60 detik)
    const ltv = Math.sin(this.tick * 0.015) * 6;

    // 4. Cek apakah saatnya event (akselerasi/deselerasi)
    if (this.tick >= this.nextEventTick && !this.accelerationActive && !this.decelerationActive) {
      if (Math.random() < 0.8) {
        // 80% kemungkinan akselerasi (normal reaktif)
        this.accelerationActive = true;
        this.accelerationTimer = 15 + Math.floor(Math.random() * 20); // 15-35 ticks
      } else {
        // 20% kemungkinan deselerasi ringan
        this.decelerationActive = true;
        this.decelerationTimer = 10 + Math.floor(Math.random() * 10); // 10-20 ticks
      }
      this.nextEventTick = this.tick + this._randomEventInterval();
    }

    // Hitung komponen akselerasi
    let accelComponent = 0;
    if (this.accelerationActive) {
      const progress = 1 - (this.accelerationTimer / 30);
      accelComponent = Math.sin(progress * Math.PI) * (15 + Math.random() * 10); // +15-25 bpm
      this.accelerationTimer--;
      if (this.accelerationTimer <= 0) this.accelerationActive = false;
    }

    // Hitung komponen deselerasi
    let decelComponent = 0;
    if (this.decelerationActive) {
      const progress = 1 - (this.decelerationTimer / 15);
      decelComponent = -Math.sin(progress * Math.PI) * (10 + Math.random() * 8); // -10-18 bpm
      this.decelerationTimer--;
      if (this.decelerationTimer <= 0) this.decelerationActive = false;
    }

    // Gabungkan semua komponen
    this.currentFHR = this.baseline + stv + ltv + accelComponent + decelComponent;
    this.currentFHR = Math.max(90, Math.min(180, this.currentFHR)); // Clamp ke range aman

    return {
      fhr: Math.round(this.currentFHR),
      baseline: Math.round(this.baseline),
      isAcceleration: this.accelerationActive,
      isDeceleration: this.decelerationActive,
    };
  }

  _randomEventInterval() {
    return 60 + Math.floor(Math.random() * 120); // 60-180 ticks (~15-45 detik)
  }
}

/**
 * Menghasilkan sinyal piezo raw yang menyerupai vibrasi mekanik
 * jantung janin. 4 channel piezo menghasilkan sinyal yang sedikit
 * berbeda (berbeda posisi di sabuk).
 */
class PiezoWaveformGenerator {
  constructor() {
    this.phase = [0, 0, 0, 0];
    this.channelGain = [1.0, 0.85, 0.7, 0.6]; // Channel 1 paling kuat (paling dekat jantung)
  }

  /**
   * Generate batch sampel piezo.
   * @param {number} fhr - FHR saat ini (bpm) untuk menentukan frekuensi detak
   * @param {number} numSamples - jumlah sampel per batch
   * @returns {number[][]} Array 4 channel, masing-masing array of numbers
   */
  generateBatch(fhr, numSamples = PIEZO_SAMPLE_RATE) {
    const heartFreq = fhr / 60; // Hz (detak per detik)
    const channels = [[], [], [], []];

    for (let i = 0; i < numSamples; i++) {
      for (let ch = 0; ch < 4; ch++) {
        this.phase[ch] += (2 * Math.PI * heartFreq) / 200; // 200 Hz internal rate

        // Simulasi sinyal jantung: S1 (lub) + S2 (dub) + noise
        const s1 = Math.exp(-((this.phase[ch] % (2 * Math.PI)) ** 2) / 0.3) * 0.8;
        const s2 = Math.exp(-(((this.phase[ch] % (2 * Math.PI)) - 1.8) ** 2) / 0.2) * 0.5;
        const noise = (Math.random() - 0.5) * 0.15;
        const maternal = Math.sin(this.phase[ch] * 0.55) * 0.08; // Artefak detak ibu

        const value = (s1 + s2 + noise + maternal) * this.channelGain[ch];
        // ADC 12-bit (0-4095) dengan offset tengah
        channels[ch].push(Math.round(2048 + value * 1500));
      }
    }

    return channels;
  }
}

/**
 * Menghasilkan sinyal kontraksi rahim via FSR408.
 * Kontraksi normal berlangsung 30-90 detik dengan interval 2-5 menit.
 */
class ContractionGenerator {
  constructor() {
    this.tick = 0;
    this.contractionActive = false;
    this.contractionTimer = 0;
    this.contractionDuration = 0;
    this.contractionIntensity = 0;
    this.nextContractionTick = 200 + Math.floor(Math.random() * 300); // 50-125 detik
    this.basePressure = 300 + Math.random() * 100; // Tekanan baseline FSR
  }

  next() {
    this.tick++;

    // Cek apakah mulai kontraksi baru
    if (this.tick >= this.nextContractionTick && !this.contractionActive) {
      this.contractionActive = true;
      this.contractionDuration = 120 + Math.floor(Math.random() * 200); // 30-80 detik (dalam ticks @4Hz)
      this.contractionTimer = this.contractionDuration;
      this.contractionIntensity = 0.4 + Math.random() * 0.6; // 40-100% intensitas
      this.nextContractionTick = this.tick + this.contractionDuration + 400 + Math.floor(Math.random() * 800);
    }

    let pressure = this.basePressure;
    if (this.contractionActive) {
      const progress = 1 - (this.contractionTimer / this.contractionDuration);
      // Bentuk bell curve — naik perlahan, puncak di tengah, turun perlahan
      const wave = Math.sin(progress * Math.PI);
      pressure += wave * this.contractionIntensity * 2500;
      this.contractionTimer--;
      if (this.contractionTimer <= 0) this.contractionActive = false;
    }

    // Tambahkan noise kecil
    pressure += (Math.random() - 0.5) * 30;

    return {
      fsrRaw: Math.round(Math.max(0, Math.min(4095, pressure))),
      isContracting: this.contractionActive,
      intensity: this.contractionActive ? Math.round(this.contractionIntensity * 100) : 0,
    };
  }
}

/**
 * Menghasilkan data SpO2 dan HR ibu (simulasi MAX30102).
 */
class MaternalVitalGenerator {
  constructor() {
    this.heartRate = MHR_BASELINE_MIN + Math.random() * (MHR_BASELINE_MAX - MHR_BASELINE_MIN);
    this.spo2 = 96 + Math.random() * 3; // 96-99%
    this.tick = 0;
  }

  next() {
    this.tick++;

    // HR ibu berubah perlahan
    this.heartRate += (Math.random() - 0.5) * 0.8;
    this.heartRate = Math.max(60, Math.min(110, this.heartRate));

    // SpO2 sangat stabil di orang sehat
    this.spo2 += (Math.random() - 0.5) * 0.1;
    this.spo2 = Math.max(94, Math.min(100, this.spo2));

    return {
      motherHR: Math.round(this.heartRate),
      spo2: Math.round(this.spo2 * 10) / 10,
      irRaw: Math.round(50000 + Math.sin(this.tick * 0.5) * 5000 + Math.random() * 1000),
      redRaw: Math.round(45000 + Math.sin(this.tick * 0.5) * 4500 + Math.random() * 900),
    };
  }
}

// ============================================
// MOCK SENSOR SERVICE (MAIN CLASS)
// ============================================

/**
 * MockSensorService — Kelas utama yang mengorkestrasi seluruh generator
 * dan memancarkan data secara berkala melalui callback listeners.
 *
 * Penggunaan:
 * ```js
 * const service = new MockSensorService();
 * service.onData((data) => {
 *   console.log(data.fhrData.fhr);        // 142
 *   console.log(data.piezoChannels[0]);    // [2100, 2050, ...]
 *   console.log(data.contraction.fsrRaw); // 350
 * });
 * service.start();
 * // ...
 * service.stop();
 * ```
 */
class MockSensorService {
  constructor() {
    this._fhrGen = new FHRGenerator();
    this._piezoGen = new PiezoWaveformGenerator();
    this._contractionGen = new ContractionGenerator();
    this._maternalGen = new MaternalVitalGenerator();

    this._listeners = [];
    this._statusListeners = [];
    this._intervalId = null;
    this._isRunning = false;
    this._sessionStartTime = null;
    this._tickCount = 0;
    this._chunkBuffer = [];
    this._chunkSequence = 0;
    this._activeSessionId = null;
    this._startPromise = null;
    this._pendingUploads = new Set();

    // Statistik sesi
    this._stats = {
      accelerationCount: 0,
      decelerationCount: 0,
      movementCount: 0,
      contractionCount: 0,
      fhrHistory: [],
      maxFHR: 0,
      minFHR: 999,
    };
  }

  // ============================================
  // PUBLIC API
  // ============================================

  /** Mulai streaming data mock dan buat session backend */
  async start() {
    if (!import.meta.env.DEV) {
      throw new Error('Simulator sensor dinonaktifkan pada build production.');
    }
    if (this._isRunning) return;
    if (this._startPromise) return this._startPromise;

    this._startPromise = this._startBackendSession();
    try {
      await this._startPromise;
    } finally {
      this._startPromise = null;
    }
  }

  async _startBackendSession() {
    this._notifyStatus('connecting');

    let session;
    try {
      session = await api.sessions.createSession();
    } catch (error) {
      this._notifyStatus('disconnected');
      throw new Error(getApiErrorMessage(error));
    }

    this._activeSessionId = session.id;
    this._chunkBuffer = [];
    this._chunkSequence = 0;
    this._isRunning = true;
    this._sessionStartTime = Date.now();
    this._tickCount = 0;

    // Reset stats
    this._stats = {
      accelerationCount: 0,
      decelerationCount: 0,
      movementCount: 0,
      contractionCount: 0,
      fhrHistory: [],
      maxFHR: 0,
      minFHR: 999,
    };

    // Notifikasi status "connected"
    this._notifyStatus('connected');

    // Mulai emit data sesuai frekuensi
    const intervalMs = 1000 / EMIT_RATE_HZ;
    this._intervalId = setInterval(() => this._emitData(), intervalMs);

    console.log(`[MockSensorService] Started @ ${EMIT_RATE_HZ}Hz with backend session ${session.id}`);
  }

  /** Hentikan streaming dan tutup session backend */
  async stop() {
    if (this._startPromise) {
      try {
        await this._startPromise;
      } catch (error) {
        console.warn('[MockSensorService] Pending start failed before stop:', getApiErrorMessage(error));
      }
    }

    if (!this._isRunning && !this._activeSessionId) return;

    this._isRunning = false;
    if (this._intervalId) {
      clearInterval(this._intervalId);
      this._intervalId = null;
    }

    const sessionId = this._activeSessionId;
    this._activeSessionId = null;
    const remainingChunk = this._chunkBuffer.splice(0);

    if (sessionId && remainingChunk.length > 0) {
      try {
        await this._sendChunk(sessionId, remainingChunk);
      } catch (error) {
        console.warn('[MockSensorService] Failed to flush final chunk:', getApiErrorMessage(error));
      }
    }

    await Promise.allSettled([...this._pendingUploads]);

    if (sessionId) {
      try {
        await api.sessions.endSession(sessionId);
      } catch (error) {
        this._notifyStatus('disconnected');
        throw new Error(getApiErrorMessage(error));
      }
    }

    this._notifyStatus('disconnected');
    console.log('[MockSensorService] Stopped');
  }

  /** Apakah sedang berjalan */
  get isRunning() {
    return this._isRunning;
  }

  /** Durasi sesi dalam detik */
  get sessionDuration() {
    if (!this._sessionStartTime) return 0;
    return Math.floor((Date.now() - this._sessionStartTime) / 1000);
  }

  /** Statistik sesi berjalan */
  get stats() {
    return { ...this._stats };
  }

  /** Daftarkan listener untuk data sensor */
  onData(callback) {
    this._listeners.push(callback);
    return () => {
      this._listeners = this._listeners.filter(cb => cb !== callback);
    };
  }

  /** Daftarkan listener untuk perubahan status */
  onStatus(callback) {
    this._statusListeners.push(callback);
    return () => {
      this._statusListeners = this._statusListeners.filter(cb => cb !== callback);
    };
  }

  // ============================================
  // PRIVATE
  // ============================================

  _emitData() {
    this._tickCount++;

    // Generate data dari setiap generator
    const fhrData = this._fhrGen.next();
    const contraction = this._contractionGen.next();
    const maternal = this._maternalGen.next();
    const piezoChannels = this._piezoGen.generateBatch(fhrData.fhr, PIEZO_SAMPLE_RATE);

    // Update statistik
    if (fhrData.isAcceleration && !this._prevAccel) this._stats.accelerationCount++;
    if (fhrData.isDeceleration && !this._prevDecel) this._stats.decelerationCount++;
    if (contraction.isContracting && !this._prevContracting) this._stats.contractionCount++;
    this._prevAccel = fhrData.isAcceleration;
    this._prevDecel = fhrData.isDeceleration;
    this._prevContracting = contraction.isContracting;

    // Random movements (~10% chance per tick)
    if (Math.random() < 0.025) this._stats.movementCount++;

    // Track FHR history (simpan 1 per detik)
    if (this._tickCount % EMIT_RATE_HZ === 0) {
      this._stats.fhrHistory.push(fhrData.fhr);
      if (this._stats.fhrHistory.length > 3600) this._stats.fhrHistory.shift(); // Max 1 jam
    }
    this._stats.maxFHR = Math.max(this._stats.maxFHR, fhrData.fhr);
    this._stats.minFHR = Math.min(this._stats.minFHR, fhrData.fhr);

    // Hitung signal quality berdasarkan gain channel terkuat
    const peakSignal = Math.max(...piezoChannels[0].map(v => Math.abs(v - 2048)));
    const signalQualityPercent = Math.min(100, Math.round((peakSignal / 1500) * 100));

    // Susun paket data lengkap
    const packet = {
      timestamp: new Date().toISOString(),
      sessionDurationSec: this.sessionDuration,

      // FHR (Detak Jantung Janin)
      fhrData: {
        fhr: fhrData.fhr,
        baseline: fhrData.baseline,
        isAcceleration: fhrData.isAcceleration,
        isDeceleration: fhrData.isDeceleration,
      },

      // Piezo raw (4 channel) — untuk grafik waveform detail
      piezoChannels, // number[4][PIEZO_SAMPLE_RATE]

      // Kontraksi Rahim (FSR)
      contraction: {
        fsrRaw: contraction.fsrRaw,
        isContracting: contraction.isContracting,
        intensity: contraction.intensity,
      },

      // Vital Ibu (MAX30102)
      maternal: {
        heartRate: maternal.motherHR,
        spo2: maternal.spo2,
        irRaw: maternal.irRaw,
        redRaw: maternal.redRaw,
      },

      // Kualitas sinyal
      signalQuality: {
        percent: signalQualityPercent,
        level: signalQualityPercent >= 80 ? 'excellent'
             : signalQualityPercent >= 60 ? 'good'
             : signalQualityPercent >= 40 ? 'fair'
             : 'poor',
      },

      // Statistik sesi berjalan
      stats: {
        accelerations: this._stats.accelerationCount,
        decelerations: this._stats.decelerationCount,
        movements: this._stats.movementCount,
        contractions: this._stats.contractionCount,
      },

      // Flag sumber data
      source: 'mock',
    };

    this._bufferSensorChunk(packet);

    // Kirim ke semua listener
    this._listeners.forEach(cb => {
      try { cb(packet); } catch (e) { console.error('[MockSensorService] Listener error:', e); }
    });
  }

  _bufferSensorChunk(packet) {
    if (!this._activeSessionId) return;

    this._chunkBuffer.push(this._toChunkSample(packet));
    if (this._chunkBuffer.length < CHUNK_PACKET_TARGET) return;

    const chunk = this._chunkBuffer.slice();
    this._chunkBuffer = [];
    this._sendChunk(this._activeSessionId, chunk).catch((error) => {
      console.warn('[MockSensorService] Failed to upload sensor chunk:', getApiErrorMessage(error));
    });
  }

  _toChunkSample(packet) {
    return {
      timestamp: packet.timestamp,
      sessionDurationSec: packet.sessionDurationSec,
      fhr: packet.fhrData.fhr,
      fhrBaseline: packet.fhrData.baseline,
      isAcceleration: packet.fhrData.isAcceleration,
      isDeceleration: packet.fhrData.isDeceleration,
      maternalHeartRate: packet.maternal.heartRate,
      spo2: packet.maternal.spo2,
      fsrRaw: packet.contraction.fsrRaw,
      isContracting: packet.contraction.isContracting,
      contractionIntensity: packet.contraction.intensity,
      signalQualityPercent: packet.signalQuality.percent,
      signalQualityLevel: packet.signalQuality.level,
      source: packet.source,
    };
  }

  _sendChunk(sessionId, chunk) {
    const sequence = this._chunkSequence++;
    const fsr = chunk
      .map((sample) => Math.round(Number(sample.fsrRaw)))
      .filter((value) => Number.isInteger(value) && value >= 0 && value <= 4095);
    if (fsr.length === 0) {
      return Promise.reject(new Error('Mock sensor chunk does not contain valid raw FSR samples.'));
    }

    const lastTimestamp = Date.parse(chunk.at(-1)?.timestamp || '');
    const payload = {
      t: Number.isFinite(lastTimestamp) ? lastTimestamp : Date.now(),
      fsr,
    };
    const upload = api.sessions.sendDataChunk(sessionId, payload, {
      source: 'mock',
      is_simulated: true,
      schema_version: 1,
      ingestion_id: `mock-${sessionId}-${sequence}`,
    });
    this._pendingUploads.add(upload);
    upload.then(
      () => this._pendingUploads.delete(upload),
      () => this._pendingUploads.delete(upload)
    );
    return upload;
  }

  _notifyStatus(status) {
    this._statusListeners.forEach(cb => {
      try { cb(status); } catch (e) { console.error('[MockSensorService] Status listener error:', e); }
    });
  }
}

// ============================================
// SINGLETON & EXPORT
// ============================================

/** Instance singleton agar seluruh app menggunakan service yang sama */
const mockSensorService = new MockSensorService();

export { MockSensorService, FHRGenerator, PiezoWaveformGenerator, ContractionGenerator, MaternalVitalGenerator };
export default mockSensorService;
