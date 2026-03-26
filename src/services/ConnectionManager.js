/**
 * ConnectionManager — Hybrid IoT Connection Service
 * ==================================================
 * 
 * PENJELASAN:
 * File ini adalah "otak" yang mengatur bagaimana app terhubung ke perangkat IoT.
 * Seperti Mi Band yang bisa connect via Bluetooth ke HP, device FETAL-GUARD 
 * juga bisa terhubung lewat 3 cara:
 * 
 * 1. BLUETOOTH LE (BLE) — Langsung dari device ke HP, tanpa internet
 *    Contoh: Mi Band → HP → Mi Fitness app
 * 
 * 2. MQTT — Device kirim data via WiFi ke MQTT Broker di cloud
 *    Contoh: Device → WiFi → MQTT Server → App ambil data
 * 
 * 3. WiFi/HTTP — Device kirim data via REST API
 *    Contoh: Device → WiFi → Cloud API → App ambil data
 * 
 * User bisa pilih mode koneksi di halaman Settings.
 */

// ============================================
// CONNECTION MODES
// ============================================

/**
 * Enum mode koneksi yang tersedia
 * Bayangkan ini seperti "channel" untuk terima data
 */
export const CONNECTION_MODES = {
  BLUETOOTH: 'bluetooth',
  MQTT: 'mqtt',
  WIFI: 'wifi',
};

/**
 * Status koneksi
 */
export const CONNECTION_STATUS = {
  DISCONNECTED: 'disconnected',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  ERROR: 'error',
};

// ============================================
// CONNECTION MANAGER CLASS
// ============================================

class ConnectionManager {
  constructor() {
    /**
     * Mode koneksi aktif — default MQTT karena paling umum untuk IoT
     * Nanti user bisa ganti di Settings
     */
    this.activeMode = CONNECTION_MODES.MQTT;

    /**
     * Status koneksi saat ini
     */
    this.status = CONNECTION_STATUS.DISCONNECTED;

    /**
     * Listener/callback yang akan dipanggil saat ada data baru
     * Seperti "subscriber" yang menunggu data dari sensor
     */
    this.dataListeners = [];

    /**
     * Listener untuk perubahan status koneksi
     */
    this.statusListeners = [];

    /**
     * Konfigurasi untuk masing-masing mode
     */
    this.config = {
      bluetooth: {
        deviceName: 'FETAL-GUARD-SENSOR',
        serviceUUID: '0000ffe0-0000-1000-8000-00805f9b34fb',  // UUID bluetooth service
        characteristicUUID: '0000ffe1-0000-1000-8000-00805f9b34fb',  // UUID bluetooth characteristic
      },
      mqtt: {
        brokerUrl: 'wss://broker.hivemq.com:8884/mqtt',  // MQTT broker (bisa ganti sesuai server kamu)
        topic: 'fetalguard/sensor/data',                   // Topic yang di-subscribe
        clientId: `fetalguard-app-${Date.now()}`,          // ID unik untuk client
        username: '',
        password: '',
      },
      wifi: {
        apiUrl: 'https://api.fetalguard.com',  // Base URL API server
        pollingInterval: 1000,                  // Ambil data setiap 1 detik
      },
    };

    /**
     * Referensi ke interval polling (untuk WiFi mode)
     */
    this._pollingTimer = null;

    /**
     * Referensi ke MQTT client
     */
    this._mqttClient = null;

    /**
     * Referensi ke device BLE yang terkoneksi
     */
    this._bleDeviceId = null;
  }

  // ============================================
  // PUBLIC METHODS — yang kamu panggil di React
  // ============================================

  /**
   * Ganti mode koneksi (dipanggil dari Settings screen)
   * @param {string} mode - salah satu dari CONNECTION_MODES
   * 
   * CONTOH PENGGUNAAN:
   * connectionManager.setMode(CONNECTION_MODES.BLUETOOTH);
   */
  async setMode(mode) {
    if (this.activeMode === mode) return;

    // Disconnect dari mode lama dulu
    await this.disconnect();

    // Set mode baru
    this.activeMode = mode;
    console.log(`[ConnectionManager] Mode changed to: ${mode}`);
  }

