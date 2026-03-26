/**
 * useMQTT Hook — Koneksi MQTT untuk IoT
 * =======================================
 * 
 * PENJELASAN:
 * MQTT = Message Queuing Telemetry Transport
 * Protokol paling populer untuk IoT karena:
 * - Sangat ringan (hemat bandwidth)
 * - Realtime (data langsung dikirim begitu tersedia)
 * - Reliable (ada QoS level untuk jamin data sampai)
 * 
 * KONSEP DASAR:
 * - BROKER = Server MQTT (seperti "kantor pos" digital)
 * - PUBLISH = Kirim pesan ke topic tertentu
 * - SUBSCRIBE = Langganan pesan dari topic tertentu
 * - TOPIC = Alamat/channel pesan (seperti channel TV)
 * 
 * ALUR DATA:
 * ESP32 → PUBLISH ke "fetalguard/sensor/data" → MQTT Broker
 *                                                    ↓
 * App Mobile ← SUBSCRIBE ke "fetalguard/sensor/data" ←
 * 
 * CARA PAKAI:
 * ```jsx
 * function MonitoringScreen() {
 *   const { isConnected, sensorData, connect, disconnect } = useMQTT({
 *     brokerUrl: 'wss://broker.hivemq.com:8884/mqtt',
 *     topic: 'fetalguard/sensor/data'
 *   });
 * 
 *   return (
 *     <div>
 *       <p>Status: {isConnected ? 'Online' : 'Offline'}</p>
 *       {sensorData && <p>FHR: {sensorData.fhr} bpm</p>}
 *     </div>
 *   );
 * }
 * ```
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// Konfigurasi default MQTT
const DEFAULT_CONFIG = {
  // URL broker MQTT — HiveMQ adalah broker gratis untuk testing
  // Untuk production, ganti dengan broker kamu sendiri (Mosquitto, EMQX, dll)
  brokerUrl: 'wss://broker.hivemq.com:8884/mqtt',

  // Topic yang di-subscribe — harus sama dengan yang di-publish oleh ESP32
  topic: 'fetalguard/sensor/data',

  // Client ID unik — agar broker bisa bedakan masing-masing app
  clientId: null,  // Auto-generate jika null

  // Credentials (opsional, tergantung broker kamu)
  username: '',
  password: '',

  // QoS (Quality of Service):
  // 0 = at most once (fastest, tapi bisa loss)
  // 1 = at least once (recommended untuk IoT monitoring)
  // 2 = exactly once (paling reliable, tapi paling lambat)
  qos: 1,

  // Auto reconnect jika terputus
  reconnect: true,
  reconnectInterval: 5000,  // 5 detik
};

export function useMQTT(config = {}) {
  const cfg = {
    ...DEFAULT_CONFIG,
    ...config,
    clientId: config.clientId || `fetalguard-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
  };

  // ============================================
  // STATE
  // ============================================

  /** Apakah terhubung ke broker MQTT */
  const [isConnected, setIsConnected] = useState(false);

  /** Sedang proses connecting? */
  const [isConnecting, setIsConnecting] = useState(false);

  /** Data sensor terbaru */
  const [sensorData, setSensorData] = useState(null);

  /** Semua data yang pernah diterima (history selama sesi) */
  const [dataHistory, setDataHistory] = useState([]);

  /** Jumlah pesan yang diterima */
  const [messageCount, setMessageCount] = useState(0);

  /** Error message */
  const [error, setError] = useState(null);

  /** Waktu terakhir menerima data */
  const [lastReceived, setLastReceived] = useState(null);

  // Ref untuk MQTT client
  const clientRef = useRef(null);
  const configRef = useRef(cfg);

  // Update config ref saat config berubah
  useEffect(() => {
    configRef.current = cfg;
  }, [cfg.brokerUrl, cfg.topic]);

  // ============================================
  // CONNECT — Hubungkan ke MQTT Broker
  // ============================================

  const connect = useCallback(async () => {
    // Jangan connect ganda
    if (clientRef.current) {
      console.warn('[useMQTT] Already connected or connecting');
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      // Import mqtt library secara dinamis
      // Library ini sudah handle WebSocket untuk browser/WebView
      const mqtt = await import('mqtt/dist/mqtt.min');

      const { brokerUrl, clientId, username, password, topic, qos, reconnect, reconnectInterval } = configRef.current;

      console.log(`[useMQTT] Connecting to ${brokerUrl}...`);

      // Buat koneksi ke broker
      const client = mqtt.connect(brokerUrl, {
        clientId,
        username: username || undefined,
        password: password || undefined,
        clean: true,                    // Clean session — start fresh
        reconnectPeriod: reconnect ? reconnectInterval : 0,
        connectTimeout: 10000,          // 10 detik timeout
      });

      clientRef.current = client;

      // --- EVENT HANDLERS ---

      // Saat berhasil terhubung ke broker
      client.on('connect', () => {
        console.log('[useMQTT] Connected!');
        setIsConnected(true);
        setIsConnecting(false);

        // Subscribe ke topic sensor data
        client.subscribe(topic, { qos }, (err) => {
          if (err) {
            console.error('[useMQTT] Subscribe error:', err);
            setError(`Gagal subscribe: ${err.message}`);
          } else {
            console.log(`[useMQTT] Subscribed to: ${topic}`);
          }
        });
      });

      // Saat menerima pesan dari topic
      client.on('message', (receivedTopic, payload) => {
        try {
          // Parse JSON dari payload
          const data = JSON.parse(payload.toString());

          // Update state
          setSensorData(data);
          setLastReceived(new Date());
          setMessageCount((prev) => prev + 1);

          // Simpan ke history (max 100 entry untuk hemat memory)
          setDataHistory((prev) => {
            const updated = [...prev, { ...data, receivedAt: new Date().toISOString() }];
            return updated.slice(-100);
          });
        } catch (e) {
          console.warn('[useMQTT] Failed to parse message:', e);
        }
      });

      // Saat terjadi error
      client.on('error', (err) => {
        console.error('[useMQTT] Error:', err);
        setError(err.message);
        setIsConnecting(false);
      });

      // Saat koneksi terputus
      client.on('offline', () => {
        console.log('[useMQTT] Offline');
        setIsConnected(false);
      });

      // Saat reconnect berhasil
      client.on('reconnect', () => {
        console.log('[useMQTT] Reconnecting...');
        setIsConnecting(true);
      });

      // Saat koneksi benar-benar ditutup
      client.on('close', () => {
        setIsConnected(false);
        setIsConnecting(false);
      });

    } catch (err) {
      console.error('[useMQTT] Connection error:', err);
      setError(err.message);
      setIsConnecting(false);
    }
  }, []);

  // ============================================
  // DISCONNECT — Putuskan koneksi dari broker
  // ============================================

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.end(true);
      clientRef.current = null;
    }
    setIsConnected(false);
    setIsConnecting(false);
  }, []);

  // ============================================
  // PUBLISH — Kirim data ke topic (opsional)
  // ============================================

  /**
   * Kirim pesan ke topic MQTT
   * Berguna jika app perlu kirim perintah ke device IoT
   * 
   * Contoh: Kirim perintah untuk adjust konfigurasi sensor
   * publish('fetalguard/sensor/config', { sampleRate: 500 });
   */
  const publish = useCallback((topic, data) => {
    if (clientRef.current && isConnected) {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      clientRef.current.publish(topic, message, { qos: cfg.qos });
      console.log(`[useMQTT] Published to ${topic}`);
    } else {
      console.warn('[useMQTT] Cannot publish: not connected');
    }
  }, [isConnected, cfg.qos]);

  // ============================================
  // CLEANUP — disconnect saat component unmount
  // ============================================

  useEffect(() => {
    return () => {
      if (clientRef.current) {
        clientRef.current.end(true);
        clientRef.current = null;
      }
    };
  }, []);

  // ============================================
  // RETURN
  // ============================================

  return {
    // State
    isConnected,      // Terhubung ke broker?
    isConnecting,     // Sedang connecting?
    sensorData,       // Data sensor terbaru
    dataHistory,      // Riwayat data selama sesi
    messageCount,     // Jumlah pesan diterima
    lastReceived,     // Waktu terakhir terima data
    error,            // Pesan error

    // Actions
    connect,          // Connect ke broker
    disconnect,       // Disconnect dari broker
    publish,          // Kirim pesan ke topic
  };
}

export default useMQTT;