  /**
   * Mulai koneksi sesuai mode yang aktif
   * 
   * CONTOH PENGGUNAAN:
   * await connectionManager.connect();
   */
  async connect() {
    this._updateStatus(CONNECTION_STATUS.CONNECTING);

    try {
      switch (this.activeMode) {
        case CONNECTION_MODES.BLUETOOTH:
          await this._connectBluetooth();
          break;
        case CONNECTION_MODES.MQTT:
          await this._connectMQTT();
          break;
        case CONNECTION_MODES.WIFI:
          await this._connectWiFi();
          break;
        default:
          throw new Error(`Mode tidak dikenal: ${this.activeMode}`);
      }

      this._updateStatus(CONNECTION_STATUS.CONNECTED);
      console.log(`[ConnectionManager] Connected via ${this.activeMode}`);
    } catch (error) {
      this._updateStatus(CONNECTION_STATUS.ERROR);
      console.error(`[ConnectionManager] Connection error:`, error);
      throw error;
    }
  }

  /**
   * Putuskan koneksi
   */
  async disconnect() {
    try {
      switch (this.activeMode) {
        case CONNECTION_MODES.BLUETOOTH:
          await this._disconnectBluetooth();
          break;
        case CONNECTION_MODES.MQTT:
          this._disconnectMQTT();
          break;
        case CONNECTION_MODES.WIFI:
          this._disconnectWiFi();
          break;
      }
    } catch (error) {
      console.warn(`[ConnectionManager] Disconnect error:`, error);
    }

    this._updateStatus(CONNECTION_STATUS.DISCONNECTED);
  }

  /**
   * Daftarkan listener untuk menerima data sensor
   * Setiap kali data baru masuk, callback ini akan dipanggil
   * 
   * CONTOH:
   * connectionManager.onData((sensorData) => {
   *   console.log('FHR:', sensorData.fhr);
   *   setCurrentFHR(sensorData.fhr);
   * });
   */
  onData(callback) {
    this.dataListeners.push(callback);
    // Return unsubscribe function
    return () => {
      this.dataListeners = this.dataListeners.filter(cb => cb !== callback);
    };
  }

  /**
   * Daftarkan listener untuk perubahan status koneksi
   * 
   * CONTOH:
   * connectionManager.onStatusChange((status) => {
   *   console.log('Connection status:', status);
   * });
   */
  onStatusChange(callback) {
    this.statusListeners.push(callback);
    return () => {
      this.statusListeners = this.statusListeners.filter(cb => cb !== callback);
    };
  }

  /**
   * Update konfigurasi koneksi (dari Settings screen)
   * @param {string} mode - mode yang akan diupdate config-nya
   * @param {object} newConfig - konfigurasi baru
   * 
   * CONTOH:
   * connectionManager.updateConfig('mqtt', { 
   *   brokerUrl: 'mqtt://my-server.com:1883' 
   * });
   */
  updateConfig(mode, newConfig) {
    this.config[mode] = { ...this.config[mode], ...newConfig };
  }

  /**
   * Get current status info
   */
  getInfo() {
    return {
      mode: this.activeMode,
      status: this.status,
      config: this.config[this.activeMode],
    };
  }

  // ============================================
  // PRIVATE METHODS — internal logic
  // ============================================

  /**
   * Update status dan notifikasi semua listener
   */
  _updateStatus(newStatus) {
    this.status = newStatus;
    this.statusListeners.forEach(cb => cb(newStatus));
  }

  /**
   * Notifikasi semua data listener
   */
  _notifyData(data) {
    /**
     * Data dari sensor di-normalize ke format standar:
     * {
     *   fhr: 142,               // Fetal Heart Rate (bpm)
     *   motherHR: 82,           // Mother Heart Rate (bpm)
     *   bloodPressure: { systolic: 118, diastolic: 75 },
     *   signalQuality: 92,      // Kualitas sinyal (%)
     *   movements: 5,           // Gerakan janin
     *   accelerations: 3,       // Akselerasi FHR
     *   decelerations: 0,       // Deselerasi FHR
     *   temperature: 36.8,      // Suhu tubuh ibu (°C)
     *   timestamp: '2026-03-16T20:00:00Z'
     * }
     */
    const normalizedData = this._normalizeData(data);
    this.dataListeners.forEach(cb => cb(normalizedData));
  }

  /**
   * Normalisasi data dari berbagai sumber ke format yang sama
   * Karena BLE, MQTT, dan WiFi bisa kirim format yang berbeda-beda
   */
  _normalizeData(rawData) {
    return {
      fhr: rawData.fhr ?? rawData.fetal_heart_rate ?? rawData.FHR ?? 0,
      motherHR: rawData.motherHR ?? rawData.mother_heart_rate ?? rawData.MHR ?? 0,
      bloodPressure: rawData.bloodPressure ?? {
        systolic: rawData.systolic ?? rawData.bp_sys ?? 0,
        diastolic: rawData.diastolic ?? rawData.bp_dia ?? 0,
      },
      signalQuality: rawData.signalQuality ?? rawData.signal_quality ?? rawData.sq ?? 0,
      movements: rawData.movements ?? rawData.fetal_movements ?? 0,
      accelerations: rawData.accelerations ?? 0,
      decelerations: rawData.decelerations ?? 0,
      temperature: rawData.temperature ?? rawData.temp ?? 0,
      timestamp: rawData.timestamp ?? new Date().toISOString(),
      raw: rawData,  // Simpan data mentah juga untuk debugging
    };
  }

  // ============================================
  // BLUETOOTH LE — Mi Band Style
  // ============================================

  async _connectBluetooth() {
    try {
      // Import dinamis — hanya load plugin BLE saat dibutuhkan
      const { BleClient } = await import('@capacitor-community/bluetooth-le');

      // 1. Inisialisasi BLE
      await BleClient.initialize();
      console.log('[BLE] Initialized');

      // 2. Scan device yang tersedia
      //    Seperti HP kamu scan Mi Band, ini scan perangkat FETAL-GUARD
      const device = await BleClient.requestDevice({
        namePrefix: this.config.bluetooth.deviceName,
        optionalServices: [this.config.bluetooth.serviceUUID],
      });

      this._bleDeviceId = device.deviceId;
      console.log(`[BLE] Found device: ${device.name} (${device.deviceId})`);

      // 3. Connect ke device
      await BleClient.connect(device.deviceId, () => {
        // Callback saat device disconnect
        console.log('[BLE] Device disconnected');
        this._updateStatus(CONNECTION_STATUS.DISCONNECTED);
      });

      // 4. Subscribe ke data stream dari sensor
      //    Setiap kali sensor kirim data, callback ini dipanggil
      await BleClient.startNotifications(
        device.deviceId,
        this.config.bluetooth.serviceUUID,
        this.config.bluetooth.characteristicUUID,
        (value) => {
          // value adalah DataView — perlu di-decode
          const decodedData = this._decodeBLEData(value);
          this._notifyData(decodedData);
        }
      );

      console.log('[BLE] Subscribed to notifications');
    } catch (error) {
      console.error('[BLE] Connection failed:', error);
      throw error;
    }
  }

  async _disconnectBluetooth() {
    if (this._bleDeviceId) {
      try {
        const { BleClient } = await import('@capacitor-community/bluetooth-le');
        await BleClient.stopNotifications(
          this._bleDeviceId,
          this.config.bluetooth.serviceUUID,
          this.config.bluetooth.characteristicUUID
        );
        await BleClient.disconnect(this._bleDeviceId);
      } catch (e) {
        console.warn('[BLE] Disconnect error:', e);
      }
      this._bleDeviceId = null;
    }
  }

  /**
   * Decode data dari BLE (DataView → JSON object)
   * 
   * FORMAT DATA BLE CONTOH (dari ESP32):
   * Byte 0-1: FHR (uint16, little-endian)
   * Byte 2-3: Mother HR (uint16)
   * Byte 4-5: BP Systolic (uint16)
   * Byte 6-7: BP Diastolic (uint16)
   * Byte 8:   Signal Quality (uint8, 0-100)
   * Byte 9:   Movements count (uint8)
   * 
   * Kamu bisa adjust format ini sesuai dengan firmware di ESP32 kamu
   */
  _decodeBLEData(dataView) {
    try {
      // Jika device mengirim JSON string via BLE
      const decoder = new TextDecoder();
      const jsonStr = decoder.decode(dataView.buffer);
      return JSON.parse(jsonStr);
    } catch {
      // Jika device mengirim binary data
      try {
        return {
          fhr: dataView.getUint16(0, true),
          motherHR: dataView.getUint16(2, true),
          bloodPressure: {
            systolic: dataView.getUint16(4, true),
            diastolic: dataView.getUint16(6, true),
          },
          signalQuality: dataView.getUint8(8),
          movements: dataView.getUint8(9),
          timestamp: new Date().toISOString(),
        };
      } catch (e) {
        console.warn('[BLE] Failed to decode data:', e);
        return { fhr: 0, timestamp: new Date().toISOString() };
      }
    }
  }

  // ============================================
  // MQTT — Via Internet (IoT Standard)
  // ============================================

  async _connectMQTT() {
    /**
     * MQTT (Message Queuing Telemetry Transport)
     * Protokol paling populer untuk IoT — ringan dan realtime.
     * 
     * Cara kerjanya:
     * 1. Device IoT (ESP32) PUBLISH data ke "topic" (seperti channel TV)
     * 2. App mobile SUBSCRIBE ke topic yang sama
     * 3. Saat device kirim data, app otomatis terima
     * 
     * Contoh topik: "fetalguard/sensor/data"
     * Device kirim:  { fhr: 142, motherHR: 82, ... }
     * App terima:    callback dipanggil dengan data tsb
     */
    try {
      // Dynamically import mqtt library
      // NOTE: kamu perlu install mqtt via: npm install mqtt
      const mqtt = await import('mqtt/dist/mqtt.min');
      
      const { brokerUrl, topic, clientId, username, password } = this.config.mqtt;

      // Connect ke MQTT broker
      this._mqttClient = mqtt.connect(brokerUrl, {
        clientId,
        username: username || undefined,
        password: password || undefined,
        clean: true,
        reconnectPeriod: 5000,  // Auto reconnect setiap 5 detik jika putus
      });

      return new Promise((resolve, reject) => {
        // Saat berhasil connect
        this._mqttClient.on('connect', () => {
          console.log('[MQTT] Connected to broker');
          
          // Subscribe ke topic sensor data
          this._mqttClient.subscribe(topic, (err) => {
            if (err) {
              reject(err);
            } else {
              console.log(`[MQTT] Subscribed to: ${topic}`);
              resolve();
            }
          });
        });

        // Saat terima pesan/data
        this._mqttClient.on('message', (receivedTopic, message) => {
          try {
            const data = JSON.parse(message.toString());
            this._notifyData(data);
          } catch (e) {
            console.warn('[MQTT] Failed to parse message:', e);
          }
        });

        // Saat error
        this._mqttClient.on('error', (err) => {
          console.error('[MQTT] Error:', err);
          this._updateStatus(CONNECTION_STATUS.ERROR);
          reject(err);
        });

        // Saat koneksi terputus
        this._mqttClient.on('offline', () => {
          console.log('[MQTT] Offline');
          this._updateStatus(CONNECTION_STATUS.DISCONNECTED);
        });

        // Timeout
        setTimeout(() => reject(new Error('MQTT connection timeout')), 10000);
      });

    } catch (error) {
      console.error('[MQTT] Connection failed:', error);
      throw error;
    }
  }

  _disconnectMQTT() {
    if (this._mqttClient) {
      this._mqttClient.end(true);
      this._mqttClient = null;
    }
  }

  // ============================================
  // WiFi/HTTP — Polling REST API
  // ============================================

  async _connectWiFi() {
    /**
     * Mode WiFi/HTTP — app secara berkala "minta" data ke server
     * Ini disebut "polling" — seperti cek email setiap beberapa detik
     * 
     * Less realtime dari MQTT/BLE, tapi paling simple untuk diimplement
     */
    const { apiUrl, pollingInterval } = this.config.wifi;

    // Test koneksi dulu
    try {
      const response = await fetch(`${apiUrl}/api/device/status`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      console.log('[WiFi] API connection OK');
    } catch (error) {
      console.error('[WiFi] API connection failed:', error);
      throw error;
    }

    // Start polling — ambil data setiap N milidetik
    this._pollingTimer = setInterval(async () => {
      try {
        const response = await fetch(`${apiUrl}/api/sensor/latest`);
        const data = await response.json();
        this._notifyData(data);
      } catch (error) {
        console.warn('[WiFi] Polling error:', error);
      }
    }, pollingInterval);
  }

  _disconnectWiFi() {
    if (this._pollingTimer) {
      clearInterval(this._pollingTimer);
      this._pollingTimer = null;
    }
  }
}

// ============================================
// SINGLETON INSTANCE
// ============================================
// Export satu instance yang dipakai di seluruh app
// Ini memastikan semua komponen React pakai koneksi yang sama

const connectionManager = new ConnectionManager();
export default connectionManager;
